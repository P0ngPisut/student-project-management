# Project create/current — approved and implemented

วันที่2026-11-07 · P09/P15/P16/P17 · **ผู้ใช้ยืนยันแล้ว; Backend/Frontend implemented/tested**

งานต่อจาก [Team Members](../progress/TEAM_MEMBERS_IMPLEMENTATION_REPORT.md) ผู้ใช้ตอบ “ใช้ตามร่าง Project Contract” ยืนยันAPI/หน้าProjectตามเอกสารนี้แล้ว ไม่เปลี่ยนRequirements, Schema V1หรือRBAC ดู [ผลทดสอบล่าสุด](../progress/PROJECT_IMPLEMENTATION_REPORT.md)

## กฎที่ยืนยันแล้ว

อ้างอิง [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) ตารางprojectsและส่วน4.2/4.4, [Reference](../database/SCHEMA_V1_REFERENCE.md) และ [SQL V1](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) ฟังก์ชันv1_project_guard

- C-01: ต้องมีTeamก่อนสร้างProject หนึ่งทีมมีได้หนึ่งProject และผู้สร้างเป็นหัวหน้าทีมปัจจุบัน
- สมาชิกทีมต้องเป็นstudentตามV1 ไม่เพิ่มขั้นต่ำจำนวนสมาชิกมากกว่า1คนเอง
- projectsมี6columnsเท่านั้น: id/name/description/team_id/created_by โดยteam_idและcreated_byห้ามเปลี่ยนหลังINSERT
- ชื่อtrimASCII whitespace ห้ามว่าง ยาวไม่เกิน255Unicode code points; descriptionไม่บังคับ trimแล้วว่างเป็นNULL ไม่เพิ่มชื่อUniqueหรือเพดานdescriptionเอง
- R-01=A: ห้ามลบProjectทุกกรณี รวมยังไม่ส่งหัวข้อและไม่มีข้อมูลลูก; ไม่มีDELETE API/UI/สิทธิ์เพิ่ม
- G-12: Backendตรวจsession/role/สมาชิกภาพทุกคำขอ ไม่Authenticate=401; ไม่พบresource/ไม่มีสิทธิ์รับรู้=404; เห็นresourceแต่ทำไม่ได้=403
- การเข้าถึงของAdvisor/Coordinatorต้องอิงProject contextและphaseตามG-12 ไม่ใช้การเปิดstudent endpointนี้ให้staffทั้งหมด

## APIที่ยืนยันและimplementแล้ว

### POST /api/v1/projects

รับเฉพาะnameและdescriptionที่ไม่บังคับ:

```json
{"name":"ระบบจัดการโครงงานนักศึกษา","description":null}
```

- ใช้session/Origin/CSRFเดิมของLogin ไม่เปลี่ยนTTL8ชั่วโมง
- BackendหาTeamจากสมาชิกภาพของactorที่ตรวจแล้ว ไม่รับteam_id/created_by/user_id/role/statusหรือข้อมูลสมาชิกในrequest
- ไม่สร้างTeamหรือusersอัตโนมัติ; ตรวจหัวหน้าปัจจุบันภายในtransactionและหลังรอteam lock
- สำเร็จ201หลังtransactionจบ คืนค่าที่normalizeแล้วจากDB:

```json
{
  "data": {
    "id": "401",
    "name": "ระบบจัดการโครงงานนักศึกษา",
    "description": null,
    "team_id": "101",
    "created_by": "301"
  }
}
```

IDsเป็นdecimal strings ไม่แปลงเป็นJavaScript Number ไม่เพิ่มstatus/phase/created_atที่projectsไม่มี created_byคือผู้สร้างเดิม ไม่ใช่ค่าที่คำนวณใหม่ตามหัวหน้าหลังโอนสิทธิ์

### GET /api/v1/projects/me

studentอ่านเฉพาะProjectของทีมที่ตนเป็นสมาชิกปัจจุบัน รวมleaderและmember ใช้sessionเดิม ไม่รับProject/Teamเป้าหมายจากclient ไม่บังคับCSRF/Origin ไม่renewsession สำเร็จ200ใช้dataรูปแบบเดียวกับPOST

กรณีไม่มีทีมตอบ404TEAM_NOT_FOUND มีทีมแต่ยังไม่มีProjectตอบ404PROJECT_NOT_FOUND ไม่ใช้200data:null ไม่เปิดรายชื่อProjectทั้งระบบ/ข้อมูลทีมอื่น ทุกresponseของสองendpointsใช้Cache-Control:no-store

### Errors

ใช้envelopeเดียวกับAuth/Team ไม่คืนrawSQL/constraint/traceback/ข้อมูลลับ:

| HTTP / code | กรณี |
|---|---|
| 401 AUTHENTICATION_REQUIRED | sessionขาด/ไม่ถูกต้อง/หมดอายุ/ถูกยกเลิก |
| 403 PROJECT_ACCESS_FORBIDDEN | advisor/coordinatorเรียกstudent endpointนี้ |
| 404 TEAM_NOT_FOUND | studentไม่มีทีมปัจจุบัน |
| 403 PROJECT_CREATION_FORBIDDEN | memberเห็นทีมแต่ไม่มีสิทธิ์สร้างProject |
| 404 PROJECT_NOT_FOUND | GETเมื่อทีมตนยังไม่มีProject |
| 409 PROJECT_ALREADY_EXISTS | POSTเมื่อทีมตนมีProjectแล้ว รวมDB UNIQUE conflict |
| 403 CSRF_INVALID / ORIGIN_NOT_ALLOWED | POSTไม่ผ่านนโยบายAuthเดิม |
| 422 VALIDATION_ERROR | name/description/JSONผิดรูปแบบหรือส่งfieldsอื่น |
| 500 INTERNAL_ERROR | configuration/storage/transaction failureที่ไม่ใช่business errorที่จำแนกได้ |

ลำดับตรวจPOST: Origin/JSON validationตามระบบเดิม → active session/CSRF/student → Team/leader → Projectซ้ำ → INSERT/transaction completion ส่วนGETไม่มีสิทธิ์เลือกProjectของทีมอื่นผ่านquery/header

## หน้าFrontendที่ยืนยันและimplementแล้ว

- ใช้Feature-basedในsrc/features/projects และroute /projects ตามรูปแบบAuth/Teamปัจจุบัน
- เพิ่มลิงก์ “โครงงานของทีม” จากหน้า/teamsสำหรับstudentที่มีทีม โดยไม่เปลี่ยนหน้า/ให้เป็นDashboard
- หน้า/projectsอ่านข้อมูลทีมจากGET /teams/meเดิม และProjectจากGETใหม่เพื่อรองรับrefresh ไม่เก็บProject/sessionลงlocalStorage/sessionStorage
- ไม่มีTeam: แสดงคำอธิบายและลิงก์ไป/teams; มีTeamแต่ไม่มีProject: leaderเห็นformชื่อ/คำอธิบาย ส่วนmemberเห็นข้อความให้หัวหน้าสร้างProject
- หลังPOST201หรือGET200แสดงชื่อ/คำอธิบายProjectเบื้องต้น ไม่มีปุ่มลบ/แก้ไข/เชิญอาจารย์/ส่งไฟล์ในรอบนี้ ไม่ถือว่าST-05ครบทุกฟังก์ชัน
- GETnetwork/500/404ที่ไม่ตรงContractแสดงerror/retry ไม่ตีความเป็นformสร้างProject; POSTไม่retryอัตโนมัติ หาก409หรือไม่ทราบผลให้ตรวจProjectผ่านGETก่อน

## Implementationและเกณฑ์ทดสอบ

1. ใช้project_app/test DBและtransaction guardเดิม ไม่มีadmin fallbackหรือgrantsเพิ่ม ตั้งapp.actor_user_idจากactive sessionแบบtransaction-local
2. ล็อกทีมผ่านv1_lock_teamก่อนINSERTตามV1 แล้วตรวจสมาชิกภาพ/leaderซ้ำ ปล่อยFK/UNIQUE/CHECK/triggersทำงาน ไม่ปิดหรือแก้constraint
3. UNIQUE projects.team_idเป็นด่านสุดท้าย แปลง23505เฉพาะpublic.projects/projects_team_id_keyเป็น409 ไม่แปลงP0001/42501ทั้งหมดด้วยข้อความtrigger
4. GETกรองProjectด้วยสมาชิกภาพactorในSQLstatementเดียว ไม่เชื่อclient-suppliedactor/team/project และไม่เผยสมาชิกภาพทีมอื่น
5. ทดสอบcreate/normalize/optionaldescription/nameขอบเขต255/IDsstrings, ไม่มีTeam/member/staff, missing/expired/revokedAuth, CSRF/Originและidentityspoof
6. ทดสอบProjectซ้ำต้องไม่เพิ่มแถว, currentTeam/GETProject/memberอ่านได้เฉพาะทีมตน, ไม่มีProject404, failureหลังINSERT/จบtransactionต้องrollbackและไม่ตอบ201
7. ทดสอบFK/immutable team_id/created_by และR-01ผ่านช่องทางที่สิทธิ์เดิมอนุญาต หากต้องใช้ownerให้จำกัดเป็นfixture/การพิสูจน์triggerภายในROLLBACK ไม่ใช้ownerสร้างProjectแทนapp
8. Browser: leaderสร้างจริง/refresh, memberอ่านและไม่เห็นform, ไม่มีTeam, validation/409/network/CSRF/sessionloss, pending-submitไม่ส่งซ้ำ, Desktop/Mobile
9. ตรวจcurrent_databaseก่อนทุกชุด เขียนเฉพาะstudent_project_management_v1_testในTransaction/ROLLBACK ตรวจmetadata/ACL/rowcountsคืนbaselineและเก็บข้อมูลเดิม ไม่สมมติว่าDBว่าง

ไม่ทำreal multi-session concurrencyด้วยการCOMMITfixtureเอง ไม่แก้Schema/RBAC/Auth/.env/Backend database config และไม่Commit/Push ผลBackendรวม150tests/Browser30tests/direct app smoke/lint/TypeScript/buildผ่านและคืนbaselineหลังROLLBACK ไม่มีงานหลักDoneเพิ่มจากการปิดcreate/readเฉพาะส่วน ดูรายงานสำหรับขอบเขตหลักฐาน

## ขอบเขตที่ผู้ใช้ยืนยัน

ยืนยันPOST/GET, request/response/error codesและหน้า/projects/ลิงก์จากteamsตามข้างต้น ไม่รวมProject update/delete, Advisor invitation, submissionหรือDashboard metrics
