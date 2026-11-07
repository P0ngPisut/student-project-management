# จุดเริ่มต้นสำหรับทีม — Student Project Management System

อัปเดต2026-11-07 · ทีมใช้ **Windows/PowerShell และ PostgreSQLแยกเครื่อง** ตามที่เจ้าของยืนยัน ฐานพัฒนาปัจจุบันfeature/database-schema; ต้องเริ่มจากcommitที่มีเอกสารนี้ ไม่ใช่remotecommit9d07c52เดิมที่ยังไม่มีงานรอบTeam/Project/Invitations

## อ่านตามลำดับ

1. [ตั้งค่าเครื่อง](LOCAL_SETUP.md) และ [ฐานข้อมูลเครื่องใหม่](DATABASE_SETUP.md)
2. [Schema V1 Reference](../database/SCHEMA_V1_REFERENCE.md), [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md), [Backlog](../progress/BACKLOG.md)
3. [งานส่งโครงงาน](SUBMISSION_WORK_PACKAGE.md) หรือ [งานMilestone](MILESTONE_WORK_PACKAGE.md) ตามส่วนที่รับผิดชอบ
4. ก่อนส่งโค้ดกลับ อ่าน [Git/checklistส่งต่อ](GIT_RELEASE_CHECKLIST.md) และ [ผลตรวจชุดส่งต่อ](HANDOFF_VERIFICATION.md)

## มีอะไรแล้ว / ยังเหลืออะไร

| ส่วน | หลักฐาน / สถานะ |
|---|---|
| Auth | Registerstudent/Login/Logout/Me, Argon2id, session8ชั่วโมง, CSRF/Origin/CORS; Frontendเชื่อมแล้ว |
| Team | สร้างTeamพร้อมตนเป็นleader อ่านทีม/รายชื่อ เพิ่มmemberด้วยemail; ยังไม่มีออก/ถอด/โอนหัวหน้าAPI/UI |
| Project | หัวหน้าสร้าง1Projectต่อทีม สมาชิกอ่านProjectตน; ห้ามลบตามR-01; ยังไม่มีmetadataupdateAPI/UI |
| Advisor invitation | เลือกadvisor/ส่ง/ประวัติ/ยกเลิก และadvisorinbox/รับ/ปฏิเสธ ครบContractที่ยืนยัน |
| Database | publicV1 14tables/86columns/28FK/52functions/24triggers + auth2tables/6columns/2FK |
| Submission/file/review | มีSQL/DB-onlyregressionบางส่วน ยังไม่มีAPI/UIหรือHTTPContractที่ยืนยันสำหรับส่วนนี้ |
| Milestone/Task | มีSQL/controlledfunctions/DB-onlyregressionบางส่วน ยังไม่มีAPI/UIหรือHTTPContractที่ยืนยันสำหรับส่วนนี้ |
| Concurrency/UAT/freshinstall | อ่านขอบเขตในBacklog/ผลตรวจ ไม่ถือว่าเสร็จจากจำนวนtests |

คำว่าDB-onlyไม่เท่ากับAPIใช้งานได้แล้ว หน้าบัญชีไม่ใช่Dashboard ตารางMilestoneไม่ใช่หลักฐานว่ามีTaskboard UI

## ข้อตกลงร่วมของสองทีม

- ห้ามเปลี่ยนSchemaV1/BusinessRules, SQLreviewที่pinchecksum หรือgrantsเพื่อแก้permissionerrorเอง ให้รายงานและยืนยันก่อน
- ใช้student_project_management_v1_testเท่านั้น ไม่ใช้DBหลัก เครื่องใหม่มีบัญชี/ข้อมูลแยกจากเครื่องเจ้าของ Gitไม่ได้ย้ายPostgreSQLหรือบัญชีadvisorไปด้วย
- Runtimeใช้project_app ส่วนownerใช้เฉพาะติดตั้ง/fixtureที่อนุมัติ ไม่ใส่adminfallbackในAPI
- ทุกAPIใช้sessionเดิม และPOST/การเขียนใช้session-boundCSRF/OriginตามContract; IDsเป็นdecimalstrings ห้ามใช้clientuser_id/roleเป็นสิทธิ์
- ทดสอบการเขียนด้วยTransaction/ROLLBACK ตรวจcurrent_databaseก่อนชุดและmetadata/ACL/rowcountsหลังชุด เก็บข้อมูลเดิม ไม่COMMITfixtureเพื่อทำmulti-sessionเอง
- การติดตั้งSchema/Authหรือสร้างบัญชีถาวรเป็นงานผู้ดูแลตามขั้นอนุมัติ ไม่ใช่testfixtureปกติ
- ไม่เผยpassword/hash/token/.env/DBdumpในGitหรือรายงาน ใช้templatesที่เว้นpasswordว่าง

## จุดต่อโค้ดที่ใช้ร่วมกัน

- [main.py](../../backend/main.py): appfactory/router/validation/storage/no-store/CORS ต้องรักษาของเดิม
- [auth_api.py](../../backend/auth_api.py), [auth_store.py](../../backend/auth_store.py): active session, error envelope, pinnedDB/appconnection; ไม่ใช้legacybackend/database.pyเป็นrequestconnection
- [project_store.py](../../backend/project_store.py), [invitation_store.py](../../backend/invitation_store.py): ตัวอย่างauthorizedquery/UOW/actorGUC/parentlocks/narrowPGerror mapping
- Frontendroutesอยู่src/app; งานใหม่แยกsrc/features/submissionsและsrc/features/milestonesเมื่อContractยืนยัน โดยreuseAuthsession/APIorigin ไม่สร้างLogin/roleระบบใหม่
- [auth_browser_server.py](../../backend/tests/auth_browser_server.py): **เพิ่มUOWoverrideของfeatureใหม่** ให้ใช้outerROLLBACKเดียวกันก่อนBrowserPOST มิฉะนั้นอาจหลุดไปCOMMITบนnormalconnection
- [test_auth_security.py](../../backend/tests/test_auth_security.py): อัปเดตOpenAPIpathsetเมื่อมีendpointที่ยืนยันเพิ่ม

SubmissionและMilestoneพัฒนาแยกbranchได้ แต่ต้องตกลงไฟล์shared main.py/tests/harness/errorhandlersก่อนmerge ไม่มีการเลือกURL/DTO/phaseหรือlibraryที่ยังไม่ยืนยันแทนเจ้าของrequirementsในเอกสารนี้
