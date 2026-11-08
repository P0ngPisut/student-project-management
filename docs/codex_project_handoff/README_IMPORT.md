# วิธีนำเอกสารส่งต่อเข้า VS Code + Codex

**สถานะปัจจุบัน 2026-11-06:** เอกสารชุดนี้อยู่ใน Workspace แล้ว และไฟล์ Database ถูกจัดโฟลเดอร์แล้ว เริ่มอ่าน [Schema V1 Reference](../database/SCHEMA_V1_REFERENCE.md), [Backlog](../progress/BACKLOG.md) และ [Database README](../../database/README.md) ส่วนวิธีนำเข้าด้านล่างเป็นข้อมูลสำหรับต้นทางชุด handoff ไม่ต้องนำเข้าซ้ำ

1. ดาวน์โหลด ZIP แล้วแตกไฟล์ จะได้โฟลเดอร์ `codex_project_handoff/`
2. เปิด Repository **เดิม** ของ Student Project Management System ใน VS Code
3. วางโฟลเดอร์นี้ที่ `docs/codex_project_handoff/` (สร้างเฉพาะโฟลเดอร์ `docs` หากยังไม่มี โดยไม่ลบ/แทนที่ไฟล์เดิม)
4. เปิด Codex ใน VS Code แล้วส่งข้อความจาก `CODEX_FIRST_MESSAGE.md` หรือสั่งให้อ่านไฟล์นั้นโดยตรง
5. ให้ Codex ตรวจ Repository แบบ read-only และแสดงรายงานก่อนอนุญาตให้แก้ไข

## ไฟล์ในชุดนี้

- `PROJECT_HANDOFF_CODEX.md` — สรุปหลักฐาน Frontend, Backend, Database, UX/UI และแผนพัฒนา รวมข้อห้ามและข้อเปิดค้าง
- `CODEX_FIRST_MESSAGE.md` — คำสั่งเริ่มต้นสำหรับ Codex (เน้นอ่าน/ตรวจ ไม่แก้ไฟล์)
- `sources/` — สำเนาไฟล์ต้นทาง 5 ไฟล์ **ตามต้นฉบับ ไม่เปลี่ยนเนื้อหา**

**ขอบเขตชุด handoff ต้นทาง:** ไม่รวมโค้ดจริง, Figma, credentials, Data Dictionary/SQL/Review หรือเอกสาร/เสียงสัมภาษณ์ต้นฉบับ ใน Workspace ปัจจุบันพบโค้ดและเอกสาร Database แยกต่างหากแล้วตามลิงก์ด้านบน ส่วน Figma และต้นฉบับสัมภาษณ์ยัง Not Verified
