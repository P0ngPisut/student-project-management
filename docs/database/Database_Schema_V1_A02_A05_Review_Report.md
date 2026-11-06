# Database Schema V1 — A-02 / A-05: Controlled Operations & RBAC Review

**สถานะ ณ 2026-11-06:** มีผลทดสอบ PostgreSQL ใน test DB จากบทสนทนารอบก่อน แต่ยังไม่พร้อม deploy; A-02/A-05 ยังไม่ปิด งานจัดโฟลเดอร์ครั้งนี้ไม่รัน DB หรือเปลี่ยน Schema

## สถานะล่าสุดหลัง regression และจัดโฟลเดอร์

- ต้นฉบับปัจจุบัน: [SQL](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql), [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql), [Data Dictionary](Database_Schema_V1_Data_Dictionary.md)
- วิธีใช้งาน: [Database README](../../database/README.md); กฎ/ข้อเปิดค้าง: [Reference](SCHEMA_V1_REFERENCE.md); งานค้าง: [Backlog](../progress/BACKLOG.md)
- SQL มี 14 ตาราง, 86 คอลัมน์, 28 FK, 52 functions และ 24 triggers; รอบย้ายไฟล์คง SQL เดิมทุก byte
- แพตช์ที่อนุมัติและทดสอบก่อนย้าย: เพิ่ม `v1_lock_team`, ปรับ `v1_lock_project` และการเรียก lock ใน `v1_team_members_guard`/`v1_project_guard`; แยกการอ่าน row type ใน `v1_team_final_cardinality` และ `v1_in_progress_has_assignee`
- [RBAC Lock Regression](../../database/tests/Database_Schema_V1_RBAC_Lock_Regression.py) เคย PASS ในบทสนทนา ครอบคลุมเส้นทางสร้าง Team/Project, สิทธิ์, R-01 และ constraint บางกรณี
- [Workflow Regression](../../database/tests/Database_Schema_V1_Workflow_Regression.py) เคย PASS 57/57 หลังแก้ `42703` ของ task deferred trigger; บังคับ `SET CONSTRAINTS ALL IMMEDIATE` และ ROLLBACK ยืนยัน definitions/ACL/owners/triggers และจำนวนแถวกลับ baseline (14 ตารางเป็น 0 แถวในรอบนั้น); sequence อาจเพิ่ม
- ผลเหล่านี้เป็นหลักฐานจากการรันจริงในบทสนทนาก่อนย้าย ไม่ใช่ผลรันใหม่ในรอบจัดโฟลเดอร์ และยังไม่มี raw log artifact ใน repo
- การเชื่อมต่อ FastAPI→DB, API G-12/SQL-injection, concurrency และ deployment ของแพตช์ถาวรยังไม่ยืนยัน; ชุดทดสอบใช้ temporary patch และ ROLLBACK
- ฐานข้อมูลที่อนุญาต: `student_project_management_v1_test`; roles ที่ใช้ก่อนหน้า: `postgres` สำหรับเชื่อม/admin, `project_owner` สำหรับ fixture/patch, `project_app` สำหรับ workflow โดยตรวจ effective role ไม่ใช่ superuser
- ไม่เชื่อมต่อฐานข้อมูลสดรอบนี้; membership/ownership/DB state ปัจจุบันเป็น Not Verified จนตรวจซ้ำตามขอบเขตที่อนุญาต

ส่วนถัดไปเก็บรายละเอียดการ review ดั้งเดิมเพื่อ traceability ตัวเลขหรือข้อความในส่วนประวัติไม่แทนสถานะล่าสุดข้างต้น

**ฐานที่ใช้:** `Database_Schema_V1_R01_REVISED_DRAFT.sql`, `Database_Schema_V1_R01_RBAC_TEMPLATE.sql`, ข้อกำหนด G-01..G-12, C-01..C-07, D-01=A, R-01=A.

## 1) ไฟล์ใหม่

- `Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql`: สำเนา Schema R-01 เดิม เพิ่ม Controlled Write Functions 17 รายการ และปรับเพียง Volatility ของ Helper 7 ตัวที่ต้องเห็นสถานะหลังได้รับ Lock
- `Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql`: Template ใหม่สำหรับแยกบัญชี Owner/App, จำกัด DML, กำหนด EXECUTE เฉพาะ Function ที่อนุญาต และตรวจสิทธิ์จริงแบบ Preflight/Postflight
- `Database_Schema_V1_A02_A05_Static_Check.json`: artifact ที่อ้างในประวัติเดิม แต่ไม่พบใน Workspace; ปัจจุบันมี [Static Gate](../../database/tests/Database_Schema_V1_Static_Gate.py) ซึ่งตรวจข้อความ/จำนวน Object ไม่ใช่ PostgreSQL Parser หรือ Runtime Test

**ไม่ได้แก้ร่าง R-01 เดิม** และไม่มีการสร้างตาราง/Column ใหม่

## 2) สิ่งที่แก้ในร่าง

### A-02 — PostgreSQL RBAC / SECURITY DEFINER

1. ปรับ Template ให้กำหนดตัวแปรชื่อ Role แยก `v1_owner_role` และ `v1_app_role` **โดยไม่สมมติชื่อบัญชีจริง** และไม่สร้าง/แก้บัญชีใดในระบบ
2. เพิ่ม Preflight ปฏิเสธกรณีเจ้าของข้อมูลเป็นบัญชีเดียวกับบัญชีแอป, บัญชีแอปมี Superuser/CREATEROLE/CREATEDB/BYPASSRLS/REPLICATION หรือสืบทอดบทบาท Owner และตรวจ Owner ของ V1 Tables/Functions
3. จำกัดสิทธิ์ใน `public`: App ได้ USAGE แต่ไม่ได้ CREATE; ถอน PUBLIC privileges ของ V1 Tables และสิทธิ์ที่ไม่อนุญาตของ App ก่อน GRANT ใหม่
4. ให้ SELECT กับ App เพื่อให้ FastAPI กรองข้อมูลตาม G-12 (ไม่เพิ่ม PostgreSQL RLS)
5. ให้ INSERT ตรงเฉพาะตารางที่มี Trigger ล็อก Parent ก่อนสร้างแถวใหม่ (`teams`, `team_members`, `projects`, `advisor_invitations`, `project_submissions`, `project_submission_files`) และให้คำสั่งแก้ไข/ลบแถวเดิมผ่าน Function ควบคุม
6. คง R-01=A: **ไม่มี GRANT DELETE projects** และคง Trigger ปฏิเสธ DELETE ทุกกรณี
7. จำกัด EXECUTE ให้เฉพาะ Helper ที่จำเป็นและ Controlled Operation ที่มีสิทธิ์เรียก ไม่ GRANT ฟังก์ชันคำนวณ Milestone ภายในและ Trigger Function
8. เพิ่ม Postflight ตรวจสิทธิ์ที่มีผลจริงผ่าน `has_table_privilege`, `has_any_column_privilege`, `has_function_privilege`, `has_schema_privilege` เพื่อจับสิทธิ์ที่ได้จากการสืบทอด

**ข้อจำกัด A-02:** `SET LOCAL app.actor_user_id` และ Operation GUC ไม่ได้พิสูจน์ตัวตนโดยตัวเอง หากข้อมูลรับจาก Browser หรือเปิดการเรียก SQL ได้ตามอำเภอใจ จะปลอมได้ การป้องกันยังต้องอาศัย Trusted FastAPI (ตรวจ Auth/Authorization, parameterized SQL, ไม่ให้ Browser เข้าถึง PostgreSQL), SQL Role/Schema Ownership ที่ตรวจจริง, และการทดสอบ Security/SQL Injection. ดังนั้น **A-02 ยังไม่ปิด**

### A-05 — Parent-first Lock Order

- เพิ่ม 17 Controlled Write Functions (ชื่อ `v1_*`) ที่อ่าน ID เป็น Locator, ล็อก Project ก่อนเมื่อเกี่ยวข้อง แล้วล็อก Milestone / Task / Child Row ตามลำดับ ก่อนใช้ UPDATE หรือ DELETE
- ครอบคลุมการแก้ Team/Project, การตอบรับ/ปฏิเสธคำเชิญ, การตรวจ Submission, Milestone/Task CRUD, การแต่งตั้ง/ถอดถอนกรรมการ, การลง Vote และคะแนน
- คง Functions เดิม `v1_assign_task`, `v1_unassign_task`, `v1_exit_team_member` สำหรับการมอบหมายงานและออกจากทีม
- ลดช่องทาง Row Lock ย้อนลำดับ: บัญชี App ไม่ได้รับ `UPDATE/DELETE` แบบตรงกับ Child Rows สำคัญ และไม่สามารถ `INSERT` Vote/Evaluation โดยตรง
- ปรับ Helper อ่านสถานะใน Transaction 7 ตัวจาก `STABLE` เป็น `VOLATILE`: `v1_actor_has_role`, `v1_is_team_leader`, `v1_is_current_member`, `v1_advisor_for_project`, `v1_has_first_evaluation`, `v1_topic_decision`, `v1_topic_metadata_editable` เพื่อให้ SQL ภายใน Helper ใช้ Fresh Snapshot ในกรณีที่ต้องอ่านข้อมูลหลังรอ Lock
- ไม่เพิ่ม/เปลี่ยนกฎการอนุญาตของ Actor; Functions เดิมใน Trigger ยังตรวจสิทธิ์และสถานะตาม G/C/D/R ที่ยืนยัน

**ข้อจำกัด A-05:** Lock Order นี้ใช้ได้เมื่อ Backend เรียก Controlled Operations; ยังไม่ได้ยืนยันว่าทุก API ใช้เส้นทางดังกล่าว และการล็อกใน Deferred Constraint/Trigger หรือ PostgreSQL ภายในอาจมีผลต่อ Concurrency ต้องทดสอบกับ PostgreSQL จริง รวมถึง Isolation Level และ Deadlock/Retry ดังนั้น **A-05 ยังไม่ปิด**

## 3) ประวัติผล Static Check ก่อนแพตช์ regression ล่าสุด

| รายการ | R-01 ก่อนแก้ | ร่างตรวจ A-02/A-05 | ผล |
|---|---:|---:|---|
| Tables | 14 | 14 | คงเดิม |
| Columns | 86 | 86 | คงเดิม |
| Foreign Keys | 28 | 28 | คงเดิม |
| Indexes | 22 | 22 | คงเดิม |
| Triggers (รวม Constraint Trigger) | 24 | 24 | คงเดิม |
| Functions | 34 | 51 | เพิ่ม Controlled Operations 17 |
| Data Types / CHECK / UNIQUE / ON DELETE | เดิม | เหมือนเดิม | เทียบข้อความ CREATE TABLE แล้ว |
| ฟังก์ชันอ่านสถานะที่ปรับ Volatility | 0 | 7 | เพื่อแก้ Snapshot หลัง Lock |
| `GRANT DELETE projects` | ไม่มี | ไม่มี | รักษา R-01=A |

วิธีตรวจในรอบดั้งเดิม: เปรียบเทียบโครงสร้างและเนื้อหา SQL ด้วย Script เชิงสถิติ ตรวจฟังก์ชันใหม่ตรงกับ RBAC Grant, การปฏิเสธ Direct DML ที่สำคัญ, การมี Pre/Postflight, และ Diff ย้อนกลับไปเทียบ R-01. รอบนั้นยังไม่ได้ทดสอบ PostgreSQL; ผล runtime ภายหลังและจำนวน functions 52 ให้ดูส่วนสถานะล่าสุดด้านบน

## 4) Matrix การทดสอบที่ต้องทำในฐานข้อมูลทดสอบแยก หลังอนุมัติ

นี่คือรายการ coverage เป้าหมายเดิม ไม่ใช่รายการ PASS ครบทุกแถว ต้องเทียบแต่ละ case กับสคริปต์/ผลรันจริง โดยเฉพาะ SEC-07/08, TX-01–TX-06 และการเปิดเผยข้อมูลผ่าน API ยังไม่ผ่านการพิสูจน์

| Case | การทดสอบ | ผลที่คาดหวัง |
|---|---|---|
| SEC-01 | App Role DELETE `projects` ที่ไม่มี Child | Permission Denied และ Project คงอยู่ |
| SEC-02 | App Role UPDATE `tasks`, `milestones`, `projects` ตรง | Permission Denied |
| SEC-03 | App Role DELETE `task_assignees` ตรง | Permission Denied |
| SEC-04 | App Role INSERT `committee_topic_votes` ตรง | Permission Denied |
| SEC-05 | App Role เรียก `v1_refresh_milestone()` | Permission Denied |
| SEC-06 | App Role สืบทอดสิทธิ์ Owner หรือ CREATE ใน public | Pre/Postflight ต้องหยุด |
| SEC-07 | Browser พยายามส่ง Actor ID ปลอมไป API | FastAPI ปฏิเสธ / ไม่ใช้ Client Actor ID |
| SEC-08 | ทดสอบ Raw SQL / SQL Injection ผ่านแอป | ไม่สามารถยกระดับ Actor / Role หรือเรียก Operation ที่ไม่ได้รับอนุญาต |
| TX-01 | เปลี่ยน Task Status กับบันทึก Evaluation แรกพร้อมกัน | ดำเนินการตาม Project Lock และห้าม Task แก้หลังคะแนนแรก |
| TX-02 | กรรมการโหวตครั้งแรกและผู้ประสานงานแก้รายชื่อพร้อมกัน | หลัง Vote แรก รายชื่อคงเดิม |
| TX-03 | เปลี่ยน Due Date Milestone ขณะเปลี่ยน Task Due Date | D-01 ต้องไม่ถูกฝ่าฝืน |
| TX-04 | สมาชิกคนหนึ่งออกจากทีมขณะอีกคนแก้ Task | คง C-02 และประวัติถอนงานอย่างถูกต้อง |
| TX-05 | สมาชิกสองคนเปลี่ยน Task คนละรายการใน Milestone เดียวกัน | Milestone คำนวณถูกต้อง ไม่มี Lost Update |
| TX-06 | Deadlock/Lock Timeout/Serialization Failure | ไม่มี Partial Commit, จัดการ Retry เฉพาะกรณีปลอดภัย |
| REG-01 | ทีมเปลี่ยนหัวหน้า | 1 Leader เสมอเมื่อ COMMIT |
| REG-02 | Team ส่ง Submission พร้อมไฟล์ | Atomic Transaction, ไฟล์ครบหนึ่งรายการ |
| REG-03 | Task DELETE ตามกฎ | CASCADE ผู้รับผิดชอบ/ประวัติ ไม่สร้าง History เทียม |
| REG-04 | Vote/Evaluation ลงครบ | คำนวณสถานะและสิทธิ์เปิดเผยตรงกับ G-12 |

## 5) ประเด็นที่ต้องทราบก่อนรันจริง

1. ใช้ roles ของ test environment ตามส่วนสถานะล่าสุด; actual FastAPI runtime role และ membership สดต้องตรวจตามขอบเขตที่อนุญาต Template ยังคง parameterized ไม่ใส่รหัสผ่าน
2. **ยืนยันว่าเป็นฐานข้อมูลทดสอบแยก** ไม่ใช่ฐานข้อมูลใช้งานที่มีอยู่; SQL นี้มี `CREATE TABLE` และ Template มี `REVOKE` ของ Object ใน Schema `public`
3. PostgreSQL Version, Driver Isolation, Connection Pool และ Workflow ใน FastAPI ยังไม่ได้ตรวจจากโค้ดจริง
4. การตรวจ API ตาม G-12 ยังคงเป็นหน้าที่ Backend; V1 ไม่ใช้ RLS

## 6) สถานะการตัดสินใจ

- A-02: **ร่าง RBAC Hardening แล้ว แต่ยังไม่ปิด** จนตรวจ Role/Ownership/SQL-Injection และ Permission จริง
- A-05: **ร่าง Parent-first Operations แล้ว แต่ยังไม่ปิด** จนทดสอบ Lock Order และ Concurrency ใน PostgreSQL
- A-01, A-03, A-04, A-06: ไม่ได้เปลี่ยนกฎ/ฟังก์ชันจากร่าง R-01 ยกเว้น Volatility Helper ที่เกี่ยวกับ A-05; ยังรอ Runtime Test
- R-01 = A: คงเดิม ห้ามลบ Project ทุกกรณี

**คำตัดสิน:** ยังไม่พร้อม Deploy หรือใช้กับฐานข้อมูลจริง; ขั้นตอนต่อไปต้องตรวจรับ Role และทดสอบในฐานข้อมูลแยกหลังได้รับอนุญาตอย่างชัดเจน

## เอกสาร PostgreSQL ที่เกี่ยวข้อง

- [CREATE FUNCTION / SECURITY DEFINER / EXECUTE](https://www.postgresql.org/docs/current/sql-createfunction.html)
- [Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [Function Volatility](https://www.postgresql.org/docs/current/xfunc-volatility.html)
- [Privilege Inquiry Functions](https://www.postgresql.org/docs/current/functions-info.html)
