# Project submissions — confirmed contract

วันที่ 2026-11-07 · V1 submission / file / advisor review · **ผู้ใช้ยืนยันขอบเขตการทำและวิธีตรวจไฟล์แล้ว**

ต่อยอด Schema V1 เดิมโดยไม่เพิ่มหรือแก้ตาราง/สิทธิ์ฐานข้อมูล ดู [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md), [Schema SQL](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) และ [งานทีม S](../team/SUBMISSION_WORK_PACKAGE.md)

## Workflow

1. หัวหน้าทีมปัจจุบันส่งไฟล์ให้ Project ที่มีอาจารย์ตอบรับคำเชิญแล้ว
2. ระบบสร้าง `project_submissions` และ `project_submission_files` ใน transaction เดียว สถานะเริ่ม `pending_review`
3. อาจารย์ที่ตอบรับเป็นที่ปรึกษาตรวจได้ครั้งเดียว: `approved` หรือ `revision_requested` พร้อมข้อความจริงเมื่อขอแก้ไข
4. เก็บ snapshot, ไฟล์ และผลตรวจของทุกรอบไว้โดยไม่แก้หรือลบ
5. ส่งรอบถัดไปได้เมื่อไม่มีรอบก่อน หรือผลล่าสุดอนุญาตให้แก้ไขตามกฎที่ DB คำนวณ รวมผลลงมติกรรมการครบถ้วน

`approved` ในรอบนี้หมายถึงอาจารย์ที่ปรึกษาอนุมัติ ไม่ใช่การอนุมัติสุดท้ายของกรรมการ

## API

ทุก ID เป็น decimal string ใน JSON; ใช้ session เดิม, `Origin`, CSRF สำหรับ POST, และ `Cache-Control: no-store` ไม่มี actor, status, snapshot หรือเวลาที่ client เลือกได้

| Method / path | ผู้ใช้ | ผล |
|---|---|---|
| `GET /api/v1/projects/me/submissions` | สมาชิกทีมปัจจุบัน (student) | ประวัติทีม เรียงรอบล่าสุดก่อน |
| `GET /api/v1/projects/me/submissions/eligibility` | student ในทีม | `data.can_submit` ตามสิทธิ์หัวหน้าทีม/ที่ปรึกษาที่ตอบรับ/phase ล่าสุด |
| `POST /api/v1/projects/me/submissions` | หัวหน้าทีมปัจจุบัน | multipart field `file` เพียงไฟล์เดียว; สำเร็จ 201 |
| `GET /api/v1/advisor/submissions` | อาจารย์ที่ตอบรับคำเชิญ | ประวัติของ Project ที่เป็นที่ปรึกษา |
| `GET /api/v1/project-submissions/{id}` | สมาชิกทีม, อาจารย์ที่ปรึกษาที่ตอบรับ, กรรมการที่ได้รับแต่งตั้ง | รายละเอียดรอบที่มีสิทธิ์ดู; coordinator เห็นเฉพาะรอบ `approved` |
| `GET /api/v1/project-submissions/{id}/file` | สิทธิ์เดียวกับรายละเอียด | ไฟล์แนบผ่าน API ที่ตรวจสิทธิ์ทุกครั้ง |
| `POST /api/v1/project-submissions/{id}/review` | อาจารย์ที่ตอบรับเป็นที่ปรึกษา | JSON `{"decision":"approved","comment":null}` หรือ `{"decision":"revision_requested","comment":"..."}` |

รายละเอียดการส่งใช้ shape:

```json
{
  "data": {
    "id": "701",
    "project_id": "401",
    "submitted_by": "301",
    "submitted_at": "2026-11-07T16:00:00Z",
    "snapshot_name": "หัวข้อโครงงาน",
    "snapshot_description": "รายละเอียด ณ เวลาส่ง",
    "status": "pending_review",
    "reviewed_by": null,
    "reviewed_at": null,
    "review_comment": null,
    "original_filename": "proposal.pdf",
    "mime_type": "application/pdf",
    "team_name": "ทีมตัวอย่าง"
  }
}
```

รายการประวัติใช้ DTO เดียวกันแต่ไม่ส่ง bytes ของไฟล์ ไฟล์ดาวน์โหลดเป็น attachment และใช้ชื่อที่ server สร้าง ไม่ echo path หรือชื่อไฟล์ลง response header

## File validation

- รับ PDF (`application/pdf`) และ PPTX (`application/vnd.openxmlformats-officedocument.presentationml.presentation`) ขนาด 1–4,000,000 bytes เท่านั้น
- อ่าน multipart ทีละ chunk และตรวจจำนวน bytes จริง มีเพดาน request body รวมส่วน multipart 4,065,536 bytes; `Content-Length` เป็นเพียง early rejection ไม่ใช่หลักฐานขนาดไฟล์
- ตรวจด้วย `pypdf` และ `python-pptx` ให้ parser อ่านเอกสารได้จริง ไม่ยอมรับเพียงนามสกุลหรือ magic bytes
- PPTX จำกัดไม่เกิน 2,000 ZIP parts และ uncompressed contents รวมไม่เกิน 32,000,000 bytes เพื่อลดความเสี่ยงจาก ZIP bomb
- Browser ส่งตรงถึง FastAPI ด้วย `multipart/form-data`; API บันทึก bytes ใน `BYTEA` ตาม Schema V1 ไม่มี Base64 หรือ public URL

Pinned packages ใน `backend/requirements.txt`: `python-multipart==0.0.33`, `pypdf==7.0.0`, `python-pptx==1.0.2`.

## Authorization and errors

- ไม่เข้าสู่ระบบ: `401 AUTHENTICATION_REQUIRED`; POST ที่ CSRF/Origin ไม่ผ่านใช้ Auth contract เดิม
- ไม่มีสิทธิ์รับรู้รายการ: `404 SUBMISSION_NOT_FOUND`; role ใช้หน้าไม่ได้: `403 SUBMISSION_ACCESS_FORBIDDEN`
- ไม่มีทีมหรือ Project: `404 TEAM_NOT_FOUND` หรือ `PROJECT_NOT_FOUND`
- ผู้ส่งไม่ใช่หัวหน้าปัจจุบัน: `403 SUBMISSION_ACTION_FORBIDDEN`
- ไม่มีอาจารย์ตอบรับ, มีรอบ pending, หรือ phase ยังไม่ให้ส่ง: `409 ACCEPTED_ADVISOR_REQUIRED`, `SUBMISSION_PENDING`, `SUBMISSION_PHASE_CLOSED`
- รอบตรวจซ้ำ: `409 SUBMISSION_ALREADY_REVIEWED`
- ไฟล์ผิด/ไม่รองรับ/เกินขนาด: `422 FILE_CONTENT_INVALID`/`FILE_TYPE_UNSUPPORTED`/`FILE_TYPE_MISMATCH`, `413 FILE_TOO_LARGE`
- Validation ไม่ผ่าน: `422 VALIDATION_ERROR`; storage/transaction ที่จัดประเภทไม่ได้: `500 INTERNAL_ERROR` โดยไม่คืน SQL หรือ traceback

## UI and verification

- นักศึกษา: `/projects/submissions` ส่งไฟล์ ดูประวัติ/ผลตรวจ และดาวน์โหลดไฟล์; ปุ่มส่งเปิดเฉพาะเมื่อ API eligibility อนุญาต
- อาจารย์: `/advisor/submissions` ดูรายการที่ตอบรับเป็นที่ปรึกษา ดาวน์โหลด และตัดสินผล/ให้คำแนะนำ
- Account และ Project screens มีทางเข้าหน้าใหม่
- `backend/tests/test_submission_validation.py` และ `backend/tests/test_submission_api_unit.py` ผ่าน; `backend/tests/test_submission_api.py` เป็น HTTP + PostgreSQL rollback suite แต่ test fixture setup ล้มเหลวใน environment นี้ จึงยังไม่ยืนยัน runtime DB/ACL
- UI ไม่มีการ retry POST อัตโนมัติ เมื่อผลเครือข่ายไม่ชัดเจนให้โหลดประวัติก่อนส่งซ้ำ
