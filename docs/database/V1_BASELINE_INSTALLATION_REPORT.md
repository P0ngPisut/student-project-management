# V1 baseline repair — installed and verified

วันที่: 2026-11-07 · สถานะ: **P06 Done เฉพาะติดตั้ง existing-baseline repair และตรวจเส้นทาง DB สร้างทีม**

ผู้ใช้อนุมัติ “ติดตั้งและทดลองได้เลย” หลังอธิบายขอบเขต6 functions และ EXECUTE helper1รายการตาม [รายงาน readiness](TEAM_DATABASE_READINESS_REPORT.md) ติดตั้งเฉพาะ student_project_management_v1_test ไม่เข้าถึงฐานข้อมูลหลัก ไม่เปลี่ยน requirements, SQL V1/Auth ต้นฉบับ, Backend/Frontend หรือ .env จริง และไม่ Commit/Push Git

## สิ่งที่ COMMIT ลง test DB

ติดตั้งโดย effective project_owner ที่ไม่ใช่ superuser ใช้ body ของ SQL review ที่ pin SHA-256 แล้วใน transaction เดียว ไม่มี fixture:

| Object | ผล |
|---|---|
| public.v1_lock_team(bigint) | เพิ่ม helper ที่ขาด ใช้ SECURITY DEFINER/project_owner |
| public.v1_lock_project(bigint) | อัปเดต body/security ตาม V1 source |
| public.v1_team_members_guard() | อัปเดตตาม source ใช้ parent-lock helper |
| public.v1_project_guard() | อัปเดตตาม source รักษา R-01 |
| public.v1_team_final_cardinality() | แก้ row-type handling ตาม source |
| public.v1_in_progress_has_assignee() | แก้ row-type handling ตาม source |
| GRANT EXECUTE ON public.v1_lock_team(bigint) TO project_app | เพิ่มเฉพาะสิทธิ์เรียก helper ที่อนุมัติ |

ไม่เพิ่ม UPDATE/DELETE/TRUNCATE ตารางให้ app ไม่สร้าง/เปลี่ยน roles หรือรหัสผ่าน ไม่สร้าง/ลบตารางหรือคอลัมน์ ไม่แก้ functions อื่นหรือสิทธิ์ Auth

[V1_Baseline_Install.py](../../database/tools/V1_Baseline_Install.py) default เป็น read-only check ส่วน --apply ติดตั้งเฉพาะ legacy fingerprint ที่รู้จัก ไม่แก้ drift ที่ไม่ตรงเอง และไม่ overwrite baseline ที่ถูกต้องแล้ว

## การตรวจใน transaction ก่อน COMMIT

- ตรวจ current_database, effective role, database owner, trigger mode, source/review checksums และ legacy function fingerprints ซ้ำ
- หลัง DDL ตรวจ52 functions ตรง source ใน body/security/volatility/owner/search_path และ helper execute/PUBLIC ACL
- เปรียบเทียบ fingerprint ของ schema/relations/columns/constraints/triggers, non-patch functions, ACL/owner ของ functions เดิม, roles/membership, DB owner/ACL และทุกตาราง row counts ก่อน/หลัง ต้องเหมือนเดิม
- ยกเว้นเฉพาะ6 definitions ที่อนุมัติ และ helperใหม่/EXECUTEใหม่1รายการ หาก postflight ไม่ผ่าน transaction จะ ROLLBACK
- ผล INSTALL_POSTFLIGHT PASS และ INSTALLED/committed=true ไม่มี fixture rows

การเชื่อมต่อ deployment ใช้ private deployment login แล้ว SET LOCAL ROLE project_owner ก่อน DDL ไม่ใช้ superuser effective role ทำ application operations

## โครงสร้างและข้อมูลหลังติดตั้ง

| Namespace | Tables | Columns | FKs | Functions |
|---|---:|---:|---:|---:|
| public V1 | 14 | 86 | 28 | 52 |
| auth | 2 | 6 | 2 | 2 |
| รวม | 16 | 92 | 30 | 54 |

V1 triggers24 เปิดใช้งานตามแบบ Helperทั้งสองเป็น SECURITY DEFINER/project_owner และ trusted search_path App เรียก helperได้ แต่ direct parent FOR UPDATE ยังถูกปฏิเสธตามสิทธิ์ตารางเดิม

หลังชุดทดสอบทุกตารางรวม0แถว ไม่มี user/credentials/session/team/project จำลองค้าง ค่า identity sequences อาจขยับแม้ ROLLBACK ไม่รวมในการเปรียบเทียบ

## ทดสอบหลัง COMMIT

| ชุด | ผล / ขอบเขต |
|---|---|
| Direct app connection | PASS; session_user=current_user=project_app ไม่มี SET ROLE ไป owner/admin และไม่มี admin fallback |
| Direct installed Team regression | PASS8 ด้วย app connection จริง: normalization, actor missing rejection, first leader+forced deferred, raw lock denied, duplicate membership23505, orphan team forced rejection, Project creation, Project DELETE denied |
| Installed Team checks พร้อม owner R-01 | PASS9 รวมพิสูจน์ว่า owner DELETE Project ก็ถูก trigger ปฏิเสธ42501 ไม่ใช่เพียง app ไม่มี DELETE grant |
| Installed Workflow เดิม | PASS57 บน baselineที่ติดตั้งแล้ว ไม่มี temporary patch หรือ reapply RBAC ระหว่างชุดนี้ |
| Boundary/Auth | PASS74 = offline guard9 + Auth65 (validation17/security16/HTTP+PostgreSQL32) |
| Auth DB regression | PASS40 บน installed baseline ไม่ patch V1 ไม่สร้าง Auth ใหม่ |
| Cleanup ทุกชุด DB | PASS metadata/ownership/ACL/row counts กลับ baselineที่ติดตั้งแล้ว ยังมี52 V1 functions ไม่ย้อนกลับเป็น51 |
| Read-only readiness | PASS source differences=[] และ effective app privileges/PUBLIC ACL ผ่าน |
| ลอง --apply ซ้ำ | PASS ALREADY_INSTALLED_VERIFIED/committed=false ไม่มี DDLเขียนทับ |

8 direct cases และ9 owner-deployment cases มีกรณีที่ซ้ำกัน ไม่บวกเป็นจำนวน unique requirements และผล single-session ไม่ใช่ Concurrency/UAT ทั้งระบบ

## คำสั่งตรวจซ้ำ

จาก root:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Install
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Team_Create_Installed_Regression
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --test-installed --workflow
& .\backend\.venv\Scripts\python.exe -B -m unittest database.tests.test_test_database backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api -q
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Auth_Regression
```

default installer ตรวจแบบ read-only; --apply เป็นการ COMMIT ที่ต้องอยู่ใน scope อนุมัติของแต่ละงาน ไม่ต้องรันเพื่อทดสอบปกติ ส่วน --rehearse เป็นโหมดสำหรับ legacy51 functions ก่อนติดตั้ง จึงไม่ใช้บน baselineปัจจุบัน ให้ใช้ --test-installed ซึ่งไม่ทำ DDL

SQL review ต้นฉบับยังจบ ROLLBACK ตามเดิม ตัวติดตั้งตรวจ checksum แล้วแยกเฉพาะ body เพื่อให้ Python transaction ควบคุม COMMIT หลัง postflight ไม่มีการเปลี่ยนไฟล์ SQL เพื่อให้ติดตั้งผ่าน

## Source hashes รุ่นที่รัน

| File | SHA-256 |
|---|---|
| SQL V1 source | 770487d56c7ca71887fb91a84e254b59d40cfa949700e8a3b188c69246baa5bc |
| SQL repair review | 773cc7f7cd7f7c8d2e368cbd3ba6bdf87fd74b4a8b11f0efaa24b7987898fa70 |
| database/tools/V1_Baseline_Install.py | aadd695da71549a0b42294b4cc9709906845a801f60fcc5c676db98dd7398f83 |
| database/tools/V1_Baseline_Prepare.py | d23c5dc05037fc9189d338d3c4fe9061163d26a439840ab5ca1e548853b64685 |
| database/tests/Team_Create_Installed_Regression.py | 26f36909f444b892a6ca4b6712e52089707041aee82fab929ad4f1d78e641467 |

## สิ่งที่ยังไม่เสร็จ

ณรอบติดตั้งพร้อมพัฒนาTeam APIต่อ ส่วนรอบถัดมาผู้ใช้ยืนยันContractและBackend create endpointมีแล้วตาม [Team Implementation Report](../api/TEAM_CREATE_IMPLEMENTATION_REPORT.md) ยังไม่มีหน้าสร้างทีม/read/member/ProjectAPI, multi-session Concurrency, fresh installของเครื่องทีม หรือsuccessful live data COMMIT ไม่มีการเปิดDBอื่นหรือเปลี่ยนnetwork/GitHub settings
