# Student Project Management System

ระบบจัดการโครงงานนักศึกษา ใช้ FastAPI + PostgreSQL และ Next.js/TypeScript

## สถานะปัจจุบัน

- Backend Auth: สมัคร student, Login, Logout และ GET /api/v1/auth/me
- Frontend Auth: /register, /login และหน้าข้อมูลบัญชีที่ / แบบ Feature-based ใน src/features/auth
- Database V1: public 14 ตาราง / 86 columns / 28 foreign keys; ส่วนขยาย Auth แยก auth.credentials และ auth.sessions
- Session คงที่ 8 ชั่วโมง; อีเมลจำลองได้แต่ต้องรูปแบบถูกต้อง รหัสผ่าน ≥8 ตัว มี A–Z และตัวเลขอย่างละ ≥1
- Team/Project API และหน้าธุรกิจ ST-01–ST-09 ยังไม่พัฒนา หน้าบัญชีปัจจุบันไม่ใช่ Dashboard

รายละเอียดและหลักฐานล่าสุด: [Backlog](docs/progress/BACKLOG.md), [Schema V1 Reference](docs/database/SCHEMA_V1_REFERENCE.md), [Auth Contract](docs/api/AUTH_CONTRACT.md), [Auth Installation Report](docs/database/AUTH_INSTALLATION_REPORT.md)

## โครงสร้าง

| โฟลเดอร์ | เนื้อหา |
|---|---|
| backend/ | FastAPI, Auth, dependencies และ HTTP/unit tests |
| frontend/ | Next.js routes/features และ Browser tests |
| database/schema/ | SQL V1 และ RBAC ต้นฉบับ |
| database/auth/ | SQL review ส่วนขยาย Auth |
| database/tests/ | Static/DB regression และ helpers ที่ tests อื่น import ใช้ |
| database/tools/ | เครื่องมือตรวจ/ติดตั้ง อ่านข้อจำกัดก่อนรัน |
| docs/ | ข้อกำหนด, API contracts, ผลทดสอบ, backlog และเอกสารประวัติ |

## GitHub กับฐานข้อมูลของทีม

Clone โค้ดไม่ได้คัดลอก PostgreSQL service, database, roles, รหัสผ่าน หรือข้อมูลในเครื่องเจ้าของโปรเจกต์ไปด้วย Repository นี้มี SQL และเครื่องมือสำหรับเตรียมฐานข้อมูล แต่ยังไม่มีชุด bootstrap เครื่องใหม่ที่ตรวจรับครบทุกขั้น

| วิธีทำงาน | สมาชิกต้องเตรียมอะไร | ข้อมูลที่มองเห็น |
|---|---|---|
| แต่ละคนใช้ PostgreSQL ในเครื่องตนเอง — แนะนำสำหรับพัฒนา | ติดตั้ง PostgreSQL, เตรียม roles/schema/RBAC/Auth และตั้ง .env ของตนเอง | โครงสร้างตรงกันเมื่อใช้ baseline รุ่นเดียวกัน แต่บัญชี/ข้อมูลแต่ละเครื่องแยกกัน |
| แต่ละคนรัน Backend ในเครื่อง แล้วเชื่อม DB กลาง | ผู้ดูแลเตรียม test DB กลางและสิทธิ์เครือข่าย; แต่ละ Backend ตั้ง AUTH_DB_HOST/PORT/PASSWORD ส่วนตัวให้ตรงปลายทาง | อ่าน/เขียนฐานข้อมูลชุดเดียวกัน การทดสอบจึงอาจกระทบกัน |

ทั้งสองแบบใช้ชื่อ **student_project_management_v1_test** เท่านั้น ห้ามใช้/เข้าถึงฐานข้อมูลหลัก student_project_management ตามขอบเขตปัจจุบัน ยังไม่ได้ตั้ง DB กลางหรือเปิดเครือข่ายในงานนี้

สำหรับ DB กลาง ผู้ดูแลต้องกำหนด listen_addresses, pg_hba.conf และ firewall ให้เฉพาะเครื่องที่อนุญาต รวมถึงพิจารณาการเข้ารหัสช่องทาง ห้ามให้ Frontend ต่อ PostgreSQL หรือใส่ DB password ลง NEXT_PUBLIC_* ส่วน Frontend/Backend ที่รันในแต่ละเครื่องยังใช้ localhost:3000/8000 ตามแบบที่ยืนยัน การเปิด Backend/Frontend กลางบน LAN/HTTPS ต้องทบทวน Origin/CORS/Cookie แยก ดู [PostgreSQL connection settings](https://www.postgresql.org/docs/18/runtime-config-connection.html) และ [client authentication](https://www.postgresql.org/docs/18/client-authentication.html)

## เตรียมเครื่องสมาชิกทีม

คำสั่งด้านล่างเป็น PowerShell จาก root ของ Repository หลัง clone branch ที่มีงานล่าสุดแล้ว

### 1. Dependencies

ใช้ Python 3.12 ตาม environment ที่ทดสอบ และ PostgreSQL 18.6 ตาม baseline โปรเจกต์ สำหรับ Windows64-bit แนะนำ Node22.x ตั้งแต่22.13.0 ตาม engines ของแพ็กเกจที่ล็อกไว้สำหรับ platform นี้ ปัจจุบันเครื่องเดิมใช้ Node20.10.0 และพบ engine warning ของ eslint-visitor-keys5.0.1 แม้ lint/build ผ่าน จึงไม่ถือว่าเป็น Node รุ่นแนะนำสำหรับเครื่องใหม่ ยังไม่ได้ทดสอบ fresh install บน Node22 ในงานนี้

```powershell
py -3.12 -m venv backend/.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
Push-Location frontend
npm ci
Pop-Location
```

อย่าส่งต่อ .venv, node_modules หรือ .next ให้ติดตั้งใหม่ตาม requirements/lockfile ของ commit เดียวกัน

### 2. Database baseline — ยังต้องเตรียมแยกก่อนใช้งานจริง

ผู้ดูแลของแต่ละ PostgreSQL instance ต้องเตรียมตามลำดับที่ตรวจรับ:

1. Roles: postgres สำหรับติดตั้ง/บริหาร, project_owner เป็น NOLOGIN และไม่ใช่ superuser, project_app เป็น LOGIN ที่ไม่มีสิทธิ์ elevated หรือสมาชิกของ owner/broad data roles
2. Database student_project_management_v1_test เจ้าของ project_owner และสิทธิ์ CONNECT ที่จำเป็น
3. ติดตั้ง SQL V1 และ RBAC ด้วย project_owner ตามขั้นตอนที่อนุมัติสำหรับ **ฐานข้อมูลว่าง** ไม่ใช้ตัวติดตั้งเริ่มต้นกับ DB ที่มีตารางอยู่แล้ว
4. ติดตั้งส่วนขยาย Auth ตาม [Database README](database/README.md) และ [Installation Report](docs/database/AUTH_INSTALLATION_REPORT.md) ให้ owner/grants ตรงแบบ ไม่มีบัญชีจำลองถาวรจากการติดตั้ง
5. ตรวจชื่อ DB, roles/ownership, functions/triggers และ effective privileges ก่อนทดสอบข้อมูลด้วย transaction/ROLLBACK

ข้อจำกัดที่พบจาก source ปัจจุบัน:

- P06: persistent test DB ของเครื่องเดิมยังขาด public.v1_lock_team เทียบกับ SQL source ไม่ถือว่า clone แล้วได้ baseline เดียวกับเครื่องเดิมอัตโนมัติ
- ตัวติดตั้ง RBAC เดิม Database_Schema_V1_RBAC_Test_Apply_Only.py ปฏิเสธกรณี DB_NAME ใน config เท่ากับ test DB จึงยังใช้เป็นคำสั่ง setup เครื่องใหม่ต่อกันทันทีภายใต้นโยบาย test-only ไม่ได้ **ห้ามตั้งค่าไป DB หลักเพื่อข้าม guard** ต้องตรวจรับ/อนุมัติการแก้เครื่องมือแยก
- Readonly_Preflight เดิมใช้ backend.database และยังไม่บังคับ target test DB ห้ามรันในงาน test-only จนแก้ guard ตามขอบเขตที่อนุมัติ
- ไม่ได้ทดสอบ fresh install ของทีมในงานจัดไฟล์นี้ และไม่ได้เปลี่ยน SQL/roles/grants เพื่อแก้ข้อจำกัดดังกล่าว

ถ้าเลือกย้ายฐานข้อมูลด้วย dump/restore ให้ทำแผนแยก ไม่อัปโหลด dump ที่มีข้อมูลบัญชี/hash/session ลง GitHub และต้องเตรียม roles ก่อน restore เพื่อรักษา ownership/grants ดู [PostgreSQL backup/restore](https://www.postgresql.org/docs/18/backup-dump.html) ยังไม่มีการ export/restore ในงานนี้

### 3. Private config

สร้าง backend/.env จาก template **เฉพาะเมื่อยังไม่มีไฟล์**:

```powershell
if (-not (Test-Path -LiteralPath backend/.env)) {
    Copy-Item -LiteralPath backend/.env.auth.example -Destination backend/.env
}
```

กรอกค่าจริงในเครื่องตนเอง ไม่ส่งใน GitHub/แชท:

| ตัวแปร | ใช้กับอะไร |
|---|---|
| AUTH_DB_HOST | host ของ PostgreSQL; ค่าเริ่มต้น localhost สำหรับ DB ในเครื่อง |
| AUTH_DB_PORT | port ของ PostgreSQL; ค่าเริ่มต้น 5432 |
| AUTH_DB_PASSWORD | รหัส PostgreSQL ของ project_app ใน instance นั้น ไม่ใช่รหัสนักศึกษา |

Auth runtime pin DB เป็น student_project_management_v1_test และ role เป็น project_app ในโค้ด ไม่ใช้ postgres/project_owner แทน app Config ตัวอย่างต้องไม่มีรหัสจริงและรหัสแต่ละเครื่องไม่จำเป็นต้องเหมือนกัน

DB tests/installer บางตัวต้องใช้ DB_HOST, DB_PORT, DB_USER และ DB_PASSWORD สำหรับ fixture/deployment เพิ่มใน backend/.env โดยผู้ดูแลตามขั้นตอนที่อนุมัติ ไม่ใช้ admin config แทน AUTH_* และไม่คัดลอก DB_NAME ของฐานข้อมูลหลักเพื่อให้เครื่องมือเก่ารันผ่าน รายละเอียดข้อจำกัดอยู่ในขั้น baseline ด้านบน

Frontend เริ่มต้นเรียก http://localhost:8000 โดยไม่ต้องสร้าง config ถ้าต้องระบุใช้ frontend/.env.example เป็นแบบสำหรับ .env.local และตั้งเฉพาะ NEXT_PUBLIC_API_BASE_URL ห้ามใส่ password/secret ใน Frontend

### 4. เปิดระบบเมื่อ baseline/config พร้อมแล้ว

Terminal แรก จาก root:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Terminal ที่สอง:

```powershell
cd frontend
npm run dev -- --hostname localhost --port 3000
```

เข้า http://localhost:3000 และ Swagger ที่ http://localhost:8000/docs ใช้ host localhost ให้ตรง Origin/Cookie ที่ยืนยัน เซิร์ฟเวอร์ปกติออกแบบให้บันทึกข้อมูลเมื่อสมัคร/Login สำเร็จ; การทดสอบเขียนข้อมูลของทีมยังต้องใช้ชุด rollback-only ตามขอบเขต ไม่ใช้การกดหน้าจอปกติแทน ROLLBACK tests

## การตรวจสอบ

ไม่เชื่อม DB:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Database_Schema_V1_Static_Gate
Push-Location frontend
npm run lint -- --no-cache
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
Pop-Location
```

หลัง baseline/private config พร้อมและอยู่ในขอบเขตทดสอบที่อนุมัติ:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api -q
```

Browser tests ต้องติดตั้ง Microsoft Edge และเว้น ports3000/8001 ให้ชุดทดสอบเปิดเอง จาก frontend ใช้ npm run test:e2e ซึ่งเรียก fixture rollback-only ไม่ใช้ Backend ปกติ ดู [Frontend README](frontend/README.md) สำหรับวิธีใช้/ข้อจำกัด ไม่รันพร้อมกับ normal Frontend3000

ผลจากรอบพัฒนา Auth ก่อนงานจัดไฟล์: Backend65 + Browser5, lint/TypeScript/build และ baseline หลัง ROLLBACK ผ่าน ผลนี้ไม่ใช่ fresh install ของทีม หรือหลักฐานว่า business workflows/Concurrency พร้อมแล้ว

## ก่อน Commit/Push

- เก็บ source, SQL, tests/tools, docs, requirements, package.json/package-lock.json และ config ตัวอย่างที่ไม่มี secrets
- ไม่เพิ่ม .env จริง, virtual environments, dependencies/cache, test artifacts หรือ DB backups
- ตรวจ git status --short และ git diff --cached ก่อน commit; สคริปต์ DB/tools และไฟล์ Auth หลายไฟล์เดิมเป็น untracked ต้องเลือกเพิ่มให้ครบ
- .gitignore ไม่ลบรหัสที่เคย commit ไปแล้ว หากพบการเผยแพร่รหัสในอดีตให้จัดการแยก งานนี้ไม่ได้ commit/push หรือแก้ประวัติ Git
