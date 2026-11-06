# Student Project Management System — Project Handoff for Codex

> วันที่จัดทำเอกสาร: 6 พฤศจิกายน 2026  
> วัตถุประสงค์: ส่งต่อ **ข้อมูลและสถานะจากเอกสารที่มีอยู่** ให้ Codex ใน VS Code เพื่อตรวจสอบความสอดคล้องกับโค้ดและรับช่วงพัฒนาในขั้นต่อไป  
> ปรับเอกสารส่งต่อหลังตรวจ Workspace และจัดโฟลเดอร์วันที่ 6 พฤศจิกายน 2026 ส่วน sources เป็นประวัติเดิม ไม่ใช่หลักฐาน implementation ปัจจุบัน

**เริ่มที่เอกสารปัจจุบัน:** [Schema V1 Reference](../database/SCHEMA_V1_REFERENCE.md), [Backlog](../progress/BACKLOG.md), [วิธีเรียกสคริปต์](../../database/README.md) และ [Progress Report Template](../progress/PROGRESS_REPORT_TEMPLATE.md)

ขอบเขตที่ผู้ใช้อนุมัติในรอบนี้คือจัดโฟลเดอร์ Database, ปรับ path/import และเอกสาร/backlog ไม่รวมแก้ Backend/Frontend/Business Rules หรือ COMMIT ลง DB คำสั่งผู้ใช้ล่าสุดมีผลเหนือรายการงานเริ่มต้นในเอกสารส่งต่อเก่า

## 0. กติกาสำหรับ Codex (อ่านก่อน)

1. **ห้ามแก้ไข สร้าง ลบ หรือย้าย Source Code / Database / UI โดยอัตโนมัติ** เพียงเพราะได้รับเอกสารนี้ การอ่านและรายงานสถานะเป็นงานแรกเท่านั้น
2. ก่อนแก้ไขส่วนใด ต้องให้ผู้ใช้ระบุขอบเขตงานและอนุญาตชัดเจน **อย่าแก้ส่วนอื่นที่ไม่ได้สั่ง**
3. หากข้อกำหนดไม่ชัดหรือแหล่งข้อมูลขัดกัน ให้รายงานประเด็นที่ต้องยืนยัน **ห้ามเดากฎธุรกิจหรือสิทธิ์การใช้งาน**
4. ใช้ไฟล์จริงใน Repository เพื่อยืนยันสถานะ implementation; ใช้เอกสารนี้เป็นประวัติการตัดสินใจ ไม่ใช่หลักฐานว่าโค้ดปัจจุบันเหมือนเดิม
5. ห้ามรันคำสั่ง destructive, DB migrations, seed, `DROP`, `DELETE`, หรือทดสอบที่เขียนข้อมูลลง DB โดยไม่ได้รับอนุญาตเฉพาะงาน
6. ห้ามแสดง/คัดลอกค่า secrets จาก `.env` หรือ environment variables มาใส่ในรายงาน/commit
7. หากพบเอกสาร Database V1 ทั้งสามไฟล์ ให้ตรวจสอบเวอร์ชัน/ข้อแตกต่างก่อนถือว่าเอกสารใดเป็น final

## 1. ขอบเขตและแหล่งที่มาของการสรุป

เอกสารนี้สังเคราะห์จากไฟล์บทสรุป 5 ไฟล์ที่แนบใน `sources/` โดยคัดเนื้อหาที่ใช้งานได้สำหรับ Codex และเก็บไฟล์ต้นทางไว้โดย **ไม่แก้ไข**:

| Source (ในโฟลเดอร์ `sources/`) | ประเด็นที่รองรับ |
|---|---|
| `ทำหน้า Frontend.txt` | ผลตรวจ Next.js และประเด็นตัดสินใจเรื่องโครงสร้าง Frontend |
| `Backend.txt` | ผลทดสอบการเชื่อมต่อ FastAPI/Python กับ PostgreSQL |
| `Data base.txt` | สถานะ Database V1; ชื่อไฟล์ Data Dictionary, SQL draft, review report; กฎ R-01 |
| `ทำหน้า UI.txt` | ข้อกำหนด Wireframe V1 9 หน้าจอ; User Flow และส่วนที่ยังไม่กำหนด |
| `วิเคราะห์ความต้องการระบบ.txt` | แนวทาง Requirements, แผน Agile/Scrum 4 สัปดาห์ และการจัดลำดับ MVP |

**ข้อจำกัดของแหล่งข้อมูล:** ทั้ง 5 ไฟล์เป็นข้อความสรุปจากการสนทนาก่อนหน้า ไม่ใช่การตรวจ Repository โดยตรง เอกสารรายวิชา 8 หัวข้อและเสียงสัมภาษณ์ต้นฉบับไม่พบใน Workspace จึงเป็น Not Verified ส่วนไฟล์ Database ที่เคยไม่ได้แนบมากับ handoff พบใน Workspace แล้วและย้ายไว้ใน `database/schema/` กับ `docs/database/`

## 2. เป้าหมายของระบบที่มีในเอกสาร

ระบบจัดการโครงงานนักศึกษาและติดตามความคืบหน้า (Student Project Management System) มีแนวทางให้รองรับ:

- การจัดการทีมและโครงงานของนักศึกษา
- การเชิญอาจารย์ที่ปรึกษา และกระบวนการยื่น/ตรวจ/แก้ไข/อนุมัติโครงงาน
- Milestone, Task, Deadline, ผู้รับผิดชอบ และ Progress/Timeline
- เอกสาร, Feedback, การมีส่วนร่วม และการประเมินผลตามลำดับการพัฒนา
- บทบาทที่กล่าวถึงในแผน: นักศึกษา, หัวหน้าทีม, อาจารย์ที่ปรึกษา, กรรมการ และผู้ประสานงานรายวิชา

**ระวัง:** เนื้อหาชุดนี้ส่วนหนึ่งเป็นข้อเสนอและเป้าหมายพัฒนา ไม่ได้หมายความว่าทุกฟังก์ชันได้รับการยืนยันเป็น Requirement ขั้นสุดท้ายหรือมีโค้ดแล้ว

## 3. Frontend — สถานะตามหลักฐานเดิม

**ผลตรวจโค้ดล่าสุด:** `frontend/src/app/page.tsx` เป็น starter Next.js ยังไม่มี ST-01–ST-09 และ business API calls; lint/TypeScript ผ่านในรอบ audit แต่ production build/เปิดเว็บสดไม่ได้ตรวจซ้ำ

**Technology:** Next.js, TypeScript (ระบุในผลการตรวจ)

สถานะที่เคยรายงานว่าผ่าน:

- `npm run lint`: ผ่าน ไม่มี Error
- `npm run build`: ผ่าน
- TypeScript: ผ่าน
- Static Page Generation: 4/4
- Development Server: เคยทดสอบเปิดเว็บได้

ข้อสรุปในบทสนทนานั้น: **Project Setup สำเร็จ** แต่ยังไม่ถือว่า Implement หน้าฟังก์ชันตาม Wireframe แล้ว

**จุดที่ยังไม่ได้ยืนยัน:** การจัด Folder Structure เป็น `Feature-based` (เช่น `projects`, `teams`, `milestones`, `tasks`) หรือ `Layer-based` (`components`, `services`, `hooks`, `types`) ยังอยู่ในขั้นให้ผู้ใช้เลือก ห้ามเลือกเองจากคำว่า “แนะนำ” ในบทสนทนา

**งานของ Codex:** ตรวจจากโค้ดปัจจุบันว่าโครงสร้างใดถูกใช้จริง มีหน้า/route/component ใดบ้าง และคำสั่ง validation ยังมีผลอย่างไร โดยยังไม่เปลี่ยนโครงสร้าง

## 4. Backend — สถานะตามหลักฐานเดิม

**ผลตรวจโค้ดล่าสุด:** มี `GET /` ใน `backend/main.py` และ ASGI smoke ตอบ 200 แบบไม่ต่อ DB; ไม่มี business endpoints หรือ request ที่ใช้ DB engine แม้ `backend/database.py` มี connector ห้ามรันคำสั่งเชื่อมต่อฐานข้อมูลหลักที่ปรากฏในประวัติด้านล่าง

**Technology:** FastAPI, Python, PostgreSQL, SQLAlchemy, psycopg; มีการอ่านค่าจาก `.env`

สิ่งที่เคยรายงานว่าทำสำเร็จ:

- มี `backend/database.py`
- รัน `python database.py` เพื่อทดสอบการเชื่อมต่อฐานข้อมูลได้
- Terminal เคยแสดง `Connected to: student_project_management`

**ข้อจำกัดของหลักฐาน:** ขั้นนั้นยังไม่ยืนยันว่ามี endpoint ทดสอบผ่าน FastAPI แล้ว เอกสารระบุการเสนอให้เพิ่ม endpoint ใน `backend/main.py` เป็นขั้นถัดไป **และขออนุญาตก่อนแก้ไฟล์** จึงห้ามสรุปว่า endpoint ถูกเพิ่มแล้วจากแหล่งนี้

**งานของ Codex:** ตรวจไฟล์ Backend ปัจจุบัน, routes, dependencies, การเชื่อม DB และสถานะ tests แบบอ่านอย่างเดียวก่อนเสนอขั้นตอนต่อไป

## 5. Database — สถานะตามหลักฐานเดิม

ไฟล์สำคัญ 3 ไฟล์พบใน Workspace แล้วและควรใช้ประกอบกันตามตำแหน่งปัจจุบัน:

| ชื่อไฟล์ที่ต้องค้นหาใน Repository | เนื้อหาที่ไฟล์สรุปอ้างถึง |
|---|---|
| [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) | **14 tables, 86 columns, 28 foreign keys**; กฎ G/C/D และรวม R-01=A แล้ว |
| [SQL V1](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) | implementation รวมแพตช์ที่อนุมัติ; 52 functions, 24 triggers |
| [Review Report](../database/Database_Schema_V1_A02_A05_Review_Report.md) | สถานะผล runtime รอบก่อน แยกจากประวัติ review เดิม |

**กฎที่ยืนยัน:** `R-01 = A` หมายถึง **ห้ามลบ Project ทุกกรณี** และ C-01 ต้องมี Team ก่อนสร้าง Project; reference/Data Dictionary ปัจจุบันรวมข้อยืนยันเหล่านี้แล้ว

**สถานะ:** Workflow Regression ผ่าน 57 กรณีบน test DB ในบทสนทนารอบก่อน และ ROLLBACK แพตช์/fixture แล้ว; ไม่มีผล concurrency/API security/end-to-end และไม่ได้ตรวจ DB สดในรอบจัดโฟลเดอร์ ไม่ถือเป็นอนุญาต deploy หรือ COMMIT

**งานของ Codex:** ค้นหาไฟล์ทั้งสามใน Workspace; เทียบความสอดคล้องกับสภาพ DB migrations/DDL จริง; รายงานปัญหาและข้อมูลที่ยังขาด โดย **ห้ามปรับ SQL หรือแก้ DB เอง**

## 6. UX/UI — Wireframe V1 ที่ระบุไว้

### 6.1 สิ่งที่กำหนดไว้แล้ว

- Scope ของ Wireframe: **Student / Team Leader**
- จำนวนหน้าจอ: **9 หน้า** (`ST-01`–`ST-09`)
- Desktop Frame: **1440 × 900 px**
- สไตล์: **Modern Academic**
- Shared layout เบื้องต้น: top header + sidebar + พื้นที่เนื้อหาหลัก
- สีตัวอย่างใน Wireframe: header `#163B70`, sidebar `#E8F1FC`, accent `#3989D6`, light surface `#F1F6FC`
- **User Flow ตาม V1 ล่าสุด:** สร้าง Team ก่อน Project ตาม C-01; ข้อความเดิมที่ให้สร้าง Project โดยไม่มี Team ถูกแทนด้วยกฎนี้แล้ว

### 6.2 รายการหน้าจอ

| Screen | ชื่อ/หน้าที่ | พฤติกรรมสำคัญในแบบร่าง |
|---|---|---|
| `ST-01` | Dashboard | ปุ่มสร้าง Project ต้องเคารพ C-01; metrics และรูปแบบแจ้งเตือนยังต้องออกแบบ |
| `ST-02` | Team Creation | สร้างทีมและระบุสมาชิก; หลังสร้างไป `ST-03` |
| `ST-03` | Team Management | เพิ่มสมาชิกตาม phase; ออก/ถอดสมาชิกและโอนหัวหน้าตาม V1 ส่วน UI controls ยังต้องออกแบบ |
| `ST-04` | Project Creation | ต้องมี Team และผู้สร้างเป็นหัวหน้าปัจจุบัน; หลังสร้างไป ST-05 |
| `ST-05` | Project Details | ข้อมูลโครงงาน ทีม อาจารย์ที่ปรึกษา สถานะ และจุดนำทางไปขั้นถัดไป |
| `ST-06` | Advisor Invitation | หัวหน้าส่ง/ยกเลิก; invited advisor ตอบรับ/ปฏิเสธ; หลัง accepted ไม่เปลี่ยนอาจารย์ใน V1 |
| `ST-07` | Project Submission | ต้องมี advisor accepted และไฟล์หนึ่งรายการพร้อม snapshot ใน transaction เดียว |
| `ST-08` | Submission Status | รอตรวจ/อนุมัติ/ขอแก้ไข; Coordinator เห็นตาม G-12 ไม่เพิ่มขั้นส่งต่อหรือสถานะเอง |
| `ST-09` | Project Revision | เห็นข้อเสนอแนะ แก้ไข ส่งใหม่ แล้วกลับ `ST-08` |

### 6.3 Flow ที่ปรับให้ตรง C-01

```text
ST-01 → ST-02 สร้างทีม/หัวหน้า → ST-03 จัดการทีม
                                   ↓
                          ST-04 สร้าง Project
                                   ↓
                          ST-05 → ST-06 เชิญอาจารย์
                                   ↓ เมื่อ accepted
                          ST-07 ส่งพร้อมไฟล์ → ST-08
                                   ↑                ↓ ขอแก้ไขตาม phase
                                   └──── ST-09 ─────┘
```

แผนผังนี้อธิบาย prerequisites ของข้อมูลตาม V1 ไม่บังคับรายละเอียด routing/หน้าตา UI เพิ่มเติม ทีมที่มีอยู่แล้วไม่ต้องสร้างใหม่ ดู phase/สิทธิ์เต็มใน reference

**สถานะจริงของงานออกแบบตามเอกสาร:** มีข้อกำหนด Wireframe/Flow ครบ 9 หน้า แต่ **ยังไม่ใช่ไฟล์ Figma หรือ High-Fidelity UI / Clickable Prototype ที่เสร็จแล้ว**. ขั้นตอนที่เสนอถัดไปคือ High-Fidelity UI ทั้ง 9 หน้าแล้วจึงทำ Clickable Prototype

**ข้อเปิดค้างปัจจุบัน:** ใช้รายการ U01–U09 ใน reference; กฎสร้าง Team ก่อน Project, การตอบคำเชิญและเงื่อนไขส่งได้รับการยืนยันใน V1 แล้ว ส่วนรายละเอียด UX ยังไม่ implement

## 7. แผนพัฒนาระบบ 4 สัปดาห์ (เป็นแผนเสนอ ไม่ใช่รายงานว่าเสร็จแล้ว)

| ช่วง | เป้าหมายและกิจกรรม | Deliverables ที่เสนอ |
|---|---|---|
| **W1** Requirements & Design | FR/NFR/Business Rules, Roles, Use Case/User Flow, ERD, Wireframe, Acceptance Criteria | SRS draft, diagrams, wireframe, backlog |
| **W2** Architecture & Core Development | โครงสร้างระบบ, ฐานข้อมูล, สร้างทีม/โครงงาน, เชิญอาจารย์, ยื่น/อนุมัติ, API contract | Backend/DB เบื้องต้น, core screens, API spec |
| **W3** Tracking & Integration | Milestone, Task, Deadline, เอกสาร, Progress/Feedback, Dashboard, Contribution, Evaluation, Integration | Workflow ติดตาม, Timeline, Dashboard, Integration |
| **W4** Testing & Delivery | Unit/Integration/System/Acceptance, RBAC, edge cases, defects, regression, user manual & demo | MVP tested, test report, manual, presentation |

สิ่งที่แผนเสนอให้จัดเป็น **MVP ก่อน**: ทีม/โครงงาน, สมาชิก/เชิญอาจารย์, ยื่นและอนุมัติ, Milestone/Task/Assignment, Progress/Timeline

**ระดับถัดไป**: เอกสารและ versioning, Comment/Revision, Dashboard/Contribution รายบุคคล, คะแนนและ Feedback กรรมการ

**เมื่อมีเวลา/ยืนยันขอบเขต**: รายงาน PDF, รูปแบบรายงาน, การแจ้งเตือนอัตโนมัติ

**ประเด็นต้องยืนยันก่อนทำ**: วิธี Login/identity และรายละเอียด UI, PDF export, notifications; การตรวจสิทธิ์และยืนยันตัวตนตาม G-12 เป็นข้อกำหนด V1 แล้ว การจัดกลุ่มความสำคัญในแผนเป็นข้อเสนอ ไม่ใช่คำสั่งให้ implement อัตโนมัติ

### แนวทางติดตามงานที่ระบุในแผน

- ใช้ Agile/Scrum: Sprint Planning, Daily Scrum, Backlog Status, Sprint Review, Retrospective
- จัดทำ Traceability: Requirement -> Design -> Code -> Test
- ทำงานร่วมกันผ่าน Git repository, issue, pull request, code review
- แยกสิ่งที่ 'เขียนแผนแล้ว' ออกจากสิ่งที่ 'ทดสอบในโค้ดแล้ว' ทุกครั้งที่สรุป Progress

## 8. ประเด็นเปิดค้างที่ต้องถาม/ตรวจ (ห้ามกำหนดแทนผู้ใช้)

1. Folder Structure ของ Frontend เลือก Feature-based หรือ Layer-based หรือมีโครงจริงแล้ว?
2. มี endpoint ตรวจการเชื่อมฐานข้อมูลผ่าน FastAPI อยู่ใน repo ล่าสุดหรือไม่?
3. ฐานข้อมูลจริงใช้ schema เวอร์ชันใด, SQL draft ผ่านการทดสอบ RBAC/Triggers แล้วหรือยัง?
4. Data Dictionary รวม R-01=A แล้ว; ติดตามความสอดคล้องของเอกสารเมื่อมีคำยืนยันใหม่
5. C-01 ยืนยัน Team ก่อน Project แล้ว; รายละเอียด UX สำหรับกรณียังไม่มี Team ต้องออกแบบโดยคงกฎนี้
6. อ่านสิทธิ์สมาชิก/คำเชิญ/Submission จาก V1; อย่าใช้ข้อเปิดค้างใน source เก่าทับกฎล่าสุด
7. มีไฟล์ Figma/High-Fidelity/Prototype จริงแล้วหรือยัง?
8. วิธี identity/Login และขอบเขต PDF/Notification คืออะไร? G-12 authorization ต้องมีแล้วตาม V1
9. ไฟล์ requirements จากการสัมภาษณ์และเอกสารรายวิชา 8 หัวข้ออยู่ใน workspace ที่ใด?

## 9. ประวัติงานแรก: Audit แบบ Read-only (ดำเนินการแล้ว)

ขั้นตอนด้านล่างเป็นบันทึกงาน audit เดิม งานถัดไปและขอบเขตที่อนุมัติให้ยึดคำสั่งผู้ใช้ล่าสุดและ Backlog:

1. อ่านเอกสารนี้และ `sources/` ทั้ง 5 ไฟล์
2. ตรวจสอบโครงสร้าง repo (Frontend/Backend/Database/Design docs), package/dependency manifests, git branch/status โดยไม่เปลี่ยนไฟล์
3. ตรวจว่าไฟล์ Database 3 ชื่อที่อ้างถึงมีจริงหรือไม่ และเวอร์ชันใด
4. เปรียบเทียบกับสถานะจากเอกสารนี้ทีละหมวด และระบุความต่างโดยให้ชื่อ path จริง
5. ส่งรายงานสั้น ๆ ที่จำแนก `ยืนยันจากโค้ด`, `ระบุไว้ในเอกสารแต่ยังไม่พบ`, `ยังตรวจไม่ได้`, `ต้องตัดสินใจ`
6. เสนอ **งานถัดไปเพียงงานเดียว** พร้อมไฟล์ที่จะถูกแตะและเหตุผล; **รออนุมัติก่อนลงมือ**

### รูปแบบรายงานที่ต้องการจาก Codex

```text
Frontend:      [พบอะไรใน repo] / [ต่างจาก handoff อย่างไร]
Backend:       [พบอะไรใน repo] / [ต่างจาก handoff อย่างไร]
Database:      [ไฟล์/schema/migrations ที่มีจริง] / [สิ่งที่ยังไม่ยืนยัน]
UX/UI:         [design assets/หน้าจอที่มีจริง] / [สิ่งที่เป็นแค่ wireframe]
Development:   [tests, scripts, CI, Git status ที่ตรวจได้]
Open decisions:[คำถามที่ต้องให้เจ้าของโปรเจกต์ตัดสินใจ]
Next step:     [ข้อเสนอหนึ่งขั้นตอน; ไม่แก้ไฟล์จนกว่าจะอนุญาต]
```

## 10. หมายเหตุเรื่องการนำเข้า Workspace

- วาง **ทั้งโฟลเดอร์ `codex_project_handoff`** ไว้ภายใต้ `docs/` ใน Repository เพื่อให้ Codex เปิดอ่านได้
- ไม่ต้องแทนที่ README, source, migrations หรือไฟล์ดีไซน์เดิม
- หากมีความขัดแย้งระหว่างโค้ดปัจจุบันกับเอกสารนี้ ให้ **รายงาน** ก่อน ไม่ overwrite ของเดิม
- เนื้อหาจากแหล่ง `sources/*.txt` เป็น snapshot ประวัติการสนทนา มีส่วน markup ประกอบการแสดงผลที่ไม่ใช่โค้ด Frontend จริง
