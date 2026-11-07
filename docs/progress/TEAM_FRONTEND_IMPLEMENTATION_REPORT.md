# Team create/current-team UI — 2026-11-07

สถานะ: **หน้า /teams เชื่อม POSTสร้างทีมและ GETทีมปัจจุบันแล้ว ทดสอบBrowser/Backendผ่านพร้อมROLLBACK**

รายงานประวัติรอบcreate/current-team: ผล111/13และbaseline0แถวด้านล่างเป็นผลในรอบนั้น งานต่อมาพัฒนาเพิ่ม/อ่านสมาชิกแล้ว ดู [Team Members Report](TEAM_MEMBERS_IMPLEMENTATION_REPORT.md) สำหรับหลักฐานล่าสุดและbaselineที่มีข้อมูลเดิม

ผู้ใช้ให้ดำเนินงานFrontendต่อและยืนยัน [Current Team Contract](../api/TEAM_CURRENT_CONTRACT.md) คำตอบแก้ไขล่าสุดยึดG-12 กรณีไม่มีทีมเป็น404TEAM_NOT_FOUND แทนข้อเสนอแรก200data:null ไม่มีการเปลี่ยนBusiness RulesหรือSchema V1

## สิ่งที่พัฒนา

- เพิ่มGET /api/v1/teams/me สำหรับstudent อ่านเฉพาะทีมที่ตนเป็นสมาชิก คืนid/name/description/membership(id,role) ไม่ส่งรายชื่อสมาชิกอื่น/email/Project IDsเป็นstrings
- ไม่มีsession=401, roleไม่ใช่student=403, ไม่มีmembership=404TEAM_NOT_FOUND, storage error=500 แบบsanitized; GETไม่บังคับOrigin/CSRF ไม่renewsession ทุกresponse no-store
- หน้า/teamsใช้Auth sessionเดิม; studentไม่มีทีมเห็นformชื่อและคำอธิบาย หลังPOST201เห็นชื่อทีม/รายละเอียด/บทบาทตนเอง Refreshอ่านGETใหม่โดยไม่พึ่งclient storage
- เพิ่มลิงก์ทีมของฉันจากหน้าบัญชีเฉพาะstudent; หน้าสำหรับstaffแสดงข้อความให้กลับบัญชีและไม่มีform Backendเป็นผู้บังคับสิทธิ์จริง
- Client validationตรงBackendเรื่องASCII trim/255Unicode code points/optionaldescription/NUL-invalid Unicode ไม่มีชื่อUniqueหรือdescription max lengthเพิ่ม
- ระหว่างsubmitdisableformและกันsubmitซ้ำด้วยpending ref; POSTใช้sessioncookie+CSRFจากLogin ไม่ส่งactor/user_id/role
- Network/500/404ผิดcontractจากGETไม่แสดงเป็นno-team; POST409หรือไม่ทราบผลมีปุ่มตรวจทีมผ่านGET ไม่มีautomatic POST retry ไม่สัญญาidempotency

## ไฟล์หลัก

| File | หน้าที่ |
|---|---|
| backend/team_api.py, team_store.py | GET model/routeและsingle-query membership filter ใช้app role/grantsเดิม |
| backend/main.py | no-store/validation/storage handlerครอบTeam rootและsubpaths |
| backend/tests/test_team_api.py | เพิ่มGET/own-member-role/privacy/session/no-renewal/storage/IDs cases |
| backend/tests/team_api_direct_smoke.py | เพิ่มอ่าน404ก่อนสร้างและอ่าน200หลังสร้างบนdirect app connection |
| frontend/src/app/teams/page.tsx | Routeของหน้าสร้าง/ดูทีมตนเอง |
| frontend/src/features/teams/ | POST/GET client, form, current-team hook, screenและstyles |
| frontend/src/features/auth/account-screen.tsx | ลิงก์ทีมของฉันสำหรับstudent ใช้Authเดิม |
| frontend/tests/teams.spec.ts | Browser testsจริงกับrollback fixture8001 |

ไม่มีmigration/SQL/RBAC/role/password/.env changes ไม่มีAPIเพิ่มสมาชิก/Project/Team listหรือการจัดการTeamเต็มรูปแบบ ไม่Commit/Pushใหม่

## ผลตรวจ

| ชุด | ผล |
|---|---|
| Backend + boundary | PASS111 = Auth65 + Team37 + offline connection boundary9 |
| Team37 | Create27เดิม + repository read2 + GET8; บางtestมีsubcases ไม่ใช่37unique requirements |
| GET coverage | 404ไม่มีทีม, leader/memberroleจริง, เฉพาะmembershipของตน, spoofedquery/headerใช้เลือกทีมอื่นไม่ได้, missing/invalid/expired/revoked session401, staff403, storage500, no-cookie/no-renewal, BIGINTstrings |
| Direct app ASGI | PASSใช้session_user=current_user=project_app ไม่สลับowner สร้างผ่านAuth→TeamและGET404→200 ข้อมูลจำลองROLLBACK |
| Frontend | ESLint/TypeScript/production build PASS มีroute /teams |
| Browser | PASS13 = Auth5เดิม + Team8 ใหม่ ใช้Microsoft Edge/Playwright1.65.0 กับFastAPI/PostgreSQLจริง |
| Browser cleanup | PASS metadata/ACL/rowcountsคืนก่อนชุดทดสอบ fixture_connections=0; identity sequencesไม่รวมในการcompare |
| ภาพ | ตรวจDesktop formและMobile current-teamแล้ว Form/ข้อความครบและไม่ล้นแนวนอนที่390×844 ภาพอยู่ในignored test-results |
| Normal servers (read-only) | เปิดFrontend3000/Backend8000แล้ว Browserเข้า/teamsโดยไม่มีsessionไป/login?reason=session เรียกเฉพาะGETไป8000; OpenAPIมีGET/POST Team, GETทีมไม่มีsession401/no-store, Swagger200 ไม่ทดสอบsuccessful writeบนnormal server |

Browser Team8ครอบคลุมcreate/normalize/requestfields+CSRF, refreshคืนข้อมูลโดยไม่client storage, clientvalidation/Unicode255/optionaldescription, busy-submitครั้งเดียว, 409แล้วอ่านทีมเดิม, serverรับPOSTแล้วresponseหายแต่GETกู้ข้อมูลได้โดยไม่POSTซ้ำ, GETnetwork/generic404ไม่เป็นemptyform, session/CSRF loss และmobilelayout

Positive flowsใช้APIจริง ส่วนfailure testsจำลองnetwork/responseด้วยPlaywright routes การทดสอบlost responseอยู่ในouterrollback fixture ไม่ใช่successful runtime data COMMIT หรือreal multi-session concurrency

Snapshotตรวจinstalled baseline52functions/โครงสร้าง/ACLและrowcountsก่อน-หลัง ทุกdata writeอยู่ในtransaction/ROLLBACK ไม่เหลือบัญชี/session/teamจำลอง และไม่เชื่อมฐานข้อมูลหลัก

## คำสั่งทดสอบ

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api database.tests.test_test_database -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_api_direct_smoke
cd frontend
npm run lint -- --no-cache
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
npm run test:e2e
```

Browser suiteต้องให้ports3000/8001ว่าง runnerเปิดprocessของตัวเองและใช้API8001เฉพาะtests ส่วนnormal Frontend3000ใช้Backend8000 ทุกwriteในการทดสอบต้องผ่านrollback fixture ไม่ใช้normal serverแทน

## ขอบเขตความคืบหน้า

มีimplementationสำหรับST-02ตามscopeสร้างทีมพร้อมผู้สร้างเป็นหัวหน้า และหน้าดูข้อมูลทีมของตนเบื้องต้น ไม่ใช่ST-03Team Managementเต็มรูปแบบ ไม่ใช่ST-01Dashboard และยังไม่มีProject/member management/Concurrencyจริง/fresh installเครื่องทีม/UATทั้งระบบ

P15 Not Started→In Progress; checklistยังDone4/20=20% เพราะยังไม่มีงานหลักทั้งแถวปิดเพิ่ม ไม่เปลี่ยนตัวหารหรือคิดว่า13Browser testsหมายถึงระบบเสร็จทั้งหมด
