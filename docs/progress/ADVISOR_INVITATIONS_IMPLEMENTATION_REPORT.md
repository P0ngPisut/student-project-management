# Advisor invitations implementation — 2026-11-07

สถานะ: **ครบส่ง/อ่านประวัติ/ยกเลิกฝั่งทีม และอ่าน/ตอบรับ/ปฏิเสธฝั่งอาจารย์ตามContractที่ยืนยัน**

รายงานนี้เป็นหลักฐานรอบInvitationซึ่งยังไม่มีadvisorถาวร ต่อมาผู้ใช้อนุมัติสร้างหนึ่งบัญชีและตรวจLoginแล้ว ดู [ผลprovisioningล่าสุด](../database/ADVISOR_ACCOUNT_PROVISIONING.md) ไม่ใช้baselineusers2หรือข้อความยังต้องเตรียมบัญชีด้านล่างแทนสถานะข้อมูลปัจจุบัน

ผู้ใช้เลือกselectรายชื่ออาจารย์และอนุมัติครบworkflowตาม [Contract](../api/ADVISOR_INVITATIONS_CONTRACT.md) ไม่สร้างบัญชีอาจารย์ถาวร ไม่ส่งอีเมลจริง และไม่เพิ่มuser directoryทั่วไป

## ไฟล์และพฤติกรรม

| ไฟล์ | การเปลี่ยน |
|---|---|
| [invitation_api.py](../../backend/invitation_api.py) | 6operations/5paths, strict positiveBIGINTstrings/decision, session/role/CSRF/Origin, DTOแยกทีม/อาจารย์และsanitizederrors |
| [invitation_store.py](../../backend/invitation_store.py) | scopedcandidates/history, Team→Projectlocks/recheckactor-state, INSERTpendingและv1_resolve_invitationตามgrantsเดิม ไม่มีdirectUPDATE/DELETE |
| [main.py](../../backend/main.py) | ต่อrouter/validation/no-storeรวมProject invitation subpathsและadvisor inbox |
| [test_invitation_api.py](../../backend/tests/test_invitation_api.py) | 24testsใช้PostgreSQLจริงบนinstalledV1 ทุกfixtureROLLBACK |
| [test_auth_security.py](../../backend/tests/test_auth_security.py) | OpenAPI15pathsและimportไม่เชื่อมDB |
| [team_api_direct_smoke.py](../../backend/tests/team_api_direct_smoke.py) | direct-app candidates/history/targetrole/inboxrole boundary เพิ่มจากAuth→Team→member→Projectเดิม |
| [auth_browser_server.py](../../backend/tests/auth_browser_server.py) | InvitationUOWในRLock/outerROLLBACK และexplicit owner-fixture modeเตรียมadvisor2/coordinator1ก่อนserveคำขอapp |
| [Playwright config](../../frontend/playwright.config.ts), [runner](../../frontend/tests/run-auth-e2e.mjs) | เปิดfixturemodeเฉพาะtest process ใช้unique fixturetagร่วมกับBrowserและbackend ไม่เก็บfixtureถาวร |
| [features/advisor-invitations](../../frontend/src/features/advisor-invitations/invitation-screen.tsx) | APIclient/DTOvalidation/history/select/actions/rolepages/styles,เวลาตามAsia/Bangkok, pendingguard/abort/retry |
| [team invitation route](../../frontend/src/app/projects/advisor-invitations/page.tsx), [advisor inbox route](../../frontend/src/app/advisor/invitations/page.tsx) | หน้า/projects/advisor-invitations และ/advisor/invitations |
| [Project screen](../../frontend/src/features/projects/project-screen.tsx), [Project styles](../../frontend/src/features/projects/projects.module.css) | ลิงก์คำเชิญเมื่อมีProjectแล้ว ไม่เปลี่ยนProjectresponse |
| [Account screen](../../frontend/src/features/auth/account-screen.tsx) | ลิงก์inboxเฉพาะadvisor ไม่เปิดให้coordinator/เพิ่มroleใหม่ |
| [invitations.spec.ts](../../frontend/tests/invitations.spec.ts) | Browser12testsกับAPI/PostgreSQLจริงและfailure injectionตามกรณี |
| README/Contracts/Reference/Backlog | อัปเดตผลล่าสุดและแยกจากประวัติรอบก่อน |

ฝั่งทีมอ่านประวัติของProjectที่ตนยังเป็นสมาชิกเท่านั้น เฉพาะหัวหน้าปัจจุบันอ่านcandidates/ส่ง/ยกเลิกได้ ไม่อาศัยsent_byเก่าเพื่อให้สิทธิ์ยกเลิก อาจารย์เห็นคำเชิญadvisor_idตนเท่านั้น pending/acceptedมีminimalProjectcontext ส่วนrejected/cancelledเลือกNULLแทนliveชื่อProject/ทีม/คำอธิบายในSQL และไม่คืนProject/TeamIDs/สมาชิก/ไฟล์/email

การเขียนล็อกTeam→Projectแล้วตรวจactor/stateใหม่ก่อนINSERTหรือcontrolledresolve ฟังก์ชันV1เป็นผู้ล็อกแถวคำเชิญและบันทึกresolved_by/at ไม่ให้app directUPDATEเพิ่ม หลังacceptedไม่ส่งใหม่/เปลี่ยนอาจารย์ หลังสิ้นสุดไม่resolveซ้ำ แปลง23505เฉพาะuq_invitations_active_projectเป็นINVITATION_CONFLICT ไม่แปลงP0001/42501หรือUNIQUEอื่นทั้งหมดเป็นbusinesserror

## ผลทดสอบ

| ชุด | ผล / ขอบเขต |
|---|---|
| Backendรวม | PASS174 = Auth65 + Team37 + member18 + Project21 + invitation24 + boundary9 |
| Invitation24 | candidateprojection/sort, emptyhistory, sent_by/pending, accept/reject/cancelและtriggerเวลา, privacyหลังfinalstate, pending/acceptedconflicts, memberreadonly, currentleaderหลังtransfer, exitedmemberlostaccess, otheradvisor/team404, identityspoof, roles/missingresource, targetrole, auth/expiry/revocation, GETnoCSRF/noTTLrenew, POSTOrigin/CSRF, strictinput, actualUNIQUEconflict, recheckafterlock, rollback/storage/completionfail, immutable/finalguard |
| Direct app ASGI smoke | PASS directLOGINsession_user=current_user=project_app สำหรับAuth→Team→member→Projectและinvitationcandidates/history/targetnotadvisor404/inboxwrongrole403 พร้อมROLLBACK ยังไม่ใช่directLOGINappที่ส่งและresolveสำเร็จครบworkflow |
| Frontend | ESLint/TypeScript/production build PASS มีสองrouteคำเชิญ |
| Browser | PASS42 = Auth5 + Team8 + member8 + Project9 + invitation12 |
| InvitationBrowser12 | select→send→advisoraccept→teamrefresh, reject/hidecontext/reinvite, cancel/hidecontext, memberreadonly, otheradvisor/rolepages, nocandidateUI/network, historynetwork/malformedresponse, lostsendresponseGETrecovery, send/respondpendingguard, stale409, CSRF/sessionloss, Mobile |
| Cleanup | metadata/ACL/rowcountsก่อน-หลังตรงกัน fixture_connections=0 ไม่รวมค่าidentitysequenceที่ROLLBACKไม่คืน |
| ภาพ | ตรวจDesktop acceptedhistoryและMobileteam/advisorhistoryแล้ว ไม่ล้นแนวนอนที่390×844 ภาพอยู่ในignoredtest-results |
| Normal servers | เปิดFrontend3000/Backend8000กลับแล้ว OpenAPI15paths/คำเชิญ6operationsตรงContract GETทั้ง3รายการเมื่อไม่มีsession401/no-store Browserสองหน้าคำเชิญเรียกเฉพาะGETไป8000แล้วredirectLogin ไม่มีdatawrites |
| Final QA | document links175จุดผ่าน Backlog20IDs/Done5ตรงสูตร Python syntax/secret scan/Git diff whitespaceผ่าน SQL V1/Auth4ไฟล์byte-identicalกับHEAD และrepairmigrationchecksumคงเดิม ไม่มีstaged changes |

PositiveflowsเรียกFastAPI/PostgreSQLจริง กรณีไม่มีcandidateจำลองresponse[]เฉพาะUIเพราะfixtureมีadvisorอยู่ ส่วนBackendempty-historyและcandidateprojectionใช้ข้อมูลจริง Failureinjectionใช้patch/Playwrightroutes ไม่ใช้ผลmockเป็นหลักฐานDBสำเร็จ

## ขอบเขตroleของBrowser fixture

Runtimeปกติยังเชื่อมด้วยproject_appผ่านAUTH_*เท่านั้น ไม่มีadmin fallback เมื่อLogin/DBล้มเหลว

Browserรอบนี้ต้องใช้บัญชีadvisorที่มีcredentialsโดยไม่COMMITfixture จึงเปิดexplicitSPMS_INVITATION_BROWSER_FIXTURES=1เฉพาะtest process: เชื่อมprivatefixtureconfigไปtestDB เปิดoutertransaction แล้วSET LOCAL ROLE project_owner ซึ่งตรวจว่าไม่ใช่superuserก่อนINSERTusers/credentialhash จากนั้นSET LOCAL ROLE project_appและassert_auth_connectionก่อนเริ่มHTTPserver ทุกrequestยืมconnectionนี้ผ่านRLock/savepoint ไม่มีowner/superuser operationเพื่อข้ามคำขอที่ถูกปฏิเสธ ไม่มีtest-onlyprovisioningHTTPendpoint

ดังนั้นBrowserพิสูจน์ **effective project_app** บนsessionที่เริ่มด้วยfixturecredentials ไม่อ้างว่าBrowserทั้งหมดเป็นdirectLOGINproject_app ส่วนdirectappconnectionมีsmokeแยกตามตารางข้างต้น เมื่อจบทุกบัญชี/credential/session/team/Project/invitationfixtureใหม่ROLLBACK ไม่มีgrants/Schema changes

Baselineรอบนี้มีusers2/credentials2/sessions1/teams1/team_members2/projects1/advisor_invitations0 และตารางธุรกิจอื่น0 เก็บข้อมูลเดิมไว้ครบ MetadataSHA256=3f10239c8cc40fcd408ad73a7c914f31b556096921f4c495f865c699d7760544 ไม่สมมติว่าDBว่าง

## วิธีทดสอบจากroot

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api backend.tests.test_team_members_api backend.tests.test_project_api backend.tests.test_invitation_api database.tests.test_test_database -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_api_direct_smoke
cd frontend
npm run lint -- --no-cache
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
npm run test:e2e
```

Browserต้องให้ports3000/8001ว่าง ใช้runnerเพื่อได้uniquetag ไม่เรียกPlaywrightตรงๆสำหรับsuiteนี้ NormalFrontend3000ยังใช้Backend8000 อย่าใช้normalserverทำsuccessfuldatawritesแทนROLLBACK tests

## สถานะและงานคงค้าง

- P10DoneเฉพาะworkflowตามContractที่ยืนยัน: API/UIส่ง/อ่าน/ยกเลิก/รับ/ปฏิเสธและimmutableหลังสิ้นสุดมีหลักฐานครบตามเกณฑ์แถวเดิม ไม่ใช่การปิดsecurity/UAT/Concurrencyทั้งระบบ
- ChecklistหลักDone5/20=25% P08/provisioningยังInProgress P18/ConcurrencyยังBlockedเรื่องsharedfixture/COMMITscope
- บนnormalserverยังต้องให้ผู้ดูแลเตรียมบัญชีadvisorพร้อมcredentialsก่อนเชิญและLoginจริง รอบนี้ไม่สร้างบัญชีถาวร/เครื่องมือprovisioning
- ตรวจสดแบบread-onlyด้วยdirectproject_appหลังทดสอบ: usersมีstudent2คนและadvisor0/coordinator0 ยืนยันว่าบัญชีstafffixtureไม่ค้างในฐานข้อมูล
- ยังไม่real multi-session concurrency, successful runtime dataCOMMIT, fresh installเครื่องทีม, HTTPS/LAN, rate-limit/UATหรือsubmission/upload
- ขั้นถัดไปที่เสนอ: ยืนยันวิธีเตรียมบัญชีอาจารย์ในtestDBสำหรับใช้งานทีม ก่อนเริ่มsubmissionContract ไม่เพิ่มบัญชีถาวรเอง

ไม่แก้SQL V1/Auth/migration/RBAC/roles/.env/backend.database.py/Requirements ไม่เข้าถึงDBหลัก และไม่Commit/Push
