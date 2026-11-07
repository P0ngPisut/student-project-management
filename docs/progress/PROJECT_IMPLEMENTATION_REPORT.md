# Project create/current implementation — 2026-11-07

สถานะ: **หัวหน้าสร้างProjectและสมาชิกอ่านProjectทีมตนผ่านAPI/หน้า /projects แล้ว**

รายงานประวัติรอบProject: ผล150/30และroleboundary/baselineด้านล่างเป็นผลในรอบนั้น ต่อมาพัฒนาAdvisor invitationsแล้ว ดู [รายงานล่าสุด](ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md) สำหรับผล174/42และexplicitowner Browserfixtures ไม่ใช้รายการinvitationที่ยังไม่ทำในประวัติแทนสถานะปัจจุบัน

ผู้ใช้ยืนยัน [Project Contract](../api/PROJECT_CREATE_CONTRACT.md) รวมPOST name/description, GETทีมตน, IDsstrings, หน้า/projectsและลิงก์จาก/teams ไม่มีProject delete/updateหรือworkflowคำเชิญ/ส่งหัวข้อในรอบนี้

## การเปลี่ยนแปลงและไฟล์หลัก

| ไฟล์ | หน้าที่ |
|---|---|
| [project_api.py](../../backend/project_api.py) | GET /api/v1/projects/me และPOST /api/v1/projects, strict input/public response, session/student/Origin/CSRF และsanitized errors |
| [project_store.py](../../backend/project_store.py) | project_app/test DB UOW, actorGUC/Teamlock/recheckleader/INSERT/forcedTeamchecks, currentProjectที่กรองด้วยmembershipในstatementเดียว |
| [main.py](../../backend/main.py) | ต่อProject router, validation/storage handlersและno-storeทุกProject response |
| [test_project_api.py](../../backend/tests/test_project_api.py) | Project21HTTP/PostgreSQL testsบนinstalledV1พร้อมROLLBACK |
| [test_auth_security.py](../../backend/tests/test_auth_security.py) | OpenAPIรวมProjectและไม่เชื่อมDBตอนimport |
| [team_api_direct_smoke.py](../../backend/tests/team_api_direct_smoke.py) | เพิ่มdirect project_app GET404→POST201→GET200→duplicate409 โดยไม่มีowner switch |
| [auth_browser_server.py](../../backend/tests/auth_browser_server.py) | เพิ่มProject UOW overrideลงconnection/RLock/outerROLLBACKเดียวกับAuth/Team ป้องกันtestPOSTหลุดไปnormal runtime |
| [features/projects](../../frontend/src/features/projects/project-screen.tsx) | API client, currentProject hook, createform, screen/stylesแยกFeature-based |
| [projects/page.tsx](../../frontend/src/app/projects/page.tsx) | Route /projects |
| [team-screen.tsx](../../frontend/src/features/teams/team-screen.tsx), [Team styles](../../frontend/src/features/teams/teams.module.css) | เพิ่มลิงก์โครงงานของทีมโดยไม่เปลี่ยนTeam contract |
| [projects.spec.ts](../../frontend/tests/projects.spec.ts) | Browser9testsกับAPI/PostgreSQLจริงในfixture8001 |
| README/Contracts/Reference/Backlog | อัปเดตหลักฐานปัจจุบันแยกจากผลรอบก่อน |

POSTเลือกTeamและcreated_byจากactive actor ไม่รับidentity/role/statusจากclient ตรวจleaderซ้ำหลังTeamlockก่อนINSERT ใช้UNIQUE projects.team_idเป็นด่านสุดท้าย แปลง23505เฉพาะpublic.projects/projects_team_id_keyเป็น409; P0001/42501หรือUNIQUEอื่นไม่แปลงเป็นbusiness errorทั้งหมด

Project CHECK/UNIQUE/FK/BEFORE guardsเป็นimmediate บังคับTeam deferred cardinality checksก่อนคืนผล และให้UOWจบสำเร็จก่อนตอบ201 GETใช้LEFT JOIN membership→projectsในstatementเดียวเพื่อแยกTEAM_NOT_FOUNDจากPROJECT_NOT_FOUNDและไม่อ่านProjectคนอื่น

Frontendอ่านTeamจากAPIเดิมและProjectจากGETใหม่ ตรวจteam_idให้ตรงก่อนแสดง เก็บstateตามactor/Team ไม่ใช้localStorage/sessionStorageกับProject/session Formให้เฉพาะหัวหน้า สมาชิกเห็นรอหัวหน้าหรืออ่านข้อมูล ไม่มีปุ่มลบ/แก้ไข/เชิญ/ส่งไฟล์และไม่เพิ่มphase/statuscolumnเอง

## ผลทดสอบ

| ชุด | ผล / ขอบเขต |
|---|---|
| Backendรวม | PASS150 = Auth65 + Team37 + member18 + Project21 + connection boundary9 |
| Project21 | normalize/optionaldescription/Unicode255/noaddedlimits, strictvalidation/JSON/identityspoof, session/expiry/revocation/staff/no-team/memberauthorization, GETnoCSRF/noTTLrenew, scope, UNIQUEconflict, same-nameคนละTeam, leaderrecheck, storage/transactionrollback, BIGINTstrings, identityimmutable/R-01และHTTPnoDELETE |
| R-01 | app directDELETE42501จากprivilege; ownerDELETEในsavepointยังถูกv1_project_guardปฏิเสธ42501กับProjectที่ยังไม่มีลูก ไม่ให้grantsเพิ่มและไม่ใช้ownerสร้างProjectแทนapp |
| Relationship guard | การINSERTcreated_byไม่ตรงactorถูกguardปฏิเสธP0001ก่อนถึงFK; การUPDATEteam_id/created_byโดยownerในsavepointถูกปฏิเสธP0001 ไม่อ้างว่าเป็น23503จากFKโดยตรง |
| Direct app ASGI | PASS Auth→Team→member→Project ใช้session_user=current_user=project_appโดยไม่สลับroleในconnectionคำขอ baselineหลังROLLBACKตรงก่อนชุด |
| Frontend | ESLint/TypeScript/production build PASS มีroute/projects |
| Browser | PASS30 = Auth5 + Teamcreate/current8 + member8 + Project9 |
| Project Browser9 | Teamnavigation/create/refresh, noTeam/memberรอ/อ่านได้, validation/optionaldescription, stale409, responseหายแล้วGETกู้ผลไม่POSTซ้ำ, GETnetwork/generic404/malformed200ไม่เป็นform, pendingsubmitครั้งเดียว, CSRF/sessionloss, Mobile |
| Cleanup | metadata/ACL/rowcountsคืนbaseline fixture_connections=0 ไม่เทียบค่าidentity sequences |
| ภาพ | ตรวจDesktopformและMobileProjectcardแล้ว อ่านครบและไม่ล้นแนวนอนที่390×844; screenshotsอยู่ในignored test-results |
| Normal servers | เปิดFrontend3000/Backend8000กลับแล้ว ตรวจread-only: OpenAPI10pathsมีPOST/GETProjectและไม่มีDELETE, GETไม่มีsession401/no-store; Browser/projectsเรียกเฉพาะGETไป8000แล้วredirectLogin ไม่มีdata writes |
| Final QA | document links148จุดผ่าน Backlog20IDs/4Doneตรงสูตร Python syntax/secret scan/Git diff whitespaceผ่าน SQL V1/Authทั้ง4ไฟล์byte-identicalกับHEADและreview migrationchecksumคงเดิม ไม่มีstaged changes |

Positive flowsใช้FastAPI/PostgreSQLจริง Failure injectionใช้patch/Playwrightroutesตามกรณี TestClient/direct smokeเป็นASGIin-process ส่วนBrowserใช้TCPfixture8001 ทุกsuccessdatawriteอยู่ในouterTransaction/ROLLBACK ไม่ใช่successful normal runtime data COMMITหรือreal multi-session concurrency

baselineรอบนี้มีusers/credentialsอย่างละ2, sessions1, teams1, team_members2 และprojects0 MetadataSHA256ยัง3f10239c8cc40fcd408ad73a7c914f31b556096921f4c495f865c699d7760544 เก็บข้อมูลเดิมเหล่านี้ไว้ครบ ไม่มีProject/บัญชี/ทีมจำลองใหม่ค้าง ไม่สมมติว่าDBว่าง

ไม่แก้SQL V1/Auth/migration/RBAC/roles/.env/backend.database.py/Requirements ไม่เชื่อมDBหลักและไม่มีCommit/Push

## คำสั่งทดสอบจากroot

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api backend.tests.test_team_members_api backend.tests.test_project_api database.tests.test_test_database -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_api_direct_smoke
cd frontend
npm run lint -- --no-cache
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
npm run test:e2e
```

Browserต้องให้ports3000/8001ว่าง runnerเปิดfixtureของตัวเอง NormalFrontend3000ใช้API8000 อย่าใช้normalserverเพื่อทดสอบsuccessful writesแทนROLLBACK fixture

## งานคงค้าง

- Project metadata update, Advisor invitation, submission/fileและหน้ารายละเอียดST-05เต็มworkflowยังไม่ทำ
- ยังไม่มีออก/ถอดสมาชิก/โอนหัวหน้าUI, Dashboard, staffProjectAPI/UI
- ยังไม่real multi-session concurrency/fresh installเครื่องทีม/HTTPS-LAN/UATทั้งระบบ
- มีimplementationST-02/ST-04และบางส่วนST-03/ST-05 ไม่ใช่4หน้าผ่านACทั้งหมด P09/P15/P16/P17ยังIn Progress; Done4/20=20%เท่าเดิม
- ขั้นถัดไปที่เสนอ: ยืนยันAdvisor invitation Contract/ACก่อนพัฒนา ไม่เพิ่มขั้นตอบรับหรือnavigationเอง
