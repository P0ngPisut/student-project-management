# ตรวจและส่งโค้ดในGit

รอบเตรียมhandoffนี้ **ไม่Commit/Push/merge/stageแทนเจ้าของ** เจ้าของเป็นผู้เลือกส่งชุดไฟล์หลังตรวจรายการและผลทดสอบ

## สิ่งที่ต้องอยู่ในcommitส่งต่อ

- backend runtime/Auth/Team/Project/Invitations และtests/requirements/devrequirements
- frontend routes/features/config/package.json/package-lock.json/tests/runner รวมAGENTS.mdของNext
- database schema/auth/migrations/tools/tests/README และ.gitattributesที่รักษาSQLเป็นLFตามpinnedchecksums
- docs/api, docs/database, docs/progress, docs/team และhistoricalhandoff/sourcesที่ยังใช้อ้างอิง
- .gitignore และconfigexamplesที่passwordว่าง โดยเฉพาะbackend/.env.exampleใหม่

หลายไฟล์ของรอบTeam/Project/Invitations/Provisioningเป็นuntrackedก่อนhandoff ถ้าcommitเฉพาะREADMEทีมจะไม่มีAPI/helpers/testsครบ ห้ามลบscriptsเดิมเพียงเพราะชื่อคล้ายกัน; บางตัวเป็นsharedimportsหรือหลักฐานDB-only

## สิ่งที่ไม่ส่ง

.envจริง/.env.local/privatepassword/hash/sessiontoken/DBdump, .venv, node_modules, .next, __pycache__, playwright-report/test-results/coverage และIDE/OSartifactsที่ignoreไว้ อย่าใช้git add -fเพื่อข้ามsecretignore บัญชีในPostgreSQLไม่ติดGitไปด้วย

หากใช้เว็บอัปโหลดไฟล์หรือส่งzipทั้งWorkspaceต้องคัดไฟล์เช่นกัน .gitignoreไม่ลบไฟล์จริงออกจากzip/การdrag-drop อย่าแนบ.envหรือdependencyfoldersไปให้ทีม

ตัวอย่างคำสั่งเจ้าของจากroot **เมื่อพร้อมส่งจริง**:

```powershell
git status --short
git diff --check
git ls-files --others --exclude-standard
git add -- .
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
```

ตรวจstageddiffบนเครื่องตนก่อนcommit ไม่ส่งdiffที่มีค่าprivateกลับแชท หากพบsecretให้เอาออกจากstaging/แก้exampleก่อน ไม่แก้ประวัติGitหรือforcepushเอง

หลังตรวจแล้วเจ้าของจึงใช้:

```powershell
git commit -m "Prepare tested application baseline and team handoff"
git push origin feature/database-schema
```

นี่เป็นคำสั่งแนะนำสำหรับเจ้าของ ไม่ใช่หลักฐานว่าCommit/Pushเกิดแล้ว ตรวจremoteURL/branchให้ตรงก่อนรัน ไม่pushเข้าmainโดยข้ามreview

## สมาชิกเริ่มแยกงานหลังเจ้าของPushแล้ว

```powershell
git fetch origin
git switch -c feature/submissions origin/feature/database-schema
```

ทีมMilestoneใช้ชื่อfeature/milestonesแทนfeature/submissions เริ่มจากbasecommitเดียวกันที่มีdocs/team/START_HERE.md ไม่เริ่มจากmainหรือcommitเก่าตามชื่อbranchอย่างเดียว

ก่อนmergeแต่ละPRให้บันทึกbase/head, contractsที่อนุมัติ, changedfiles, tests/DBrollbackproof และข้อจำกัด โดยเฉพาะsharedmain.py/router/OpenAPI/harness/repositoryhelperที่สองทีมอาจแก้ชนกัน อย่าforcepush/reset/rebaseงานร่วมโดยไม่ได้ตกลง
