# Create Team Backend — 2026-11-07

รายงานประวัติรอบ Backend create: **POST /api/v1/teams implemented/tested ตามรูปแบบที่ผู้ใช้ยืนยัน** ผล101tests/checksumsด้านล่างเป็นหลักฐาน ณ รอบนั้น ต่อมาพัฒนาFrontend /teams และGETทีมของตนแล้ว ดู [รายงานล่าสุด](../progress/TEAM_FRONTEND_IMPLEMENTATION_REPORT.md) ยังไม่พิสูจน์multi-session Concurrency

ผู้ใช้ยืนยัน “ใช้รูปแบบนี้ตามร่าง” หลังสรุปrequest name/description, ใช้Session/CSRFจากLogin, สร้างผู้ใช้ปัจจุบันเป็นหัวหน้า, IDsเป็นstring และสถานะ201/401/403/409/422/500 ตาม [Contract](TEAM_CREATE_CONTRACT.md)

## ไฟล์และพฤติกรรม

| ไฟล์ | หน้าที่ |
|---|---|
| [team_api.py](../../backend/team_api.py) | strict request/response, Auth/CSRF/student check, sanitized validation/response |
| [team_store.py](../../backend/team_store.py) | project_app/test DB UOW, actorGUC, parent lock, Team+leader, forced deferred, narrow UNIQUE mapping |
| [main.py](../../backend/main.py) | เพิ่มTeam routerและdispatch validation/storage errorsเฉพาะTeam; no-store; Auth/root/CORSเดิมคงพฤติกรรม |
| [test_team_api.py](../../backend/tests/test_team_api.py) | HTTP/actual PostgreSQL27tests พร้อมouterROLLBACK/installed baseline comparison |
| [team_api_direct_smoke.py](../../backend/tests/team_api_direct_smoke.py) | Auth→Teamผ่านASGIด้วยapp-password connectionจริง ไม่มีowner switch |
| [auth_browser_server.py](../../backend/tests/auth_browser_server.py) | rollback-only fixture8001ครอบทั้งAuthและTeam UOW เพื่อไม่ให้routeใหม่หลุดไปruntime connection |
| [test_auth_security.py](../../backend/tests/test_auth_security.py) | ปรับOpenAPI expectationให้รวมTeam route โดยยังพิสูจน์ว่าimport/OpenAPIไม่เชื่อมDB |

ไม่มีSchema/RBAC/role/password/.env/Frontend changesในรอบนี้ SQL V1/Auth/repair reviewเดิมไม่เปลี่ยน test DBยังมีpublic14/86/28/52functions และauth2/6/2/2functions

## Transaction/security

อ่านactive sessionจากDBในtransactionเดียวกับการเขียน ตรวจOrigin/CSRF/student แล้วตรวจmembership ไม่รับactorจากJSON/header/query ตั้งapp.actor_user_idจากusers.idที่resolveแล้วแบบtransaction-localและparameterized

กำหนดTeam cardinality constraintsสองตัวเป็นDEFERREDก่อน INSERT Team ล็อกparentผ่านhelperที่ติดตั้งแล้ว INSERTผู้สร้างเป็นleader แล้วforce IMMEDIATEก่อนคืนผล ไม่มีProject/สมาชิกอื่นเพิ่ม ไม่มีdirect users writeหรือapp UPDATE grant

การตอบ201อยู่หลังUOWออกสำเร็จ Runtimeออกแบบให้COMMITก่อนresponse แต่testsยืมconnectionในouterROLLBACKและใช้savepointsต่อrequest จึงยังไม่ใช่หลักฐานsuccessful live data COMMIT อ้างอิง [Psycopg transaction semantics](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)

พบระหว่างทดสอบว่าtransactionร่วมอาจมีTeam constraintsเป็นIMMEDIATEจากoperationก่อนหน้า ทำให้INSERT Teamถูกตรวจ cardinalityก่อนใส่leader จึงระบุDEFERRED→IMMEDIATEในcontrolled operationให้ชัด และเพิ่มtestสำหรับสภาวะนี้ ผ่านโดยไม่เปลี่ยนSchema/ปิดtriggers ดู [PostgreSQL SET CONSTRAINTS](https://www.postgresql.org/docs/18/sql-set-constraints.html)

PG23505แปลง409เฉพาะschema/table/constraintของteam_members.user_id ทั้งprecheckและDBunique path ข้อผิดพลาด42501จากDB grants/lockingและconstraintอื่นเป็นsanitized500 ไม่แปลงเป็น403ของผู้ใช้หรือสลับใช้admin

Validationไม่ส่งPydantic input/body/ctxหรือfieldชื่อที่clientสร้างเองกลับไปในerror ใช้fixed field/code lists และปฏิเสธNUL/invalid Unicodeที่DBtextเก็บไม่ได้ ไม่มีการเพิ่มชื่อUnique/description length limit อ้างอิง [FastAPI validation handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/) และ [Pydantic validators](https://docs.pydantic.dev/latest/concepts/validators/)

## ผลตรวจรอบนี้

| ชุด | ผล |
|---|---|
| Team API | PASS27 tests (หลายtestมีsubcases) ไม่ใช่27requirements |
| รวมBackend/boundary | PASS101 = Auth65 + Team27 + offline boundary9 |
| Direct app ASGI smoke | PASS: identityเป็นproject_appทั้งsession/current user, unsigned401, Register201, Login200, CSRF403, Team201, duplicate409/no orphan และROLLBACK |
| Live TCP บนrollback fixture8001 | PASS401→Register201→Login200→CSRF403→Team201→duplicate409; user/leaderตรงกันและdescription normalize; หลังหยุดfixture metadata/ACL/row countsตรงก่อนทดสอบ, fixture_connections=0, total_rows=0 |
| Baseline cleanup | ทุกDBwriteอยู่ในtransaction/ROLLBACK คงinstalled52functions/เดิม ไม่มีfixtureค้าง ไม่รวมidentity sequence values |
| Normal Backend/OpenAPI | เปิดlocalhost:8000แล้ว GET /docs=200 และ /openapi.jsonมีTeamPOST/201 รวม6paths ไม่มีsuccessful data POSTไปnormal serverในรอบนี้ |

Coverageรวมname/type/length/Unicode/trim, optionaldescription, duplicateชื่อข้ามstudent, role/identity spoof, missing/expired/revoked session, CSRFผูกsession, Origin/CORS, BIGINTจริงเกิน2^53ส่งstring, duplicate membership, narrow23505 mapping, leader/deferred/transaction-completion failures, DB permission500 และno secret reflection

การจำลองstale precheckใช้mockเฉพาะผลprecheck แต่ให้real PostgreSQL UNIQUEปฏิเสธและROLLBACKจริง ไม่ใช่การส่งrequestพร้อมกันสองsessions ส่วนtransaction completion failureจำลองก่อนออกsavepoint ไม่ได้ทำให้เกิดreal COMMIT failureที่เก็บข้อมูลถาวร

Fixturesอาจใช้effective project_ownerสร้างadvisor/coordinatorสำหรับnegative403แล้วสลับเป็นproject_appก่อนrequests ผลdirectASGI/TCPแยกใช้project_app connectionจริงและไม่มีowner fallback/role switchในการทำrequest

## Source hashes รุ่นที่ทดสอบ

| File | SHA-256 |
|---|---|
| backend/team_api.py | 2b58b29ea691cfde71580cdc292ba5ae7f0a0f16897b122b9f9fabb11d435f2b |
| backend/team_store.py | 9aec19b2f2e4ab52ac89d812161c086f09ec371b22b79417b239f44d9da0742b |
| backend/main.py | 9c382458a945c2f4e7cedca17bf14b105ec3fb8a938919c399feb59c2a6f9d2b |
| backend/tests/test_team_api.py | 5f4837924adbb5e6425d9c7688e341b839f46710cfead2a9ffe7b4a07386fa40 |
| backend/tests/team_api_direct_smoke.py | 65249b7d6a35db223c6821fe1cb5c4d7898ec89ab51b13b6412fc4e2a707f4c7 |
| backend/tests/auth_browser_server.py | da38b06257724d3f7bcc3d370ed144fa3f722416d2efbb33c2676acdecce2b10 |

## รันซ้ำ

จากroot ต้องมีinstalled baseline/private configพร้อม:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api database.tests.test_test_database -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_api_direct_smoke
```

สำหรับTCP fixture ใช้SPMS_AUTH_BROWSER_ROLLBACK=1เฉพาะprocessที่เปิด backend.tests.auth_browser_server บน8001 ต้องให้portว่างและตรวจsnapshotหลังปิด ห้ามใช้fixtureเป็นเซิร์ฟเวอร์ปกติเพราะข้อมูลไม่persist ส่วนBackendปกติ8000เป็นruntimeที่ออกแบบให้COMMITเมื่อสำเร็จ ไม่ใช้แทนrollback tests

## สิ่งที่ยังเหลือ

- Frontendสร้างทีมและการอ่านข้อมูลทีมหลังrefreshยังไม่มี ไม่เพิ่มGET/navigation/idempotency/retry policyในรอบBackendนี้
- TEAM-10/Concurrencyจริง, successful live data COMMIT, full-system security/UAT และfresh installเครื่องทีมยังไม่รับรอง
- scopeรอบนี้ไม่เพิ่มProject/member management endpoints ไม่แก้Requirements และไม่Commit/Push Git
