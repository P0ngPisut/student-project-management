# ตั้งค่าเครื่องทีม — Windows/PowerShell

คู่มือนี้ใช้ฐานข้อมูลPostgreSQLในเครื่องแต่ละคน ไม่มีDBกลาง/การเปิดLANในขอบเขตรอบนี้ การติดตั้งใหม่ครบเส้นทางยังเป็นNotVerifiedดู [ผลตรวจ](HANDOFF_VERIFICATION.md); คำสั่งด้านล่างอิงไฟล์/เครื่องมือจริง ไม่ใช่ผลfreshinstallที่ทดสอบแล้ว

## 1. โค้ดและโปรแกรม

หลังเจ้าของPushชุดhandoffแล้ว:

```powershell
git clone --branch feature/database-schema --single-branch https://github.com/ponrakitk-spec/student-project-management.git
cd student-project-management
git status --short
git log -1 --oneline
```

ต้องพบdocs/team/START_HERE.mdและbackend/invitation_api.py หากไม่มีแปลว่ายังไม่ได้baseรุ่นส่งต่อ ไม่ใช้เฉพาะcommit9d07c52เดิม

- Python3.12 และPostgreSQL18.6ตามbaselineโครงการ
- Nodeสำหรับเครื่องใหม่ใช้22.xตั้งแต่22.13.0ตามenginesในlockfileของdependencyที่เข้มที่สุดที่ตรวจพบ เครื่องเดิมทดสอบด้วย20.10.0/npm10.2.3แล้วlint/buildผ่าน แต่มีenginewarning; ยังไม่ได้พิสูจน์freshinstallบนNode22 ไม่ถือว่ารุ่นเครื่องเดิมเป็นรุ่นแนะนำ
- Browsertestsใช้MicrosoftEdgeที่ติดตั้งในWindows ไม่ต้องเปลี่ยนchannelหรือดาวน์โหลดbrowserทดแทนเอง

```powershell
py -3.12 -m venv backend/.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
& .\backend\.venv\Scripts\python.exe -m pip check
Push-Location frontend
npm ci
Pop-Location
```

ไม่copy.venv/node_modules/.nextจากเพื่อนและไม่รันnpm updateแทนnpm ci ระหว่างตั้งbaseline รักษาpackage-lock/requirementsเดิม

## 2. Privateconfig

```powershell
if (-not (Test-Path -LiteralPath backend/.env)) {
    Copy-Item -LiteralPath backend/.env.example -Destination backend/.env
}
```

กรอกด้วยeditorบนเครื่องตน ไม่ส่งในGit/แชท:

| ค่า | ใช้งาน |
|---|---|
| AUTH_DB_HOST/PORT/PASSWORD | Runtimeproject_app; passwordต้องตรงroleproject_appในPostgreSQLของเครื่องตน |
| DB_HOST/PORT/USER/PASSWORD | ผู้ดูแลติดตั้ง/rollbackfixtures; installerเดิมคาดloginpostgresแล้วSETROLEowner/appตามงาน ไม่ใช้เป็นAPIfallback |
| DB_NAME | ใส่testDBตามtemplateเพื่อความปลอดภัยของlegacyconnector แต่runtime/toolsหลักpinDBเอง |

backend/.env.auth.exampleยังเป็นtemplateย่อยสำหรับruntime-only; templateครบสำหรับเครื่องทีมคือbackend/.env.example อย่าoverwrite.envเดิม มีconfigครบไม่ได้แปลว่าDBพร้อม ต้องทำ [Database Setup](DATABASE_SETUP.md)

FrontenddefaultAPIคือhttp://localhost:8000 ไม่ต้องสร้าง.env.local หากต้องระบุให้ใช้frontend/.env.exampleและใส่เฉพาะpublicAPIorigin ห้ามใส่DBsecretในNEXT_PUBLIC_*

## 3. เปิดระบบหลังDBพร้อม

Terminalจากroot:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

อีกTerminal:

```powershell
cd frontend
npm run dev -- --hostname localhost --port 3000
```

เข้าhttp://localhost:3000/login และhttp://localhost:8000/docs ใช้browserhostlocalhostตามOrigin/Cookieที่ยืนยัน ไม่เปลี่ยนเป็น127.0.0.1/LANเอง

Normalruntimeบันทึกข้อมูลเมื่อoperationสำเร็จ การทดสอบอัตโนมัติใช้rollbackfixtureด้านล่างแทนการกดnormalUIเพื่อseedข้อมูลถาวร

## 4. ตรวจรับbaselineก่อนเริ่มfeature

จากroot ไม่รันsuiteนี้พร้อมเพื่อนบนDBเดียวกัน:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Database_Schema_V1_Static_Gate
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Install --check-runtime
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api backend.tests.test_team_members_api backend.tests.test_project_api backend.tests.test_invitation_api database.tests.test_test_database database.tests.test_advisor_provision -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_api_direct_smoke
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --test-installed --workflow
```

StaticGateไม่ใช่PostgreSQLruntimecheck หากDB/role/grantsไม่ตรงให้หยุดอ่านerror อย่ารันinitialinstallerซ้ำบนตารางที่มีอยู่หรือเพิ่มappUPDATEเพื่อให้ผ่าน

จากfrontend:

```powershell
npm run lint -- --no-cache
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
npm run test:e2e
```

ปิดnormalFrontend3000ก่อนbuild/Browserและให้8001ว่าง ใช้npmrunnerเพื่อได้uniquefixturetag Backendfixture8001เตรียมstaffด้วยnon-superuserownerในtransactionแล้วserveทุกrequestเป็นeffectiveproject_app; runtime8000ยังเป็นdirectLOGINapp Roleboundaryดู [รายงานInvitations](../progress/ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md) ไม่ใช่หลักฐานrealmulti-sessionconcurrency

เมื่อเพิ่มfeatureใหม่ ให้รันtestsเฉพาะงานก่อน แล้วregression/Browserที่ได้รับผลกระทบและพิสูจน์ROLLBACKcleanup อย่าเพิ่มpermanentfixturesเพื่อหลบข้อจำกัด
