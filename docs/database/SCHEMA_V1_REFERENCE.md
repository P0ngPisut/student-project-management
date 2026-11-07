# Student Project Management System — Schema V1 Reference

อัปเดต: 2026-11-07 · ขอบเขต: รวบรวมข้อกำหนดที่ยืนยันแล้วและแก้ความคลาดเคลื่อนของเอกสาร ไม่เพิ่ม Business Rules หรือเปลี่ยน Schema

## ลำดับการอ้างอิง

1. ข้อกำหนดที่ผู้ใช้ยืนยันล่าสุด รวม R-01=A และข้อจำกัดการใช้งานฐานข้อมูล
2. [Data Dictionary](Database_Schema_V1_Data_Dictionary.md): รายละเอียด G/C/D, 14 ตาราง, 86 คอลัมน์, 28 FK และ ERD ในเนื้อหา
3. [SQL Schema](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) และ [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql): implementation ที่ต้องตรวจตามข้อกำหนด ไม่ใช่อำนาจให้เปลี่ยนข้อกำหนด
4. [Review Report](Database_Schema_V1_A02_A05_Review_Report.md), [Backlog](../progress/BACKLOG.md): สถานะ/หลักฐาน/งานค้าง
5. [ต้นทางการสนทนา](../codex_project_handoff/sources/): ประวัติเดิม เก็บโดยไม่แก้ไข; ข้อเสนอหรือ Wireframe เก่าไม่ลบล้างกฎ V1 ที่ยืนยันภายหลัง

หากเกิดความขัดแย้งใหม่ที่ยังไม่มีคำยืนยัน หยุดงานส่วนที่ต้องตัดสินใจและถามผู้ใช้ก่อน ห้ามอนุมานกฎเพิ่มจากชื่อหน้าจอหรือโครงสร้างตาราง

## กฎที่ยืนยันแล้ว

| หมวด | ข้อกำหนดอ้างอิง | หลักฐานใน V1 |
|---|---|---|
| Users / roles | `users.role` มี student/advisor/coordinator และแก้หลังสร้างไม่ได้; ชื่อ trim ห้ามว่าง; email trim/lowercase/unique; Backend ตรวจรูปแบบ email | Data Dictionary ตาราง users; `v1_normalize_user` |
| หัวหน้าทีม/กรรมการ | leader เป็นบทบาทสมาชิกทีม; กรรมการเป็น advisor ที่ได้รับแต่งตั้ง ไม่ใช่ค่าใหม่ใน users.role | team_members, committee_assignments |
| Team / C-01 | สร้างทีมก่อน Project; ทีมที่ยังอยู่ต้องมีสมาชิกอย่างน้อย 1 และหัวหน้า 1 เมื่อจบ transaction; ผู้ใช้มีสมาชิกภาพปัจจุบันได้สูงสุดหนึ่งทีม | Data Dictionary 4.1–4.2; `v1_team_final_cardinality` |
| Project / R-01=A | ต้องมี Team; หนึ่งทีมมีได้หนึ่ง Project; ผู้สร้างเป็นหัวหน้าปัจจุบัน; **ห้ามลบ Project ทุกกรณี** | `projects.team_id` NOT NULL/UNIQUE/FK; `v1_project_guard`; ไม่มี app DELETE grant |
| สมาชิกและ metadata | การเพิ่มสมาชิกและแก้ Team/Project ขึ้นกับ phase ตาม C-07/4.2; โอนหัวหน้าผ่าน operation ที่กำหนด; ออก/ถอดสมาชิกตามสิทธิ์และ C-02 | `v1_team_members_guard`, `v1_transfer_team_leader`, `v1_exit_team_member` |
| Advisor invitation | หัวหน้าส่ง/ยกเลิก; อาจารย์ที่ถูกเชิญตอบรับ/ปฏิเสธ; pending → accepted/rejected/cancelled; หลัง accepted ไม่เปลี่ยนอาจารย์ใน V1 | `v1_invitation_guard`, `v1_resolve_invitation` |
| Submission / revision | ผู้ส่งเป็นหัวหน้าปัจจุบันและมี advisor accepted; snapshot และประวัติคงเดิม; ต้องมีไฟล์หนึ่งรายการใน transaction; การตรวจจบได้ครั้งเดียว; ขอแก้ไขต้องมีข้อความจริง; รอบส่งใหม่ขึ้นกับผลตรวจรอบล่าสุด | Data Dictionary 4.2; `v1_submission_guard`, `v1_submission_file_required` |
| File & API | PDF/PPTX 1–4,000,000 bytes; Browser ส่ง multipart binary ตรง FastAPI; Backend ตรวจเนื้อหาจริง/extension/MIME อ่านเป็น chunk และตอบ 413 เมื่อเกิน; ดาวน์โหลดผ่าน API ตรวจสิทธิ์ทุกครั้งและเป็น attachment | Data Dictionary 4.3; DB CHECK ตรวจขนาด/extension/MIME ไม่พิสูจน์เนื้อหาไฟล์ |
| Committee / votes | Coordinator แต่งตั้งหลัง advisor approved; advisor ของ Project เป็นกรรมการ Project เดียวกันไม่ได้; อย่างน้อย 3 คนก่อน vote แรก; roster ล็อกหลัง vote แรก; สรุปเมื่อทุกคนลงครบและ approved >50% | `v1_committee_assignment_guard`, `v1_committee_vote_guard`, `v1_topic_decision` |
| Milestone / Task / D-01 | สถานะ Milestone คำนวณจาก Tasks; due date ตรวจตามวัน Asia/Bangkok; Task due ไม่เกิน Milestone; ห้ามย่อวัน Milestone จน Task เกินวันใหม่; transition และสิทธิ์เปิด Task ใหม่ตาม 4.2 | `v1_milestone_guard`, `v1_task_guard`, `v1_refresh_milestone` |
| Assignee / C-02 | in_progress ต้องมีผู้รับผิดชอบ; เข้า completed ต้องมีอย่างน้อย 1; สมาชิกออกต้องไม่ทิ้ง in_progress ไร้ผู้รับผิดชอบ; completed/not_started อาจไม่มีผู้รับผิดชอบจากการออกทีมได้; บันทึกประวัติถอนงาน | `v1_in_progress_has_assignee`, `v1_exit_team_member`, `v1_record_unassignment` |
| Evaluation | กรรมการที่ได้รับแต่งตั้งประเมินครั้งเดียว หลังหัวข้อผ่านกรรมการและมี Milestone completed ≥1; score เป็น integer 0–100 และ comment ห้ามว่าง; immutable; คะแนนแรกล็อกงานตาม 4.2; ผลรวม/เฉลี่ยเปิดเมื่อครบตามสิทธิ์ โดยเฉลี่ยปัดจำนวนเต็ม | Data Dictionary 4.2, 4.4; `v1_committee_evaluation_guard` |
| API access / G-12 | Backend ยืนยันตัวตน ตรวจสิทธิ์ Role/Project และกรอง response ทุกคำขอ; 401/403/404 ตามกรณี; V1 ไม่ใช้ PostgreSQL RLS; ข้อมูล Vote/Evaluation เปิดตามช่วงเวลาและบทบาทที่กำหนด | Data Dictionary 4.4 และ SQL deployment notes |
| Transaction / G-11 | Backend ใส่ actor ที่ตรวจแล้วใน transaction; custom GUC ไม่ใช่หลักฐานยืนยันตัวตน; ล็อก parent ตาม teams → projects → milestones → tasks เมื่อเกี่ยวข้อง; ต้องตรวจ deferred constraints และ concurrency | Data Dictionary 4.6; controlled `v1_*` operations |

ตารางนี้เป็นดัชนีสรุป ต้องอ่านรายละเอียด Data Dictionary โดยเฉพาะ phase, ลำดับแสดงข้อมูล และการเปิดเผยข้อมูล G-12 ก่อนเขียน API ไม่อนุมานว่าแต่ละแถวผ่านการทดสอบครบจากการมีฟังก์ชัน SQL

## ปรับความเข้าใจ Wireframe เดิมให้ตรง V1

| หน้าจอเดิม | ข้อกำหนดที่ต้องใช้ในการพัฒนาต่อ |
|---|---|
| ST-01 Dashboard | ปุ่มสร้าง Project ต้องเคารพ C-01; รูปแบบแจ้งเตือน/นำทางยังต้องออกแบบ ไม่อนุญาต Project ที่ไม่มี Team |
| ST-02 Team Creation | บันทึกทีมและหัวหน้าคนแรกใน transaction เดียว แล้วตรวจ deferred constraints |
| ST-03 Team Management | การเพิ่มสมาชิกตาม phase; การออก/ถอดสมาชิกและโอนหัวหน้าตามสิทธิ์ V1 ส่วนตำแหน่งปุ่ม/confirmation ยังไม่ยืนยัน |
| ST-04 Project Creation | ต้องมี Team และผู้สร้างเป็นหัวหน้าปัจจุบัน; ข้อความเก่าว่า “สร้างได้แม้ไม่มีทีม” ถูกแทนด้วย C-01 แล้ว |
| ST-05 Project Details | แสดง/แก้เฉพาะข้อมูลตาม G-12 และ phase; ไม่มี Project DELETE workflow ตาม R-01 |
| ST-06 Advisor Invitation | ใช้ pending/accepted/rejected/cancelled และไม่เปลี่ยน advisor หลัง accepted |
| ST-07 Project Submission | ต้องมี advisor accepted และไฟล์หนึ่งรายการ; ส่งกับ snapshot อย่าง atomic |
| ST-08 Submission Status | แสดงผลตรวจและผลกรรมการตามสิทธิ์; ไม่สร้างสถานะหรือขั้น “ส่งต่อ Coordinator” เพิ่มเอง; Coordinator เห็นตาม G-12 |
| ST-09 Project Revision | ใช้ revision ของรอบล่าสุดและสร้าง submission รอบใหม่ตาม phase; ไม่แก้ snapshot/ไฟล์ประวัติเดิม |

ข้อกำหนดหน้าจอไม่ใช่หลักฐานว่ามีReact component/Figma/APIแล้ว ปัจจุบันมีAuth/หน้าบัญชี, Team/Project create-currentและAdvisor invitationส่ง-ยกเลิก-ตอบรับ-ปฏิเสธพร้อมUIตาม [รายงานล่าสุด](../progress/ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md) มีimplementationST-02/ST-04/ST-06และบางส่วนST-03/ST-05 รวมadvisor inboxที่ยืนยันเพิ่ม ยังไม่มีออก/ถอดสมาชิก/โอนหัวหน้า/Project update/submission UI หน้าบัญชีไม่ใช่Dashboard ST-01

**คำยืนยันเพิ่มเติม:** APIแรกสร้างทีมพร้อมผู้สร้างเป็นหัวหน้าแล้วเพิ่มสมาชิกภายหลัง ผู้ใช้ยืนยันwire formatของ [Create Team Contract](../api/TEAM_CREATE_CONTRACT.md) แล้วใน2026-11-07 Backendimplemented/testedตามรายงานAPI ไม่เปลี่ยนSchemaหรือBusiness Rules

**U02 — ยืนยันแล้ว:** ผู้ใช้เลือก Feature-based ให้ Auth อยู่ใน `frontend/src/features/auth` และ routes อยู่ใน `frontend/src/app` ไม่ใช่ประเด็นรอตัดสินใจแล้ว ขอบเขตนี้ไม่กำหนดรูปแบบ business UI ที่ยังไม่อนุมัติ

## ข้อกำหนด/หลักฐานที่ยังไม่ยืนยัน

รายการเหล่านี้ไม่ใช่คำสั่งให้ implement และไม่นับเป็นฟังก์ชันเสร็จแล้ว

| ID | สิ่งที่ยังต้องยืนยัน | ขอบเขตที่ทราบแล้ว / ผลต่อการทำงาน |
|---|---|---|
| U01 | Admin provisioning/recovery และ security policy ที่เหลือ | Auth self-managed/email จำลอง/รหัสผ่าน ≥8 + ตัวใหญ่/เลข/student สมัครเอง/ผู้ดูแลเตรียมอาจารย์ ยืนยันแล้ว; TTL 8h/localhost:3000,8000; [Auth ติดตั้งและ direct app connection ผ่านแล้ว](AUTH_INSTALLATION_REPORT.md) ล่าสุด suite 65 + Browser 5 ผ่านพร้อม ROLLBACK ส่วน DB-only 40 เป็นผลรอบก่อน ยังไม่ใช่ Team integration หรือ G-12 ครบ |
| U03 | นิยาม Dashboard metrics, Timeline และ Contribution รายบุคคล | มีข้อเสนอในแผน; การมี task status/history ไม่ได้ยืนยันสูตรหรือหน้าจอรายงาน |
| U04 | เอกสารทั่วไป/versioning นอก Submission V1 | V1 ยืนยันไฟล์หนึ่งรายการต่อ Submission และเก็บประวัติรอบส่งแล้ว; ระบบเอกสารทั่วไปยังไม่ยืนยัน |
| U05 | PDF export/report format | เป็นข้อเสนอมีเงื่อนไขในแผนเดิม ยังไม่อยู่ใน implementation ที่ยืนยัน |
| U06 | Notification อัตโนมัติ | ช่องทาง เหตุการณ์ และขอบเขตยังไม่ยืนยัน |
| U07 | Figma/High-Fidelity/Clickable Prototype และหน้าจอ advisor/coordinatorที่เหลือ | Advisor inboxยืนยันและimplementedเฉพาะคำเชิญแล้ว ส่วนFigma/Prototype/หน้าจอบทบาทอื่นไม่พบartifactในWorkspace; Not Verified ไม่สรุปว่าไม่มีในบริการภายนอก |
| U08 | เอกสารรายวิชา 8 แหล่งและเสียงสัมภาษณ์ต้นฉบับ | ไม่พบใน Workspace; มีเพียงข้อความสรุป จึงตรวจ traceability ย้อนกลับทั้งหมดไม่ได้ |
| U09 | Acceptance criteria/NFR ทั้งระบบและ backlog ที่เจ้าของงานรับรอง | มี Business Rules V1; เกณฑ์ performance, deployment และรายละเอียด UAT ทั้งระบบยังไม่ครบ |

## สถานะการพิสูจน์

- SQL ใน repository: 14 ตาราง, 86 คอลัมน์, 28 FK, 52 functions, 24 triggers
- ผลก่อนย้ายไฟล์ในบทสนทนาวันที่ 2026-11-06: Workflow Regression ผ่าน 57 กรณีบน test DB พร้อม forced deferred checks และ ROLLBACK; RBAC Lock Regression มีผล PASS ก่อนหน้านั้น
- นี่เป็นหลักฐานของชุดทดสอบและเวอร์ชันที่รันในรอบก่อน ไม่ใช่การรับรองทุก G/C/D/R หรือการตรวจฐานข้อมูลสดในรอบจัดโฟลเดอร์
- แพตช์ที่ทดสอบยังไม่ติดตั้งถาวรตามผลรอบก่อน; concurrency, API security และ end-to-end ยังไม่ผ่านการพิสูจน์
- งานปรับโฟลเดอร์รอบนี้ตรวจ syntax/import/path/Static Gate แบบไม่เชื่อมต่อ DB เท่านั้น; ไม่สร้างผลทดสอบ PostgreSQL ใหม่
- รอบ Auth ต่อมา วันที่ 2026-11-06: storage/RBAC ผ่าน 40/40 โดยใช้ project_owner เตรียม DDL/fixtures และ project_app ทำ app operations บน test DB เท่านั้น; ROLLBACK และยืนยัน metadata/ACL/row counts คืน baseline 14 ตาราง/0 แถว ไม่รวมค่า identity sequences ผลนี้ไม่ใช่ HTTP Auth/Concurrency หรือการติดตั้งถาวร
- รอบ Backend Auth วันที่ 2026-11-06: hash/verify + 3 Auth endpoints มีโค้ดและ suite PASS 57 tests = validation 17/security 16/HTTP+PostgreSQL 24 ใช้ outer transaction/savepoints และยืนยัน baseline หลัง ROLLBACK; คนละชุดกับ V1 Workflow 57 เดิม ไม่แก้ Schema/RBAC SQL ไม่ใช่ Browser/Frontend/Team/Concurrency หรือ runtime COMMIT/direct app-password connection ที่ผ่านแล้ว
- รอบติดตั้ง Auth ต่อมา: COMMIT เฉพาะ Auth DDL/grants ลง test DB แล้ว มี public 14/86/28 และ auth 2/6/2 ข้อมูลรวม 0 แถว Tests 57 + 40 บน installed baseline ผ่านและ ROLLBACK ข้อมูลทั้งหมด; ไม่มี role/password changes Main DB ไม่ได้เชื่อมต่อ Runtime app password ยังรอตั้งค่า
- ตรวจ V1 persistent read-only พบ 51 functions ซึ่งขาด v1_lock_team จาก source 52 เป็น P06 เดิม ไม่ได้แก้พร้อม Auth; จำนวน functions ใน repository ไม่ใช่หลักฐานว่า persistent DB มีแพตช์ครบ
- หลังผู้ใช้ตั้ง AUTH_DB_PASSWORD: direct role project_app เข้า test DB ผ่านใน read-only preflight และ smoke 7 จุดผ่าน (Register201, wrong-login401, Login200, CSRF403, Logout204, ROLLBACK cleanup, live TCP unknown Login401) ไม่ใช้ SET ROLE/admin fallback ไม่แก้ schema/grants/role หรือ COMMIT test data
- รอบ Frontend Auth/Me ล่าสุด 2026-11-07: suite 65 (17+16+32), lint/TypeScript/build และ Browser 5/5 ผ่านจริง Browser ใช้ direct app fixture 8001/Frontend 3000 และตรวจ metadata/ACL/row counts คืน baseline ไม่มี fixture connection ค้าง ไม่รวม sequence values; SQL V1/Auth และ grants ไม่เปลี่ยน ไม่ใช่หลักฐานว่า business integration/concurrency หรือ runtime data COMMIT ผ่านแล้ว
- รอบเตรียมTeam DB 2026-11-07: ตรวจสดยืนยัน6function drift/51functions และ direct app first-leader42501/deferred42703 เตรียมSQL reviewตามsourceเดิม Rehearsal Team9/Workflow57ผ่านโดยeffective owner/app ที่ไม่ใช่superuserและคืนbaselineครบ ยังไม่ติดตั้งถาวร; offline boundary9 + Auth65ผ่านรวม74 ปรับPreflight/เครื่องมือV1ให้pin test DBและไม่importbackend engineแล้ว อ่าน [Team Database Readiness Report](TEAM_DATABASE_READINESS_REPORT.md) สำหรับscope/สิทธิ์helperที่รออนุมัติ
- รอบติดตั้งหลังผู้ใช้อนุมัติ: COMMITเฉพาะ6functionsตามsourceและEXECUTE v1_lock_team1รายการลงtest DBแล้ว V1มี52functionsตรงsource ไม่มีUPDATE/DELETEเพิ่ม direct project_app Team8/owner-Team9/installed Workflow57/Auth74+40ผ่านและคืนbaselineหลังROLLBACK ไม่มีfixtureค้าง P06Done อ่าน [V1 Baseline Installation Report](V1_BASELINE_INSTALLATION_REPORT.md) ผลนี้ไม่ใช่API/Concurrency/fresh installของเครื่องทีม
- รอบTeamHTTPหลังยืนยันContract: [Backend API](../api/TEAM_CREATE_IMPLEMENTATION_REPORT.md) สร้างเฉพาะTeam+leaderจากactive session, บังคับOrigin/CSRF/student และtransaction-local actor/parent lock/forced deferred ผ่าน101tests=Auth65+Team27+boundary9/direct app ASGI+TCP rollback smoke ไม่แก้SQL/สิทธิ์/.env/Frontend ยังไม่ConcurrencyจริงหรือTeamFrontendflow
- รอบTeamFrontend/current-team: /teamsสร้างและอ่านทีมของตนหลังrefreshตามGET Contractที่ยืนยัน ไม่มีทีม404TEAM_NOT_FOUNDตามG-12 ผ่านBackend111/Browser13พร้อมROLLBACKและlint/TypeScript/build ไม่เพิ่มสิทธิ์หรือแก้SchemaV1 P15InProgress ยังไม่member management/Project/Concurrencyจริง ดู [รายงานล่าสุด](../progress/TEAM_FRONTEND_IMPLEMENTATION_REPORT.md)
- รอบTeamMembers: ผู้ใช้ยืนยันเพิ่มด้วยอีเมลตรงตัวทันทีและอ่านรายชื่อทีมตนเองแล้ว พัฒนาGET/POST /teams/me/membersและUI /teams ผ่านBackend129/Browser21/direct app smoke/lint/TypeScript/build คืนbaselineที่มีข้อมูลเดิมทุกครั้ง ไม่แก้SQL/RBAC/.envและไม่Commit/Push ยังไม่ออก/ถอด/โอนหัวหน้า/Project/Concurrencyจริง ดู [รายงานMembers](../progress/TEAM_MEMBERS_IMPLEMENTATION_REPORT.md)
- รอบProject: ผู้ใช้ยืนยันContractแล้ว พัฒนาPOST /projectsและGET /projects/meพร้อม/projectsและลิงก์จากteams หัวหน้าสร้าง/สมาชิกอ่านเฉพาะทีมตน IDsstrings ไม่มีDELETE ผ่านBackend150/Browser30/direct app smoke/lint/TypeScript/buildและคืนbaselineที่มีข้อมูลเดิม ไม่แก้Schema/RBAC/.envและไม่Commit/Push ยังไม่invitation/submission/update/Concurrencyจริง ดู [รายงานProject](../progress/PROJECT_IMPLEMENTATION_REPORT.md)
- รอบAdvisor invitations: ยืนยันselectและworkflowครบแล้ว Implement6operations/สองหน้าทีม-advisor ผ่านBackend174/Browser42และคืนbaselineที่มีข้อมูลเดิม Browserเตรียมบัญชีด้วยownerก่อนserveทุกrequestเป็นeffectiveapp ไม่สร้างadvisorถาวร/เพิ่มสิทธิ์/แก้SQL/.env P10DoneเฉพาะขอบเขตContract ไม่รวมprovisioning/Concurrency/UAT ดู [รายงานInvitations](../progress/ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md)
- รอบAdvisor provisioning: CLIสร้างadvisorใหม่และ17tests/Regression191รอบเตรียมผ่าน ต่อมาผู้ใช้อนุมัติบันทึกadvisor1บัญชีด้วยproject_ownerแล้ว เพิ่มusers/credentialsอย่างละ1เท่านั้น directproject_appLogin/Me/inbox/Logoutและ17testsหลังapplyผ่านโดยROLLBACKsessions/fixtures ไม่เปลี่ยนSchema/RBAC/.env/บัญชีเดิม ดู [คู่มือและผลบันทึก](ADVISOR_ACCOUNT_PROVISIONING.md)
