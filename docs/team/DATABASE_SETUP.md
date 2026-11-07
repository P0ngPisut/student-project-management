# Database Setup สำหรับPostgreSQLแยกเครื่อง

**ใช้เฉพาะstudent_project_management_v1_testของเครื่องสมาชิก** คู่มือนี้ไม่สั่งเชื่อมDBหลัก ไม่export/restoreข้อมูลเจ้าของ และรอบhandoffไม่ได้รันinstallers/DDLบนDBปัจจุบัน Freshinstallบนinstanceว่างใหม่ยังNotVerified อ่าน [ผลตรวจ](HANDOFF_VERIFICATION.md)

## A. ผู้ดูแลเตรียมinstanceก่อน

ในpgAdminของPostgreSQLเครื่องตน ให้ผู้ดูแลตรวจ/เตรียมรายการต่อไปนี้ ไม่ใช้รหัสผ่านในGitหรือcopyroles/dataจากเครื่องเจ้าของ:

| รายการ | baseline |
|---|---|
| postgres | loginผู้ดูแลที่มีอยู่ตามการติดตั้ง PostgreSQL; ใช้เฉพาะinventory/deployment/fixtureที่สลับroleก่อนDML |
| project_owner | NOLOGIN, NOSUPERUSER; ownerของDBและSchemaobjects ไม่ให้project_appเป็นสมาชิก |
| project_app | LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS; ตั้งรหัสเองบนเครื่อง และไม่มีowner/pg_read_all_data/pg_write_all_data membership |
| testdatabase | ชื่อstudent_project_management_v1_test, ownerproject_owner; appต้องCONNECTได้ ไม่มีตารางpublic/authเดิมสำหรับinitialinstall |

การสร้างroles/databaseเป็นงานผู้ดูแลที่ต้องอยู่ในขอบเขตของเครื่องนั้น ยังไม่มีauto-bootstraproles/DBในrepository อย่าสร้างด้วยappหรือใช้ฐานข้อมูลหลักแทน หากroles/DBมีอยู่แล้วให้ตรวจpropertiesก่อน ไม่drop/recreateหรือเปลี่ยนสิทธิ์ของของเดิมเพื่อให้ตรงคู่มือเอง

เลือกdefaultencodingUTF8และบันทึกlocale/collationที่ใช้เมื่อทดสอบnamesort ไม่ถือว่าลำดับชื่อข้ามOS/localeตรงกันโดยไม่ตรวจ PostgreSQL18ใช้schemaownerpublicตามpg_database_ownerได้เมื่อDBownerถูกต้อง; installerเป็นผู้ตรวจความพร้อมอีกชั้น

กรอกbackend/.envจาก [คู่มือเครื่อง](LOCAL_SETUP.md) โดยDB_USER=postgresสำหรับinstallersปัจจุบัน และAUTH_DB_PASSWORDเป็นรหัสproject_appของinstanceนี้ ไม่มีค่าpasswordกลางที่ทีมควรใช้ร่วมกัน

## B. Initialinstall — เฉพาะtestDBที่ว่าง

คำสั่งกลุ่มนี้มีDDL/grantsCOMMITบนเครื่องสมาชิก ต้องให้ผู้ดูแลรับรู้ผลก่อนรัน ไม่ใช่ชุดทดสอบปกติ ห้ามรันตามกลุ่มนี้บนDBปัจจุบันของเจ้าของที่ติดตั้งแล้ว

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Database_Schema_V1_Dry_Run_Only
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Database_Schema_V1_Test_Install_Only
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Database_Schema_V1_RBAC_Dry_Run_Only
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Database_Schema_V1_RBAC_Test_Apply_Only
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Install
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Install --apply
```

1. DryRunV1สร้างชั่วคราว/ROLLBACK ต้องผ่านก่อนinitialschemaCOMMIT
2. TestInstallตรวจpinnedSQLและpublicว่าง ติดตั้งเป็นproject_owner คาด14tables/28FK/52functions/24triggers
3. RBACdryrun/Applyสำหรับinitialgrantsที่appยังไม่มีSELECTusersเท่านั้น ถ้ามีแล้วจะปฏิเสธ ไม่ใช้rerunเป็นmigration
4. AuthdefaultrehearsalROLLBACK แล้ว--applyติดตั้งauth2tables/2functions/grantsเมื่อยังไม่มี namespace; มีAuthแล้วvalidateโดยไม่ติดตั้งซ้ำ

sourceV1ปัจจุบันรวม6functionrepairแล้ว Freshinstallไม่ต้องรัน001_v1_baseline_repair_review.sqlหรือV1_Baseline_Install--applyซ้ำ ไฟล์repairใช้เส้นทางlegacybaselineที่reviewแยก ไม่สลับROLLBACK/COMMITในSQLเพื่อทำให้installerผ่าน

อ่านรายละเอียด [Database README](../../database/README.md) และ [V1 Baseline Report](../database/V1_BASELINE_INSTALLATION_REPORT.md) ผลในreportเป็นเครื่องเจ้าของ ไม่ใช่หลักฐานfreshinstallของเครื่องใหม่

## C. DBที่มีSchemaแล้ว

เริ่มอ่านอย่างเดียว:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Database_Schema_V1_Readonly_Preflight
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Install --check-runtime
```

V1ควร14tables/86columns/28FK/52functions/24triggers และAuth2tables/6columns/2FK Ownerproject_owner, runtimeproject_app หากdrift/permissiondeniedให้แนบSQLSTATEกับfunctionที่เกี่ยวข้องแบบไม่มีsecretsแล้วขอreview ไม่ใช้initialinstallทับobjectsหรือเพิ่มprivilegesเอง

## D. ข้อมูลบัญชีและfixtures

- บัญชีadvisor01@example.testบนเครื่องเจ้าของ **ไม่ติดไปกับclone** และไม่มีpasswordในrepository
- ผู้ดูแลแต่ละเครื่องเตรียมadvisorใหม่ตาม [Provisioning Guide](../database/ADVISOR_ACCOUNT_PROVISIONING.md) DefaultDRY_RUNไม่ทำให้Loginได้ การ--applyเป็นการบันทึกusers/credentialsถาวรแยกจากtests ต้องอนุมัติชื่อ/email/ขอบเขตข้อมูลในเครื่องนั้นก่อน
- studentสมัครผ่านAPI/UIเดิมได้สำหรับการใช้งานที่อนุมัติ ไม่เปิดsignupเลือกroleเป็นadvisor/coordinator
- testsปัจจุบันเตรียมstudent/staffเองภายในROLLBACK จึงไม่ต้องสร้างบัญชีถาวรเพื่อให้regressionผ่าน Adminconfigต้องพร้อมสำหรับownerfixtures
- ห้ามuploadDBdump/credentialhash/sessiontokenของเครื่องตนเพื่อให้ทีมมีข้อมูลเหมือนกัน ให้ใช้sourceSQLและfixturesที่ทำซ้ำได้ตามขอบเขตแทน
