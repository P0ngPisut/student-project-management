# Team database readiness — 2026-11-07

สถานะล่าสุด: **ผู้ใช้อนุมัติแล้ว ติดตั้งแพตช์ถาวรและทดสอบ direct project_app ผ่าน** อ่าน [ผลติดตั้งและคำสั่งทดสอบปัจจุบัน](V1_BASELINE_INSTALLATION_REPORT.md) รายละเอียดด้านล่างเก็บหลักฐานรอบก่อนติดตั้ง

ทำงานบน branch feature/database-schema ต่อจาก commit9d07c52 ไม่ต้องตั้ง GitHub เพิ่ม รอบนี้ไม่ Commit/Push ไม่แก้ Backend/Frontend, .env จริง, Business Rules หรือ SQL V1/Auth ต้นฉบับ และไม่เชื่อมฐานข้อมูลหลัก

## Baseline ที่ตรวจจริงก่อนติดตั้ง

เชื่อมตรงด้วย project_app ไป student_project_management_v1_test ใน read-only transaction ยืนยัน session_user=current_user=project_app ไม่มี superuser/elevated attributes หรือสมาชิก owner/broad data roles

| รายการ | ผล |
|---|---|
| PostgreSQL | 18.6 |
| Database owner | project_owner; role นี้ NOLOGIN/non-superuser |
| public / auth | V1 14 ตารางและ Auth2 ตาราง เจ้าของ project_owner |
| V1 functions | live51 / source52 |
| V1 triggers | 24 เปิดใช้งานทั้งหมด; team cardinality เป็น deferred ตามแบบ |
| สิทธิ์ app | SELECT users/teams/team_members/projects; INSERT เฉพาะ teams/team_members/projects ในกลุ่มนี้; ไม่มี UPDATE/DELETE |
| Helpers | v1_lock_team ขาด; v1_lock_project ยังเป็น SECURITY INVOKER |

เทียบ function body/owner/security/volatility/search_path กับ SQL ที่ pin checksum พบความต่างเฉพาะ6 functions ด้านล่าง ไม่มีเหตุให้เปลี่ยนตาราง/คอลัมน์/ข้อกำหนด

## พิสูจน์ปัญหาก่อนแพตช์

ใช้ direct project_app connection สร้าง student จำลองผ่าน auth.register_student ภายใน rollback-only transaction ไม่ใช้ owner/superuser สร้างทีมแทน app

| ขั้น | ผล |
|---|---|
| INSERT teams | PASS แต่ deferred checks ยังไม่ครบ |
| INSERT หัวหน้าคนแรก | FAIL / 42501 permission denied for table teams ใน v1_team_members_guard |
| บังคับ SET CONSTRAINTS ALL IMMEDIATE | FAIL / 42703 record old has no field team_id ใน v1_team_final_cardinality |
| ROLLBACK และ snapshot | PASS metadata/ACL/row counts คืน baseline ไม่รวม sequence values |

Trigger เดิมพยายาม SELECT ... FOR UPDATE ด้วยสิทธิ์ invoker แต่ app ไม่มี UPDATE ตามที่ออกแบบไว้ PostgreSQL ต้องใช้สิทธิ์ UPDATE เพิ่มจาก SELECT เพื่อทำ row locking แบบนี้ แนวแก้ใช้ narrow SECURITY DEFINER helper ที่มีอยู่ใน SQL V1 แล้ว ไม่ให้ app ได้ UPDATE ตาราง ดู [PostgreSQL SELECT](https://www.postgresql.org/docs/18/sql-select.html) และ [CREATE FUNCTION/security properties](https://www.postgresql.org/docs/18/sql-createfunction.html)

Deferred trigger เดิมอ้าง field ของ team_members บน record ชนิด teams จึงต้องใช้ branch ตาม TG_TABLE_NAME แยก statements ตาม source V1 ที่แก้ไว้แล้ว ปัญหาเดียวกันของ tasks/task_assignees อยู่ในแพตช์ baseline นี้ด้วย

## ขอบเขตแพตช์ที่เตรียม

[SQL review](../../database/migrations/001_v1_baseline_repair_review.sql) จบ ROLLBACK เสมอ ไม่มี COMMIT/role/password changes และมี database/owner/legacy-body fingerprint guard

| Function | การเปลี่ยนแปลงจาก baseline |
|---|---|
| v1_lock_team(bigint) | เพิ่ม helper ที่ขาด ใช้ SECURITY DEFINER โดย project_owner ตรวจ actor และล็อก parent |
| v1_lock_project(bigint) | แทน body/security ด้วย source V1 ที่ยืนยันแล้ว |
| v1_team_members_guard() | ใช้ parent-lock helper ตาม source |
| v1_project_guard() | ใช้ parent lock ตาม source รักษา R-01 |
| v1_team_final_cardinality() | แยก row types ก่อนตรวจ cardinality |
| v1_in_progress_has_assignee() | แยก row types ก่อนตรวจ assignee |

ทั้ง6 definitions คัดจาก source V1 เดิม ไม่ออกแบบกฎใหม่ Pin search_path และปิด PUBLIC EXECUTE เฉพาะ functions ที่แตะ ส่วน ACL ของ existing functions คงเดิมผ่าน CREATE OR REPLACE

**สิทธิ์ใหม่ที่ต้องอนุมัติสำหรับการติดตั้งถาวร:** EXECUTE บน public.v1_lock_team(bigint) ให้ project_app เพียงรายการเดียว ตาม whitelist RBAC V1 ไม่มี UPDATE/DELETE/TRUNCATE หรือสิทธิ์ users/credentials เพิ่ม

Checksum source V1: 770487d56c7ca71887fb91a84e254b59d40cfa949700e8a3b188c69246baa5bc

Checksum SQL review: 773cc7f7cd7f7c8d2e368cbd3ba6bdf87fd74b4a8b11f0efaa24b7987898fa70

## ผลทดสอบแพตช์ชั่วคราว

[V1_Baseline_Prepare](../../database/tools/V1_Baseline_Prepare.py) default/--check เป็น read-only; --rehearse เท่านั้นจึงทดลอง DDL และไม่มี apply mode ทุกกรณี ROLLBACK; --workflow เรียก regression เดิมเพิ่มใน transaction เดียว

DDL ทำด้วย effective project_owner และ application operations ด้วย effective project_app ที่ไม่ใช่ superuser ภายใน deployment connection เดียว เพื่อเห็น DDL ที่ยังไม่ COMMIT ผลนี้ **ยังไม่ใช่ direct app-password flow บน persistent baseline ที่ติดตั้งแล้ว** ก่อนแพตช์ได้พิสูจน์ direct app path ว่าติดจริงตามตารางด้านบน

| ชุด | ผล |
|---|---|
| Team readiness | PASS9: normalize name/description, missing actor rejected, first leader+forced deferred, raw parent lock denied, duplicate membership rejected23505, orphan team rejectedเมื่อ force deferred, Project creation, app Project DELETE denied, owner Project DELETE rejectedโดย R-01 |
| V1 Workflow เดิม | PASS57 พร้อม forced deferred checks ครอบคลุมผลต่อ tasks/assignees/evaluations ด้วย |
| Offline connection boundary | PASS9: pin targetแม้ DB_NAME ชี้ main/ไม่มี DB_NAME, wrong identity/failureปิด connection, ไม่มี app-credential fallback, readonly ตั้งก่อน query, autocommit explicit |
| Auth suite เดิม | PASS65 = validation17 + security16 + HTTP/PostgreSQL32; รวมกับ boundary9 เป็น74 tests |
| Snapshot cleanup | PASS ทั้งก่อน/หลัง fixtures และหลัง ROLLBACK ทั้งชุด ตรวจ public/auth definitions, structure, ownership, ACLs, roles, DB ACL และ row counts ไม่รวม sequence values |

หลัง ROLLBACK ฐานข้อมูลยังมี51 V1 functions และยังไม่มี helper/EXECUTE ใหม่ถาวร การทดสอบผ่านจึงยังไม่ทำให้ P06 Done และยังไม่เปิด Team API

SQL review ผ่าน PostgreSQL runtime ใน rehearsal; Python syntax/import ผ่าน ไม่ใช้ static gate หรือ parser แทนผล PostgreSQL readiness check ตรวจ effective app privileges/PUBLIC ACL เพิ่มจากการเทียบ definitions ด้วย

## เครื่องมือ test-only ที่แก้แล้ว

- เพิ่ม [Test_Database.py](../../database/tools/Test_Database.py) อ่าน private deployment credentials แต่ ignore DB_NAME แล้ว pin dbname=test DB พร้อมตรวจ current_database หลังเชื่อม ไม่ import backend.database ไม่มี fallback ไปฐานข้อมูลอื่น
- Preflight, Schema Dry Run, Schema Install, RBAC Dry Run และ RBAC Apply ใช้ helper นี้ครบ5ตัว
- Preflight บังคับ read-only ตั้งแต่เริ่ม connection และ ROLLBACK ปิด connection; admin login ใช้อ่าน inventory เท่านั้น ไม่ใช่ application identity
- เอา guard เดิมที่ห้าม DB_NAME=test ออกจาก RBAC Apply เพราะ target ถูก pin โดยตรงแล้ว ไม่ต้องตั้งค่าให้ชี้ DB หลักเพื่อหลบ guard
- เพิ่ม .gitattributes ให้ SQL ใน database/ เป็น LF เพราะ core.autocrlf=true อาจทำให้ raw-byte checksum ไม่ตรงเมื่อ checkout บนเครื่องทีม ไม่เปลี่ยนเนื้อหา SQL ต้นฉบับ
- ไม่รัน Schema Install/RBAC Apply หรือ default Dry Run กับ persistent DB ที่มี schema แล้ว เครื่องมือ initial-install ยังไม่ใช่ migration และยังไม่มี fresh-install ของเครื่องทีมที่ตรวจครบ

## คำสั่งตรวจซ้ำ

จาก root ใช้ private config ในเครื่อง ห้ามนำค่ารหัสผ่านเข้า Git:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Database_Schema_V1_Readonly_Preflight
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --rehearse --workflow
& .\backend\.venv\Scripts\python.exe -B -m unittest database.tests.test_test_database backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api -q
```

คำสั่ง --rehearse ด้านบนเป็นรอบ legacy51 ก่อนติดตั้ง ปัจจุบัน --check ผ่านและต้องใช้ --test-installed แทนเพื่อทดสอบโดยไม่ patch ซ้ำ อย่ารันคำสั่งทดสอบเขียนพร้อมกับงานของทีมบน DB เดียวกัน เพราะ snapshot comparison ต้องไม่มีการเปลี่ยนข้อมูลจาก session อื่นระหว่างชุดทดสอบ

## แผนติดตั้งที่เสนอในรอบก่อน — ได้รับอนุมัติและดำเนินการแล้ว

1. ตรวจ target/owner/source checksums และ legacy fingerprints ซ้ำก่อนเปลี่ยนแปลง
2. ใช้เฉพาะ body ของ SQL review ใน transaction เดียวโดย project_owner ไม่มี fixture data
3. Postflight: 52 functions ตรง source, helper owner/search_path/definer ถูกต้อง, PUBLIC EXECUTE ปิด, app ไม่มี direct UPDATE/DELETE/TRUNCATE, schema/Auth/roles/ข้อมูลเดิมไม่เปลี่ยน
4. COMMIT เฉพาะ6 function definitions และ helper EXECUTE หนึ่งรายการ หาก postflight ไม่ผ่านให้ ROLLBACK
5. หลัง COMMIT ใช้ direct project_app connection ทดสอบ Team→leader→Project/negative/deferred/R-01 อีกครั้ง โดย fixture ทั้งหมด ROLLBACK และตรวจ Auth regression

ผู้ใช้อนุมัติขั้น1–5 นี้แล้วตามคำสั่ง “ติดตั้งและทดลองได้เลย” ผลติดตั้งและทดสอบหลัง COMMIT อยู่ในรายงานติดตั้ง ไม่มีการ Commit/Push Git ในรอบนี้
