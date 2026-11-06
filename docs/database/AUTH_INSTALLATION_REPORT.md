# Auth installation — test database

อัปเดต: 2026-11-07 · สถานะ: **ติดตั้ง Auth แล้ว; Auth/Me + Frontend Browser ผ่านพร้อม ROLLBACK**

ผลการติดตั้งและ smoke วันที่ 2026-11-06 ด้านล่างเป็นประวัติของรอบนั้น ผลล่าสุดของ Frontend/Me อยู่ท้ายรายงาน ไม่ได้ติดตั้ง SQL/grants ซ้ำในรอบ Frontend

อ้างอิง [Auth Contract](../api/AUTH_CONTRACT.md), [Auth Design](../api/AUTH_DESIGN.md), [installer](../../database/tools/Auth_Install.py), [DB regression](../../database/tests/Auth_Regression.py) และ [HTTP tests](../../backend/tests/test_auth_api.py)

## ขอบเขตและการติดตั้ง

ดำเนินการต่อจากขั้นที่แจ้งว่าต้องติดตั้ง Auth schema/grants ถาวรและตั้ง config ตามคำสั่งผู้ใช้ “ดำเนินการต่อได้เลย” ผู้ใช้ยืนยันว่าทราบรหัส PostgreSQL ของ project_app และจะตั้ง AUTH_DB_PASSWORD ในเครื่องเอง ไม่ส่งรหัสผ่านผ่านแชท

installer ทดลอง DDL/RBAC ตาม SQL review ด้วย ROLLBACK ก่อน แล้วใช้ `--apply` เพื่อ **COMMIT เฉพาะ auth schema/2 tables/2 functions/indexes และ Auth grants ที่ review แล้ว** ไม่มี fixture/บัญชี/session ถาวร ไม่สร้าง role หรือเปลี่ยนรหัส/สมาชิก role ไม่แก้ V1 functions/SQL files และไม่เชื่อมฐานข้อมูลหลัก

| รายการ | ผล |
|---|---|
| Target | student_project_management_v1_test; ตรวจ current_database ก่อนดำเนินการ |
| Effective deployment role | project_owner ซึ่งไม่ใช่ superuser; มี CREATE บน test DB อยู่แล้ว |
| Owner ของ Auth objects | project_owner |
| Runtime role | project_app; จำกัดสิทธิ์ตาม Auth RBAC ที่ผ่าน review |
| Dry-run ก่อนติดตั้ง | PASS / DRY_RUN_ROLLED_BACK / committed=false |
| ติดตั้ง | PASS / INSTALLED / committed=true เฉพาะ DDL/grants |
| ตรวจซ้ำหลังติดตั้ง | PASS / ALREADY_INSTALLED_VERIFIED / committed=false; ไม่เขียนทับ object |

## โครงสร้างและข้อมูลหลังติดตั้ง/ทดสอบ

| Namespace | ตาราง | Columns | Foreign keys | Functions |
|---|---:|---:|---:|---:|
| public — V1 เดิม | 14 | 86 | 28 | 51 ตาม persistent baseline เดิม |
| auth — ส่วนขยาย | 2 | 6 | 2 | 2 |
| รวม | 16 | 92 | 30 | 53 |

ณหลังติดตั้งและรันชุด 57/40 ก่อนผู้ใช้ตั้ง runtime config: users=0, credentials=0, sessions=0 และทุกตารางรวม 0 แถว ไม่มี fixture ค้าง ค่า identity sequence อาจขยับและไม่รวมในการตรวจ row counts ส่วน smoke หลังตั้ง config ตรวจว่าเฉพาะ fixture ถูก ROLLBACK และจำนวนแถวที่ app อ่านได้ตรงก่อนทดสอบตามรายละเอียดด้านล่าง

V1 object definitions/owners/columns/constraints, schema/table/column/function ACLs, role attributes, database ACL และจำนวนแถวเดิมตรวจว่าไม่เปลี่ยนตามขอบเขต fingerprint ของ installer Incoming internal FK triggers บน public.users จาก Auth FK เป็นผลของส่วนขยายที่ออกแบบไว้ ไม่ได้อ้างว่า catalog ทุก object ต้องเหมือนก่อนมี Auth

**รายการค้าง V1 เดิม:** SQL source มี 52 functions แต่ persistent public มี 51 โดยขาด public.v1_lock_team ผลนี้ตรวจด้วย read-only และมีอยู่ก่อนการติดตั้ง Auth ตาม fingerprint ก่อน/หลัง เป็น P06 ที่เคยทดสอบแพตช์แล้ว ROLLBACK ยังไม่ติดตั้งถาวร ไม่แก้ในรอบนี้และไม่ถือว่า Auth installation ทำให้ V1 patches ครบ

## การทดสอบหลังติดตั้ง

- Auth suite **PASS 57 tests**: validation 17 + hash/token/config 16 + HTTP/PostgreSQL 24
- Auth DB Regression **PASS 40/40** พร้อม baseline_mode=installed
- ทุก fixture/request ใน tests อยู่ใน transaction/savepoints และ ROLLBACK; metadata/ACL/row counts กลับ baseline ที่มี public 14 + auth 2 ตาราง ไม่ลบ installed Auth
- HTTP test fixtures ใช้อีเมล UUID ไม่ชนบัญชีเดโมที่อาจมีภายหลัง
- Validator ตรวจ owner, columns/NOT NULL, function bodies ตรง SQL review, SECURITY DEFINER/search_path, constraints และ effective ACL ก่อนใช้ installed baseline ไม่ DROP/CREATE OR REPLACE หรือซ่อม schema เดิมเอง

พบและแก้เฉพาะตัวตรวจใหม่ระหว่าง dry-run: PostgreSQL 18 เก็บ NOT NULL เป็น pg_constraint.contype='n' ด้วย จึงตรวจ NOT NULL ผ่าน attnotnull และแยกชุด PK/FK/CHECK ออกจาก generated NOT NULL names ไม่แก้ SQL constraints เพื่อให้ tests ผ่าน

## Backend และ config ที่เหลือ

เปิด Backend ที่ http://localhost:8000 แล้ว GET /, /openapi.json และ /docs ตอบผ่าน มี Auth POST routes 3 รายการ ไม่มี live POST signup/login/logout ในรอบนี้และไม่มี runtime fixture COMMIT

ก่อนผู้ใช้ตั้ง AUTH_DB_PASSWORD ผลตรวจเป็น NOT_READY ต่อมาผู้ใช้แจ้งว่าตั้งค่าแล้วและตรวจผ่านตามส่วนผล runtime ด้านล่าง ค่านี้เป็นรหัส PostgreSQL role project_app ตาม [ตัวอย่าง config](../../backend/.env.auth.example) ไม่ใช่รหัสนักศึกษา ไม่มีการแสดงค่า/แก้ .env โดย assistant โค้ดอ่าน AUTH_* ทุกครั้งที่เชื่อมจึงใช้ค่าที่ผู้ใช้ตั้งใหม่ได้โดยไม่แก้ source

ตรวจหลังตั้งค่าเสร็จจาก Workspace root:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Install --check-runtime
```

คำสั่งนี้เชื่อมตรงด้วย project_app ใน read-only transaction แล้ว ROLLBACK ผลล่าสุดคือ PASS/RUNTIME_APP_READONLY_VERIFIED โดยไม่พิมพ์ config/รหัสผ่าน/connection URL ผล NOT_READY เดิมเป็นประวัติก่อนผู้ใช้ตั้งค่า

ไม่มีการ reset project_app password เพราะ role/password PostgreSQL เป็นขอบเขตระดับ cluster การเปลี่ยนอาจกระทบการเชื่อมต่อฐานข้อมูลอื่น

## ผลตรวจหลังผู้ใช้ตั้ง AUTH_DB_PASSWORD

วันที่ 2026-11-06: runtime preflight ผ่านบน student_project_management_v1_test โดย project_app และ committed=false จากนั้นทดสอบ flow ด้วย open_auth_connection() จริง ไม่มี SET ROLE หรือ admin fallback ยืนยันทั้ง session_user และ current_user เป็น project_app

| Smoke check | ผล |
|---|---|
| สมัคร student ผ่าน HTTP/ASGI ด้วย direct app connection | PASS / 201; ตรวจ Argon2id hash ด้วย verify_password ภายใน ไม่แสดงรหัส/hash |
| Login รหัสผิด | PASS / 401 |
| Login รหัสถูก | PASS / 200; session resolve เป็นผู้ใช้ที่เพิ่งสร้าง |
| Logout ไม่มี CSRF header | PASS / 403 |
| Logout พร้อม CSRF | PASS / 204; session ถูกเพิกถอนและ cookie ทั้งสองถูกล้าง |
| ROLLBACK verification | PASS; ไม่พบ user/credentials/session ของ fixture; public.users/auth.sessions counts ตรงก่อนทดสอบ ไม่รวม sequence values |
| Live TCP Login บัญชีที่ไม่มีอยู่หลัง ROLLBACK | PASS / 401 INVALID_CREDENTIALS จาก Backend localhost:8000; ไม่มี Set-Cookie หรือ fixture COMMIT |

Smoke checks 7 จุดนี้แยกจาก Auth suite 57 tests และ DB-only 40 cases ที่บันทึกไว้ก่อนหน้า ใช้ outer transaction(force_rollback=True) และ savepoints ในการทดสอบที่เขียนข้อมูล ส่วน live TCP เรียกเฉพาะ unknown Login ที่ถูกปฏิเสธและ rollback ตาม error path ไม่มี live successful signup/login ที่ COMMIT ข้อมูลถาวร

ข้อจำกัดที่ยังเหลือ: successful runtime data COMMIT, Browser/Frontend flow, Team/Project integration, concurrency และ V1 patch P06 ยังไม่ถูกรับรองจากผลรอบนี้ ไม่แสดง/เผยแพร่ค่าจาก .env และไม่เปลี่ยน schema/grants/role/password ในรอบตรวจ config นี้

## เครื่องมือและคำสั่งรันซ้ำ

```powershell
# ค่าเริ่มต้น dry-run; หากติดตั้งแล้วจะ verify ของเดิม ไม่ apply ซ้ำ
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Install

# Tests ใช้ได้ทั้งก่อนและหลังติดตั้ง และ ROLLBACK ข้อมูลจำลองทั้งหมด
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Auth_Regression
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api -q
```

`--apply` เป็นโหมดติดตั้ง/COMMIT ต้องอยู่ในขอบเขตอนุมัติของการติดตั้งนั้น ส่วน `--check-runtime` เป็น read-only และใช้ร่วมกับ --apply ไม่ได้ SQL review ต้นฉบับที่จบ ROLLBACK ยังเหมือนเดิม เครื่องมือใช้ renderer ที่ pin checksum และเป็นผู้ควบคุม transaction แยก

SHA-256 รุ่นที่รันรอบนี้:

| ไฟล์ | SHA-256 |
|---|---|
| database/tools/Auth_Install.py | 49642fce426b46efbff59a385233ed73ddf25b1c5fa58854c2559e9bffb44e61 |
| database/tests/Auth_Regression.py | 587f1d1f8f6de99df9e5fefa876f38cdbcac92e4d4af421b13176156f3586613 |
| backend/tests/test_auth_api.py | ee641e0867b3b2242d123417b809e4ecd6d463a91194d2bbf6de2d4003198bf5 |

ค่ารุ่นก่อนใน Auth Design ส่วน 10–11 เป็นหลักฐานของรอบก่อนติดตั้ง ไม่ใช่ SHA ของ tests ที่ปรับรองรับ installed baseline ในรอบนี้ SQL review และ runtime Auth source ไม่เปลี่ยน ไม่มี Git commit/push

## Frontend Auth และ Me — ผลล่าสุด 2026-11-07

ผู้ใช้เลือก Feature-based ให้ Auth อยู่ใน `frontend/src/features/auth` และ routes อยู่ใน `frontend/src/app` เพิ่ม GET /api/v1/auth/me อ่านผู้ใช้จาก active session โดยไม่ต่ออายุ/ตั้ง cookie และไม่รับ actor จาก client จากนั้นทำหน้าสมัคร/Login/บัญชี/Logout ต่อ API จริง รายละเอียดใน [Auth Contract](../api/AUTH_CONTRACT.md) และ [Frontend README](../../frontend/README.md)

| การตรวจ | ผล |
|---|---|
| Backend Auth suite | PASS 65 = validation17 + security16 + HTTP/PostgreSQL32; เพิ่ม Me 8 tests จาก 57 เดิม |
| Me cases ใหม่ | valid identity/no-store, missing/malformed/unknown, expired, revoked, current DB identity, no renewal/cookie rotation, spoofed input ignored, sanitized DB error |
| Frontend | ESLint, TypeScript และ production build PASS |
| Browser Microsoft Edge / Playwright1.65.0 | PASS 5/5: full Auth flow/refresh/Logout, validation/duplicate feedback, cookie หาย, network retry, mobile layout |
| ภาพ Desktop/Mobile | ตรวจ login desktop และ register mobile แล้ว ข้อความ/ฟอร์มครบ ไม่มี horizontal overflow ใน mobile 390×844; screenshots อยู่ใน ignored test-results |
| Test target/role | student_project_management_v1_test เท่านั้น; fixture เปิด connection ตรงเป็น project_app ไม่มี SET ROLE/admin fallback สำหรับ requests |
| Transaction | ทุก Browser request อยู่ใน savepoint ของ outer transaction(force_rollback=True); ปฏิเสธ request ถ้า outer transaction หาย |
| Cleanup | PASS metadata/ACL/row counts ก่อน/หลังเท่ากัน และ fixture_connections=0; ไม่รวมค่า identity sequences |
| DB-only regression40 | ไม่รันซ้ำในรอบนี้ SQL/grants ไม่เปลี่ยน ผล40/40 ข้างบนเป็นรอบก่อน |
| เซิร์ฟเวอร์ปกติหลังทดสอบ | เปิด Frontend3000/Backend8000 แล้ว; Browser read-only ยืนยัน API target8000 และ redirect ไป Login เมื่อไม่มี session; TCP GET /,/docs,/openapi.json ผ่าน และ GET /me=401 |

Browser test เปิด Backend fixture ที่ localhost:8001 และ Frontend localhost:3000 เป็น process ทดสอบเท่านั้น ค่า API ปกติยัง localhost:8000 มี network guard บล็อก Auth requests ออกนอก fixture ก่อนส่ง ไม่ใช้ live successful POST ที่ COMMIT เปิด test fixture ต้องตั้ง SPMS_AUTH_BROWSER_ROLLBACK=1 ใน process และปิดเมื่อ suite จบ

ครั้งแรก Browser tests ล้มเหลว 2 cases เพราะ locator role=alert พบทั้งข้อความผิดพลาดของ form และ Next.js route announcer จึงแก้ selector ให้เลือกข้อความของ form โดยเฉพาะ จากนั้นรันครบใหม่ผ่าน 5/5 ไม่เปลี่ยนโค้ดผลิตภัณฑ์เพื่อข้ามผลทดสอบ

ขอบเขตไฟล์: Backend แก้ auth_api.py และ tests; Frontend เพิ่ม feature/routes/styles/config/test dependencies/browser harness; เอกสารอัปเดตตามผลจริง Next dev สร้าง frontend/AGENTS.md อัตโนมัติตาม Next รุ่นติดตั้ง ไม่ใช่ business feature ไม่แก้ SQL V1/Auth, grants, roles, backend/database.py, .env จริง หรือ Requirements และไม่มี Git commit/push

npm install รายงาน 8 moderate vulnerabilities และ engine warning ของ eslint-visitor-keys5.0.1 ที่มีอยู่ใน lockfile เดิมบน Node20.10.0; lint/build ผ่าน ไม่อัปเกรด dependencies เดิมหรือใช้ audit fix ในขอบเขตนี้ ยังไม่ถือว่าปิด dependency security review แล้ว

สิ่งที่ยังไม่รับรอง: runtime successful data COMMIT, Team/Project/G-12 business authorization, admin provisioning/recovery/rate limiting, multi-session concurrency และ HTTPS/LAN/deployment หน้า `/` เป็นข้อมูลบัญชีหลัง Login ยังไม่ใช่ ST-01 และ P06/public.v1_lock_team ยังค้างจาก baseline เดิม

SHA-256 ของ source/tests รุ่นเพิ่ม Me/Browser:

| ไฟล์ | SHA-256 |
|---|---|
| backend/auth_api.py | 25df7b1d1edd7c09aab393c3e791fdfe5ab4a2cbacc29573363bd00ad34de5c1 |
| backend/tests/test_auth_api.py | 2477198517a695b808627f40baa4e94c8ded02ec14d1cd5b85395e55449d8462 |
| backend/tests/test_auth_security.py | c8635db7fdae5016c4e318ddbf8a69f833e37d2587fc5baf704388db098284b6 |
| backend/tests/auth_browser_server.py | b798c8089c60ba0b3696f3752b2b1b771aad8f5d6101d4886ef882ff2bb39f55 |
| frontend/tests/auth.spec.ts | 982c290c60b069325397029acc864bc3277b15a401d3d0a7dd9831496bd9e6ad |
