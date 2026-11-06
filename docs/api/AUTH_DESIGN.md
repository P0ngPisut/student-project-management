# Auth Design — ระบบ Login ที่ Backend ดูแลเอง

วันที่: 2026-11-06 · งาน: P08 / U01 · สถานะ: **Auth ติดตั้งแล้ว Tests 57 + 40 ผ่าน; direct app authentication และ smoke 3 APIs ผ่านพร้อม ROLLBACK**

อ้างอิง [Schema V1 Reference](../database/SCHEMA_V1_REFERENCE.md), [Create Team Contract](TEAM_CREATE_CONTRACT.md), [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql) และ [Backlog](../progress/BACKLOG.md)

HTTP Contract ปัจจุบันและวิธีตั้งค่าอยู่ใน [AUTH_CONTRACT.md](AUTH_CONTRACT.md) ผล DB-only 40 cases เดิมอยู่ส่วน 10 ผล hash/HTTP implementation ล่าสุดอยู่ส่วน 11

สถานะติดตั้งและตรวจ runtime ล่าสุดอยู่ใน [Auth Installation Report](../database/AUTH_INSTALLATION_REPORT.md): Auth DDL/grants ติดตั้งแล้ว ผู้ใช้ตั้ง AUTH_DB_PASSWORD เองและ direct app connection ผ่าน มี smoke Register/Login/Logout + cleanup และ live unknown Login=401 ไม่มี fixture ค้างจากการทดสอบ

## 1. สิ่งที่ผู้ใช้ยืนยันแล้ว

- ระบบนี้ใช้ส่งอาจารย์และทดสอบภายในทีม ไม่ได้เตรียมเปิดให้ใช้งานจริง
- ไม่ใช้ Firebase; ให้ Backend ดูแล Login เอง
- ใช้อีเมลจำลองได้ ตรวจรูปแบบอีเมล ไม่จำกัด Gmail ไม่ตรวจว่ามีกล่องรับข้อความจริง และไม่ส่งอีเมลยืนยัน
- รหัสผ่านอย่างน้อย 8 ตัวอักษร มีตัวพิมพ์ใหญ่อย่างน้อย 1 ตัวและตัวเลขอย่างน้อย 1 ตัว
- ตอน Login ต้องใช้รหัสตรงกับที่ตั้งไว้ ไม่ใช่เพียงกรอกรหัสที่ผ่านกฎความซับซ้อน
- นักศึกษาสมัครเองได้เป็น student; ผู้ดูแลเตรียม advisor/coordinator ไม่มีช่องเลือก role อาจารย์ในหน้าสมัครนักศึกษา
- ผู้ใช้ยืนยัน session อายุ 8 ชั่วโมง และรอบแรกใช้ Frontend http://localhost:3000 / Backend http://localhost:8000; cookie HTTP localhost ตาม Contract
- รอบแรกเตรียมและทดสอบด้วย ROLLBACK; รอบถัดมาดำเนินการต่อจากขั้นติดตั้ง Auth ถาวรตามคำสั่งผู้ใช้ COMMIT เฉพาะ Auth DDL/grants ตาม Installation Report ทุก fixture/test ยัง ROLLBACK และไม่มีการเปลี่ยนรหัส/สมาชิก role
- Schema V1 / กฎ G-12 / Roles ธุรกิจเดิมยังเป็นฐานอ้างอิง

## 2. แบบที่เสนอ

Next.js แสดงฟอร์ม Login → FastAPI ตรวจอีเมล/รหัสผ่าน → สร้าง session → ใช้ session ระบุ users.id ในคำขอถัดไป → ตรวจ role/สิทธิ์จาก V1 ก่อนทำงาน เช่นสร้างทีม

รายละเอียดต่อไปนี้เป็นข้อเสนอทาง implementation ไม่ใช่ข้อกำหนดที่ยืนยันทั้งหมด:

- เก็บรหัสผ่านเป็น **Argon2id hash** โดยใช้ไลบรารี เช่น pwdlib/Argon2; ไม่เก็บรหัสผ่านดิบหรือเขียนอัลกอริทึมเอง ตาม [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) และตัวอย่างการ hash ใน [FastAPI](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) การอ้างอิงตัวอย่างนี้ไม่ใช่การเลือก JWT/OAuth2
- ใช้ session ที่ Backend จัดการ: สุ่ม token ใหม่ด้วย CSPRNG 32 bytes เมื่อ Login สำเร็จ เก็บเฉพาะ SHA-256 digest ของ token ใน DB แล้วส่ง token ดิบใน cookie ไม่ใส่ user_id/role ลง cookie เป็นหลักฐานสิทธิ์ ตาม [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- Cookie ใช้ HttpOnly และ SameSite=Lax; ใช้ Secure เมื่อเสิร์ฟผ่าน HTTPS ส่วนการทดลอง HTTP localhost ต้องกำหนดโหมดให้ชัดก่อน implementation ไม่ผูก configuration กับ .env เดิมที่อาจชี้ DB หลัก
- ทุกคำขอที่เขียนข้อมูลต้องตรวจ Origin ที่อนุญาตและใช้การป้องกัน CSRF ที่ผูกกับ session; SameSite เพียงอย่างเดียวไม่ใช่ข้อพิสูจน์ว่าป้องกันครบ ตาม [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- อายุ session แบบตายตัว 8 ชั่วโมง ไม่มีต่ออายุเงียบหรือ Remember me ตามที่ผู้ใช้ยืนยันแล้ว
- Logout ลบ session ฝั่ง Backend และล้าง cookie จึงใช้ token เดิมซ้ำไม่ได้; การหมดอายุบังคับที่ Backend
- ส่ง error Login แบบเดียวกันเมื่อไม่พบบัญชีหรือรหัสผิด ไม่คืน hash/token/traceback; ต้องทดสอบการจำกัดความถี่ของ Login ก่อนใช้ร่วมกัน โดยยังไม่กำหนดจำนวนครั้งแทนผู้ใช้

ตัวอย่าง: ผู้ทดสอบ Login ด้วยบัญชีจำลองที่ผูก users.id ของ student ไว้แล้ว เมื่อสร้างทีม Backend อ่านตัวตนจาก session และตรวจ role จริง จึงตั้งผู้สร้างเป็น leader ได้ การใส่ role/user_id อื่นใน Browser ไม่ทำให้เปลี่ยนตัวตน

## 3. ที่เก็บข้อมูล — อนุมัติให้เตรียมไฟล์ส่วนขยายแล้ว

เสนอ schema ชื่อ `auth` ภายใน **student_project_management_v1_test เท่านั้น** คำว่า schema ในที่นี้หมายถึง namespace ของ PostgreSQL ไม่ใช่ฐานข้อมูลอีกตัว

| ตาราง / คอลัมน์ | ชนิด / ข้อเสนอข้อจำกัด | หน้าที่ |
|---|---|---|
| auth.credentials.user_id | BIGINT, PRIMARY KEY, FK → public.users.id, ON DELETE RESTRICT | ผูกบัญชีแบบหนึ่งต่อหนึ่ง ไม่เพิ่ม email/role สำเนา |
| auth.credentials.password_hash | TEXT, NOT NULL, ขึ้นต้นด้วย $argon2id$ และมีเนื้อหาต่อจาก prefix; ไม่มีช่องว่างหัวท้าย | เก็บ Argon2id encoded hash; CHECK ตรวจ prefix เท่านั้น ไม่ได้พิสูจน์ว่า encoding/parameters หรือรหัสต้นฉบับถูก policy; Backend ต้องสร้าง/verify ด้วยไลบรารี |
| auth.sessions.token_hash | BYTEA, PRIMARY KEY, ความยาว 32 bytes | SHA-256 ของ token สุ่ม ไม่เก็บ session token ดิบ |
| auth.sessions.user_id | BIGINT, NOT NULL, FK → auth.credentials.user_id, ON DELETE CASCADE | ระบุเจ้าของ session |
| auth.sessions.created_at | TIMESTAMPTZ, NOT NULL | เวลาสร้างจาก server |
| auth.sessions.expires_at | TIMESTAMPTZ, NOT NULL, มากกว่า created_at | เวลาหมดอายุ ตรวจทุกครั้งก่อนใช้ |

มี index ที่ sessions.user_id สำหรับเพิกถอน session ของบัญชี และ expires_at สำหรับค้นหา session หมดอายุ; งาน reset password/การล้าง session ยังไม่มี implementation

**ผลต่อขอบเขตหลังติดตั้ง:** public V1 คง 14 ตาราง / 86 columns / 28 foreign keys ส่วน auth เพิ่ม 2 ตาราง / 6 columns / 2 foreign keys รวม 16 ตาราง / 92 columns / 30 foreign keys ไม่แก้ไฟล์ SQL/RBAC V1 เดิม FK ของ credentials ปฏิเสธการลบ users ที่ยังผูก credentials ตาม ON DELETE RESTRICT ที่ออกแบบไว้

ไฟล์ SQL ตามส่วน 8 ผ่าน rehearsal แล้ว เครื่องมือ Auth_Install --apply ติดตั้ง Auth DDL/grants ถาวรในรอบต่อมา รายละเอียดตาม Installation Report ไม่เก็บบัญชี/session fixture ถาวร Tests รองรับ baseline ที่ติดตั้งแล้วโดย validate แทนการ DROP/สร้างทับ และ ROLLBACK ข้อมูลทุกชุด

## 4. สิทธิ์ DB ที่เสนอและวิธีจัดเตรียมบัญชีที่ยืนยันแล้ว

RBAC ปัจจุบันมีสิทธิ์ Auth ที่ติดตั้งแล้วตามส่วน 8 และยังไม่ให้ project_app INSERT/UPDATE users ตรง Runtime ต้องใช้ AUTH_DB_PASSWORD ของ project_app ที่ผู้ใช้ตั้งในเครื่องก่อนเชื่อมต่อ ไม่ใช้ admin fallback

- งาน business เช่นสร้างทีมยังใช้ project_app ตามเดิม ไม่ใช้ postgres/project_owner เป็น role ของ runtime API
- ใช้ project_owner เป็น owner และติดตั้งสิทธิ์ Auth เฉพาะส่วนให้ project_app ตามส่วน 8 แล้ว ไม่มีการสร้าง role ใหม่หรือเปลี่ยนสมาชิก/รหัสผ่าน role
- ไม่ให้ client เลือก users.id/role/หัวหน้าทีมผ่าน payload เพื่อข้ามสิทธิ์
- POST /api/v1/auth/register ตรวจข้อมูล/hash แล้วเรียก auth.register_student สร้าง users + credentials ใน function statement เดียวและกำหนด role='student' ตายตัว ไม่เปิด INSERT users ตรงให้ project_app; ผ่าน HTTP/PostgreSQL tests แล้วใน transaction/ROLLBACK
- advisor/coordinator ให้ผู้ดูแลเตรียมผ่านเครื่องมือ provisioning ที่จะออกแบบแยก ไม่เปิด API สมัครเป็นอาจารย์หรือ runtime owner ในรอบนี้ ยังไม่มีเครื่องมือหรือบัญชีที่เตรียมแล้ว
- เมื่อ email ซ้ำกับ users ที่มีอยู่ ห้ามถือสิทธิ์ในบัญชีนั้นเพียงเพราะกรอกอีเมลตรง การเปิดใช้ credentials ของ user เดิมต้องผ่าน provisioning ที่อนุมัติ

## 5. API ที่เสนอ

| Endpoint | Input / ผลที่เสนอ | สถานะ |
|---|---|---|
| POST /api/v1/auth/login | email + password; สำเร็จตั้ง cookie และคืนข้อมูลผู้ใช้ที่เปิดเผยได้; ผิดบัญชี/รหัสตอบ 401 ข้อความเดียวกัน | Implemented/tested ตาม Auth Contract |
| GET /api/v1/auth/me | ตรวจ session และอ่าน users ปัจจุบัน; ไม่มี/หมดอายุตอบ 401 | Draft; ไม่คืน hash หรือ session token |
| POST /api/v1/auth/logout | เพิกถอน session ปัจจุบันและล้าง cookie; ป้องกัน Origin/CSRF | Implemented/tested; 204 |
| POST /api/v1/auth/register | ผู้สมัครใหม่เป็น student เท่านั้น; ไม่รับ role/password_hash/user_id จาก client | Implemented/tested; 201; ไม่ auto-login |

รูปแบบ envelope/error จะต้องสอดคล้อง Create Team Contract เมื่อรับรอง API ชุดนี้ ไม่ส่ง plaintext password/credential hash กลับใน response หรือ log

## 6. หลักฐานและเกณฑ์ทดสอบ

ทำแล้ว: validation helper/unit tests PASS 17 tests ในรอบพัฒนา helper และ [Auth DB Regression](../../database/tests/Auth_Regression.py) PASS 40/40 ในรอบนี้ ไม่ใช้ Firebase ตัว DB regression อ่าน connection config ภายในโดยไม่แสดงค่า และบังคับ dbname เป็น test DB โดยไม่ใช้ DB_NAME จาก .env

ฟังก์ชัน validate_new_password ใช้ตอนตั้งรหัสใหม่ การ Login ยังต้อง verify hash ของบัญชีจริง ส่วน validate_email_format ตรวจ syntax โดยไม่ normalize; implementation provisioning/login ต้อง normalize ให้ตรง V1 ก่อน lookup/store ไม่ใช้ helper เป็นระบบ Auth สำเร็จรูป

| กลุ่มทดสอบ | เกณฑ์ / สถานะล่าสุด |
|---|---|
| Hash | ผ่าน helper/API tests: salt ต่างกัน, verify รหัสถูก/ผิด/corrupt hash, secret masking และไม่ส่ง password/hash ใน response |
| Provisioning | DB + HTTP signup ผ่าน: atomic users/credentials, duplicate/role/input spoof ถูกปฏิเสธ; เครื่องมือผู้ดูแลยังไม่ทำ |
| Login | HTTP tests ตรวจ hash จริง อ่าน user_id/role จาก DB, error unknown/wrong เหมือนกัน; ยังไม่มี rate-limit policy |
| Session | DB และ HTTP tests ผ่าน: insert/delete, constraints, token rotation, expiry filter, Logout และ CSRF/cookie; ไม่ใช่ Concurrency/Browser จริง |
| HTTP | cookie headers/Origin/CSRF/CORS ผ่าน ASGI tests; Frontend credentials/Browser จริงยังไม่เชื่อม |
| G-12 / Team | student ใช้ session สร้าง Team+leader; advisor/coordinator ถูกปฏิเสธ; ตรวจ role/สมาชิกภาพปัจจุบันใน DB |
| DB guard / RBAC | ตรวจ target/effective role ทุกชุดและ postflight ACL ผ่าน; app direct users/credentials writes และคำสั่ง session ที่ไม่อนุญาตถูกปฏิเสธ; ไม่เชื่อม DB อื่นเพื่อทดสอบ guard |

ตารางข้างต้นเป็นฐานเกณฑ์ก่อนทำ HTTP รายการ DB-only มีผลส่วน 10 ส่วน Hash/Login/HTTP/CSRF/Expiry/Logout มี implementation และ tests ล่าสุดตามส่วน 11 แล้ว G-12 ของ Team/Project, rate limit, Browser จริง และ Concurrency ยังไม่ครบ ไม่ใช้จำนวน tests แทนการรับรองทั้งระบบ

## 7. สถานะการตัดสินใจ

| ID | ต้องยืนยัน | เหตุผล |
|---|---|---|
| AUTH-D01 | ติดตั้ง Auth DDL/grants ถาวรตามขั้นถัดไปแล้ว | Tests 40 และ 57 ผ่านทั้งก่อน/หลังติดตั้ง; ไม่ COMMIT fixture |
| AUTH-D02 | ยืนยันแล้ว: student สมัครเอง; ผู้ดูแลเตรียม advisor/coordinator | ช่องทาง student ในร่าง SQL กำหนด role ตายตัว; เครื่องมือผู้ดูแลยังไม่ได้ทำ |
| AUTH-D03 | ยืนยันแล้ว: 8 ชั่วโมง; Frontend localhost:3000 / Backend localhost:8000 | HTTP cookie/Origin/CSRF/CORS ตาม Auth Contract ผ่าน ASGI tests แล้ว; Browser จริง/HTTPS ยังไม่ทดสอบ |
| AUTH-D04 | Auth RBAC ติดตั้งแล้วและ regression ผ่าน 40/40 | Direct app password/role guard/read-only privilege probe ผ่านแล้ว; smoke ใช้ session_user/current_user เป็น app โดยไม่มี SET ROLE |

ลำดับถัดไป: เลือก scope ทดสอบ Browser/เชื่อม Frontend หรือ Team; runtime credential ตรวจผ่านแล้ว V1 patch P06 ยังเป็นงานแยกและไม่เปลี่ยน SQL review ที่จบ ROLLBACK

## 8. SQL ที่เตรียมแล้ว — ผ่าน rehearsal และ ROLLBACK

- [001_auth_storage_review.sql](../../database/auth/001_auth_storage_review.sql): entry point สำหรับ psql เริ่ม transaction, ตรวจชื่อ test DB/effective owner/non-superuser roles/สิทธิ์ users เดิม, ปฏิเสธ auth schema ที่มีอยู่แล้ว, สร้าง 2 ตารางและ indexes แล้ว include ไฟล์ RBAC; จบด้วย ROLLBACK เท่านั้น
- [002_auth_rbac_review.sql](../../database/auth/002_auth_rbac_review.sql): ใช้ผ่าน entry point ใน transaction เดียวกัน ต้องพบ marker แบบ transaction-local จากไฟล์แรก; ตรวจ DB/owner ซ้ำและกำหนดสิทธิ์เฉพาะส่วน auth

| ส่วน | สิทธิ์ Auth ที่ติดตั้งให้ project_app |
|---|---|
| auth schema | USAGE; ไม่มี CREATE |
| auth.credentials | ไม่มี direct SELECT/INSERT/UPDATE/DELETE; lookup hash ผ่าน auth.lookup_credentials(email) ที่ Backend เรียกเท่านั้น |
| สมัครนักศึกษา | EXECUTE auth.register_student(full_name, email, password_hash); ใช้ role student ตายตัว; ไม่ใช้ ON CONFLICT เพื่อผูกบัญชีเดิม |
| auth.sessions | SELECT, DELETE; INSERT เฉพาะ token_hash/user_id/expires_at; created_at ใช้เวลา server; ไม่มี UPDATE/TRUNCATE |
| public.users และ business objects | ไม่มี grants เพิ่ม; INSERT users เกิดเฉพาะ controlled registration function ที่มี owner เป็น project_owner |

ฟังก์ชันใหม่ 2 ตัวเป็น SECURITY DEFINER, อ้างตารางแบบ schema-qualified, กำหนด search_path = pg_catalog, pg_temp และ REVOKE EXECUTE จาก PUBLIC ใน transaction เดียวกันตาม [PostgreSQL 18 CREATE FUNCTION](https://www.postgresql.org/docs/18/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY) postflight effective access ผ่านใน DB regression แล้วและสิทธิ์ทั้งหมดถูก ROLLBACK

ข้อจำกัด: DB role ของ Backend เป็น trusted boundary และไม่มี RLS เช่นเดียวกับ V1 จึงต้องกรอง session ตามคำขอจริงใน Backend การมีสิทธิ์ SELECT/DELETE sessions ไม่ได้บังคับสิทธิ์รายผู้ใช้ให้เอง Hash lookup เป็นข้อมูลภายในที่ห้ามส่งใน HTTP response ร่างนี้ยังไม่พิสูจน์ความปลอดภัยของ Login จนกว่าจะมี handler และการทดสอบครบ

Baseline รอบแรกยืนยันว่า owner มี CREATE บน test DB และไม่มี app direct users write; owner/app ไม่เป็น superuser V1 มี 14 ตาราง/0 แถวและยังไม่มี Auth ต่อมาหลังติดตั้งมี public 14 + auth 2 ตารางตาม Installation Report หาก baseline ไม่ตรงแบบที่ตรวจรับ validator จะหยุด ไม่แก้/เพิ่มสิทธิ์เพื่อข้ามเอง

ไฟล์นี้เป็นร่างสำหรับ test rehearsal ไม่ใช่ migration ที่ติดตั้งถาวร: ห้ามเปลี่ยน ROLLBACK เป็น COMMIT หรือใช้ installer V1 เพื่อทำให้ส่วนขยายคงอยู่โดยไม่มีขอบเขตอนุมัติ ข้อความ not executed ในหัว SQL เป็นข้อความจากรอบเตรียมไฟล์ สถานะ rehearsal ล่าสุดให้อ้างส่วน 10 โดยไม่แก้ SQL ที่ผ่าน review/pinned checksum

## 9. ผลตรวจ offline ของไฟล์ SQL วันที่ 2026-11-06

| รายการ | ผล / ขอบเขต |
|---|---|
| SQL parser | PASS ด้วย pglast 8.7 / PostgreSQL parser 18.6: 24 statements รวม 2 ไฟล์ (ไม่นับ psql meta-commands) |
| Function/DO bodies | PASS: PL/pgSQL bodies 4 จุด และ SQL function body 1 จุด; ไม่ได้ resolve ชนิดข้อมูล/สิทธิ์กับ catalog จริง |
| โครงสร้าง Auth | PASS ตาม AST: 2 ตาราง / 6 columns / 2 foreign keys / 2 SECURITY DEFINER functions |
| ขอบเขตคำสั่ง | PASS: BEGIN→ROLLBACK, include อ้างไฟล์ RBAC ถูกต้อง, guard DB/owner อยู่ก่อน DDL, functions มี pinned search_path และ revoke PUBLIC; ไม่มี ALTER/DROP V1 หรือ CREATE/ALTER ROLE |
| Grants ที่เสนอ | PASS ตาม AST: ผู้รับคือ project_app และ targets อยู่เฉพาะ auth; ไม่ GRANT บน public.users; student registration ไม่รับ role และไม่ upsert บัญชีเดิม |
| PostgreSQL runtime / effective ACL / signup/session | **Not Run / Not Verified**; ไม่เชื่อมฐานข้อมูลและไม่อ่าน .env |

ตัว parser ติดตั้งใน temporary directory ภายนอก Workspace สำหรับตรวจไฟล์เท่านั้น ไม่เพิ่ม pglast ลง Backend requirements หรือเพิ่มสคริปต์ทดสอบถาวร ผล static ไม่ใช้แทนผล integration/RBAC runtime

## 10. ผล Auth DB Regression รอบแรกก่อนติดตั้ง วันที่ 2026-11-06

คำสั่งจาก Workspace root:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Auth_Regression
```

ผลรอบสุดท้าย: **PASS 40/40 cases** บน PostgreSQL 18.6 เฉพาะ student_project_management_v1_test ใช้ project_owner สำหรับ DDL/fixture และ project_app สำหรับ application operations ทั้งสอง effective roles ไม่เป็น superuser ไม่ patch V1 ไม่สร้าง role และไม่มี COMMIT

| กลุ่ม | จำนวน cases | ผล |
|---|---:|---|
| Guard/baseline, Auth DDL/RBAC postflight, ownership/search_path/PUBLIC ACL | 3 | PASS |
| สร้าง student + normalize และ lookup credentials/unknown email | 3 | PASS |
| อีเมลซ้ำ/บัญชี advisor-coordinator เดิม/role spoof/name/hash/atomic rollback | 9 | PASS |
| app direct users/credentials access, CREATE auth object, session UPDATE/TRUNCATE/override timestamp | 11 | PASS; SQLSTATE 42501 เป็นการปฏิเสธที่คาดหวัง |
| Session insert/server timestamp, UNIQUE/hash length/FK/NULL/lifetime/delete | 10 | PASS |
| User delete RESTRICT, expired session filter, owner credential delete cascade, forced constraints | 4 | PASS |

พบข้อผิดพลาดในค่าคาดหวังของ test ครั้งแรก: การลบ users ที่ credentials อ้างถึงถูกปฏิเสธจาก credentials_user_id_fkey ด้วย **23001 restrict_violation** แต่ test คาด 23503 ตรวจซ้ำแบบ isolated ยืนยันว่า FK ทำงานถูกต้อง จึงแก้เฉพาะค่าคาดหวังใน test และรันครบใหม่ ไม่แก้ SQL/grants ตาม [PostgreSQL error codes](https://www.postgresql.org/docs/18/errcodes-appendix.html) ส่วน session FK ที่อ้าง user ไม่พบยังคืน 23503 ตามที่ทดสอบ

หลัง ROLLBACK: metadata ของ public/auth (ตาราง/columns/constraints/functions/triggers), ownership, schema/table/column/function ACLs, role attributes, database ACL และจำนวนแถวตรง baseline; auth schema หายไป, public เหลือ 14 ตาราง และทุกตารางรวม 0 แถว ค่าของ identity sequences ไม่รวมใน comparison เพราะ INSERT ที่ ROLLBACK ยังใช้ sequence ไปได้

ขอบเขตหลักฐาน: ใช้ synthetic encoded hash fixture เพื่อทดสอบ storage เท่านั้น ยังไม่ verify รหัสผ่านจริง/Argon2 parameters ไม่ทดสอบ HTTP cookies/Logout/CSRF/G-12/Concurrency ไม่ได้ติดตั้ง Auth ถาวร การทดสอบ expired session ยืนยันว่าต้องมี WHERE expires_at > clock_timestamp() ใน Backend; DB ไม่กรองแถวหมดอายุให้อัตโนมัติ

SHA-256 ของไฟล์ที่รัน:

| ไฟล์ | SHA-256 |
|---|---|
| Auth_Regression.py | c124dec030f7264fe31b0ed5d8d991fca4356891b2ca9246c592d98de9b13337 |
| 001_auth_storage_review.sql | 6a3589160160dd73f6a0c6532e39594ecbd9324caf5190e28d9840985039fe9e |
| 002_auth_rbac_review.sql | 818f6e78d26ae78a538cd5440d35fd6ebe8e3b0addcedf5dd02c65d5036ae8f7 |

Harness ตรวจ checksum SQL ก่อนใช้, ขยายเฉพาะ include ที่กำหนดและนำ BEGIN/ROLLBACK ภายนอกออกเพื่อให้ connection เป็นผู้ควบคุม transaction ทั้งชุด จบด้วย rollback ใน finally และเปิด read-only transaction เพื่อตรวจ baseline หลังทดสอบ ไม่ import backend.database หรือใช้ DB_NAME จาก config

## 11. Backend hash/HTTP implementation รอบก่อนติดตั้ง

ทำตามคำสั่งพัฒนา hash/verify + Register/Login/Logout ไม่มีการเพิ่ม GET /auth/me หรือ Team endpoint ในรอบนี้ โค้ดอยู่ใน [auth_api.py](../../backend/auth_api.py), [auth_security.py](../../backend/auth_security.py), [auth_store.py](../../backend/auth_store.py) และ [main.py](../../backend/main.py) รายละเอียด wire format/settings อยู่ใน [Auth Contract](AUTH_CONTRACT.md)

ผู้ใช้ยืนยัน TTL 8 ชั่วโมงและ localhost สอง origin แล้ว ใช้ Argon2id ผ่าน pwdlib, session token สุ่ม 32 bytes/เก็บ digest เท่านั้น, CSRF ที่ผูกกับ session + Origin, Cookie HttpOnly สำหรับ session และ cookie CSRF ที่ JS อ่านได้ Runtime UOW จบก่อนส่ง response/cookie ส่วน tests ใช้ outer transaction/rollback กับ savepoints ต่อ request ไม่มี runtime COMMIT ในการทดสอบ

| ชุด | จำนวน tests | ผลวันที่ 2026-11-06 |
|---|---:|---|
| test_auth_validation.py | 17 | PASS; email/new-password policy |
| test_auth_security.py | 16 | PASS; Argon2id/salt/verify, malformed hashes, token/CSRF, secret masking, BIGINT, config/DB/role guards |
| test_auth_api.py | 24 | PASS; HTTP + PostgreSQL จริงด้วย effective project_app รวม role/input spoof, duplicate, cookies/expiry/CSRF/Origin/CORS, relogin/Logout และ transaction completion failure จำลอง |
| รวม Auth suite | 57 | PASS; แยกจาก V1 Workflow Regression 57 เดิม และ DB-only Auth 40 เดิม |

หลัง ROLLBACK snapshot metadata/ACL/row counts ตรง baseline ไม่มี auth schema และยังมี public 14 ตาราง/0 แถว (sequence values excluded) ไม่แก้ SQL Schema/RBAC V1 หรือ Auth SQL ที่ review แล้ว ไม่แก้ Backend database.py, Frontend หรือ .env จริง

Dependencies เพิ่ม pwdlib[argon2] 0.3.1/argon2-cffi และแยก httpx2 2.16.0 เป็น dev dependencies ตาม Starlette 1.10.0 (แทน httpx ที่มี deprecation warning) `pip check` ผ่าน คำสั่งเดิม uvicorn main:app จาก backend และ backend.main:app จาก root ยัง import/OpenAPI ได้โดยไม่เชื่อม DB

ขอบเขตที่ยังไม่พิสูจน์: direct runtime connection ด้วย AUTH_DB_PASSWORD ของ project_app, runtime commit path จริง, persistent install, Browser/TCP/HTTPS/Frontend, rate limiting, admin provisioning/reset password และ Role/Project authorization ของ business API ไม่มีการเปลี่ยนสิทธิ์/COMMIT เพื่อข้าม prerequisites เหล่านี้

SHA-256 ของ source/tests ที่ผ่านรอบนี้:

| ไฟล์ | SHA-256 |
|---|---|
| backend/main.py | fb21a9534eaff9141a26e973a581e26903ddbdde7281013ceb2dc310c611eb6c |
| backend/auth_api.py | d7b59b853cd0afeaed9bcbbd59fbb2128beb0aafdbe7eebfb7c0e1bf16c4569d |
| backend/auth_security.py | 2b74ef01bcefe6ce86e4ace12c78060a38cd4a85d6144088fb6cfb8b6a452e97 |
| backend/auth_store.py | adfae39be2b8d7ff2223338e9bdecf9b719991b57149b926ce1199025a1253b0 |
| backend/tests/test_auth_security.py | 6023c9cdff98eb57cfa4f63e67021410d199f4008eef469a0158c45926ec55e5 |
| backend/tests/test_auth_api.py | aaceca633e2630292bbc8803b6fdcbd74be24d83acc63cef74713f4806693231 |

## 12. สถานะหลังติดตั้ง Auth

ดู [รายงานติดตั้ง](../database/AUTH_INSTALLATION_REPORT.md) สำหรับผล dry-run, COMMIT เฉพาะ Auth objects/grants, การตรวจซ้ำแบบไม่เขียนทับ, Tests 57 + 40 บน installed baseline, source hashes รุ่นปัจจุบัน และผล GET Backend/Swagger

test DB ปัจจุบันมี 16 ตาราง/92 columns/30 foreign keys แบ่ง public V1 เดิม 14/86/28 และ auth 2/6/2 ไม่มี users/credentials/sessions fixture ค้างอยู่ V1 persistent มี 51 functions ซึ่งขาด v1_lock_team จาก source 52 ตามงาน P06 เดิม ไม่ได้แก้ V1 ในการติดตั้ง Auth

หลังผู้ใช้ตั้ง AUTH_DB_PASSWORD ตรวจ read-only direct app connection และ smoke 7 จุดผ่านแล้วตาม Installation Report ทั้ง session_user/current_user เป็น project_app ไม่มี admin fallback/SET ROLE และ live unknown Login ผ่าน TCP ตอบ 401 ถูกต้อง ส่วน successful runtime data COMMIT/Browser/Frontend ยังไม่รับรอง ไม่เปลี่ยน role/password/schema/grants หรือแตะ main DB ในรอบตรวจ config

## 13. Frontend Auth/Me — อัปเดต 2026-11-07

เพิ่ม GET /api/v1/auth/me และ Frontend register/login/บัญชี/Logout แบบ Feature-based ตามคำยืนยัน U02 แล้ว ไม่เปลี่ยน SQL/storage/grants/session policy อ่าน Contract/การรันใน [Auth Contract](AUTH_CONTRACT.md) และ [Frontend README](../../frontend/README.md)

ผลปัจจุบัน suite65 + Browser5 ผ่านพร้อม ROLLBACK/คืน baseline รวม lint/TypeScript/build ผ่าน ส่วน suite57/DB40 ในหัวข้อก่อนหน้าเป็นผลตามรุ่นในรอบนั้น ไม่ใช่ผลรันซ้ำล่าสุด รายละเอียด fixture/direct project_app และ source hashes รุ่นใหม่อยู่ท้าย [Installation Report](../database/AUTH_INSTALLATION_REPORT.md) ยังไม่ทดสอบ runtime data COMMIT/Team/Concurrency/HTTPS และ P06 ยังแยกจาก Auth
