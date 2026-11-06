# Backlog — Student Project Management System

อัปเดต: 2026-11-07 · Branch ที่ตรวจ: `feature/database-schema` · HEAD: `9867354` (`Initial project setup`)

ฐานอ้างอิง: [Schema V1 Reference](../database/SCHEMA_V1_REFERENCE.md), [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md), [Review Report](../database/Database_Schema_V1_A02_A05_Review_Report.md) และแผน 4 สัปดาห์ใน [handoff](../codex_project_handoff/PROJECT_HANDOFF_CODEX.md)

นี่คือรายการติดตามจากการ audit โค้ดและหลักฐานในบทสนทนา ไม่ใช่การอนุมัติให้ทำทุกแถว ผู้รับผิดชอบ/กำหนดส่งยังไม่ระบุ; ลำดับถัดไปเป็นข้อเสนอ ต้องรักษาขอบเขตคำสั่งผู้ใช้

## ความหมายสถานะและหลักฐาน

- **Done**: ผ่านเกณฑ์เฉพาะงานย่อยนั้น ไม่ขยายผลเป็นทั้งระบบ
- **In Progress**: มี implementation/artifact บางส่วน แต่ยังไม่ครบเกณฑ์ ไม่ได้หมายถึงมีผู้พัฒนากำลังทำขณะนี้
- **Not Started**: ไม่พบ implementation ของงานนั้นใน Workspace ที่ตรวจ
- **Blocked**: มีเงื่อนไขหรือสิทธิ์อนุมัติที่ต้องผ่านก่อนดำเนินงานส่วนที่ติด
- **Not Verified**: ป้ายกำกับหลักฐานที่ยังตรวจไม่ได้ ใช้คู่กับสถานะ; ไม่เดาผลงานที่อาจอยู่นอก Workspace
- **DB-only**: เรียก SQL ผ่านสคริปต์ ไม่ใช่ผ่าน FastAPI/Frontend

## รายการหลัก 20 งาน — คง ID จากรายงาน audit

| ID | งาน / ข้อกำหนด | สถานะ | หลักฐานปัจจุบัน | เงื่อนไขปิดงาน / งานถัดไป |
|---|---|---|---|---|
| P01 | Frontend starter | Done | [page.tsx](../../frontend/src/app/page.tsx), package/config; ล่าสุด lint/TypeScript/production build ผ่าน | Done เฉพาะ scaffold/build ไม่ใช่ business screens เสร็จ |
| P02 | Backend starter | Done | [main.py](../../backend/main.py); GET / ตอบ 200 ใน ASGI smoke แบบไม่ต่อ DB | Done เฉพาะ skeleton ไม่รวม business API |
| P03 | Requirements/ERD/UI specification สอดคล้อง V1 | In Progress | มี Data Dictionary/ERD, reference ล่าสุด และต้นทาง UI; แก้ความคลาดเคลื่อน C-01/R-01 ในเอกสารอ้างอิงแล้ว | ยืนยัน U01–U09 ที่จำเป็น, acceptance criteria และ design artifacts ที่ยังขาด; ไม่ถือว่ามี Figma แล้ว |
| P04 | SQL Schema/RBAC ตาม V1 | In Progress | [Schema](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql), [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql); มี tests บางเส้นทาง | ครบ requirement-to-test mapping และพิสูจน์ integration/security/concurrency ก่อนปิด |
| P05 | ชุด single-session Workflow Regression 57 กรณี | Done | [Workflow Regression](../../database/tests/Database_Schema_V1_Workflow_Regression.py); PASS 57/57 ในบทสนทนาก่อนย้ายไฟล์ พร้อม forced deferred checks/ROLLBACK | Done เฉพาะชุดที่รัน ไม่ใช่ทุกกฎของ V1; หลังย้ายตรวจ import/path แบบ offline ยังไม่ได้รัน DB ซ้ำ |
| P06 | test DB baseline ที่มีแพตช์ V1 ถาวร | Blocked | ตรวจสดหลังติดตั้ง Auth พบ public มี 51 functions ขาด v1_lock_team จาก source 52; V1 patches เดิมยังไม่ติดตั้ง ไม่ใช่งาน Auth | ต้องเตรียมแพตช์ V1/อนุมัติขอบเขตติดตั้งแยก Auth installation ไม่ได้แก้ V1 และ installer schema ว่างใช้แทนไม่ได้ |
| P07 | Backend DB request integration | In Progress | auth_store/HTTP tests SQL จริงผ่าน; direct project_app connection จาก AUTH config และ smoke 3 Auth APIs ด้วย session_user=current_user=project_app ผ่านพร้อม ROLLBACK; ไม่ใช้ admin fallback | business API ยังต้อง actor/authorization ตาม V1; successful runtime data COMMIT ยังไม่ทดสอบ |
| P08 | Authentication และ API authorization / G-12 | In Progress | Auth 4 endpoints รวม Me/hash/session8h + Frontend Auth แบบ Feature-based; suite 65 + Browser 5/5 ผ่านพร้อม ROLLBACK; DB-only 40/smoke 7 จุดเป็นผลก่อนหน้า ตาม [รายงาน](../database/AUTH_INSTALLATION_REPORT.md) | Team authorization/admin provisioning/recovery/rate limit และ G-12 ระบบเต็มยังไม่ครบ |
| P09 | Team/member/Project / C-01,C-02,C-07,R-01 | In Progress | มี SQL, RBAC Lock/Workflow tests บางเส้นทาง; DB-only | API/UI ใช้ Team→leader→Project, phase และสมาชิกตามกฎ; ไม่มี Project DELETE; integration tests ผ่าน |
| P10 | Advisor invitation | In Progress | มี v1_invitation_guard/v1_resolve_invitation และ tests บางเส้นทาง; DB-only | API/UI ส่ง/ตอบรับ/ปฏิเสธ/ยกเลิกตาม actor; ยืนยัน immutable หลังสรุป |
| P11 | Submission/file/review/revision | In Progress | SQL snapshot/file-required และ tests บางเส้นทาง; DB-only | ส่งกับไฟล์ atomic, revision รอบใหม่, MIME/เนื้อหาจริง/chunk/413 และ download authorization; API/UI/tests |
| P12 | Committee appointment/vote | In Progress | SQL และ tests แต่งตั้ง/ลงมติ; DB-only | API/UI ตาม role/phase, vote ครบจึงสรุป, ไม่เผย metadata รายบุคคลต่อ Team/Advisor |
| P13 | Milestone/Task/Assignee/history / D-01,C-02 | In Progress | SQL และ tests วันที่/สถานะ/deferred/exit/cascade; DB-only | API/UI ใช้ controlled operations; transaction/concurrency และผลประวัติถูกต้อง |
| P14 | Evaluation และการเปิดเผยผล | In Progress | SQL และ tests score 0–100, comment, unique, first-score lock; DB-only | API/UI เปิดข้อมูลเมื่อครบตาม G-12; ผลรวม/เฉลี่ยตาม V1 และทดสอบสิทธิ์ |
| P15 | หน้าจอ Student/Leader ST-01–ST-09 | Not Started | มี Auth UI/หน้าบัญชีแล้ว แต่ยังไม่มี 9 หน้าธุรกิจ; มี spec เป็นข้อความ | Implement ตาม reference V1 และ AC; หน้าบัญชีไม่ใช่ Dashboard ST-01 |
| P16 | Business API Contract | In Progress | [Auth Contract](../api/AUTH_CONTRACT.md) มี 4 implemented endpoints/OpenAPI และ tests; [Team Contract](../api/TEAM_CREATE_CONTRACT.md) ยังร่างและไม่มี Team endpoint | รับรอง/implement Team wire format ตาม V1 และทำ Contract ของ API ธุรกิจอื่น |
| P17 | Frontend→Backend→DB integration | In Progress | Auth UI→FastAPI→PostgreSQL จริงผ่าน Browser 5/5 ด้วย direct project_app และ ROLLBACK; ยังไม่มี business workflow integration | Team/Project และ workflow ที่กำหนดผ่านครบเส้นทาง พร้อม rollback/error handling |
| P18 | Concurrency / TX-01–TX-06 | Blocked | ยังไม่มีชุด multi-session; baseline/fixture ร่วมยังไม่เตรียม | เขียนแผนได้ก่อน; การรันต้อง baseline/fixture ที่อนุมัติและใช้ได้ทั้งสอง session; ห้าม COMMIT เพื่อข้ามข้อจำกัดเอง |
| P19 | API security/System/UAT | In Progress | Auth negative tests มีหลักฐาน secret redaction, role/input spoof, Origin/CSRF/CORS, cookies/expiry/Logout, DB guards และ transaction failure; ยังไม่มี SEC-07/08/ระบบเต็ม | trace Requirement→Code→Test และขยายสิทธิ์ไฟล์/votes/scores/Role-Project, rate limiting และ UAT; ไม่ใช้ Auth tests แทนทั้งระบบ |
| P20 | User manual/Demo ส่งมอบ | Not Started | README มีวิธีเปิดและทดสอบ Auth แต่ยังไม่มีคู่มือ/Demo ระบบธุรกิจ | คู่มือและ Demo อิง workflow ที่ทดสอบจริง; ตรวจ acceptance กับผู้รับงาน |

## สิ่งที่ทำในรอบจัดโฟลเดอร์ (ไม่นำมาเพิ่มตัวหาร 20 งาน)

- ย้าย SQL 2, Python scripts 8 และเอกสาร DB 2 ตาม [ผัง](../../database/README.md)
- ปรับ path/import และคำสั่งเรียกใช้ โดยคงเนื้อหา SQL และ logic ธุรกิจเดิม
- เพิ่ม reference/backlog/template และปรับ handoff ให้ชี้กฎล่าสุด; ต้นทาง sources เก็บเดิม
- ไม่เปลี่ยน Backend/Frontend, ไม่อ่านค่า secrets, ไม่เชื่อมต่อ DB, ไม่ Commit/Push

### ผลตรวจหลังย้ายไฟล์ วันที่ 2026-11-06

| รายการ | ผล / ขอบเขต |
|---|---|
| Python syntax | PASS ทั้ง 8 สคริปต์ |
| Import/path | PASS 16 กรณี: 8 สคริปต์ × module จาก root / direct path จาก frontend; ตรวจแบบไม่เรียก main ของ DB scripts และแทน backend connection module ด้วย stub เพื่อไม่อ่าน .env |
| Static Gate | PASS จาก `python -B -m database.tests.Database_Schema_V1_Static_Gate`; ไม่เชื่อม DB |
| SQL integrity / installer checksum | SQL ทั้ง 2 ไฟล์ byte-for-byte เหมือนก่อนย้าย; SHA256 ของ Schema ยังตรง installer |
| Logic ของ Python | เปรียบเทียบ AST ของ functions/classes ทั้ง 8 ไฟล์: เหมือนเดิม ยกเว้นข้อความชี้ตำแหน่ง SQL เมื่อหาไฟล์ไม่พบใน Static Gate |
| เอกสาร | ลิงก์ภายใน 61 จุด resolve ได้; 20 Task IDs ไม่ซ้ำและจำนวนสถานะตรงสูตร |
| ไฟล์นอกขอบเขต | checksum ของ Backend/Frontend และ sources เดิม 27 ไฟล์ไม่เปลี่ยน; ไม่อ่านค่า .env |
| PostgreSQL regression หลังย้าย | **Not Run** ในรอบนี้; ผล 57/57 ด้านบนเป็นผลก่อนย้าย ไม่ใช่การรันซ้ำ |

## วิธีคำนวณความคืบหน้า

คงฐาน 20 งานจาก audit เพื่อเปรียบเทียบข้ามรอบ: Done 3, In Progress 13, Not Started 2, Blocked 2

`Done / Total × 100 = 3 / 20 × 100 = 15%`

ให้น้ำหนักเท่ากัน นับเฉพาะ Done ไม่ให้คะแนน 50% แก่งานที่ยังไม่จบ ตัวเลขนี้เป็นอัตราปิด checklist ไม่ใช่ effort/time completion หรือความครอบคลุม SRS ทั้งระบบ Auth UI เสร็จตาม scope นี้แต่ยังไม่ครบงาน G-12/ธุรกิจทั้งแถว จึงยังคง 15% ประวัติการอัปเดตด้านล่างเป็นผล ณ แต่ละรอบ ไม่ใช่สถานะล่าสุดแทนตารางด้านบน

อัปเดตรอบ API Contract วันที่ 2026-11-06: P16 เปลี่ยน Not Started → In Progress; ตัวหารคง 20 ไม่มีงาน Done เพิ่ม ผู้ใช้ยืนยันสร้างทีมพร้อมผู้สร้างเป็นหัวหน้าแล้วเพิ่มสมาชิกภายหลัง และไม่มี SSO ที่แอปใช้ได้ ข้อเสนอ Firebase Email/Password ยังรอตัดสินใจ ไม่ใช่ Auth ที่ implement แล้ว รอบนี้แก้เฉพาะเอกสาร ไม่รัน DB/API tests

อัปเดตขอบเขต Auth วันที่ 2026-11-06: ผู้ใช้ยืนยันว่าเป็นโปรเจกต์ส่งอาจารย์และทดสอบภายในทีม ใช้อีเมลจำลองที่มี `@` และตั้งรหัสผ่านเองได้ ไม่ต้องมีกล่องอีเมลจริง เพิ่มข้อเสนอ Firebase Authentication Emulator ใน Contract; ยังรอยืนยันการตรวจรูปแบบอีเมล ความยาวรหัสผ่าน และวิธีจัดเตรียม/ผูกบัญชี ไม่ได้ติดตั้งหรือ implement Auth และยังไม่ได้รันการทดสอบ Login/DB สถานะ P08 กับเปอร์เซ็นต์ยังคงเดิม

อัปเดตล่าสุด — validation วันที่ 2026-11-06: ผู้ใช้ยืนยันตรวจรูปแบบอีเมล ไม่จำกัด Gmail และรหัสผ่าน ≥8 ตัว มีตัวพิมพ์ใหญ่ ≥1/ตัวเลข ≥1 เพิ่ม helper พร้อม unit tests PASS 17 tests และ dependencies email-validator/dnspython (`pip check` ผ่าน) โดยไม่เรียก DB/อ่าน .env ไม่ได้เชื่อม helper เข้ากับ endpoint หรือสร้างบัญชี P08 เปลี่ยน Not Started → In Progress; ไม่มีงาน Done เพิ่ม จึงยัง 15% วิธี Auth/provisioning/mapping/session ยังคงเปิดใน U01

อัปเดตการเลือก Auth วันที่ 2026-11-06: ผู้ใช้เลือก **Backend ดูแล Login เอง ไม่ใช้ Firebase** แทนข้อเสนอเดิม ทำ Auth Design เสนอ Argon2id + server-side session และส่วนขยาย auth.credentials/auth.sessions; สองตารางนี้ยังไม่อนุมัติและยังไม่มี migration/grants/DB writes ต้องยืนยันวิธีสร้างบัญชีและ role ของบัญชีใหม่ก่อนทำ Signup สถานะ P08 ยัง In Progress และความคืบหน้ายัง 15%

อัปเดตล่าสุด — Auth SQL review วันที่ 2026-11-06: ผู้ใช้ยืนยัน student สมัครเอง/ผู้ดูแลเตรียม advisor-coordinator และอนุมัติให้เตรียม migration/RBAC ตามแบบที่อธิบาย เพิ่ม SQL draft 2 ไฟล์ใน database/auth โดย storage include RBAC ใน transaction เดียวและจบ ROLLBACK เสมอ ร่างให้สมัคร student ผ่าน controlled function/lookup hash ผ่าน function/จัดการ session ด้วยสิทธิ์จำกัด ไม่มี direct users write หรือ credentials table access ให้ app รอบนี้ยังไม่เชื่อม DB/รัน grants/COMMIT และไม่แก้ SQL V1 เดิม สถานะ P08 ยัง In Progress ความคืบหน้ายัง 15%

ผลตรวจไฟล์ Auth SQL รอบนี้: parser PostgreSQL 18.6 (pglast 8.7) ผ่าน 24 statements, PL/pgSQL bodies 4 จุดและ SQL function body 1 จุด; AST checks ของ transaction/guard/โครงสร้าง/ขอบเขต GRANT ผ่าน รายละเอียดใน Auth Design ส่วน 9 ทั้งหมดเป็น offline ไม่ใช่ผล PostgreSQL runtime/ACL/Login PASS; unit tests validation 17 กรณีเป็นผลรอบพัฒนา helper ไม่ได้รันซ้ำในรอบ SQL review

อัปเดตล่าสุด — Auth DB regression วันที่ 2026-11-06: ผู้ใช้ให้ดำเนินการขั้นทดสอบต่อ ตรวจ baseline แบบ read-only แล้วทดสอบบน student_project_management_v1_test ได้ **PASS 40/40** ตาม Auth Design ส่วน 10 ทดลอง DDL/RBAC/fixtures ด้วย project_owner และคำสั่ง app ด้วย project_app ไม่ใช้ superuser ข้ามคำสั่งที่ถูกปฏิเสธ แก้เฉพาะ expected SQLSTATE ใน test ลบ user จาก 23503 เป็น 23001 หลังยืนยัน ON DELETE RESTRICT ทำงานถูกต้อง ไม่มีการแก้ SQL/grants เพิ่ม หลัง ROLLBACK metadata/ACL/row counts คืน baseline 14 ตาราง/0 แถว (ไม่รวม sequence values) ยังไม่ COMMIT/ติดตั้ง Auth ถาวร/ทำ HTTP Login; P08 ยัง In Progress และเปอร์เซ็นต์ยัง 15%

อัปเดตล่าสุด — Backend Auth วันที่ 2026-11-06: ผู้ใช้สั่งพัฒนา hash/verify + Register/Login/Logout และยืนยัน session 8 ชั่วโมง/localhost:3000,8000 เพิ่ม auth_security/auth_store/auth_api, ต่อ main.py และ config example ที่ไม่มี secrets ไม่แก้ .env จริง/Frontend/SQL Runtime pin project_app + test DB ไม่มี admin fallback; HTTP tests ยืม connection ที่ effective role เป็น app และใช้ savepoints ภายใน outer ROLLBACK ได้ PASS 57 tests (17+16+24) พร้อม baseline verification; ไม่ใช่ V1 Workflow 57 เดิม แยก dev dependencies เป็น httpx2 ให้ตรง Starlette และ pip check ผ่าน P19 เปลี่ยน Not Started→In Progress เพราะมี Auth negative tests จริง แต่ไม่มี Done เพิ่ม จึงยัง 15%

อัปเดตล่าสุด — ติดตั้ง Auth วันที่ 2026-11-06: ดำเนินการต่อจากขั้นติดตั้งถาวร เพิ่ม Auth_Install (dry-run/--apply/--check-runtime) แล้ว COMMIT เฉพาะ Auth DDL/grants ลง student_project_management_v1_test ไม่มี fixture/role/password changes ปรับ tests รองรับ installed baseline และ UUID emails โดยตรวจ function bodies/owner/ACL ก่อนใช้งาน แก้เฉพาะ validator ให้รู้จัก NOT NULL catalog ของ PG18 ไม่แก้ SQL review Tests 57+40 ก่อน/หลังติดตั้งผ่านและคืน baseline 16 ตาราง/0 แถวหลัง ROLLBACK เปิด Backend ที่ localhost:8000 GET /,/docs,/openapi.json ผ่าน รอผู้ใช้ตั้ง AUTH_DB_PASSWORD ซึ่งผู้ใช้ยืนยันว่าจะตั้งเอง; ไม่แสดง secrets ยังไม่รับรอง direct app-password connection และ P06 V1 v1_lock_team ยังค้าง ไม่มี Done เพิ่มจึงยัง 15%

อัปเดตล่าสุด — ตรวจ config/runtime วันที่ 2026-11-06: ผู้ใช้แจ้งว่าตั้ง AUTH_DB_PASSWORD แล้ว ตรวจ read-only direct connection ผ่านและ smoke 7 จุดด้วย project_app session จริง ไม่มี SET ROLE/admin fallback: Register201/wrongLogin401/Login200/CSRF403/Logout204/ROLLBACK cleanup/live TCP unknownLogin401 ไม่แสดง config/password/token/hash และไม่แก้ .env/source/schema/grants/role ผล smoke แยกจาก suite 57 และ DB-only 40 เดิม ยังไม่ทดสอบ successful runtime COMMIT หรือ Browser/Frontend/Team ไม่มี Done เพิ่มจึงยัง 15%

อัปเดตล่าสุด — Frontend Auth/Me 2026-11-07: ผู้ใช้เลือก Feature-based src/features/auth เพิ่ม GET /api/v1/auth/me + หน้า register/login/บัญชี/Logout เชื่อม API จริง ไม่เปลี่ยน SQL/RBAC/Requirements/.env/backend.database ผล suite 65 (17+16+32), lint/TypeScript/build และ Browser 5/5 ผ่าน ตรวจ Desktop/Mobile และ baseline หลัง ROLLBACK/ไม่มี fixture connection ค้าง ใช้ test DB เท่านั้น Browser fixture 8001 ไม่เปลี่ยน default API8000; เพิ่ม Playwright และ test runner ที่ไม่เก็บ fixtures ถาวร P17 เปลี่ยน Not Started→In Progress เพราะมี Auth integration จริง แต่ยังไม่มี business flow จึงไม่มี Done เพิ่มและยัง 15% U02 ยืนยันแล้ว; U01 security/provisioning ที่เหลือยังเปิด

- หน้าจอ ST-01–ST-09 ที่ implement: 0/9
- ผล Workflow DB รอบก่อน: 57/57 PASS เป็นอัตราผ่านของชุดนั้น ไม่ใช่ requirement coverage 100%
- รายการ U01–U09 ใน [reference](../database/SCHEMA_V1_REFERENCE.md) ยังไม่นับเพิ่มในตัวหารจนยืนยันขอบเขต
- หากแตก/รวม/เพิ่ม/ตัดงาน ให้บันทึกเหตุผลและฐานตัวหารก่อน/หลัง ไม่เปลี่ยนตัวเลขเงียบ ๆ

## ลำดับที่เสนอให้พัฒนาต่อ

1. Auth/Me/Frontend Browser ผ่านแล้ว: ตรวจรับ [Team Contract](../api/TEAM_CREATE_CONTRACT.md) และเตรียมแผนแก้ P06 ของ V1 ก่อนพัฒนา workflow Team/Project โดยไม่ติดตั้งแพตช์เอง
2. เตรียมแผน test DB baseline/แพตช์ถาวร/fixture ร่วมให้ตรวจรับก่อนขออนุญาต COMMIT เฉพาะส่วนที่จำเป็น
3. ทำ API Contract, actor/auth/authorization และ transaction integration ก่อนเชื่อมหน้าจอ workflow แรก
4. ขยาย invitations→submissions→committee→tasks→evaluation พร้อม tests ตามแต่ละงาน; พิสูจน์ concurrency เมื่อ prerequisites พร้อม
5. ปิด security/UAT และคู่มือ โดยใช้ [Progress Report Template](PROGRESS_REPORT_TEMPLATE.md) อัปเดตหลักฐานทุกครั้ง

## ประเด็นบำรุงรักษาที่แยกจากฟังก์ชันธุรกิจ

| ID | ประเด็น | สถานะ / ขอบเขตถัดไป |
|---|---|---|
| M01 | Readonly Preflight ยังใช้ backend engine ไม่บังคับ test DB | ต้องอนุมัติแก้ target/guard แยก; งานย้ายไฟล์ไม่ได้แก้พฤติกรรมนี้ |
| M02 | เอกสาร/โค้ด DB ยังไม่อยู่ใน Git commit | คง untracked ตามสิทธิ์ปัจจุบัน; ห้าม commit/push เอง |
| M03 | ไฟล์ __pycache__ ที่ root อยู่ก่อนแล้ว | ไม่ใช่ source; ไม่ได้ลบ/เปลี่ยน ignore ในงานนี้ |
| M04 | เก็บผลทดสอบต่อเนื่องเป็น artifact ที่อ้างเวอร์ชันได้ | Auth Design ส่วน 10–11 เป็นหลักฐานรุ่นก่อนติดตั้ง; Installation Report มีสถานะติดตั้ง/tests 57+40 และ hashes รุ่นรองรับ installed baseline; V1 Workflow 57 เดิมยังอ้างบทสนทนา ต้องแยก suite/ขอบเขตและไม่เผย secrets |
