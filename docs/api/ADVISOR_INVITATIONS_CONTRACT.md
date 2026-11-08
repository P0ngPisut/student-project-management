# Advisor invitations — approved and implemented

วันที่2026-11-07 · P10/P15/P16/P17 · **ผู้ใช้ยืนยันแล้ว; Backend/Frontend implemented/tested**

งานต่อจาก [Project create/current](../progress/PROJECT_IMPLEMENTATION_REPORT.md) ผู้ใช้ยืนยันเลือกจากรายชื่อและทำครบส่ง–ยกเลิก–ตอบรับ–ปฏิเสธพร้อมAPI/UIตามเอกสารนี้แล้ว ไม่เปลี่ยนSchema/RBAC/Requirementsหรือสร้างบัญชีอาจารย์ถาวร ดู [รายงานผล](../progress/ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md)

## กฎที่ยืนยันแล้ว

อ้างอิง [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) ตารางadvisor_invitationsและส่วน4.1/4.2/4.4/4.5, [SQL V1](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) v1_invitation_guard/v1_resolve_invitation และ [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql)

- ต้องมีProjectก่อนส่งคำเชิญ ผู้ส่งและผู้ยกเลิกเป็นหัวหน้าทีมปัจจุบัน ผู้ถูกเชิญต้องมีusers.role=advisor
- เริ่มpendingเสมอ เปลี่ยนได้ครั้งเดียวเป็นaccepted/rejected/cancelled ไม่มีการแก้คำเชิญที่สิ้นสุดแล้วหรือลบประวัติ
- อาจารย์ที่ถูกเชิญเท่านั้นตอบรับ/ปฏิเสธ หัวหน้าทีมปัจจุบันเท่านั้นยกเลิกpending หลังacceptedเปลี่ยนอาจารย์ไม่ได้ในV1
- แต่ละProjectมีคำเชิญpendingหรือacceptedรวมกันได้สูงสุด1รายการ ตามpartialUNIQUE uq_invitations_active_project ไม่เพิ่มโควตาจำนวนProjectต่ออาจารย์เอง
- sent_byมาจากหัวหน้าจริง sent_atมาจากPostgreSQL ห้ามเปลี่ยนidentity/sent_at; resolved_by/atต้องครบคู่และถูกเติมโดยtriggerเมื่อสิ้นสุด resolved_at>=sent_at
- สมาชิกทีมปัจจุบันเห็นประวัติคำเชิญของProjectตน เมื่อออกจากทีมสิทธิ์จากสมาชิกภาพสิ้นสุด อาจารย์เห็นเฉพาะประวัติคำเชิญที่ส่งถึงตน
- อาจารย์ที่มีpendingเห็นชื่อทีม/Project/คำอธิบายตามG-12; เมื่อrejected/cancelledเหลือสิทธิ์ประวัติคำเชิญตนเอง ไม่เปิดข้อมูลProjectปัจจุบันต่อจากคำเชิญนั้น
- เรียงประวัติsent_at DESC, id DESC ไม่มีขั้นส่งอีเมลจริง/แจ้งเตือนอัตโนมัติที่ยืนยันแล้ว
- วิธีสร้างบัญชียังคงstudentสมัครเอง; ผู้ดูแลเตรียมadvisor/coordinator ไม่มีpublic signupที่เลือกroleเป็นadvisor

## ขอบเขตที่ผู้ใช้ยืนยัน

1. **วิธีเลือกอาจารย์:** selectรายชื่ออาจารย์จากid/full_name โดยไม่คืนemail ตามแนวST-06ใน [UIต้นทาง](../codex_project_handoff/sources/ทำหน้า%20UI.txt) รายชื่อนี้ให้เฉพาะหัวหน้าที่มีProjectตนแล้ว ไม่เปิดuser directoryทั่วไป
2. **ขอบเขตรอบพัฒนา:** ทำครบส่ง/อ่านประวัติ/ยกเลิกฝั่งทีม และอ่านคำเชิญ/ตอบรับ/ปฏิเสธฝั่งอาจารย์ พร้อมหน้าตามหัวข้อUIด้านล่าง

API/UIต่อไปนี้เป็นขอบเขตที่ยืนยันและimplementแล้ว ไม่เปิดให้studentสมัครหรือเลือกroleเป็นadvisor

## APIที่ยืนยันและimplementแล้ว

ทุกendpointใช้sessionเดิม; POSTบังคับOriginและsession-bound CSRF ตามAuthเดิม GETไม่บังคับCSRF/Origin ไม่ต่ออายุsession และทุกresponse no-store IDsทุกชนิดเป็นdecimal strings เวลาเป็นISO8601พร้อมtimezone/offsetจากTIMESTAMPTZ และresolved_atเป็นnullเมื่อpending

### 1. GET /api/v1/projects/me/advisor-candidates

เฉพาะหัวหน้าทีมปัจจุบันที่มีProjectแล้ว คืนเฉพาะบัญชีrole=advisor:

```json
{"data":[{"id":"501","full_name":"อาจารย์ตัวอย่าง"}]}
```

เรียงfull_name ASC,id ASC ไม่คืนemail/บัญชีstudent/coordinator ไม่ใช้รายชื่อนี้เป็นสิทธิ์ตอนPOST ต้องตรวจtargetroleใหม่เสมอ ถ้าไม่มีadvisorคืน200data:[] ไม่สร้างบัญชีให้เอง เวอร์ชันนี้ยังไม่มีpagination

### 2. GET /api/v1/projects/me/advisor-invitations

studentที่เป็นสมาชิกทีมปัจจุบันอ่านประวัติของProjectตนได้ทั้งleader/member สำเร็จ200dataเป็นarrayตามลำดับV1 ว่างเป็น[] ไม่รวมคำเชิญProjectทีมอื่น ตัวอย่างรายการ:

```json
{
  "id":"601",
  "advisor":{"id":"501","full_name":"อาจารย์ตัวอย่าง"},
  "status":"pending",
  "sent_at":"2026-11-07T06:00:00Z",
  "resolved_at":null
}
```

ไม่คืนemail/sent_by/resolved_by/ข้อมูลลับในDTOรอบแรก ชื่ออาจารย์เป็นข้อมูลปัจจุบันจากusers ไม่เพิ่มsnapshotที่Schemaไม่มี

### 3. POST /api/v1/projects/me/advisor-invitations

leaderส่งJSONเฉพาะadvisor_id:

```json
{"advisor_id":"501"}
```

advisor_idต้องเป็นdecimal stringที่แทนpositiveBIGINTได้ ไม่รับproject_id/team_id/sent_by/status/sent_at/resolved_byจากclient เลือกProjectจากสมาชิกภาพactorและกำหนดsent_byจากsession ไม่สร้างusersหรือProjectอัตโนมัติ สำเร็จ201dataเป็นรายการรูปแบบเดียวกับประวัติทีม โดยstatus=pendingและresolved_at=null หลังtransactionจบ

### 4. POST /api/v1/advisor-invitations/{invitation_id}/cancel

หัวหน้าทีมปัจจุบันยกเลิกpendingของProjectทีมตน ไม่มีbodyfieldsที่ใช้เลือกactor/เปลี่ยนสถานะอื่น สำเร็จ200dataเป็นรายการDTOฝั่งทีมที่status=cancelled

คำเชิญProjectอื่น/ผู้ใช้ไม่มีสิทธิ์รับรู้=404 ไม่เลือกหัวหน้าจากsent_byเก่า เพราะอาจโอนหัวหน้าภายหลัง; memberในทีมเห็นประวัติได้แต่ยกเลิกไม่ได้=403

### 5. GET /api/v1/advisor-invitations/me

เฉพาะrole=advisorอ่านประวัติที่advisor_idเป็นตน สำเร็จ200dataเป็นarray ว่างเป็น[] DTOต่อรายการ:

```json
{
  "id":"601",
  "status":"pending",
  "sent_at":"2026-11-07T06:00:00Z",
  "resolved_at":null,
  "project_context":{
    "team_name":"ทีมตัวอย่าง",
    "project_name":"โครงงานตัวอย่าง",
    "project_description":null
  }
}
```

project_contextมีเฉพาะpending/accepted และจำกัดชื่อทีม/ชื่อProject/คำอธิบายProject สำหรับrejected/cancelledให้project_context=null เหลือid/status/sent_at/resolved_atของคำเชิญตน ไม่คืนรายชื่อสมาชิก/ไฟล์/Submission/email/IDProjectหรือทีม และไม่เพิ่มสิทธิ์ให้GET /projects/meเดิมที่จำกัดstudent

### 6. POST /api/v1/advisor-invitations/{invitation_id}/respond

อาจารย์ที่ถูกเชิญส่งเฉพาะdecision:

```json
{"decision":"accepted"}
```

รับacceptedหรือrejectedเท่านั้น ไม่รับcancelled/pending/actor/bodyfieldsอื่น สำเร็จ200dataเป็นDTOฝั่งอาจารย์ หลังrejectedไม่มีproject_context หลังacceptedคงminimal contextตามข้างต้น คำเชิญสิ้นสุดแล้วตอบ409 ไม่มีautomatic POST retry/idempotency guarantee ให้GETตรวจผลเมื่อresponseหาย

## Errors

ใช้envelopeAuth/Team/Projectเดิม ไม่ส่งrawSQL/constraint/traceback/ข้อมูลคนอื่น:

| HTTP / code | กรณี |
|---|---|
| 401 AUTHENTICATION_REQUIRED | sessionขาด/ผิด/หมดอายุ/ถูกยกเลิก |
| 403 INVITATION_ACCESS_FORBIDDEN | roleไม่รองรับendpointนั้น เช่นstudentเรียกadvisor inbox หรือstaffเรียกstudent Project endpoint |
| 404 TEAM_NOT_FOUND / PROJECT_NOT_FOUND | student endpointยังไม่มีTeam/Projectตามลำดับ |
| 403 INVITATION_ACTION_FORBIDDEN | memberเห็นProject/คำเชิญแต่ส่ง/ยกเลิก/อ่านcandidatesไม่ได้ |
| 404 ADVISOR_NOT_FOUND | advisor_idไม่มีหรือไม่ใช่advisor ไม่คืนroleจริง |
| 404 INVITATION_NOT_FOUND | ไม่มีคำเชิญหรือactorไม่มีสิทธิ์รับรู้คำเชิญนั้น |
| 409 INVITATION_ALREADY_PENDING | ส่งใหม่ขณะProjectมีpendingแล้ว |
| 409 ADVISOR_ALREADY_ACCEPTED | ส่งใหม่ขณะProjectมีacceptedแล้ว ห้ามเปลี่ยนอาจารย์ |
| 409 INVITATION_ALREADY_RESOLVED | พยายามตอบรับ/ปฏิเสธ/ยกเลิกคำเชิญที่ไม่ใช่pending |
| 409 INVITATION_CONFLICT | DB UNIQUE conflictเฉพาะactive invitationที่ไม่สามารถจำแนกจากprecheckเดิม ให้โหลดประวัติใหม่ |
| 403 CSRF_INVALID / ORIGIN_NOT_ALLOWED | POSTไม่ผ่านนโยบายAuthเดิม |
| 422 VALIDATION_ERROR | ID/JSON/decisionผิดหรือส่งfieldsอื่น |
| 500 INTERNAL_ERROR | storage/config/transaction failureที่จำแนกเป็นbusiness errorไม่ได้ |

สำหรับส่งใหม่ ตรวจactiveคำเชิญภายใต้Projectlockก่อนตรวจtarget เพื่อไม่เปิดadvisor lookupเกินจำเป็น หากยังเกิดUNIQUEconflictให้rollbackและใช้INVITATION_CONFLICTเฉพาะuq_invitations_active_project ให้clientโหลดประวัติใหม่ ไม่ตีความ23505ทุกชนิดเป็นpending และไม่ส่งชื่อconstraintให้client

## Frontendที่ยืนยันและimplementแล้ว

- Feature-based src/features/advisor-invitations; หน้า/projects/advisor-invitations จากลิงก์ในหน้าProjectที่สร้างแล้ว ให้สมาชิกอ่านประวัติและleaderเลือกอาจารย์/ส่ง/ยกเลิกpendingได้
- หน้า/advisor/invitations จากลิงก์หน้าบัญชีของrole=advisor แสดงคำเชิญตนพร้อมตอบรับ/ปฏิเสธเฉพาะpending; coordinatorไม่มีลิงก์และไม่มีสิทธิ์พิเศษที่เพิ่มเอง
- ไม่แสดงformส่งใหม่หากมีpending/accepted ไม่ให้ยกเลิกaccepted/เปลี่ยนอาจารย์ ไม่มีปุ่มลบประวัติ
- ไม่มีadvisorให้แสดงข้อความว่าต้องให้ผู้ดูแลเตรียมบัญชี ไม่ให้studentสร้างadvisorหรือเปลี่ยนroleผ่านformนี้
- ใช้ชื่อสถานะภาษาไทย แสดงเวลาตามAsia/Bangkok; ไม่ต่ออายุsession/เก็บข้อมูลลงlocalStorage/sessionStorage และไม่ส่งอีเมลจริง
- pending/disabledป้องกันsubmitซ้ำ; error/retryสำหรับGET; POSTไม่ทราบผลให้ตรวจประวัติใหม่แทนretryอัตโนมัติ ไม่ตีความnetwork/500เป็นประวัติว่าง
- ยังไม่ทำsubmission/upload/แจ้งเตือน/Project metadata update/admin provisioning toolในรอบนี้

## Implementationและเกณฑ์ทดสอบ

1. ใช้project_app/test DBและUOWเดิม กำหนดactorGUCจากactive session ไม่ใช้client identity ใช้parameterized SQLและgrantsเดิม
2. ผูกสิทธิ์กับสมาชิกภาพปัจจุบัน/Projectหรือadvisor_idของsessionทุกคำขอ ล็อกparentตามลำดับV1แล้วตรวจactor/สถานะซ้ำก่อนเขียน (Team→Project→Invitationเมื่อเกี่ยวข้อง)
3. ส่งด้วยINSERT advisor_invitationsตามRBAC ส่วนaccept/reject/cancelผ่านv1_resolve_invitation ไม่ให้directUPDATE/DELETEเพิ่ม ไม่ปิดtriggerหรือแก้SQL
4. ทดสอบleaderส่ง/memberอ่าน/leaderยกเลิก/advisorรับ-ปฏิเสธจริง พร้อมDBsent_by/resolved_by/เวลาจากtrigger ตรวจimmutable/finalstate/UNIQUEและยืนยันไม่มีประวัติหาย
5. ทดสอบexpired/revokedAuth/CSRF/Origin/role/actor spoof/IDของProjectอื่น/advisorอื่น/memberออกจากทีม และresponseไม่เผยข้อมูลที่G-12ห้าม โดยเฉพาะrejected/cancelledต้องไม่มีliveProjectcontext
6. ทดสอบpendingซ้ำ/acceptedแล้วส่งใหม่/ตอบซ้ำ/ยกเลิกหลังสิ้นสุด, targetไม่พบ/ไม่ใช่advisor, invalidBIGINT/decision/extra fields และfailureหลังเขียน/จบtransactionต้องrollback ไม่ตอบsuccess
7. Browserทดสอบครบเส้นทางที่ยืนยัน รวมrefresh/noadvisor/emptyhistory/memberreadonly/rolepages/error/responseหาย/pending-submit/Desktop/Mobile โดยpositiveflowsใช้API/PostgreSQLจริง
8. ทุกชุดตรวจcurrent_database ใช้เฉพาะstudent_project_management_v1_test และTransaction/ROLLBACK พร้อมmetadata/ACL/rowcounts baseline comparison เก็บข้อมูลเดิม ไม่COMMITfixtureเพื่อทำconcurrencyเอง
9. บัญชีadvisor/coordinatorในtestsเตรียมเฉพาะfixtureด้วยproject_ownerที่ไม่ใช่superuserตามขอบเขตfixtureเดิม รวมcredentialhashเมื่อทดสอบLogin แล้วคืนเป็นproject_appสำหรับคำขอแอปและROLLBACKทั้งหมด ไม่สร้างบัญชีถาวร/ไม่เพิ่มสิทธิ์/ไม่เปิดrole signup

ก่อนใช้หน้าadvisorบนnormalserverต้องมีบัญชีadvisorพร้อมcredentialsที่ผู้ดูแลเตรียม ขั้นตอนถาวรนี้ยังไม่ใช่งานที่ทำแล้ว และต้องอยู่ในขอบเขตการเขียนข้อมูลที่ผู้ใช้อนุญาตแยกจากtests ไม่เพิ่มบัญชีตัวอย่างเองเพื่อทำDemo

ผลปัจจุบันBackend174tests/Browser42tests/lint/TypeScript/build/direct-app boundary smokeผ่าน ทุกfixtureROLLBACKและคืนbaseline ไม่แก้Schema/RBAC/.env ไม่เชื่อมDBหลักและไม่Commit/Push ผลนี้ไม่ใช่real multi-session concurrencyหรือsuccessful runtime data COMMIT อ่านรายงานสำหรับcoverageและข้อจำกัด
