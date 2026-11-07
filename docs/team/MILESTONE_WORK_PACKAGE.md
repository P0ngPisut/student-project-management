# งานทีมM — Milestone และจุดต่อTask

สถานะส่งต่อ: **มีSQL/controlledoperations/DB-onlytests แต่ยังไม่มีAPI/UIหรือHTTPContractที่ยืนยัน** งานนี้ไม่อนุมัติTask/Assigneeเต็มระบบ, Dashboardmetrics, TimelineหรือContributionformulaเอง

อ่าน [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) ตาราง11–14/ส่วน4.2/4.4, [SQL V1](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) v1_milestone_guard/v1_task_guard/v1_refresh_milestone และ [Reference](../database/SCHEMA_V1_REFERENCE.md)

## กฎที่ยืนยันแล้ว

| เรื่อง | V1ที่ต้องรักษา |
|---|---|
| Project/ผู้สร้าง | ต้องอยู่ในProjectจริง หัวหน้าทีมปัจจุบันสร้าง/แก้metadata/ลบตามกฎ created_byมาจากactorจริง |
| ชื่อ | trimไม่ว่างVARCHAR255; UNIQUE(project_id,LOWER(name)) ไม่ใช้case-sensitiveprecheckแทนDBconstraint |
| Description | optionalTEXT trimแล้วว่างเป็นNULL ไม่เพิ่มmaxlenใหม่เอง |
| Due date | DATE, เมื่อสร้างหรือแก้วันที่ต้องไม่ก่อนวันนี้ในAsia/Bangkok ไม่ใช้UTC/browserlocaleเป็นbusinessclockแทนDB |
| D-01 | ห้ามย่อMilestonedueจนมีTaskdueเกินวันใหม่ ให้ปฏิเสธ ไม่เลื่อนTaskอัตโนมัติ |
| Status | derivedจากTasks: ไม่มีTask/ทุกTasknot_started=not_started ทุกTaskcompleted=completed กรณีอื่น=in_progress ไม่รับstatusจากformMilestone |
| ประวัติ | created_at/created_by/project_idimmutable updated_at/byเปลี่ยนเมื่อข้อมูลที่กำหนดเปลี่ยนจริง completed_atตามderivedstatus |
| First evaluation | หลังกรรมการบันทึกEvaluationแรก ห้ามcreate/update/deleteMilestoneและงานตามกฎ ไม่ใช้headervalueแทนDBstate |
| Delete | v1_delete_milestoneไม่เท่ากับProjectDELETE Milestoneที่มีTaskถูกFKRESTRICT ไม่เพิ่มcascadeเพื่อให้ลบผ่าน |

**อย่าเพิ่มphasegateเอง:** v1_milestone_guardปัจจุบันตรวจProject/leaderและfirst-evaluationlock ไม่ได้บังคับว่าต้องรอadvisorตอบรับ/กรรมการอนุมัติก่อนสร้างMilestone หากทีมอยากเพิ่มเงื่อนไขนี้ต้องขอเปลี่ยนRequirementก่อน ไม่อนุมานจากลำดับหน้าจอของSubmission

## แบ่งงานที่ควรทำ

| ID | งาน | หลักฐานปิดงาน |
|---|---|---|
| M01 | Contractcreate/list/detail/updatemetadata/deleteและauthorizationmatrix | เจ้าของยืนยันURL/DTO/errors/readroles/UXก่อนimplement |
| M02 | Repository/UOW/actor/controlledfunctions/authorizedreads | appใช้grantsเดิม IDsstrings PGerrorsจำแนกเฉพาะcase ไม่มีadminfallback |
| M03 | หน้ารายการ/formรายละเอียดMilestoneและderivedstatus | ไม่เปิดstatusdropdown/created_byeditable วันที่ตามBangkokหลังrefreshตรงDB |
| M04 | Taskintegrationfixtures/D-01/derivedstatus/first-scorelock | พิสูจน์ด้วยTaskจริงผ่านcontrolledoperationsในtransaction ไม่แก้Milestonestatusตรงเพื่อทำUItest |
| M05 | HTTP/PostgreSQL/Browserregression/report | baselineคืนหลังROLLBACK และnegativeauthorizationผ่าน |

## Controlledoperationsที่มีแล้ว

```text
v1_create_milestone(bigint,text,text,date) -> bigint
v1_update_milestone(bigint,text,text,date) -> void
v1_delete_milestone(bigint) -> void
```

ไม่ให้project_appdirectINSERT/UPDATE/DELETEMilestoneเพิ่มเอง ฟังก์ชันที่reviewแล้วล็อกProject/rowและreuseguardsตามRBAC ถ้าพบpermissiondeniedให้รายงานSQLSTATE/function/grantsจริงก่อน ไม่ใช้ownerสร้างMilestoneแทนappในpositiveAPIcase

Task/Assigneefunctionsที่เกี่ยวข้องมีv1_create_task/v1_update_task_metadata/v1_set_task_status/v1_assign_task/v1_unassign_task/v1_exit_team_member ตรวจsignatureจริงก่อนใช้ ไม่มีการอนุมัติTaskAPIเพิ่มจากการเห็นชื่อเหล่านี้

## จุดต่อโค้ดร่วมกับทีมS

- เพิ่มbackend/milestone_api.pyและmilestone_store.pyกับfrontend/src/features/milestonesเมื่อContractยืนยัน
- main.py/router/errorhandlers/no-store, test_auth_security.py/OpenAPI และauth_browser_server.py/newUOWoverrideเป็นsharedfiles ต้องตกลงผู้แก้/mergeกับทีมS
- CORSปัจจุบันallowGET/POSTเท่านั้น หากContractใหม่เลือกPATCH/PUT/DELETEต้องreviewและทดสอบCORS/CSRFตามverbนั้นด้วย require_originเดิมตรวจการเขียนที่ไม่ใช่GET/HEAD/OPTIONSได้ แต่CSRFของendpointใหม่ต้องตรวจเอง ไม่ขยายmethodsโดยไม่มีContract
- ใช้Projectcontext/active sessionเดิม ไม่สร้างAuthหรือroleleaderในusersใหม่ leaderยังเป็นmembershiprole
- parentlockorderยึดV1โดยอ่านcontrolledfunctionsจริง: Projectก่อนMilestone/Task; operationsสมาชิกเริ่มTeamก่อนProject ไม่ทำrawrowlocksจนต้องเพิ่มUPDATEprivilegeเอง
- milestonesstatusและdateconstraintsสัมพันธ์กับTasks ส่วนSubmission/Committee/Evaluationเปลี่ยนeligibilityตามกฎเดิม เลือกfixturehelperร่วมกันแทนให้แต่ละทีมสร้างstateคนละความหมาย
- ต่อBrowserfixtureก่อนทดสอบPOST/PATCH/DELETEใหม่ อย่าลืมว่าการfallbackไปnormalUOWจะCOMMITแม้ใช้port8001

## Acceptance testsขั้นต่ำ

1. leadercreate/read/update/deleteemptyMilestoneผ่าน DBเป็นผู้ตั้งactor/time/status; memberสร้าง/แก้/ลบไม่ได้และcrossProjectไม่รั่ว
2. nameblank/255/256Unicode, duplicatecase-insensitiveในProjectเดียว vsชื่อเดียวคนละProject, descriptionnormalize, clientspoofstatus/project/actor/timestamps
3. dueyesterday/today/tomorrowคำนวณจากDBBangkokdate และการแก้วันเดิม/วันใหม่ข้ามเที่ยงคืนตามกฎ ไม่hardcodeวันที่วันนี้ในfixture
4. D-01มีTaskจริง dueเกินMilestoneวันใหม่แล้วปฏิเสธ ไม่มีTaskถูกเลื่อนหรือpartialupdate
5. ไม่มีTask/allnot_started/mixed/allcompleted เปลี่ยนderivedMilestonestatusถูกต้อง timestampsตามการเปลี่ยนจริง ไม่รับstatusจากAPIตรง
6. มีTaskแล้วdeleteถูกRESTRICT; emptydeleteสำเร็จตามสิทธิ์; ProjectDELETEยังถูกห้ามทุกกรณี
7. firstEvaluationlockจริงและPGfunctionguardไม่ถูกข้ามด้วยpayload; ownerใช้เฉพาะsetupfixtureที่อนุมัติ ทุกคำขอbusinessเป็นapp
8. unauthorized/CSRF/Origin/sessionexpired-revoked/storage/transactioncompletionfail/rollback/errorredaction และrealDB/BrowserDesktopMobile

## ยังต้องยืนยันก่อนเขียนAPI/UI

- URL/JSON/updateverb/errorcodes/pagination/การเรียงMilestonelist (DD4.5กำหนดdue_dateASC,idASCแล้ว ต้องรักษา)
- บทบาทที่อ่านMilestoneได้นอกcurrentteamให้ทำG-12matrixตามProjectcontext ห้ามเปิดทุกProjectเพียงเพราะroleadvisor/coordinator
- form/list/detail/navigation/TaskAPIอยู่ในscopeทีมนี้แค่ไหน ไม่มีSTหน้าหรือDashboardmetricsที่ยืนยันสำหรับMilestoneในwireframeเก่า
- อาจมีsingle-sessionDBcoverageเดิม แต่realmulti-sessionconcurrencyยังไม่พิสูจน์ ห้ามCOMMITfixturesเพื่อข้ามข้อจำกัด

ให้บันทึกContract/AC/tests/ข้อจำกัดพร้อม [Progress Template](../progress/PROGRESS_REPORT_TEMPLATE.md) และไม่mergeAPIของทีมSโดยไม่ได้ทดสอบread/lock/authorizationร่วมกัน
