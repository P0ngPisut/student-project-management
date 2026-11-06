# Database Schema V1 — จุดเริ่มต้นใช้งาน

ปรับโครงสร้างไฟล์วันที่ 2026-11-06 ตามขอบเขตที่อนุมัติ: ย้ายไฟล์และปรับ path/import เท่านั้น ไม่มีการเปลี่ยน SQL, Business Rules, Backend, Frontend หรือฐานข้อมูล

## ตำแหน่งไฟล์

| โฟลเดอร์ | เนื้อหา |
|---|---|
| [schema](schema/) | SQL Schema และ RBAC ต้นฉบับ 2 ไฟล์ |
| [auth](auth/) | SQL review ส่วนขยาย Login 2 ไฟล์; ติดตั้งถาวรใน test DB แล้วผ่าน Auth_Install; SQL review ต้นฉบับยังจบ ROLLBACK |
| [tests](tests/) | Static Gate, RBAC Lock Regression, Workflow Regression และ Auth Regression |
| [tools](tools/) | Preflight, Dry Run และเครื่องมือติดตั้ง 5 ไฟล์ |
| [docs/database](../docs/database/) | Data Dictionary, Review Report และข้อกำหนดอ้างอิงล่าสุด |
| [docs/progress](../docs/progress/) | Backlog และแบบรายงานความคืบหน้า |

อ่าน [Schema V1 Reference](../docs/database/SCHEMA_V1_REFERENCE.md) และ [Backlog](../docs/progress/BACKLOG.md) ก่อนเลือกงานถัดไป ชื่อไฟล์เดิมคงไว้; เปิดแท็บ SQL ใหม่จาก `database/schema/` แทนตำแหน่งเดิมที่ root

## คำสั่งตรวจแบบไม่เชื่อมต่อฐานข้อมูล

เปิด PowerShell ที่ repository root แล้วใช้ Python ของ Backend:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Database_Schema_V1_Static_Gate
```

สคริปต์ใช้ตำแหน่งไฟล์ของตัวเองหา repository root จึงไม่อาศัย current working directory ในการหา SQL รองรับการเรียกด้วย absolute file path ด้วย ส่วนคำสั่ง `-m` ข้างต้นต้องเริ่มที่ repository root

## เลือกเครื่องมือให้ตรงงาน

รายการ V1 ในตารางละคำนำหน้า `Database_Schema_V1_`; รายการ Auth ใช้ชื่อเต็ม ชื่อไฟล์จริงไม่ได้เปลี่ยน

| สคริปต์ | ผลต่อ DB | เงื่อนไขใช้งาน |
|---|---|---|
| [Static_Gate.py](tests/Database_Schema_V1_Static_Gate.py) | ไม่เชื่อมต่อ | ตรวจจำนวน/รูปแบบ SQL ไม่ใช่ PostgreSQL runtime |
| [RBAC_Lock_Regression.py](tests/Database_Schema_V1_RBAC_Lock_Regression.py) | แพตช์ 5 ฟังก์ชัน, RBAC และ fixture ชั่วคราว แล้ว ROLLBACK | ใช้ test DB เท่านั้น; ทดสอบ Team/Project และสิทธิ์ |
| [Workflow_Regression.py](tests/Database_Schema_V1_Workflow_Regression.py) | แพตช์ 6 ฟังก์ชัน, RBAC และ fixture ชั่วคราว แล้ว ROLLBACK | ใช้ test DB เท่านั้น; ล่าสุดผ่าน 57 กรณีในรอบก่อนย้ายไฟล์ |
| [Auth_Regression.py](tests/Auth_Regression.py) | Validate installed Auth หรือสร้างชั่วคราวเมื่อไม่มี; fixtures ทุกกรณี ROLLBACK | PASS 40/40 ทั้งก่อน/หลังติดตั้ง; ไม่ patch V1 |
| [Auth_Install.py](tools/Auth_Install.py) | default dry-run/verify; --apply **COMMIT Auth DDL/grants**; --check-runtime read-only | ใช้ test DB เท่านั้น; ไม่สร้างบัญชี/session fixture หรือเปลี่ยน role/password |
| [Dry_Run_Only.py](tools/Database_Schema_V1_Dry_Run_Only.py) | สร้าง Schema ชั่วคราวแล้ว ROLLBACK | ต้องเป็น test schema ว่าง ไม่ใช่เครื่องมืออัปเดต DB ที่มีตารางแล้ว |
| [Test_Install_Only.py](tools/Database_Schema_V1_Test_Install_Only.py) | **COMMIT Schema** | ต้องเป็น test schema ว่างและได้รับอนุญาตติดตั้งโดยเฉพาะ |
| [RBAC_Dry_Run_Only.py](tools/Database_Schema_V1_RBAC_Dry_Run_Only.py) | ทดลองสิทธิ์แล้ว ROLLBACK | ตรวจ baseline ก่อนติดตั้งสิทธิ์; ปฏิเสธกรณี app มี SELECT แล้ว |
| [RBAC_Test_Apply_Only.py](tools/Database_Schema_V1_RBAC_Test_Apply_Only.py) | **COMMIT สิทธิ์** | ติดตั้ง RBAC ครั้งแรกตามเงื่อนไขสคริปต์; ต้องอนุญาตโดยเฉพาะ |
| [Readonly_Preflight.py](tools/Database_Schema_V1_Readonly_Preflight.py) | SELECT ผ่าน backend engine | **ยังไม่บังคับ test DB**: ห้ามใช้ในงาน test-only จนแก้ guard ในงานที่อนุมัติแยก |

เมื่อมีขอบเขตอนุญาตให้ทดสอบ DB จึงเรียกชุด regression เช่น:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Database_Schema_V1_RBAC_Lock_Regression
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Database_Schema_V1_Workflow_Regression
```

เครื่องมือใน `tools/` ใช้รูปแบบ `-m database.tools.<ชื่อไฟล์ที่ไม่มี .py>` แต่ไม่ใช่รายการคำสั่งให้รันต่อกัน ตัวติดตั้งเดิมไม่สามารถใช้แทน migration ของแพตช์บนฐานข้อมูลที่มี Schema แล้วได้

## ขอบเขตที่ยังต้องรักษา

- ฐานข้อมูลทดสอบที่อนุญาตคือ `student_project_management_v1_test`; ห้ามเข้าถึงฐานข้อมูลหลัก `student_project_management`
- fixture/แพตช์ในการทดสอบต้องอยู่ใน transaction และ ROLLBACK; identity sequence อาจเพิ่มแม้ ROLLBACK
- fixture ใช้ `project_owner`; workflow ใช้ `project_app` และตรวจ effective role ที่ไม่ใช่ superuser
- การย้ายไฟล์ครั้งนี้ไม่ใช่การอนุญาต COMMIT, ติดตั้งแพตช์ถาวร, เปิดใช้ DB อื่น หรือเพิ่มสิทธิ์ app
- ไม่พิมพ์ค่า `.env` หรือ connection URL และไม่ส่ง actor ที่ Browser ระบุมาเชื่อโดยตรง
- Python imports ที่ข้ามโฟลเดอร์ใช้ชื่อ `database.tests...` และ `database.tools...`; หากย้ายอีกต้องตรวจ import และตำแหน่ง SQL/.env ใหม่

SQL ยังคง byte-for-byte เหมือนก่อนย้าย รวมทั้ง comment ประวัติเดิมในหัวไฟล์ สถานะ runtime ล่าสุดให้อ่านใน [Review Report](../docs/database/Database_Schema_V1_A02_A05_Review_Report.md) และ Backlog ไม่ใช้ comment ว่า “NOT EXECUTED” เป็นสถานะปัจจุบัน

## ส่วนขยาย Auth ที่เตรียมสำหรับ review

ผู้ใช้อนุมัติให้เตรียมไฟล์และดำเนินการทดสอบต่อแล้ว ผลตาม [Auth Design](../docs/api/AUTH_DESIGN.md) ส่วน 10 คือ PASS 40/40 และ ROLLBACK ไม่มีการติดตั้งถาวร:

- [001_auth_storage_review.sql](auth/001_auth_storage_review.sql) เป็น entry point: ตรวจ test DB/effective owner ก่อนสร้าง auth.credentials/auth.sessions, include ไฟล์ RBAC และจบ ROLLBACK
- [002_auth_rbac_review.sql](auth/002_auth_rbac_review.sql) ใช้ใน transaction ของไฟล์แรก ไม่ใช่คำสั่ง apply แยกสำหรับ schema ที่มีอยู่แล้ว

ร่างไม่แก้ public ของ V1 ไม่สร้าง/เปลี่ยน roles และไม่ COMMIT ชุดทดสอบที่ใช้จริงคือ:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Auth_Regression
```

Harness บังคับ target เป็น test DB, pin checksum ของ SQL ทั้งสองไฟล์, ควบคุม transaction/ROLLBACK และตรวจ metadata/ACL/row counts คืน baseline; identity sequence values อาจขยับ ไม่ใช้คำสั่งนี้เป็นการติดตั้ง baseline สำหรับเดโมหรือหลักฐาน HTTP Auth ผ่าน

## Backend Auth HTTP tests

รอบต่อมามี Register/Login/Logout และ hash/verify แล้ว ดู [Auth Contract](../docs/api/AUTH_CONTRACT.md) และ [ผลใน Auth Design ส่วน 11](../docs/api/AUTH_DESIGN.md) ชุดใหม่อยู่ที่ backend/tests และทดสอบ SQL จริงด้วย effective project_app โดยยืม connection ใน outer transaction/ROLLBACK ไม่ import engine เดิมที่อาจชี้ DB หลัก:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api -v
```

PASS 57 tests = validation 17 + hash/token/config 16 + HTTP/PostgreSQL 24 แยกจาก Auth DB-only 40 และ V1 Workflow 57 เดิม ทุกชุดคืน baseline หลัง ROLLBACK ไม่รวม sequence values หลังติดตั้ง Auth ถาวรแล้ว tests ใช้ baseline เดิมที่ตรวจรับแทนการสร้างทับ และใช้อีเมล UUID เพื่อไม่ชนข้อมูลเดโม

## Auth ที่ติดตั้งแล้วและ runtime preflight

ดู [Installation Report](../docs/database/AUTH_INSTALLATION_REPORT.md): ติดตั้งผ่าน Auth_Install --apply โดย COMMIT เฉพาะ Auth objects/grants ใน test DB แล้ว รวม public 14 + auth 2 ตาราง/0 แถว Tests 57+40 หลังติดตั้งผ่าน ไม่มีการเปลี่ยน role/password หรือแพตช์ V1

คำสั่งตรวจที่ไม่ติดตั้งซ้ำ:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Install
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Install --check-runtime
```

คำสั่งแรก verify installed baseline หรือ dry-run หากยังไม่มี Auth คำสั่งที่สองเชื่อมโดยตรงด้วย AUTH_DB_PASSWORD ของ project_app ใน read-only transaction ไม่พิมพ์ secrets/URL หลังผู้ใช้ตั้งค่าแล้วผลเป็น PASS/RUNTIME_APP_READONLY_VERIFIED และ smoke Register/Login/Logout ด้วย direct app connection ผ่านพร้อม ROLLBACK รวม live TCP unknown Login=401 ดู Installation Report Backend GET/Swagger เปิดที่ localhost:8000 แล้ว

Auth_Install --apply ใช้เฉพาะงานติดตั้งที่อยู่ในขอบเขตอนุมัติ ไม่ใช่คำสั่ง test และไม่แทนตัวติดตั้งแพตช์ V1 P06 ซึ่งยังขาด v1_lock_team ใน persistent baseline
