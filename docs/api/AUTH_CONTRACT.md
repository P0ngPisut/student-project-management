# Auth API — Register / Login / Logout / Me

อัปเดต: 2026-11-07 · สถานะ: **Auth 4 endpoints และ Frontend สมัคร/Login/Logout/ตรวจ session ผ่าน Browser tests พร้อม ROLLBACK**

อ้างอิง [Auth Design](AUTH_DESIGN.md), [Auth API source](../../backend/auth_api.py), [storage](../../backend/auth_store.py), [hash/token helpers](../../backend/auth_security.py) และ [Backlog](../progress/BACKLOG.md)

## ขอบเขตที่ยืนยัน

- นักศึกษาสมัครเองได้เป็น student; advisor/coordinator ใช้บัญชีที่ผู้ดูแลเตรียม ไม่มี API สมัครเป็นอาจารย์หรือเครื่องมือ provisioning ในรอบนี้
- ใช้อีเมลจำลองรูปแบบถูกต้อง ไม่จำกัด Gmail; รับ .test ไม่ตรวจ DNS/กล่องอีเมล และไม่ส่ง verification email
- ตั้งรหัสผ่าน ≥8 ตัว มี A–Z ≥1 และ 0–9 ≥1 ไม่บังคับตัวเล็ก/อักขระพิเศษ; รหัสผ่านไม่ trim หรือเปลี่ยน case
- Session อายุคงที่ 8 ชั่วโมง ไม่มี Remember me/ต่ออายุเงียบ; Logout เพิกถอน session ปัจจุบัน
- สภาพแวดล้อมที่ผู้ใช้ยืนยันคือ Frontend http://localhost:3000 และ Backend http://localhost:8000 เท่านั้น ไม่รวม 127.0.0.1 origin, LAN หรือ deployment ภายนอก

## HTTP และรูปแบบข้อมูล

Register/Login/Logout ใช้ POST และต้องส่ง `Origin` ที่ตรงกับ localhost:3000 หรือ localhost:8000 เช่นเดียวกับ Browser (รวม CLI/test tools) Origin ขาด/null/ไม่อนุญาตตอบ 403 ไม่มี wildcard CORS เปิด credentials เฉพาะ origins นี้ ส่วน GET /me เป็นการอ่าน ไม่บังคับ Origin หรือ CSRF header; CORS ยังคุมการอ่านจาก Browser ตาม origins เดิม

Register/Login ใช้ Content-Type: application/json และ JSON object; ไม่รับ fields นอก Contract HTTP responses ของ Auth กำหนด Cache-Control: no-store และไม่ส่ง password/hash/session token ใน JSON หรือ raw SQL errors ให้ client

### POST /api/v1/auth/register

| Field | กฎ |
|---|---|
| full_name | string บังคับ; trim ASCII whitespace ตาม V1, ห้ามว่าง, ค่าที่บันทึก ≤255 ตัวอักษร |
| email | string บังคับ; trim ASCII whitespace, ตรวจรูปแบบ, ≤255 ตัวอักษร; SQL V1 เป็นผู้ normalize เป็น lowercase ก่อนบันทึก |
| password | string บังคับตามกฎที่ยืนยัน; Backend hash ด้วย pwdlib/Argon2id ก่อนส่งเข้าฟังก์ชันสมัคร |

ไม่รับ role, user_id, password_hash หรือ field เพิ่มเติม ไม่มี client-supplied hash/id/role

ตัวอย่างข้อมูลจำลอง:

```json
{"full_name":"นักศึกษาจำลอง","email":"student01@example.test","password":"DemoPass1"}
```

สำเร็จ 201:

```json
{"data":{"id":"101","full_name":"นักศึกษาจำลอง","email":"student01@example.test","role":"student"}}
```

IDs ส่งเป็น decimal strings เพื่อรักษา BIGINT precision; ค่าใน response มาจาก DB หลัง normalize การสมัครไม่ Login อัตโนมัติและไม่ตั้ง session cookie บัญชีอีเมลซ้ำตอบ 409 ไม่เปลี่ยนรหัส/ผูก credentials เข้าบัญชีเดิม

### POST /api/v1/auth/login

Request มี email/password เท่านั้น ใช้ password ที่ตรงกับรหัสเดิมจริง ไม่บังคับกฎตั้งรหัสใหม่ซ้ำที่ Login (เช่นรหัสผิดสั้น ๆ ให้ 401 ไม่ใช่ยืนยันว่าผ่านเพราะซับซ้อนพอ) แต่ชนิดข้อมูล/ค่าว่าง/email syntax ยังตรวจตาม input model

```json
{"email":"student01@example.test","password":"DemoPass1"}
```

สำเร็จ 200 พร้อม data ของผู้ใช้ 4 fields เช่นเดียวกับ Register; Login ได้ทั้ง student/advisor/coordinator ที่มี credentials ตรวจผ่าน และอ่าน role จริงจาก users ไม่รับ role จาก request

ตั้ง cookie 2 ตัวโดยไม่ส่ง token ใน JSON:

| Cookie | หน้าที่ / attributes ในโหมด localhost ที่ยืนยัน |
|---|---|
| spms_session | token สุ่ม 32 bytes แบบ base64url; HttpOnly, SameSite=Lax, Path=/, Max-Age=28800, Host-only |
| spms_csrf | ค่า CSRF ที่ผูกกับ session; JavaScript อ่านได้, SameSite=Lax, Path=/, Max-Age=28800, Host-only |

Secure=False สำหรับ HTTP localhost รอบนี้ การใช้ HTTPS/LAN ต้องทบทวน settings แยก ไม่ถือว่าทดสอบ deployment แล้ว Session token ดิบอยู่ใน cookie; DB เก็บเฉพาะ SHA-256 digest และ expiry จากเวลา server

Login ซ้ำจะออก token ใหม่และเพิกถอน token เดิมที่ Browser ส่งมาใน transaction เดียว หาก transaction ไม่สำเร็จ จะไม่ส่ง success/cookie ใหม่ และ session เดิมยังอยู่ตาม rollback ไม่สัญญาว่า Login จากหลาย Browser จะล้างทุก session ของบัญชี

อีเมลไม่พบ/รหัสผิดตอบ 401 ด้วย envelope เดียวกัน (`INVALID_CREDENTIALS`) ไม่เปิดเผยว่ามีบัญชี และกรณีไม่พบอีเมลยังเรียก verify กับ dummy hash ไม่ใช่การรับรองว่าป้องกัน timing/rate-limit attacks ครบแล้ว

### POST /api/v1/auth/logout

ไม่ต้องมี request body ต้องส่ง session cookie, CSRF cookie, Origin และ header `X-CSRF-Token` ที่ตรงกับ spms_csrf และตรวจว่าเป็นค่าที่ผูกกับ session นี้

Frontend ต้องใช้ credentials: include และอ่านเฉพาะ spms_csrf เพื่อใส่ header ไม่ต้องอ่าน session token ที่เป็น HttpOnly

Backend ตรวจ session กับ DB โดยมี `expires_at > clock_timestamp()` และอ่าน users.role ปัจจุบัน จากนั้นลบ session และล้าง cookie ทั้งสอง สำเร็จ 204 ไม่มี response body Session ขาด/ปลอม/หมดอายุ/ถูกเพิกถอนตอบ 401; CSRF ขาด/ผิด/มาจาก session อื่นตอบ 403 และไม่ลบ session ที่ยังใช้ได้

### GET /api/v1/auth/me

ส่ง session cookie ด้วย `credentials: include` ไม่รับ user_id/role จาก client สำเร็จ 200 พร้อม `data` ที่มี id/full_name/email/role รูปแบบเดียวกับ Login อ่านข้อมูลผู้ใช้ปัจจุบันจาก DB เฉพาะ session ที่ `expires_at > clock_timestamp()` ไม่คืน hash/token และไม่ต่ออายุ session/ตั้ง cookie ใหม่

Cookie ขาด/รูปแบบผิด/ไม่รู้จัก/หมดอายุ/ถูกเพิกถอนตอบ 401 AUTHENTICATION_REQUIRED ทุก response มี Cache-Control: no-store ส่วน DB/config error ตอบ sanitized 500 เช่นเดิม

Frontend เรียก endpoint นี้เมื่อเปิดหน้าบัญชี โหลดใหม่ กลับมาโฟกัสหน้า และลองเชื่อมใหม่ หน้า `/` ยังเป็นหน้าข้อมูลบัญชี ไม่ใช่ Dashboard ST-01 และการ redirect ฝั่ง UI ไม่ทดแทน Backend authorization ของ business endpoints

## Error envelope

```json
{"error":{"code":"INVALID_CREDENTIALS","message":"อีเมลหรือรหัสผ่านไม่ถูกต้อง"}}
```

| HTTP | Code | กรณี |
|---|---|---|
| 401 | INVALID_CREDENTIALS | Login อีเมลไม่พบ/รหัสผิด |
| 401 | AUTHENTICATION_REQUIRED | Me/Logout ไม่มี active session ที่ถูกต้อง |
| 403 | ORIGIN_NOT_ALLOWED | Origin ไม่อยู่ในรายการที่อนุญาต |
| 403 | CSRF_INVALID | Logout มี session แต่ CSRF ไม่ผ่าน |
| 409 | EMAIL_ALREADY_REGISTERED | UNIQUE users.email ของการสมัคร |
| 422 | VALIDATION_ERROR | field/type/format/policy/JSON ไม่ผ่าน; เพิ่ม fields เฉพาะชื่อ field/code ที่กำหนด ไม่สะท้อน input/password/body/ctx |
| 500 | INTERNAL_ERROR | DB/config/role guard/SQL/transaction completion ไม่พร้อม; ไม่ส่ง SQLSTATE, hash, params หรือ traceback |

เฉพาะ users_email_key ของ SQLSTATE 23505 ถูกแปลงเป็น 409; errors ของ DB grants หรือ constraints อื่นไม่ถูกแปลงเป็น 403 ของผู้ใช้เอง

## DB connection และ transaction

Runtime Auth ใช้ psycopg แยกจาก backend.database ซึ่งอาจชี้ DB หลัก โดย pin dbname=student_project_management_v1_test และ user=project_app ไม่มี owner/admin fallback ไม่อ่าน DB_USER/DB_PASSWORD/DB_NAME เดิมเป็น credential ของ Auth

ดู [ตัวอย่าง config ที่ไม่มี secrets](../../backend/.env.auth.example): AUTH_DB_PASSWORD ต้องเป็นค่าของ project_app ที่ผู้ใช้ตั้งในเครื่องเอง; AUTH_DB_HOST/PORT มี default localhost/5432 รหัสจริงไม่เขียนลงตัวอย่างหรือบทสนทนา ไม่แก้ backend/.env ในรอบนี้

ทุก transaction ตรวจ current_database/current_user, superuser/elevated attributes, owner/broad data role membership และ trigger mode ก่อน query Auth ตาราง/SQL/grants V1/Auth ที่ review ไว้ไม่เปลี่ยนแปลง

Runtime ปกติออกแบบให้ transaction สำเร็จก่อนส่ง 201/200/cookie การติดตั้ง COMMIT เฉพาะ Auth DDL/grants ตาม [Installation Report](../database/AUTH_INSTALLATION_REPORT.md) ส่วน test data ใช้ outer rollback-only transaction/savepoints ล่าสุดผู้ใช้ตั้ง AUTH_DB_PASSWORD แล้ว direct authentication ผ่าน ยืนยัน session_user/current_user=project_app และทดสอบ 3 Auth endpoints ผ่านด้วย connection นี้โดยไม่เก็บ fixture ถาวร

## ติดตั้ง dependencies และทดสอบ

ติดตั้ง dependencies ลง virtual environment โดยใช้ไฟล์ runtime และ dev แยกกัน:

```powershell
& .\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

รันจาก Workspace root:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api -v
```

ผลล่าสุด 2026-11-07: **PASS 65 tests** = validation 17 + hash/token/config 16 + HTTP/PostgreSQL 32 เพิ่ม 8 tests สำหรับ Me จาก suite 57 เดิม ไม่ใช่ V1 Workflow 57 และแยกจาก Auth DB Regression 40 ซึ่งผ่านในรอบก่อนติดตั้ง/หลังติดตั้ง รอบนี้ไม่รันชุด DB-only ซ้ำเพราะ SQL/grants ไม่เปลี่ยน ตรวจ baseline หลัง ROLLBACK ไม่รวม sequence values Tests validate Auth ที่ติดตั้งแล้วแทนการสร้างทับ ใช้ UUID emails ไม่ชนข้อมูลเดโม

Coverage รวม hash salt/verify/wrong/corrupt hash, secret redaction, BIGINT IDs, role/input spoofing, duplicate email, cookies/8h expiry, CSRF/origins/CORS, relogin rotation, Logout, expired/unknown session, config/role guards และการไม่ตอบ success เมื่อ transaction completion ล้มเหลว (จำลอง failure ภายใน savepoint) ใช้ [Starlette TestClient](https://starlette.dev/testclient/) กับ httpx2 ที่ตรงกับเวอร์ชันติดตั้ง

เริ่ม Backend จาก root ได้ด้วย `python -m uvicorn backend.main:app --port 8000` หรือคำสั่งเดิม `uvicorn main:app` จาก backend; การเปิด app/OpenAPI ไม่เชื่อม DB และไม่ติดตั้ง schema คำสั่งนี้ไม่ใช่คำสั่งอนุมัติทดสอบ POST ที่เก็บข้อมูลถาวร

## งานที่ยังเหลือ

- Auth schema/grants และ direct app password connection ตรวจผ่านแล้ว รันตรวจซ้ำแบบ read-only ด้วย `python -B -m database.tools.Auth_Install --check-runtime` ได้ ไม่ใช้รหัสนักศึกษาหรือ admin credential แทน
- GET /auth/me และ Frontend Auth เชื่อมจริงแล้วแบบ Feature-based ใน src/features/auth; Browser 5/5 ผ่าน พร้อมตรวจ ROLLBACK/ไม่มี fixture connection ค้าง อ่านคำสั่งใน [Frontend README](../../frontend/README.md)
- Team/member/Project create-currentและAdvisor invitationsครบส่ง-ยกเลิก-รับ-ปฏิเสธเชื่อมBackend/Frontendแล้ว ใช้session/CSRFเดิม ผ่านBrowser rollback testsตาม [รายงานล่าสุด](../progress/ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md) ส่วนออก/ถอดสมาชิก/โอนหัวหน้า/Project update/submission เครื่องมือผู้ดูแล/password reset/rate-limit policy/multi-session concurrencyยังไม่ครบ ไม่มีadvisorถาวรใหม่จากtests
- ผู้ดูแลมี [CLIสร้างadvisorใหม่](../database/ADVISOR_ACCOUNT_PROVISIONING.md) แยกจากAPIแล้ว DefaultROLLBACK/รหัสผ่านhiddenTTY ไม่activateบัญชีเดิมหรือเลือกroleผ่านsignup ทดสอบ17กรณี/Regression191ในรอบเตรียมผ่าน ต่อมาบันทึกadvisor1บัญชีตามอนุมัติด้วย--applyสำเร็จ ตรวจdirectappLogin/Me/inbox/Logoutและprovisioning17testsหลังapplyผ่านโดยROLLBACKsessions/fixtures
- TCP GET /, /openapi.json, /docs และ live POST unknown Login=401 ผ่านในรอบก่อน; HTTPS และ successful runtime data COMMIT ยังไม่ทดสอบ Browser ใช้ fixture 8001 เฉพาะ process ทดสอบ ไม่เปลี่ยน default Backend 8000

อ้างอิง implementation: [pwdlib](https://frankie567.github.io/pwdlib/reference/pwdlib/), [Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html), [OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) รูปแบบ CSRF ใช้ HMAC กับ session secret ผูกค่ากับ session ไม่ใช่เปรียบเทียบ cookie/header สองค่าที่ client ตั้งเองเท่านั้น
