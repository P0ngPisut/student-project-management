# Current Team — approved and implemented

วันที่2026-11-07 · สถานะ **ผู้ใช้ยืนยันคำตอบล่าสุดตาม G-12 แล้ว; Backend GET และ Frontend /teams implemented/tested**

ใช้ประกอบหน้าสร้างทีม/อ่านทีมหลังrefresh ไม่ใช่Team list/Member management/Project API และไม่เปลี่ยนSchema V1

การอ่าน/เพิ่มรายชื่อสมาชิกมีendpointแยกตาม [Members Contract](TEAM_MEMBERS_CONTRACT.md) ที่ยืนยันและimplementภายหลัง ไม่เพิ่มfieldsรายชื่อเข้าresponseของGET /teams/meเดิม

## รูปแบบที่ยืนยันหลังตรวจ G-12

GET /api/v1/teams/me ใช้session cookieเดิม อ่านเฉพาะทีมที่ผู้ใช้ปัจจุบันเป็นสมาชิก ไม่รับuser_id/team_idเพื่อเลือกเป้าหมายจากBrowser จำกัดendpointนี้สำหรับstudent ส่วนAdvisor/Coordinatorที่มีสิทธิ์เห็นTeamผ่านProject contextจะเป็นContractแยก

สำเร็จ200:

```json
{
  "data": {
    "id": "101",
    "name": "ทีมตัวอย่าง",
    "description": null,
    "membership": { "id": "201", "role": "leader" }
  }
}
```

IDsเป็นdecimal strings บทบาทmembershipมีleader/member ไม่ส่งemail/รายชื่อสมาชิกอื่น/Project หรือข้อมูลลับ ไม่เพิ่มคอลัมน์status/created_at/created_byที่teamsไม่มี

| สถานะ | ความหมาย |
|---|---|
| 200 | ทีมปัจจุบันและmembershipของผู้ใช้เอง |
| 401 AUTHENTICATION_REQUIRED | ไม่Login/sessionไม่ถูกต้องหรือหมดอายุ |
| 403 TEAM_ACCESS_FORBIDDEN | endpointนี้ไม่รองรับadvisor/coordinator |
| 404 TEAM_NOT_FOUND | ผู้ใช้studentยังไม่มีทีม ยึดG-12กรณีไม่มีresource |
| 500 INTERNAL_ERROR | sanitized storage/config error |

ข้อเสนอแรกใช้200data:nullเมื่อไม่มีทีม ต่อมาพบData Dictionary4.4/G-12ระบุ404เมื่อไม่มีresource ผู้ใช้ยืนยันคำถามแก้ไขล่าสุดว่า “ใช้ Contract นี้ตาม G-12” จึงใช้404TEAM_NOT_FOUNDเท่านั้น ไม่รองรับ200data:nullเป็นempty state

GETเป็นการอ่าน ไม่บังคับCSRF/Originและไม่ต่ออายุsession ใช้CORS/credentialsตามAuthเดิม ทุกresponse no-store การอ่านข้อมูลใช้membershipของactorที่Backendตรวจแล้ว ไม่ใช้ค่าจากheader/query/client stateเป็นสิทธิ์ ใช้JOIN statementเดียวกรองm.user_idด้วยusers.idจากactive session ไม่เผยชื่อทีมที่ผู้ใช้ไม่ได้เป็นสมาชิก

## หน้าจอที่ implement

ใช้Feature-basedในfrontend/src/features/teams หน้า/teamsจากลิงก์ในหน้าบัญชีของstudent เมื่อได้404TEAM_NOT_FOUNDจะแสดงformชื่อ/คำอธิบาย หลังPOST201แสดงค่าที่Backendคืนพร้อมบทบาทleader เมื่อเข้าหน้าใหม่/refreshจะอ่านGETจากBackend ไม่เก็บข้อมูลทีมในlocalStorage/sessionStorageและไม่POSTซ้ำอัตโนมัติเมื่อเครือข่ายผิดพลาด

หากGETเกิดnetwork/500/404ที่ไม่ใช่TEAM_NOT_FOUNDหรือresponseผิดรูปแบบ แสดงerror/retryแทนformสร้างทีม หากPOST409หรือไม่ทราบผลเพราะresponseหาย มีปุ่มตรวจสอบทีมผ่านGET ไม่มีautomatic retryของPOST ไม่ใช่idempotency guarantee

Frontendguardไม่แสดงformให้advisor/coordinator และBackendตรวจrole/สมาชิกภาพซ้ำทุกคำขอ ผลปัจจุบัน Backend111tests + Browser13ผ่านและคืนbaselineหลังROLLBACK ดู [Frontend Team Implementation Report](../progress/TEAM_FRONTEND_IMPLEMENTATION_REPORT.md) ไม่มีSchema/RBAC/.env/GitCommit/Pushในรอบนี้
