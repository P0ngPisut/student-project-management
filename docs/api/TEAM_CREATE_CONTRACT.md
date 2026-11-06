# API Contract — สร้างทีมพร้อมหัวหน้าทีม

วันที่: 2026-11-06 · Task: P16 / P09 · สถานะ: **Draft สำหรับทบทวน ยังไม่มี endpoint implementation**

อ้างอิง [Schema V1 Reference](../database/SCHEMA_V1_REFERENCE.md), [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md), [SQL](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql), [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql) และ [Backlog](../progress/BACKLOG.md)

## 1. ขอบเขตและคำยืนยัน

| รายการ | สถานะ |
|---|---|
| API แรกสร้างทีมพร้อมผู้สร้างเป็นหัวหน้า แล้วเพิ่มสมาชิกภายหลัง | **ผู้ใช้ยืนยันในรอบนี้** |
| ต้องมี Team ก่อนสร้าง Project; ห้ามลบ Project ทุกกรณี | ยืนยันแล้วตาม C-01 / R-01 |
| ผู้สร้างต้องเป็น student และมีสมาชิกภาพปัจจุบันได้สูงสุดหนึ่งทีม | ยืนยันแล้วตาม V1; ต้องตรวจทั้งสิทธิ์ API และ DB constraint |
| บันทึก Team + leader ใน transaction เดียว; ทีมต้องมีหัวหน้า 1 และสมาชิก ≥1 | ยืนยันแล้วตาม V1 |
| มหาวิทยาลัยไม่มี SSO ที่แอปนี้ใช้ได้ | **ผู้ใช้ยืนยันในรอบนี้** |
| ใช้งานเพื่อส่งอาจารย์และทดสอบภายในทีม ไม่ได้ตั้งใจเปิดใช้งานจริง | **ผู้ใช้ยืนยัน 2026-11-06** |
| ใช้อีเมลจำลองที่ไม่มีกล่องรับข้อความจริง และตั้งรหัสผ่านเองได้ | **ผู้ใช้ยืนยัน 2026-11-06**; ตรวจรูปแบบอีเมล ไม่จำกัด Gmail; รหัสผ่านอย่างน้อย 8 ตัว มีตัวพิมพ์ใหญ่อย่างน้อย 1 ตัวและตัวเลขอย่างน้อย 1 ตัว |
| วิธี Login | Backend ดูแลเอง ไม่ใช้ Firebase; Register/Login/Logout มีโค้ด/tests แล้วตาม [Auth Contract](AUTH_CONTRACT.md); session 8 ชั่วโมง/localhost ตามที่ยืนยัน |
| การสร้างบัญชี | **ผู้ใช้ยืนยัน** student สมัครเอง; ผู้ดูแลเตรียม advisor/coordinator; Auth storage/RBAC ผ่าน DB regression 40/40 และ ROLLBACK แล้ว ยังไม่มี Signup endpoint |
| URL, JSON envelope, ID encoding, error codes ในเอกสารนี้ | ข้อเสนอทาง API ของร่างนี้ ไม่ใช่ข้อความ Requirement V1 เดิม |

สถานะปัจจุบัน: Auth มี 3 endpoints/hash/tests และ schema/grants ถาวรแล้ว Direct project_app connection และ smoke Register/Login/Logout ผ่านพร้อม ROLLBACK ส่วน POST /teams ยังเป็นร่าง ไม่มี Team endpoint รายละเอียดอยู่ในส่วน 7 และ Auth Contract

## 2. Endpoint ที่เสนอ

`POST /api/v1/teams`

- Content-Type: `application/json`
- ต้องผ่าน Auth ของ Backend ก่อน handler ได้รับ `current_user` ที่ผูกกับ `users.id` จริง
- ไม่ใช้ `user_id`, `role`, `actor_user_id` จาก request เพื่อเลือกตัวผู้สร้าง
- เวอร์ชันนี้สร้างเฉพาะ Team และหัวหน้าคนแรก ไม่สร้าง Project และไม่เพิ่มสมาชิกอื่นใน request เดียว
- ชื่อ Team ซ้ำกับทีมอื่นได้ตาม Schema; ไม่เพิ่ม unique rule ให้ชื่อทีม

### Request

| Field | ชนิด | บังคับ | ความหมาย / validation |
|---|---|---|---|
| `name` | string | ใช่ | trim ให้ตรง V1; ค่าที่บันทึกต้องไม่ว่างและยาวไม่เกิน 255 อักขระ; ไม่รับ null/ชนิดข้อมูลอื่น |
| `description` | string หรือ null | ไม่ | trim; ไม่ส่ง/null/ว่างหลัง trim เก็บเป็น null; V1 ไม่กำหนดความยาวสูงสุดของ TEXT |

ข้อเสนอ wire validation: ปฏิเสธ field นอกเหนือสองรายการนี้ด้วย 422 รวมถึง `id`, `leader_id`, `user_id`, `role`, `members`, `member_ids` และ `project` การเพิ่มสมาชิกภายหลังจะออกแบบ Contract แยกตามสิทธิ์/phase ของ V1

ตัวอย่าง request ซึ่งเป็นข้อมูลจำลอง:

```json
{
  "name": "ทีมโครงงานตัวอย่าง",
  "description": "โครงงานสำหรับวิชาโครงงาน"
}
```

รายละเอียด normalization ให้ยึด `v1_team_guard`/CHECK ของ teams ไม่เพิ่มการแปลงตัวพิมพ์ Unicode normalization หรือกฎชื่ออื่นเอง การทดสอบ API ต้องเทียบกับ SQL ก่อนถือว่าผ่าน

### Success response ที่เสนอ

`201 Created` ส่งหลัง transaction บันทึกสำเร็จเท่านั้น

```json
{
  "data": {
    "id": "101",
    "name": "ทีมโครงงานตัวอย่าง",
    "description": "โครงงานสำหรับวิชาโครงงาน",
    "members": [
      {
        "id": "201",
        "user_id": "301",
        "role": "leader"
      }
    ]
  }
}
```

- IDs เป็นข้อมูลตัวอย่าง; ร่างเสนอส่ง BIGINT เป็น decimal string เพื่อให้ client เก็บค่าได้ครบโดยไม่พึ่งขอบเขต JavaScript Number
- `data.id` มาจาก teams.id; `members[0].id` มาจาก team_members.id; user_id มาจากผู้ใช้ที่ Backend ตรวจแล้ว
- response แสดงค่าที่อ่านคืนจาก DB หลัง normalization; members มีหนึ่งคนตามขอบเขตที่ผู้ใช้ยืนยัน
- ไม่เพิ่ม `created_by`, `created_at`, `status` ลง teams เพราะไม่มีคอลัมน์เหล่านี้ใน V1
- ยังไม่สัญญา GET endpoint, Location header, idempotency key หรือการ retry ที่ให้ผลเหมือนเรียกครั้งเดียว ซึ่งยังไม่มี Contract

## 3. Transaction และ actor

ลำดับสำหรับ implementation ในอนาคต:

1. ตรวจหลักฐาน Auth และ resolve เป็นผู้ใช้ที่มีอยู่ใน V1; ถ้ายังจับคู่บัญชีไม่ได้ ให้ปฏิเสธก่อนเขียน Team ไม่สร้าง users อัตโนมัติจาก request นี้
2. ตรวจ JSON/normalize ตามกฎ แล้วเริ่ม transaction ด้วย application DB role `project_app`
3. ตรวจผู้ใช้จริงเป็น student และไม่มีสมาชิกภาพปัจจุบัน; precheck ใช้เพื่อให้ error ชัด แต่ต้องรักษา UNIQUE ของ DB เพื่อรองรับ race
4. กำหนด `app.actor_user_id` แบบ transaction-local จากผู้ใช้ที่ตรวจแล้ว โดยใช้ parameterized SQL; ไม่เชื่อ custom GUC ที่ client ส่งมา
5. INSERT teams ด้วย name/description และอ่าน id ที่ DB สร้าง
6. INSERT team_members ด้วย team_id ที่เพิ่งได้, user_id ของผู้สร้าง และ role='leader'; ใช้สิทธิ์ INSERT ที่ RBAC อนุญาตและปล่อย triggers ทำงาน
7. บังคับตรวจ constraint ที่เกี่ยวข้องก่อนสรุปผล เช่น `SET CONSTRAINTS c_team_created_has_leader, c_team_member_cardinality IMMEDIATE`; การจบ transaction ต้องสำเร็จก่อนตอบ 201
8. ถ้า INSERT/constraint/การจบ transaction ล้มเหลว ให้ย้อนกลับทั้ง Team และ leader; ไม่มีทีมกำพร้า ไม่มีผลสำเร็จบางส่วน

API ปกติไม่ใช้ postgres/project_owner เพื่อข้ามสิทธิ์ และไม่เพิ่ม grants เมื่อเจอ permission denied ต้องรายงาน configuration/patch ที่ขาด

รอบออกแบบนี้ไม่ได้อนุญาต COMMIT ลง test DB การทดสอบ DB ตามข้อจำกัดเดิมต้อง transaction/ROLLBACK และตรวจชื่อ `student_project_management_v1_test` ทุกชุดก่อนเขียน; การเปิด endpoint ที่บันทึกถาวรหรือเตรียม baseline/fixture ถาวรต้องมีขอบเขตที่อนุมัติแยก

## 4. Error contract ที่เสนอ

| HTTP | Code | กรณี | ที่มา |
|---|---|---|---|
| 401 | `AUTHENTICATION_REQUIRED` | ไม่มี/ไม่ผ่านหลักฐานยืนยันตัวตน | G-12; รายละเอียด token/session ขึ้นกับ Auth ที่เลือก |
| 403 | `TEAM_CREATION_FORBIDDEN` | ยืนยันตัวตนแล้ว แต่ไม่มีสิทธิ์สร้างทีม เช่นไม่ใช่ student | G-12 และข้อ student-only |
| 403 | `ACCOUNT_NOT_PROVISIONED` | ข้อเสนอเดิมสำหรับ external identity; ไม่ใช่ code ที่ Auth API ปัจจุบัน implement | ต้องทบทวนก่อนใช้ Team handler เพราะ self-managed session ปัจจุบันอ้าง users.id ผ่าน FK |
| 409 | `ALREADY_IN_TEAM` | ผู้สร้างเป็นสมาชิกทีมแล้ว รวม race ที่อีก transaction บันทึกสำเร็จก่อน | UNIQUE team_members.user_id; HTTP/code เป็นข้อเสนอ |
| 422 | `VALIDATION_ERROR` | JSON/field/type/name ไม่ถูกต้อง หรือส่ง fields ที่ไม่รองรับ | รูปแบบ validation ที่เสนอ |
| 500 | `INTERNAL_ERROR` | unexpected DB/configuration/transaction failure | ไม่ส่ง raw SQLSTATE, constraint name, SQL หรือ traceback ให้ client |

G-12 ยังคงกำหนด 404 สำหรับ resource ที่ไม่มี/ไม่มีสิทธิ์รับรู้ว่ามีอยู่ แต่ POST นี้ไม่มี resource ID เป้าหมายใน URL จึงไม่เพิ่มกรณี lookup ทีมของคนอื่นเอง

ตัวอย่าง error จำลอง:

```json
{
  "error": {
    "code": "ALREADY_IN_TEAM",
    "message": "คุณเป็นสมาชิกทีมอยู่แล้ว"
  }
}
```

รายละเอียด field validation ในร่างเสนอให้เพิ่ม `fields` เฉพาะเมื่อจำเป็น เช่น:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "ข้อมูลไม่ถูกต้อง",
    "fields": [
      {"field": "name", "code": "REQUIRED_OR_BLANK"}
    ]
  }
}
```

ข้อควรยืนยันตอน implement:

- แปลง SQLSTATE `23505` เป็น ALREADY_IN_TEAM เฉพาะ constraint `team_members_user_id_key` ของ operation นี้ ไม่แปลง UNIQUE ทุกชนิดเหมือนกัน
- `42501` ที่เกิดจาก DB grants/actor configuration ผิด ไม่ใช่ข้อพิสูจน์ว่าเป็น 403 ของผู้ใช้เสมอ ต้องแยกจาก business authorization
- `P0001` เป็น exception ทั่วไปในหลาย triggers จึงห้ามแปลงทั้งหมดเป็น input error; deferred cardinality failure ของ handler เป็นความผิดพลาดภายในที่ต้อง rollback
- ไม่เปิดเผยชื่อทีมอื่น/สมาชิกอื่นใน error; พฤติกรรมกรณีมีหลาย error พร้อมกันให้กำหนดกับ validation implementation ไม่อนุมานจากลำดับข้อความในตาราง
- ยังไม่กำหนด automatic retry/timeout/idempotency policy; ไม่สัญญาว่า request ซ้ำจะสร้างข้อมูลครั้งเดียวในทุก failure mode

## 5. Acceptance cases ของ Contract

ตารางนี้เป็นเกณฑ์ที่เสนอจากกฎ V1 และขอบเขตที่ผู้ใช้ยืนยัน **ยังไม่ใช่ผล API test PASS**

| Case | สถานการณ์ | ผลที่ต้องพิสูจน์ |
|---|---|---|
| TEAM-01 | student ไม่มีทีม ส่ง name ถูกต้อง | สร้าง Team + leader ของผู้สร้างหนึ่งคน; 201 หลัง transaction สำเร็จ |
| TEAM-02 | ไม่ส่ง description/null/ช่องว่าง | เก็บ null ตาม normalization และ response ตรง DB |
| TEAM-03 | name ขาด/null/ว่าง/ผิดชนิด/เกินความยาวที่บันทึกได้ | 422; ไม่มีแถวตกค้าง |
| TEAM-04 | นักศึกษาคนละคนที่ยังไม่มีทีม ใช้ชื่อทีมเดียวกัน | ไม่ปฏิเสธเพราะชื่อซ้ำ |
| TEAM-05 | ไม่มี/ปลอม/หมดอายุหลักฐาน Auth | 401 ก่อนเขียนข้อมูล |
| TEAM-06 | advisor/coordinator เรียกสร้างทีม | 403; ไม่มี Team/member ใหม่ |
| TEAM-07 | student เป็นสมาชิกทีมอยู่แล้ว | 409; ไม่มี Team กำพร้า |
| TEAM-08 | ส่ง user_id/leader_id/role/member_ids เพื่อเลือกผู้สร้างหรือสมาชิก | 422 ตาม wire validation ที่เสนอ; ไม่ใช้ field เหล่านี้เป็น actor |
| TEAM-09 | บังคับขั้นสร้าง leader หรือ deferred check ให้ล้มเหลว | rollback Team และ member ทั้งหมด; ไม่ตอบ 201 |
| TEAM-10 | request พร้อมกันของ student เดียวกัน | คงสมาชิกภาพได้สูงสุดหนึ่งทีม; transaction ที่ชนสมาชิกภาพที่บันทึกแล้วต้องไม่ทิ้ง Team กำพร้า; ยังต้อง concurrency test |
| TEAM-11 | ID ของ DB เกินช่วง integer ที่ JS Number เก็บได้ตรง | response string และ client ไม่แปลงจนเสีย precision |
| TEAM-12 | token/session ถูกต้องแต่ไม่มี mapping กับบัญชี V1 | ปฏิเสธตาม Auth contract ที่ตกลง; ไม่ auto-create user/role |
| TEAM-13 | DB grants/patch ไม่ครบ | rollback และ internal error ที่ไม่เผยข้อมูลลับ; ไม่สลับใช้ superuser |

หลักฐานเดิม: [RBAC Lock Regression](../../database/tests/Database_Schema_V1_RBAC_Lock_Regression.py) มีกรณีสร้าง Team/leader, ชื่อว่าง, orphan team และตรวจ deferred; [Workflow Regression](../../database/tests/Database_Schema_V1_Workflow_Regression.py) ทดสอบ DB workflow รวม 57 กรณีก่อนย้ายไฟล์ ทั้งสองชุดเป็น DB-only ไม่พิสูจน์ HTTP/Auth/JSON response ในตารางนี้ และรอบทำ Contract ไม่ได้รัน DB ซ้ำ

## 6. งานที่ยังต้องทำก่อนทดสอบ workflow ผ่าน API

- ใช้แนวทาง Backend ดูแล Login เอง และปิดประเด็นที่เหลือใน [Auth Design](AUTH_DESIGN.md): ที่เก็บ credentials/session, provisioning, สิทธิ์ DB, อายุ session และ logout/recovery
- รับรอง wire format ของร่างนี้ก่อนให้ Frontend/Backend ยึดเป็น Contract เดียวกัน
- เตรียม test DB baseline ที่มีแพตช์ตามขอบเขตที่อนุมัติ โดยไม่ใช้ installer schema ว่างเป็น migration
- Implement request/response models, handler/service/transaction และ tests ตาม Contract; ยังไม่ได้แก้ backend/main.py
- เพิ่มสมาชิกและสร้าง Project เป็น Contract ถัดไป ไม่รวมใน endpoint แรกนี้

## 7. ข้อเสนอ Auth หลังยืนยันว่าไม่มี SSO

### ขอบเขตล่าสุด: โปรเจกต์ส่งอาจารย์และทดสอบภายในทีม

ผู้ใช้ยืนยันวันที่ 2026-11-06 ว่าใช้ระบบเพื่อส่งอาจารย์และทดสอบภายในทีม ต้องการใช้อีเมลจำลองที่มีเครื่องหมาย `@` และตั้งรหัสผ่านเองได้ ไม่จำเป็นต้องมีกล่องรับอีเมลจริง ขอบเขตนี้ไม่ใช่การอนุมัติเปลี่ยน Schema V1 หรือยกเลิกการตรวจตัวตน/สิทธิ์ตาม G-12

กฎ validation ที่ผู้ใช้ยืนยันแล้ว:

- ตรวจรูปแบบอีเมลทั่วไป เช่น `student01@example.test` ไม่จำกัด Gmail ไม่ตรวจ DNS/ว่ามีกล่องรับข้อความจริง และไม่ส่งอีเมลยืนยัน
- รหัสผ่านอย่างน้อย 8 ตัวอักษร มีตัวพิมพ์ใหญ่อย่างน้อย 1 ตัว และตัวเลขอย่างน้อย 1 ตัว; ไม่เพิ่มข้อบังคับตัวพิมพ์เล็กหรืออักขระพิเศษ

มี implementation ใน [auth_validation.py](../../backend/auth_validation.py): `validate_email_format` ใช้ email-validator โดยปิด deliverability และเปิด test_environment เพื่อรับ `.test`; `validate_new_password` ตรวจความยาวและตัวพิมพ์ใหญ่ `A–Z`/ตัวเลข `0–9` ฟังก์ชันไม่เปลี่ยนค่าที่รับ ไม่ trim/เปลี่ยน case ของรหัสผ่าน และไม่จัดเก็บข้อมูลหรือยืนยันตัวตน การ normalize อีเมลสำหรับบันทึกบัญชียังคงต้องทำตาม V1 ใน provisioning ที่จะออกแบบต่อ

ผล [unit tests](../../backend/tests/test_auth_validation.py) วันที่ 2026-11-06: **PASS 17 tests** ครอบคลุม `.test`/โดเมนอื่น, อีเมลผิดรูปแบบ, ไม่เรียก DNS/network, รหัสผ่านขอบเขต 7/8 ตัว, ขาดตัวใหญ่/ตัวเลข, ไม่เพิ่มกฎตัวเล็ก/อักขระพิเศษ, ไม่เปลี่ยนรหัสผ่าน และข้อความ error ไม่สะท้อนข้อมูลที่กรอก ทั้งหมดเป็นการทดสอบตัวตรวจข้อมูล ไม่ใช่การทดสอบ Signup/Login/API/DB

คำสั่งจาก root ของ Workspace:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation -v
```

### แนวทางที่ผู้ใช้เลือก: Backend ดูแล Login เอง

ผู้ใช้ยืนยันว่า **ไม่ใช้ Firebase** รายละเอียดอยู่ใน [Auth Design](AUTH_DESIGN.md) ข้อเสนอ Firebase/Emulator ก่อนหน้านี้ถูกแทนที่ และยังไม่มีการติดตั้ง Firebase

Auth ปัจจุบันใช้ Argon2id และ session ที่ Backend จัดการใน auth.credentials/auth.sessions ผูกกับ users.id ตาม [Auth Contract](AUTH_CONTRACT.md) ส่วนการตรวจ role/สมาชิกภาพก่อนสร้างทีมยังต้อง implement ใน Team API รหัสผ่านจริงและ session token ไม่ส่งกลับใน JSON/log

ส่วนขยาย Auth: [storage](../../database/auth/001_auth_storage_review.sql) และ [RBAC](../../database/auth/002_auth_rbac_review.sql) ติดตั้งถาวรผ่าน Auth_Install แล้วตาม [Installation Report](../database/AUTH_INSTALLATION_REPORT.md) test DB มี 16 ตาราง แบ่ง public V1 14/86/28 และ auth 2/6/2 Tests 40 และ 57 ผ่านและ ROLLBACK เฉพาะข้อมูลจำลองกลับ baseline ที่มี Auth อยู่

วิธีสร้างบัญชียืนยันแล้ว: student สมัครเอง; ผู้ดูแลเตรียม advisor/coordinator ร่าง auth.register_student กำหนด role student ตายตัวและสร้าง users/credentials แบบ atomic โดยไม่ให้ project_app INSERT users ตรง สิทธิ์จริงยังเป็น baseline เดิมจนกว่าจะทดสอบและติดตั้งตามขอบเขตที่อนุมัติ; session policy/HTTP Contract ยังมีรายละเอียดเปิดตาม Auth Design

Auth suite ผ่าน 57 tests (17+16+24) แยกจาก Auth DB-only 40 ทั้งก่อนและหลังติดตั้ง ทุก test data write ใช้ transaction/ROLLBACK แต่ Auth DDL/grants ติดตั้งถาวรแล้ว ไม่มีบัญชี/session fixture ค้าง ผล Auth API ไม่ได้พิสูจน์ว่า Team API/Frontend เชื่อมแล้ว
