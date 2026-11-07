# Backlog — Student Project Management System

อัปเดต: 2026-11-07 · Branch: `feature/database-schema` · ฐาน commit ก่อนรอบเตรียม Team DB: `9d07c52` (`Add Schema V1 tooling and self-managed authentication`); งานรอบใหม่ยังไม่ Commit/Push

ฐานอ้างอิง: [Schema V1 Reference](../database/SCHEMA_V1_REFERENCE.md), [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md), [Review Report](../database/Database_Schema_V1_A02_A05_Review_Report.md) และแผน 4 สัปดาห์ใน [handoff](../codex_project_handoff/PROJECT_HANDOFF_CODEX.md)

นี่คือรายการติดตามจากการ audit โค้ดและหลักฐานในบทสนทนา ไม่ใช่การอนุมัติให้ทำทุกแถว ผู้รับผิดชอบ/กำหนดส่งยังไม่ระบุ; ลำดับถัดไปเป็นข้อเสนอ ต้องรักษาขอบเขตคำสั่งผู้ใช้

**ส่งต่อให้ทีม:** [เริ่มต้น/ตั้งค่า](../team/START_HERE.md), [ทีมS: Submission](../team/SUBMISSION_WORK_PACKAGE.md), [ทีมM: Milestone](../team/MILESTONE_WORK_PACKAGE.md) และ [Git/ผลตรวจ](../team/HANDOFF_VERIFICATION.md) ชื่อทีมS/Mเป็นworkpackages ไม่ใช่การระบุเจ้าของงานบุคคลหรืออนุมัติHTTPContractที่ยังเปิดอยู่

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
| P05 | ชุด single-session Workflow Regression 57 กรณี | Done | ล่าสุดรัน57/57 ผ่านใน V1_Baseline_Prepare --test-installed --workflow บน persistent baseline52functions ไม่มี temporary patch พร้อม forced deferred/ROLLBACK | Done เฉพาะชุดที่รัน ไม่ใช่ concurrency/ทุกกฎของ V1 |
| P06 | test DB baseline ที่มีแพตช์ V1 ถาวร | Done | [ติดตั้งตามอนุมัติ](../database/V1_BASELINE_INSTALLATION_REPORT.md) COMMITเฉพาะ6functions+EXECUTE helper1รายการ มี52functionsตรงsource; direct app Team8/owner-Team9/Workflow57/Auth74+40ผ่าน และคืนbaselineหลังROLLBACK; applyซ้ำตรวจรับไม่เขียนทับ | Doneเฉพาะbaseline repair/เส้นทางDBนี้ ไม่รวมfresh installของเครื่องทีม/Concurrency/API |
| P07 | Backend DB request integration | In Progress | Auth→Team→member→Project create/currentใช้SQLจริงผ่านdirect project_app ASGI/Browser rollback fixture ไม่มีadmin fallback บังคับTeam deferred checksและจบUOWก่อนตอบsuccess | businessAPIอื่น/authorizationตามV1ยังไม่ครบ และsuccessful runtime data COMMITยังไม่ทดสอบ |
| P08 | Authentication และ API authorization / G-12 | In Progress | Auth4endpoints/Frontendและ [CLIสร้างadvisorใหม่](../database/ADVISOR_ACCOUNT_PROVISIONING.md) พร้อม17tests/Regression191รอบเตรียม ผ่าน--applyบันทึกadvisor1บัญชีตามอนุมัติแล้ว directappLogin/Me/inbox/Logoutและ17testsหลังapplyผ่าน | coordinator/existing-account/recovery/rate-limitและG-12ระบบเต็มยังไม่ครบ ไม่ปิดทั้งแถวเพียงบันทึก1บัญชี |
| P09 | Team/member/Project / C-01,C-02,C-07,R-01 | In Progress | Team37/member18/Project21testsและBrowserTeam8/member8/Project9ผ่านพร้อมROLLBACK มีProject create/currentตามC-01/R-01และTeam add/listแล้ว | ออก/ถอดสมาชิก/โอนหัวหน้า/Project metadata update และConcurrencyจริงยังไม่ครบ ไม่ปิดทั้งแถวเพียงcreate/read |
| P10 | Advisor invitation | Done | [Contract/API/UIครบworkflow](../api/ADVISOR_INVITATIONS_CONTRACT.md): invitation24tests/Browser12ผ่านจริง รวมactor/role/transfer/exit/privacy/finalimmutable/rollback ตาม [รายงาน](ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md) | Doneเฉพาะขอบเขตที่ยืนยัน ไม่รวมadmin provisioning(P08)/multi-session(P18)/ระบบsecurity-UAT |
| P11 | Submission/file/review/revision | In Progress | SQL snapshot/file-required และDB-onlytestsบางเส้นทาง มี [workpackageทีมS](../team/SUBMISSION_WORK_PACKAGE.md) แยกconfirmed rules/decisionsแล้ว ยังไม่มีAPI/UI | ยืนยันContract/library/contentvalidatorก่อนimplement ส่งกับไฟล์atomic/revision/chunk/413/downloadauthorizationและtests |
| P12 | Committee appointment/vote | In Progress | SQL และ tests แต่งตั้ง/ลงมติ; DB-only | API/UI ตาม role/phase, vote ครบจึงสรุป, ไม่เผย metadata รายบุคคลต่อ Team/Advisor |
| P13 | Milestone/Task/Assignee/history / D-01,C-02 | In Progress | SQL/DB-onlytestsวันที่/status/deferred/exit/cascade มี [workpackageทีมM](../team/MILESTONE_WORK_PACKAGE.md) โดยไม่อนุมัติTaskAPIทั้งหมด | ยืนยันMilestoneContract/readroles/UI ใช้controlledoperations/derivedstatus/D-01 ไม่เพิ่มphasegateหรือgrantsเอง |
| P14 | Evaluation และการเปิดเผยผล | In Progress | SQL และ tests score 0–100, comment, unique, first-score lock; DB-only | API/UI เปิดข้อมูลเมื่อครบตาม G-12; ผลรวม/เฉลี่ยตาม V1 และทดสอบสิทธิ์ |
| P15 | หน้าจอ Student/Leader ST-01–ST-09 | In Progress | ST-02/ST-04/ST-06และบางส่วนST-03/ST-05 พร้อมadvisor inboxที่ผู้ใช้ยืนยัน Desktop/Mobileผ่าน [รายงาน](ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md) | มีimplementation5/9หน้ารวมหน้าที่มีบางส่วน ไม่ใช่5หน้าDoneหรือACทุกหน้า; หน้าบัญชีไม่ใช่Dashboard ST-01 |
| P16 | Business API Contract | In Progress | Auth/Team/Members/Projectและ [Advisor invitations](../api/ADVISOR_INVITATIONS_CONTRACT.md) ผู้ใช้ยืนยัน/implemented/OpenAPI/testsแล้ว; missingresource404ตามG-12 | ยังต้องContractสำหรับsubmission/Project update/ออก-ถอดสมาชิก/โอนหัวหน้าและธุรกิจอื่นก่อนimplement |
| P17 | Frontend→Backend→DB integration | In Progress | Auth/Team/member/Project/invitations UI→FastAPI→PostgreSQLจริงผ่านBrowser42/42ด้วยeffectiveproject_appและROLLBACK; directLOGINappมีboundarysmokeแยก | submissionและworkflowอื่นยังไม่ครบ รวมถึงConcurrency/UAT; Browserownerfixtureไม่ใช่directLOGINapp |
| P18 | Concurrency / TX-01–TX-06 | Blocked | baseline52functionsพร้อมแล้ว แต่ยังไม่มีชุดmulti-session/fixtureร่วมและแผนสิทธิ์COMMIT fixtureที่อนุมัติ | เตรียมแผน/fixtureให้ตรวจรับก่อนรัน ห้ามCOMMITข้อมูลจำลองเพื่อข้ามข้อจำกัดเอง |
| P19 | API security/System/UAT | In Progress | Auth/Teamcreate/current-team testsครอบคลุมrole/actor spoof, session/CSRF/Origin, privacyเฉพาะสมาชิกภาพตน, no-store, expiry/revocation, atomic/deferred failuresและsanitized500 ไม่มีadmin fallback | ยังไม่SEC-07/08/ระบบเต็ม, rate limiting/UAT, file/vote/scoreauthorizationหรือmulti-session concurrency |
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

คงฐาน20งานจากauditเพื่อเปรียบเทียบข้ามรอบ: Done5, In Progress13, Not Started1, Blocked1

`Done / Total × 100 = 5 / 20 × 100 = 25%`

ให้น้ำหนักเท่ากัน นับเฉพาะDone ไม่ให้คะแนน50%แก่งานที่ยังไม่จบ ตัวเลขเป็นอัตราปิดchecklist ไม่ใช่effort/timeหรือcoverageทั้งระบบ P10 In Progress→DoneในรอบinvitationเพราะAPI/UIส่ง-ยกเลิก-รับ-ปฏิเสธตามContractและimmutableหลังสิ้นสุดมีหลักฐานครบตามเกณฑ์แถวเดิม จึงเพิ่มจาก20%เป็น25% ไม่ได้ปิดAuth/provisioning/การจัดการทีมทั้งหมด/Projectทุกworkflow/Concurrency ประวัติด้านล่างเป็นผล ณ แต่ละรอบ

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

- หน้าจอST-01–ST-09ที่มีimplementation: 5/9 (ST-02/ST-04/ST-06และบางส่วนST-03/ST-05ตามscopeที่ยืนยัน); ไม่ใช่5หน้าDoneหรือการผ่านACทุกหน้า advisor inboxนับแยกจาก9หน้าstudentเดิม
- ผล Workflow DB รอบก่อน: 57/57 PASS เป็นอัตราผ่านของชุดนั้น ไม่ใช่ requirement coverage 100%
- รายการ U01–U09 ใน [reference](../database/SCHEMA_V1_REFERENCE.md) ยังไม่นับเพิ่มในตัวหารจนยืนยันขอบเขต
- หากแตก/รวม/เพิ่ม/ตัดงาน ให้บันทึกเหตุผลและฐานตัวหารก่อน/หลัง ไม่เปลี่ยนตัวเลขเงียบ ๆ

## ลำดับที่เสนอให้พัฒนาต่อ

1. [บันทึกadvisor1บัญชีตามอนุมัติแล้ว](../database/ADVISOR_ACCOUNT_PROVISIONING.md): ยืนยันSubmission/file ContractตามV1เป็นworkflowถัดไปก่อนเขียนAPI/UI ไม่เพิ่มstatusหรือขั้นCoordinatorนอกข้อกำหนด
2. เตรียมแผน fixtureร่วม/Concurrencyให้ตรวจรับ ก่อนขออนุญาตCOMMITข้อมูลจำลองเฉพาะส่วนที่จำเป็น แยกจากDDL repairที่ติดตั้งแล้ว
3. ขยายProjectรายละเอียด/metadataที่อนุญาตตามphaseเป็นContractแยก ไม่เพิ่มProject DELETEตามR-01
4. ขยาย invitations→submissions→committee→tasks→evaluation พร้อม tests ตามแต่ละงาน; พิสูจน์ concurrency เมื่อ prerequisites พร้อม
5. ปิด security/UAT และคู่มือ โดยใช้ [Progress Report Template](PROGRESS_REPORT_TEMPLATE.md) อัปเดตหลักฐานทุกครั้ง

## ประเด็นบำรุงรักษาที่แยกจากฟังก์ชันธุรกิจ

| ID | ประเด็น | สถานะ / ขอบเขตถัดไป |
|---|---|---|
| M01 | Test-only connection boundary | แก้ Preflight/เครื่องมือ V1ทั้ง5ตัวแล้ว: pin DB/readonly guard ไม่ import backend engine; offline boundary9ผ่าน ไม่ใช่ fresh-install proof |
| M02 | ส่งต่อโค้ดใน Git | commit9d07c52/Pushแล้วตามอนุมัติรอบก่อน; งานเตรียมTeam DBรอบใหม่นี้ยังไม่Commit/Push |
| M03 | ไฟล์ __pycache__ ที่ root อยู่ก่อนแล้ว | .gitignoreที่rootกันcacheแล้ว ไม่ได้ลบไฟล์ในเครื่อง |
| M04 | เก็บผลทดสอบต่อเนื่องเป็น artifact ที่อ้างเวอร์ชันได้ | Auth Design ส่วน 10–11 เป็นหลักฐานรุ่นก่อนติดตั้ง; Installation Report มีสถานะติดตั้ง/tests 57+40 และ hashes รุ่นรองรับ installed baseline; V1 Workflow 57 เดิมยังอ้างบทสนทนา ต้องแยก suite/ขอบเขตและไม่เผย secrets |

อัปเดตล่าสุด — ติดตั้ง V1 baseline 2026-11-07: ผู้ใช้อนุมัติ “ติดตั้งและทดลองได้เลย” ติดตั้ง6definitionsตามsourceและEXECUTE v1_lock_team1รายการด้วยeffective project_owner ไม่มีfixture/role/password changes มี52V1functionsตรงsource direct project_app ไม่มีowner switchผ่าน8cases, owner-Team9/installed Workflow57/boundary+Auth74/AuthDB40ผ่าน ข้อมูลทั้งหมดROLLBACKคืนinstalled baseline; installerซ้ำ ALREADY_INSTALLED_VERIFIED/committed=false P06 Done และ checklistเป็น20% ยังไม่GitCommit/Pushใหม่ ไม่ใช่TeamHTTP/Concurrency/fresh-install proof

อัปเดตล่าสุด — Team API 2026-11-07: ผู้ใช้ยืนยันrequest/response/status/session-CSRFตามร่างแล้ว ImplementPOST /api/v1/teamsเฉพาะTeam+ผู้สร้างleader เพิ่มteam_api/team_store, ต่อmain.py/handlers และtest fixtureให้ทั้งAuth/Teamrollback Tests101=Auth65+Team27+boundary9 และdirect project_app ASGI/TCPผ่าน ตรวจmetadata/ACL/rowcountsคืนbaseline52functions/0แถว ไม่แก้Schema/RBAC/Frontend/.env และไม่GitCommit/Pushใหม่ P09/P16ยังInProgressเพราะmember/read/Project/UIยังไม่ครบ ไม่มีDoneเพิ่มจึงคง20%

อัปเดตล่าสุด — Team Frontend/current-team 2026-11-07: ผู้ใช้ยืนยันGETทีมของตนตามG-12 ไม่มีทีม404TEAM_NOT_FOUND แทนข้อเสนอเดิม200data:null พัฒนา/teamsในfeatures/teamsพร้อมcreate/refresh/readเฉพาะสมาชิกภาพตน Backend111tests (65+37+9), Browser13/13 (Auth5+Team8), lint/TypeScript/build/direct app ASGIผ่าน ทุกfixtureROLLBACKและคืนbaseline52functions/0แถว ไม่มีSQL/grants/.envหรือGitCommit/Pushใหม่ P15→InProgress; Doneยัง4/20=20% ดูรายงานFrontendสำหรับหลักฐาน/ข้อจำกัด

อัปเดตล่าสุด — Team Members 2026-11-07: ผู้ใช้ยืนยันกรอกอีเมลตรงตัวแล้วเพิ่มทันทีและGET/POST /teams/me/members พัฒนาBackend/Frontendแล้ว Backend129=65+37+18+9, Browser21=5+8+8, direct app smoke/lint/TypeScript/buildผ่าน เก็บข้อมูลเดิมที่มีบัญชี/ทีมอย่างละ1ไว้ ทุกfixtureใหม่ROLLBACKและmetadata/ACL/rowcountsคืนbaseline แก้Auth test countให้เทียบbaselineแทนสมมติDBว่าง ไม่แก้SQL/grants/.env/Business Rulesและไม่GitCommit/Push P09/P15/P16/P17ยังInProgress ไม่มีDoneเพิ่มจึงยัง4/20=20%

อัปเดตล่าสุด — Project 2026-11-07: ผู้ใช้ยืนยันProject Contractแล้ว พัฒนาPOST /projects และGET /projects/meพร้อมหน้า/projects/ลิงก์จากteams ไม่มีDELETE/UPDATE Backend150=65+37+18+21+9, Browser30=5+8+8+9/direct app smoke/lint/TypeScript/buildผ่าน มีC-01/UNIQUE/actor/role/R-01/rollback/error coverage เก็บข้อมูลเดิมusers2/credentials2/sessions1/teams1/team_members2/projects0ไว้ ทุกfixtureROLLBACK metadata/ACL/rowcountsคืนbaseline ไม่แก้SQL/grants/.env/Requirementsและไม่Commit/Push P09/P15/P16/P17ยังInProgress Done4/20=20%

อัปเดตล่าสุด — Advisor invitations 2026-11-07: ผู้ใช้ยืนยันselectจากรายชื่อ/ทำครบworkflowแล้ว พัฒนา6operations/5pathsและสองหน้าทีม-advisor Backend174/Browser42/direct app boundary/lint/TypeScript/buildผ่าน Browserใช้project_ownerเตรียมadvisor2/coordinator1ในoutertransactionก่อนswitchเป็นeffectiveproject_appทุกHTTPrequest ไม่มีadminfallbackruntime ทุกfixtureROLLBACKคืนbaselineที่มีprojects1/users2เดิม ไม่สร้างadvisorถาวร/แก้SQL/grants/.env/Commit/Push P10Doneตามเกณฑ์API/UI/immutableที่ยืนยัน Done5/20=25% P08/P18ยังไม่ปิด

อัปเดตล่าสุด — Advisor provisioning 2026-11-07: เพิ่มownerCLIสร้างadvisorใหม่เท่านั้น DefaultDRY_RUN/ROLLBACK --applyต้องconfirmtestDB รหัสผ่านhiddenTTYไม่รับargument/env/file ไม่upsert/activateบัญชีเก่า 17testsและRegression191ผ่าน --checkอ่านสด/TTYdryrunข้อมูลที่ผู้ใช้ระบุผ่านจริง ยังไม่--apply/COMMITข้อมูลบัญชีถาวร ไม่แก้API/Frontend/SQL/RBAC/.env/Requirements ไม่Commit/Push P08ยังInProgress Done5/20=25%

อัปเดตล่าสุด — บันทึกadvisorตามอนุมัติ 2026-11-07: ผู้ใช้ตอบอนุมัติบันทึกหนึ่งบัญชี รัน--apply/confirmtestDB/hiddenTTYด้วยeffectiveproject_ownerแล้ว APPLIED/persisted=true เพิ่มusers1/credentials1เท่านั้น บัญชีroleadvisor/user_id1667 ตรวจconnectionใหม่พบhashArgon2idและdirectLOGINproject_app TestClientLogin200/Me200/inbox200/Logout204ในouterROLLBACK Provisioning17testsหลังapplyผ่าน metadata/ACLไม่เปลี่ยน sessionsยัง1 fixture0 บัญชีเดิมอยู่ครบ ไม่แก้Source/Schema/RBAC/.envและไม่Commit/Push P08ยังInProgress Done5/20=25%

อัปเดตล่าสุด — เตรียมส่งต่อทีม 2026-11-07: เจ้าของยืนยันWindows/PostgreSQLแยกเครื่อง เพิ่มdocs/teamสำหรับsetup/DB/Submission/Milestone/Gitchecklist/verification และblankbackend/.env.example ไม่implementfeaturesใหม่ รันRegression191/Browser42/build/lint/TypeScript/DBworkflow57และROLLBACKcleanupผ่าน ตรวจsecrets/ignore/imports/links/sourceSQLchecksumแล้ว FreshmachineinstallยังNotVerified ไม่มีstaging/Commit/Push Done5/20=25%เท่าเดิม
