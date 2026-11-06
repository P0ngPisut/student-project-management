# SPMS Frontend

Next.js App Router + TypeScript สำหรับ Student Project Management System

## ขอบเขตปัจจุบัน

- `/register`: สมัครเป็น student ด้วยชื่อ อีเมลจำลองรูปแบบถูกต้อง และรหัสผ่าน ≥8 ตัว มี A–Z/ตัวเลขอย่างละ ≥1
- `/login`: เข้าสู่ระบบด้วยบัญชีที่มีอยู่ สมัครสำเร็จแล้วต้อง Login เอง
- `/`: ตรวจ session ผ่าน Backend และแสดงชื่อ/อีเมล/บทบาท พร้อม Logout ยังไม่ใช่ Dashboard ST-01
- Session คงที่ 8 ชั่วโมง; โหลดหน้าใหม่และกลับมาโฟกัสหน้าจะตรวจ `/auth/me` อีกครั้ง เมื่อได้ 401 จึงกลับ Login ส่วน network/server error แสดงปุ่มลองใหม่

ผู้ใช้เลือก **Feature-based**: routes อยู่ใน `src/app` ส่วน form, API client, session hook และ styles อยู่ใน `src/features/auth` ไม่มี token/password/user cache ใน localStorage หรือ sessionStorage ใช้ HttpOnly session cookie และอ่านเฉพาะ CSRF cookie สำหรับ Logout

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

Fixture ใช้ direct project_app connection ไป `student_project_management_v1_test` และ outer rollback-only transaction ทุก request ใช้ savepoint ไม่เปลี่ยน SQL/grants/roles ก่อน/หลังทดสอบตรวจ metadata/ACL/row counts และไม่มี fixture connection ค้าง ไม่รวมค่า identity sequences ที่อาจขยับแม้ ROLLBACK การอ่าน baseline ใช้ private DB config เดิมใน read-only transaction ไม่มีการพิมพ์ secrets

ผลล่าสุด **2026-11-07**: lint/TypeScript/build PASS, Browser **5/5 PASS**, baseline หลัง ROLLBACK PASS ภาพ Desktop/Mobile อยู่ใน `test-results` ที่ Git ignore; ปิด traces เพื่อไม่เก็บ session tokens ใน trace artifacts อย่าเปิด normal dev server พร้อม Browser suite บน port เดียวกัน

ยังไม่ครอบคลุม Team/Project, multi-session concurrency, HTTPS/LAN/deployment, admin provisioning หรือ password recovery อ่านสถานะต่อใน [Backlog](../docs/progress/BACKLOG.md) และ [Auth Contract](../docs/api/AUTH_CONTRACT.md)
