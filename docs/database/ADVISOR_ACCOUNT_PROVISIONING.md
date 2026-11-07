# เตรียมบัญชีอาจารย์ — test database only

วันที่2026-11-07 · สถานะ: **CLIพร้อม และบันทึกadvisorใหม่1บัญชีในtestDBตามอนุมัติแล้ว** ค่าเริ่มต้นของเครื่องมือยังคงDRY_RUN/ROLLBACK

ใช้ [Auth_Provision_Advisor.py](../../database/tools/Auth_Provision_Advisor.py) สำหรับผู้ดูแลสร้างusers.role=advisorใหม่พร้อมauth.credentialsแบบatomic ไม่ใช่publicsignup/BackendAPI ไม่เปลี่ยนSchema/RBAC/roleของPostgreSQLหรือบัญชีเดิม

## ขอบเขตที่รองรับ

- ต่อเฉพาะstudent_project_management_v1_testผ่านTest_Database helper; ignoreDB_NAMEและไม่เปิดฐานข้อมูลหลัก
- การINSERTทำด้วยeffectiveproject_ownerที่ตรวจว่าไม่ใช่superuserและownerของusers/credentials; project_appไม่มีสิทธิ์ใช้เครื่องมือนี้สร้างบัญชี
- ชื่อ/email/passwordใช้กฎAuthเดิม อีเมลจำลองรูปแบบถูกต้องเช่นadvisor01@example.testได้ ไม่ตรวจกล่องรับจริง/ส่งอีเมล
- Passwordอย่างน้อย8ตัว มีA–Zและ0–9อย่างละ1 ไม่trim/เปลี่ยนpassword ใช้Argon2idจากAuthhelperเดิม
- ค่าเริ่มต้นเป็นDRY_RUN/ROLLBACK การบันทึกถาวรต้องเลือก--applyพร้อมconfirmชื่อtestDBและอยู่ในขอบเขตที่ผู้ใช้อนุมัติ
- ปฏิเสธemailที่มีusersอยู่แล้วทุกrole ไม่activatecredentialsของบัญชีเก่า/เปลี่ยนrole/resetpassword/upsertเอง ถ้าต้องเปิดบัญชีเก่าให้ยืนยันกระบวนการแยก
- ยังไม่รองรับสร้างcoordinator, batchimport, resetpassword หรือการเลือกroleจากclient

## เตรียมก่อนรัน

ใช้VS CodeTerminal/PowerShellจากrootRepositoryและPythonvenvเดิม เครื่องผู้ดูแลต้องมีprivateDB_HOST/DB_PORT/DB_USER/DB_PASSWORDที่ใช้SET ROLE project_ownerได้ในbackend/.env ไม่ใช้AUTH_DB_PASSWORDของproject_appแทนสิทธิ์ผู้ดูแล ไม่ส่งไฟล์.env/รหัสDBให้ทีมผ่านGitHubหรือแชท

เครื่องมือไม่แก้.envและไม่ขอDBpasswordในformบัญชี หากconfigไม่พร้อมให้ผู้ดูแลตั้งเอง ไม่สลับไปใช้DBอื่นหรือเพิ่มสิทธิ์ให้appเพื่อให้ผ่าน

### 1. ตรวจbaselineแบบอ่านอย่างเดียว

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Provision_Advisor --check
```

ไม่มีformข้อมูลบัญชีและไม่มีDML ตรวจชื่อDB/owner/non-superuser/normalize trigger/effectiveINSERTprivilegesที่เกี่ยวข้อง สำเร็จmode=CHECK,persisted=false ไม่ใช่การติดตั้งSchemaหรือรับรองfreshinstallทุกระบบ

### 2. ทดลองสร้างแล้วROLLBACK — ค่าเริ่มต้น

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Provision_Advisor
```

โปรแกรมถามชื่อ/อีเมลและรหัสผ่านสองครั้งในTerminal รหัสผ่านซ่อนข้อความ ต้องใช้interactiveTTY หากซ่อนรหัสไม่ได้จะหยุด ไม่รับpasswordทางargument/environment/file/stdinpipe และไม่พิมพ์password/hash/DSN/configหรือrawSQLerror

ให้ระบุชื่อ/emailเป็นargumentsได้ถ้าต้องการ แต่ไม่ใส่รหัสผ่านในcommand:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Provision_Advisor --dry-run --full-name "Advisor demo" --email "advisor01@example.test"
```

ชื่อนี้และอีเมลเป็นตัวอย่าง ไม่ได้ถูกสร้างไว้ หากสำเร็จmode=DRY_RUN,persisted=false แปลว่าบัญชีนั้นยังLoginไม่ได้เพราะROLLBACKแล้ว IDsอาจขยับแม้ROLLBACKตามidentitysequenceของPostgreSQL

### 3. บันทึกบัญชีใหม่ถาวร — ต้องได้รับอนุมัติขอบเขตข้อมูลก่อน

คำสั่งสำหรับผู้ดูแลเมื่ออนุมัติชื่อ/emailและการบันทึกถาวรแล้ว รอบล่าสุดผู้ใช้อนุมัติบัญชีหนึ่งและรันสำเร็จตามผลท้ายเอกสาร อย่ารันซ้ำเพื่อresetหรือแก้บัญชีเดิม:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Provision_Advisor --apply --confirm-database student_project_management_v1_test
```

กรอกข้อมูลและรหัสผ่านเองบนเครื่อง ไม่มีรหัสผ่านเริ่มต้นให้ในเอกสาร เมื่อUOWจบสำเร็จจึงรายงานmode=APPLIED,persisted=true บัญชี+hashถูกบันทึกพร้อมกัน ไม่มีsessionหรือคำเชิญสร้างอัตโนมัติ

หลังบันทึกจึงใช้Loginเดิมที่localhost:3000ได้ ฝั่งนักศึกษาเปิดProject→คำเชิญอาจารย์แล้วเลือกชื่อบัญชีใหม่นี้ อาจารย์เปิดลิงก์คำเชิญจากหน้าบัญชี สำหรับการทดสอบอัตโนมัติยังใช้Transaction/ROLLBACK ไม่ใช้successfulnormalserverwritesแทนชุดtests

หากresponse/Terminalหายหลัง--apply อย่าสร้างบัญชีชื่อใหม่หรือresetทันที ตรวจผลบัญชีเดิมก่อน การรันซ้ำจะปฏิเสธACCOUNT_ALREADY_EXISTS ไม่แก้ข้อมูลเดิมและไม่รับประกันidempotencyทุกfailuremode

## Error codes

| Code | ความหมาย |
|---|---|
| ARGUMENT_ERROR | flagsไม่รองรับ/ขัดกัน เช่นพยายามส่ง--password; ไม่echoargumentvalues |
| TEST_DATABASE_CONFIRMATION_REQUIRED | --applyยังไม่confirmtestDBหรือconfirmชื่ออื่น |
| ACCOUNT_INPUT_TTY_REQUIRED / PASSWORD_TTY_REQUIRED | ต้องกรอกข้อมูล/รหัสผ่านผ่านTerminalที่รองรับ ไม่fallbackไปechoรหัสผ่าน |
| PASSWORD_MISMATCH / INVALID_PASSWORD_POLICY | ยืนยันรหัสไม่ตรงหรือไม่ผ่านกฎAuth |
| INVALID_FULL_NAME / INVALID_EMAIL / INVALID_ACCOUNT_TEXT | ข้อมูลบัญชีไม่ถูกต้อง/มีtextที่PostgreSQLเก็บไม่ได้ |
| ACCOUNT_ALREADY_EXISTS | emailมีอยู่แล้ว ต้องไม่ยึด/แก้บัญชีเดิมอัตโนมัติ |
| TEST_DATABASE_REQUIRED / OWNER_BASELINE_REQUIRED | baseline/roleไม่ตรงแบบที่อนุมัติ |
| DATABASE_OPERATION_FAILED / INTERNAL_ERROR | storage/config/permissionfailure ไม่คืนข้อความSQLหรือsecret ต้องตรวจconfig/สิทธิ์ตามขอบเขตก่อน ไม่เพิ่มgrantsเอง |
| CANCELLED | ยกเลิกการกรอก ไม่มีการบันทึกบัญชีจากขั้นprompt |

CLIใช้ASCIIJSONเพื่อไม่ให้Terminalที่แสดงUnicodeได้ไม่ครบรายงานผิดหลังtransaction ค่าชื่อในDBยังเป็นUnicodeเดิม ไม่ส่งhashหรือpasswordในJSON

## หลักฐานการทดสอบ

ชุด [test_advisor_provision.py](../../database/tests/test_advisor_provision.py) **PASS17** = CLI/boundary9 + PostgreSQLintegration8 ทุกdatawriteROLLBACK:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest database.tests.test_advisor_provision -q
```

- defaultdryrun/flags/check/nopasswordargument, confirmationguardและwrongDBก่อนrolechange/DML
- non-TTYfailclosed/getpasswarning/mismatch, validationก่อนconnectและno-secretecho
- สร้างadvisorใหม่/normalize/hashverify, existingstudentcredentialsคงเดิม, existingadvisorไม่มีcredentialไม่ถูกactivate
- credentialCHECKล้มเหลวแล้วไม่มีusersกำพร้า, helperไม่COMMIToutertransaction, realrootDRY_RUNไม่เหลือแถว
- directLOGINproject_appไม่สามารถSETROLEownerเพื่อprovisionได้
- ownerprovisionfixture→switchproject_app→Loginจริง→รับคำเชิญ→ตอบรับผ่านAPI โดยไม่มีadminfallbackruntime

รอบเตรียมเครื่องมือ: --checkตรวจสดผ่านและทดลองCLIผ่านinteractiveTTYจริงโดยไม่echo ผลPASS/DRY_RUN/persisted=false ส่วน--applycommitbranchในunit testsตรวจด้วยmockเฉพาะflagforwarding ต่อมาผู้ใช้อนุมัติบันทึกบัญชีจริงตามหัวข้อถัดไป

Regressionรวม **PASS191 = Auth65 + Team37 + member18 + Project21 + invitation24 + boundary9 + provisioning17** ตรวจbaselineหลังROLLBACKผ่าน ไม่รันBrowser/lint/buildซ้ำเพราะรอบนี้ไม่แก้API/Frontend ผลBrowser42เป็นหลักฐานรอบInvitationก่อนหน้า

ไฟล์รอบนี้: เพิ่มCLIและtestsสองไฟล์ตามลิงก์ด้านบน เพิ่มคู่มือนี้ และปรับREADME/database README/Auth Design/Auth Contract/Backlogเฉพาะสถานะprovisioning ไม่มีroleใหม่หรือpublicendpointเพิ่ม ค่าDoneยัง5/20=25% เพราะP08ยังมีcoordinator/existing-account/recovery/rate-limitและG-12ระบบเต็มที่ไม่ปิด

ไม่แก้SourceCodeของAuthAPI/Frontend/SQL/RBAC/Requirements ไม่แตะDBหลักและไม่Commit/Push

## ผลบันทึกตามอนุมัติ — 2026-11-07

ผู้ใช้ยืนยัน “อนุมัติบันทึกบัญชีนี้” หลังตรวจDRY_RUNแล้ว รันCLI--applyพร้อมconfirmstudent_project_management_v1_testด้วยeffectiveproject_ownerที่ไม่ใช่superuser รับรหัสผ่านสองครั้งผ่านhiddenTTY ไม่บันทึกpassword/hashลงเอกสารหรือไฟล์config

| รายการ | ผล |
|---|---|
| บัญชี | อาจารย์หนึ่ง / advisor01@example.test / role=advisor / user_id=1667 |
| CLI | PASS, mode=APPLIED, persisted=true หลังroottransactionสำเร็จ |
| ที่บันทึกถาวร | public.usersเพิ่ม1 และauth.credentialsเพิ่ม1 เก็บArgon2idhash ไม่มีsession/คำเชิญใหม่ถาวร |
| Verifyผ่านconnectionใหม่ | พบuser_id1667/roleadvisorและcredentialArgon2idจริง ไม่ใช่ข้อมูลที่ยังค้างในsavepoint |
| Login verification | DirectLOGINproject_app + TestClientASGI: Login200, Me200, inbox200/ว่าง, Logout204 Sessionทดสอบอยู่outerTransaction/ROLLBACK ไม่ใช้successfulliveTCPPOST |
| Testsหลังบันทึก | Provisioning17testsผ่านอีกครั้งบนbaselineที่มีบัญชีนี้ และคืนbaselineครบ; Regression191เป็นผลรอบเตรียมก่อนapply ไม่ได้รัน191ซ้ำในรอบบันทึก |
| Integrity | metadata/ACLdigestคงเดิม3f10239c8cc40fcd408ad73a7c914f31b556096921f4c495f865c699d7760544 ตารางอื่น/ข้อมูลเดิมคงเดิม auth.sessionsยัง1และfixture_connections=0 ไม่รวมidentitysequencevalues |

Baselineใหม่users3/credentials3/sessions1/teams1/team_members2/projects1/advisor_invitations0 ต่างจากก่อนapplyเฉพาะusers/credentialsอย่างละ1 ไม่มีการอนุมัติสร้างบัญชีอื่น/เปลี่ยนSchema/RBAC/roleหรือรหัสผ่านบัญชีเดิม

เข้าlocalhost:3000/loginด้วยemailนี้และรหัสที่ผู้ใช้กำหนด จากนั้นใช้ลิงก์คำเชิญของฉัน นักศึกษาเลือกชื่ออาจารย์นี้จากหน้าProject→คำเชิญอาจารย์ได้ ไม่ต้องrestartserverเพราะruntimeอ่านDBทุกrequest
