# SPMS Frontend

Next.js App Router + TypeScript สำหรับ Student Project Management System

สำหรับทีมWindowsที่ใช้PostgreSQLแยกเครื่อง อ่าน [Team Start Here](../docs/team/START_HERE.md) และ [Local Setup](../docs/team/LOCAL_SETUP.md) ก่อน คู่มือรวมมีfullenvtemplate/adminfixtureconfigและลำดับเตรียมDBที่จำเป็น Browsertestsไม่ใช่normalserverสำหรับseedข้อมูลถาวร

## ขอบเขตปัจจุบัน

- `/register`: สมัครเป็น student ด้วยชื่อ อีเมลจำลองรูปแบบถูกต้อง และรหัสผ่าน ≥8 ตัว มี A–Z/ตัวเลขอย่างละ ≥1
- `/login`: เข้าสู่ระบบด้วยบัญชีที่มีอยู่ สมัครสำเร็จแล้วต้อง Login เอง
- `/`: ตรวจ session ผ่าน Backend และแสดงชื่อ/อีเมล/บทบาท พร้อม Logout ยังไม่ใช่ Dashboard ST-01
- `/teams`: studentสร้างทีมพร้อมตนเป็นหัวหน้า อ่านทีม/รายชื่อสมาชิกหลังrefresh หัวหน้าเพิ่มmemberด้วยอีเมลตรงตัว สมาชิกธรรมดาอ่านรายชื่อได้; กรณีไม่มีทีมใช้404TEAM_NOT_FOUNDตามG-12 ไม่มีuser directory
- `/projects`: หัวหน้าสร้างProjectของทีม สมาชิกอ่านProjectได้ เข้าจากลิงก์ใน/teams; ไม่มีทีมแนะนำไป/teams มีทีมแต่ไม่มีProjectให้leaderเห็นformและmemberเห็นข้อความรอ ไม่มีProject delete/update UI
- `/projects/advisor-invitations`: สมาชิกอ่านประวัติ หัวหน้าเลือกอาจารย์/ส่ง/ยกเลิกpending หลังacceptedเปลี่ยนอาจารย์ไม่ได้
- `/advisor/invitations`: advisorอ่านคำเชิญตน/ตอบรับ/ปฏิเสธ จากลิงก์ในหน้าบัญชี หลังrejected/cancelledไม่คืนliveProjectcontext บัญชีadvisorต้องให้ผู้ดูแลเตรียมก่อน ไม่เปิดrole signup
- Session คงที่ 8 ชั่วโมง; โหลดหน้าใหม่และกลับมาโฟกัสหน้าจะตรวจ `/auth/me` อีกครั้ง เมื่อได้ 401 จึงกลับ Login ส่วน network/server error แสดงปุ่มลองใหม่

ผู้ใช้เลือก **Feature-based**: routesอยู่ในsrc/app ส่วนAuth/Team/Project/Invitationsอยู่ในsrc/features/auth, teams, projects, advisor-invitations ไม่มีtoken/password/user/team/Project/invitation cacheในlocalStorage/sessionStorage ใช้HttpOnly sessioncookie อ่านเฉพาะCSRFcookieสำหรับwrite requestsที่ต้องใช้

## เปิดในเครื่อง

จาก Workspace root เปิด Backend ใน terminal แรก:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

เปิด Frontend ในอีก terminal:

```powershell
cd frontend
npm install
npm run dev -- --hostname localhost --port 3000
```

เข้า [http://localhost:3000](http://localhost:3000) โดยใช้ชื่อ host `localhost` ให้ตรง Origin/Cookie ที่ยืนยัน ค่า API เริ่มต้นคือ `http://localhost:8000` ตัวอย่าง public config อยู่ใน [.env.example](.env.example) ไม่ใส่ DB password หรือ secret ลงตัวแปร NEXT_PUBLIC_*

Backend ต้องติดตั้ง Auth และตั้ง private config แล้วตาม [Installation Report](../docs/database/AUTH_INSTALLATION_REPORT.md) การใช้หน้าสมัคร/Login ของเซิร์ฟเวอร์ปกติจะบันทึกข้อมูลตาม runtime transaction จึงต้องได้รับอนุญาตเรื่องข้อมูลทดสอบถาวรก่อนใช้เพื่อทดสอบ เส้นทาง Browser tests ด้านล่างใช้ ROLLBACK โดยเฉพาะ

## ตรวจสอบและทดสอบ

จากโฟลเดอร์ `frontend`:

```powershell
npm run lint -- --no-cache
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
npm run test:e2e
```

Browser tests ใช้ Microsoft Edge ที่ติดตั้งในเครื่องและ Playwright 1.65.0 ต้องให้ ports **3000 และ 8001 ว่าง** ชุดทดสอบเปิด Frontend บน 3000 โดย override API ไป fixture 8001 เฉพาะ process ทดสอบ ไม่ใช้ Backend ปกติ 8000 และบล็อก Auth requests ที่ออกนอก 8001

Fixtureใช้student_project_management_v1_testและouterrollback-onlytransactionทุกrequestเป็นsavepoint เวอร์ชันคำเชิญเปิดexplicitowner-fixturemodeเฉพาะtestprocess เพื่อเตรียมadvisor2/coordinator1ด้วยproject_ownerที่ไม่ใช่superuser แล้วswitchเป็นeffectiveproject_appก่อนserveHTTPทั้งหมด Runtime8000ยังใช้directproject_appตามเดิม ไม่มีadminfallback ดู [roleboundary](../docs/progress/ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md) ก่อนรัน ใช้npm runnerเพื่อได้uniquetag ไม่เรียกPlaywrightตรงสำหรับsuiteนี้ ก่อน/หลังตรวจmetadata/ACL/rowcountsและfixtureconnections=0 ไม่รวมidentitysequencesที่ROLLBACKไม่คืน ไม่พิมพ์secrets

ผลล่าสุด **2026-11-07**: lint/TypeScript/build PASS, Browser **42/42 PASS** (Auth5+Team8+member8+Project9+invitation12), baselineหลังROLLBACK PASS เก็บข้อมูลเดิมไว้ ภาพDesktop/Mobileอยู่ในignoredtest-results ปิดtracesเพื่อไม่เก็บsessiontokens อย่าเปิดnormaldevพร้อมBrowser suiteบนportเดียวกัน Backend174tests/direct app boundary smokeผ่าน ดู [Invitations Report](../docs/progress/ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md)

ยังไม่ครอบคลุมออก/ถอดสมาชิก/โอนหัวหน้า/Project update/submission, multi-session concurrency, HTTPS/LAN/deployment, admin provisioning/password recoveryหรือsuccessful runtime dataCOMMIT หากGETผิดพลาดที่ไม่ตรงContractจะแสดงretryและไม่เปิดformสร้าง POSTไม่retryอัตโนมัติ เมื่อไม่ทราบผลให้ตรวจข้อมูลผ่านGET อ่าน [Backlog](../docs/progress/BACKLOG.md), [Auth Contract](../docs/api/AUTH_CONTRACT.md), [Invitations Contract](../docs/api/ADVISOR_INVITATIONS_CONTRACT.md)
