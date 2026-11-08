# Team members — approved and implemented

วันที่2026-11-07 · P09/P15/P16 · **ผู้ใช้ยืนยันแล้ว; Backend/Frontend implemented/tested**

ขั้นต่อจาก [Team Frontend](../progress/TEAM_FRONTEND_IMPLEMENTATION_REPORT.md) ผู้ใช้ตอบ “ใช้ตามร่าง: กรอกอีเมลตรงตัวแล้วเพิ่มทันที” ยืนยันวิธีเลือกสมาชิก/API/UIในเอกสารนี้แล้ว ไม่เปลี่ยนRequirements, SQL Schema V1หรือRBAC ดู [ผลทดสอบล่าสุด](../progress/TEAM_MEMBERS_IMPLEMENTATION_REPORT.md)

## กฎที่ยืนยันแล้วจากV1

อ้างอิง [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) ส่วน3/4.2/4.4/4.5 และ [SQL](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) ฟังก์ชันv1_team_members_guard

- ผู้กระทำต้องเป็นหัวหน้าทีมปัจจุบัน ผู้ถูกเพิ่มต้องเป็นstudent และสมาชิกใหม่เริ่มด้วยrole=member
- ผู้ใช้หนึ่งคนมีสมาชิกภาพปัจจุบันได้สูงสุดหนึ่งทีม ตามUNIQUE team_members.user_id ไม่ตั้งจำนวนสมาชิกสูงสุดเพิ่มเอง
- เพิ่มได้ก่อนส่งครั้งแรก ระหว่างอาจารย์ขอแก้ไข หรือกรรมการสรุปขอแก้ไขแล้วแต่ยังไม่ส่งรอบใหม่; ห้ามระหว่างรอตรวจหรือหลังอนุมัติตามC-07 การยังไม่มีProjectไม่ทำให้เพิ่มสมาชิกไม่ได้
- ไม่มีขั้นตอบรับคำเชิญสมาชิกทีมในV1ปัจจุบัน ฟังก์ชันAdvisor Invitationเป็นคนละเรื่อง; การออกแบบให้มีขั้นตอบรับสมาชิกต้องแยกพิจารณา ไม่เพิ่มเอง
- Backendตรวจสิทธิ์ทุกคำขอ: ยังไม่Authenticate=401; ไม่มีresource/ไม่มีสิทธิ์รับรู้=404; เห็นresourceแต่ทำไม่ได้=403ตามG-12
- ลำดับรายชื่อ: leaderก่อนmember แล้วusers.full_name ASC, team_members.id ASC
- ใช้project_appและstudent_project_management_v1_testเท่านั้น ไม่มีadmin fallbackหรือสิทธิ์เพิ่ม

## ประเด็นที่ผู้ใช้ยืนยันตามร่าง

| ประเด็น | ข้อเสนอ | สถานะ |
|---|---|---|
| วิธีระบุนักศึกษา | หัวหน้าพิมพ์อีเมลที่ลงทะเบียนไว้ให้ตรงบัญชี เพิ่มเป็นmemberทันทีเมื่อผ่านกฎ ไม่มีหน้าค้นหารายชื่อผู้ใช้ทั้งหมด | ยืนยันแล้ว |
| ขอบเขตUI | เพิ่มformอีเมลและรายชื่อสมาชิกใน/teams ให้เฉพาะหัวหน้าใช้form สมาชิกทั่วไปอ่านรายชื่อได้ | ยืนยันแล้ว |
| API/response/error | สองendpointsและรูปแบบด้านล่าง | ยืนยันแล้ว |

ตัวอย่าง: บัญชีAเป็นหัวหน้าทีม กรอกstudent02@example.test ซึ่งสมัครและยังไม่มีทีม BackendตรวจsessionของAและเพิ่มบัญชีBเป็นmember โดยBไม่ต้องเปิดหน้าตอบรับ และไม่ส่งอีเมลจริง

## APIที่ยืนยันและimplementแล้ว

### POST /api/v1/teams/me/members

รับเฉพาะJSON:

```json
{"email":"student02@example.test"}
```

- ใช้session/Origin/CSRFเดิม ไม่รับteam_id, actor_user_id, user_idหรือroleจากBrowser
- ตรวจรูปแบบอีเมลและnormalizeให้ตรงAuth/V1เดิม ไม่ตรวจDNSหรือส่งอีเมล ไม่สร้างบัญชีผู้ถูกเพิ่มอัตโนมัติ
- เลือกทีมจากสมาชิกภาพของactorที่ตรวจแล้ว ไม่ใช้ทีมที่clientระบุ และตรวจactorเป็นleaderอีกครั้งภายในtransactionก่อนเขียน
- สำเร็จ201หลังtransactionจบ คืนเฉพาะสมาชิกที่เพิ่งเพิ่ม:

```json
{
  "data": {
    "id": "202",
    "user_id": "302",
    "full_name": "นักศึกษาทดสอบ",
    "role": "member"
  }
}
```

IDsเป็นdecimal strings ไม่มีemail/hash/session/ข้อมูลทีมอื่นในresponse

### GET /api/v1/teams/me/members

ใช้sessionเดิม อนุญาตstudentที่ยังเป็นสมาชิกทีมปัจจุบัน อ่านเฉพาะทีมตน ไม่บังคับCSRF/Origin และไม่renewsession สำเร็จ200:

```json
{
  "data": [
    {"id":"201","user_id":"301","full_name":"หัวหน้าทีม","role":"leader"},
    {"id":"202","user_id":"302","full_name":"นักศึกษาทดสอบ","role":"member"}
  ]
}
```

เรียงตามV1ด้านบน ไม่มีpaginationในร่างแรก และไม่เปลี่ยนresponseของ [GET /teams/me](TEAM_CURRENT_CONTRACT.md) เดิม ทุกresponseของสองendpointsใช้Cache-Control:no-store

### Errors

ใช้envelopeเดิมของAuth/Team ข้อความไม่เปิดเผยSQL/ชื่อทีมอื่น/ข้อมูลลับ:

| HTTP / code | กรณี |
|---|---|
| 401 AUTHENTICATION_REQUIRED | sessionขาด/ไม่ถูกต้อง/หมดอายุ/ถูกยกเลิก |
| 403 TEAM_ACCESS_FORBIDDEN | advisor/coordinatorเรียกendpointstudentนี้ |
| 404 TEAM_NOT_FOUND | studentไม่มีทีมปัจจุบัน |
| 403 TEAM_MEMBER_ADDITION_FORBIDDEN | เป็นmemberธรรมดาจึงอ่านทีมได้แต่เพิ่มสมาชิกไม่ได้ |
| 403 CSRF_INVALID / ORIGIN_NOT_ALLOWED | POSTไม่ผ่านนโยบายAuthเดิม |
| 404 MEMBER_NOT_FOUND | ไม่พบนักศึกษาที่มีสิทธิ์เพิ่มตามอีเมลนั้น; ใช้ข้อความเดียวสำหรับไม่พบบัญชี/บัญชีไม่ใช่student ไม่เปิดเผยrole |
| 409 MEMBER_UNAVAILABLE | studentเป้าหมายมีทีมแล้ว รวมตนเอง/สมาชิกเดิม/สมาชิกทีมอื่น ไม่คืนชื่อหรือIDทีมของเป้าหมาย |
| 409 MEMBER_ADDITION_LOCKED | phaseของProjectไม่อนุญาตตามC-07 |
| 422 VALIDATION_ERROR | emailขาด/ผิดรูปแบบ/ชนิดข้อมูลผิด หรือส่งfieldsอื่น |
| 500 INTERNAL_ERROR | storage/config/transaction failureที่ไม่ใช่business errorที่ตรวจจำแนกได้ |

การตอบ404/409เกี่ยวกับบัญชีเป้าหมายยืนยันพร้อมวิธีเลือกด้วยอีเมลแล้ว ไม่ถือว่าG-12อนุญาตuser directoryทั้งหมด ไม่เปิดเผยว่าเป็นสมาชิกของทีมใด

## Implementationและขอบเขต

- ใช้Team UOW/active sessionเดิม ตั้งapp.actor_user_idแบบtransaction-localจากactorที่ตรวจแล้ว และล็อกteamผ่านv1_lock_teamก่อนchild write
- ตรวจสมาชิกภาพ/roleซ้ำหลังteam lock แล้วล็อกProjectถ้ามีและตรวจphaseด้วยv1_topic_metadata_editable ลำดับteam→projectตรงกับV1 transfer/exit/metadata operations ไม่อ้างว่ามีconcurrency proofจากprecheck
- ใช้parameterized SQLและINSERT team_members(...,role='member') ตามgrantsเดิม ปล่อยtriggers/CHECK/UNIQUE/FKทำงาน บังคับdeferred checksที่เกี่ยวข้องก่อนตอบสำเร็จ
- UNIQUE raceยังต้องให้DBตัดสิน แปลง23505เฉพาะpublic.team_members/team_members_user_id_key ไม่แปลงP0001/42501ทั้งหมดเป็นbusiness errorโดยอ่านข้อความtrigger
- ไม่มีautomatic POST retry; ถ้าไม่ทราบผลให้โหลดรายชื่อจากGETก่อน ไม่มีidempotency guarantee
- ไม่แก้SQL/RBAC/roles/Auth contract/.env และไม่ทำremove/leave/transfer leader/Project/invitationในรอบเพิ่มสมาชิก

## เกณฑ์ทดสอบ

1. leaderเพิ่มstudentไม่มีทีมได้ในทีมที่ไม่มีProjectและphaseที่C-07อนุญาต; response201/rolemember/IDsstrings รายชื่อหลังrefreshตรงDB
2. GETเห็นเฉพาะทีมตน เรียงleaderก่อน/ชื่อ/id ไม่เผยemailหรือสมาชิกทีมอื่น; current-team endpointเดิมไม่เปลี่ยน
3. ไม่มีAuth401; staff403; studentไม่มีทีม404; memberธรรมดาGETได้แต่POST403; spoofedactor/team/roleไม่เปลี่ยนสิทธิ์
4. เป้าหมายไม่พบ/ไม่ใช่student404, มีทีมแล้ว/เพิ่มซ้ำ/ตนเอง409 ไม่เผยข้อมูลทีมอื่น; ไม่สร้างบัญชีอัตโนมัติ
5. pending review/approved/committee voteยังไม่สรุปปฏิเสธตามphaseจริง; revisionที่อนุญาตผ่าน ตรวจทั้งBackendและtrigger
6. Origin/CSRF/validation/expiry/revocation, rollbackเมื่อconstraint/storageผิดพลาด, no-store, no-session-renewal และsanitized errors
7. Frontendformเฉพาะleader, loading/error/retry/submitซ้ำ/responseหาย, Desktop/Mobile; successเชื่อมAPI/PostgreSQLจริง
8. ตรวจcurrent_databaseก่อนทุกชุด write ใช้test DBเท่านั้น ทุกfixtureTransaction/ROLLBACK ตรวจmetadata/ACL/rowcountsคืนbaseline ไม่COMMITfixtureเพื่อทำconcurrencyเอง

ผลปัจจุบัน: Backendรวม129tests (เพิ่มmember18), Browser21tests (เพิ่มmember8), direct app smoke/lint/TypeScript/buildผ่าน และsnapshotก่อน-หลังคืนbaseline ผลนี้ไม่ใช่real multi-session concurrencyหรือsuccessful runtime data COMMIT อ่านรายงานสำหรับcoverage/ข้อจำกัด ไม่เพิ่มDoneทั้งแถวหรือเปอร์เซ็นต์ความคืบหน้า
