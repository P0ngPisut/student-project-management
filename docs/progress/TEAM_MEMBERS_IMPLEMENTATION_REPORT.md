# Team members implementation — 2026-11-07

สถานะ: **เพิ่มสมาชิกด้วยอีเมลและอ่านรายชื่อทีมตนเอง เชื่อมBackend/Frontend/PostgreSQLแล้ว**

รายงานประวัติรอบMembers: ผล129/21และbaselineที่ระบุด้านล่างเป็นผลในรอบนั้น ต่อมาพัฒนาProject create/currentแล้ว ดู [Project Report](PROJECT_IMPLEMENTATION_REPORT.md) สำหรับหลักฐานล่าสุด ไม่ใช้รายการProjectที่ยังไม่ทำในประวัติแทนสถานะปัจจุบัน

ผู้ใช้ยืนยัน [Team Members Contract](../api/TEAM_MEMBERS_CONTRACT.md) ว่าหัวหน้ากรอกอีเมลตรงตัว เพิ่มเป็นmemberทันทีโดยไม่ต้องตอบรับ ไม่มีuser directoryหรือส่งอีเมลจริง

## พฤติกรรมและไฟล์ที่เปลี่ยน

| ไฟล์ | การเปลี่ยน |
|---|---|
| [team_api.py](../../backend/team_api.py) | GET/POST /api/v1/teams/me/members, strict email-only input, session/student/CSRF/Origin, public member DTOและerror contract |
| [team_store.py](../../backend/team_store.py) | อ่านรายชื่อด้วยsingle queryที่กรองสมาชิกภาพactor; เพิ่มmemberผ่านapp role/team→project locks/ตรวจleaderซ้ำ/phase/deferred checks |
| [test_team_members_api.py](../../backend/tests/test_team_members_api.py) | เพิ่ม18testsกับinstalledV1จริง รวมphaseของAdvisor/Committeeและnegative cases |
| [test_auth_security.py](../../backend/tests/test_auth_security.py) | ตรวจOpenAPIรวมmember endpoints โดยไม่เชื่อมDB |
| [test_auth_api.py](../../backend/tests/test_auth_api.py) | แก้assertionจำนวนsessionsจาก1ตายตัวเป็นbaseline+1 เพื่อไม่สมมติว่าDBว่าง ไม่เปลี่ยนAuth behavior |
| [team_api_direct_smoke.py](../../backend/tests/team_api_direct_smoke.py) | เพิ่มdirect app add/list/duplicate member พร้อมROLLBACK |
| [teams/api.ts](../../frontend/src/features/teams/api.ts) | member DTO, GET/POST client,ตรวจresponse/IDsstringsและfixed error messages |
| [member-add-form.tsx](../../frontend/src/features/teams/member-add-form.tsx) | ฟอร์มemailสำหรับleader, pending guard/abort/CSRF/validation/error,ตรวจผลด้วยGETเมื่อPOSTไม่ทราบผล |
| [team-members.tsx](../../frontend/src/features/teams/team-members.tsx) | รายชื่อชื่อ/บทบาท/ตนเอง, loading/error/retry,ไม่แสดงformก่อนตรวจรายชื่อ,ใช้roleของactorจากรายการ |
| [team-screen.tsx](../../frontend/src/features/teams/team-screen.tsx), [styles](../../frontend/src/features/teams/teams.module.css) | ต่อส่วนสมาชิกเข้าหน้า/teams; reset stateเมื่อactor/teamเปลี่ยน, layoutตามAuthเดิม |
| [team-members.spec.ts](../../frontend/tests/team-members.spec.ts) | Browser8testsกับrollback-onlyAPI8001 |
| README/Contracts/Reference/Backlog | อัปเดตสถานะและหลักฐานแยกจากผลประวัติรอบก่อน |

GETเดิม /teams/meยังคืนเฉพาะmembershipตนเองตามContractเดิม endpointใหม่อ่านสมาชิกทั้งหมดของทีมตนด้วยmembership authorizationและprojectionในSQLstatementเดียว เรียงleaderก่อนmember แล้วชื่อASC/idASC ไม่คืนemail/hash/session/ข้อมูลทีมอื่น

POSTเลือกทีมจากactive actor ไม่รับteam_id/user_id/roleเป็นfields ตรวจleaderอีกครั้งหลังรอteam lock ล็อกProjectก่อนตรวจphase หากไม่มีProjectก็เพิ่มได้ เป้าหมายต้องมีusers.role=studentและยังไม่มีteam_members แปลงเฉพาะmembership UNIQUE23505เป็น409 ไม่ตีความP0001/42501ทั้งหมดเป็นbusiness error

## ผลทดสอบ

| ชุด | ผล / ขอบเขต |
|---|---|
| Backendรวม | PASS129 = Auth65 + Teamcreate/current37 + member18 + connection boundary9 |
| Member18 | เพิ่มด้วยemailnormalize/IDsstrings/publicfields, ordering+tie, memberอ่านได้แต่เพิ่มไม่ได้, scope/spoof, invalid/missing/expired/revoked session, staff/no-team, GETnoCSRF/noTTLrenew, POSTOrigin/CSRF, validation, target404/409, stale-precheckUNIQUE, recheckauthority, rollbackหลังINSERT, phase |
| Phaseจากข้อมูลจริง | ไม่มีProject/ก่อนsubmissionผ่าน; pending_reviewปฏิเสธ; advisor revisionผ่าน; advisor approvedปฏิเสธ; committee votesยังไม่ครบปฏิเสธ; summary revisionผ่าน; summary approvedปฏิเสธ; ส่งรอบใหม่แล้วปฏิเสธ มีdirect trigger rejectionด้วย |
| Direct app ASGI smoke | PASS Auth→Team→เพิ่มmember→รายชื่อ→เพิ่มซ้ำ409; session_user=current_user=project_app ไม่มีowner switchในrequest connection |
| Frontend | ESLint/TypeScript/production build PASS |
| Browser | PASS21 = Auth5 + Teamcreate/current8 + member8, Microsoft Edge/Playwright |
| Member Browser8 | add/refresh/privacy, memberreadonly+forgedPOST403, target/validation errors, pending submitครั้งเดียว, responseหายแล้วGETกู้ผลไม่POSTซ้ำ, GETfailureไม่เป็นempty/form, CSRF/sessionloss, Mobile |
| Cleanup | metadata/ACL/rowcountsก่อน-หลังตรงกัน fixture_connections=0 ไม่เทียบidentity sequence values |
| ภาพ | ตรวจDesktop/Mobileสมาชิกและformแล้ว ไม่ล้นแนวนอนที่390×844; artifactsอยู่ในignored test-results |
| Normal servers | เปิดFrontend3000/Backend8000กลับแล้ว ตรวจread-only: OpenAPIมีGET/POST members, GETไม่มีsession401/no-store; Browser /teamsเรียกเฉพาะGETไป8000แล้วredirectLogin ไม่มีdata writes |
| Final QA | document links107จุดผ่าน, Backlog20IDs/4Doneตรงสูตร, Python syntax/secret scan/Git diff whitespaceผ่าน SQL V1/Authทั้ง4ไฟล์byte-identicalกับHEADและreview migrationchecksumคงเดิม |

Positive flowsใช้FastAPI/PostgreSQLจริง ส่วนfailure injectionใช้patch/Playwrightroutesตามกรณี ชุดBrowserรอบแรกพบselectorชนNext route announcer แก้selectorให้scopeในregionสมาชิกแล้วรันครบใหม่ผ่าน21/21 ไม่เปลี่ยนพฤติกรรมแอปเพื่อให้testsผ่าน

ก่อนรอบนี้DBมีusers/credentials/sessions/teams/team_membersอย่างละ1แถวจากข้อมูลเดิม ชุดทดสอบเก็บข้อมูลเหล่านั้นไว้ ไม่ลบทิ้งเพื่อทำให้testsผ่าน ทุกfixtureใหม่อยู่ในTransaction/ROLLBACK รายงานก่อนหน้าที่กล่าว0แถวเป็นbaselineในรอบก่อน ไม่ใช่baselineรอบนี้

ไม่แก้SQL V1/Auth/migration/RBAC/roles/.env/backend.database.py/Business Rules ไม่เข้าถึงDBหลัก และไม่มีGit Commit/Push

## คำสั่งตรวจรับจากroot

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api backend.tests.test_team_members_api database.tests.test_test_database -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_api_direct_smoke
cd frontend
npm run lint -- --no-cache
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
npm run test:e2e
```

Browser suiteต้องให้ports3000/8001ว่าง และใช้fixture8001เท่านั้น ไม่ใช้normal8000ทำsuccessful data POSTเพื่อทดสอบ เพราะnormal runtimeบันทึกข้อมูลเมื่อtransactionสำเร็จ

## งานคงค้าง

- ยังไม่มีremove/leave/transfer leader/Team metadata UI และProject API/UI
- Formไม่รู้phaseล่วงหน้าจากGETเดิม จึงให้BackendตรวจC-07ทุกPOSTและแสดง409เมื่อถูกล็อก ไม่เพิ่มphasefieldเข้าContractเอง
- ยังไม่ใช่real multi-session concurrency, successful runtime data COMMIT, fresh installเครื่องทีม หรือUATทั้งระบบ แผนshared fixturesยังต้องจัดการตามขอบเขตROLLBACK
- P09/P15/P16/P17ยังIn Progress มีimplementationST-02และบางส่วนST-03 ไม่ใช่ทั้ง9หน้าจอเสร็จ Checklist Done4/20=20%เท่าเดิม
- ขั้นถัดไปที่เสนอ: ยืนยันProject create Contract/ACตามC-01/R-01ก่อนพัฒนา
