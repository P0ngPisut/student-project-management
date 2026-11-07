# งานทีมS — ส่งโครงงาน / ไฟล์ / ตรวจและขอแก้ไข

สถานะส่งต่อ: **มีDBSchema/guards/DB-onlyregression แต่ยังไม่มีAPI/UIหรือHTTPContractที่เจ้าของยืนยัน** เอกสารนี้เป็นขอบเขตอ้างอิง/รายการงาน ไม่ใช่การอนุมัติendpoint/library/หน้าจอใหม่

อ่าน [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) ตาราง6–7/ส่วน4.2–4.5, [Schema Reference](../database/SCHEMA_V1_REFERENCE.md), [SQL V1](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql), [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql) ก่อนเขียนContract

## กฎที่ยืนยันแล้ว

| เรื่อง | ข้อกำหนดV1 |
|---|---|
| ผู้ส่ง | หัวหน้าทีมปัจจุบัน และProjectมีadvisor invitationที่accepted |
| หนึ่งรอบส่ง | project_submissions1รายการ + project_submission_files1รายการในtransactionเดียว สำเร็จทั้งคู่หรือrollbackทั้งหมด |
| Snapshot | DBคัดลอกprojects.name/description ณเวลาส่ง ห้ามรับsnapshot/actor/reviewfieldsจากBrowserเพื่อเลือกเอง |
| สถานะ | เริ่มpending_review; advisorที่ตอบรับตรวจได้ครั้งเดียวเป็นapprovedหรือrevision_requested; ขอแก้ไขต้องมีข้อความจริง |
| รอบส่งใหม่ | ครั้งแรก/หลังadvisorขอแก้ไข/หลังกรรมการลงครบและสรุปขอแก้ไข จึงส่งรอบใหม่ได้ ไม่แทรกรอบใหม่ระหว่างpendingหรือหลังfinalapprovalเอง |
| ล่าสุด/ประวัติ | ล่าสุดคือmax(submission.id)ต่อProject เก็บทุกรอบ ไม่แก้snapshot/ไฟล์ประวัติ ไม่DELETEsubmission/ไฟล์ |
| ไฟล์ | PDFหรือPPTXหนึ่งไฟล์ bytes1..4,000,000 นามสกุล/MIME/เนื้อหาจริงตรงกัน |
| การส่งBinary | Browserส่งmultipart/form-dataตรงFastAPI ไม่Base64JSONและไม่ให้Nextserverรับแทน; เก็บBYTEAตามV1 |
| Streaming | Backendอ่านเป็นchunk คุมbytesที่อ่านจริง ตอบ413เมื่อเกิน ไม่เชื่อcontent-length/นามสกุล/MIMEจากclientอย่างเดียว |
| Download | ผ่านFastAPIตรวจสิทธิ์ทุกครั้ง Content-Disposition: attachment ไม่publicURL |

SQL v1_submission_file_guardระบุชัดว่าเนื้อหาPDF/PPTXจริงเป็นหน้าที่FastAPI DB-onlyfixtureเช่นb'%PDF-fixture' **ไม่ใช่ไฟล์PDFที่validatorใหม่ต้องรับผ่าน** ให้สร้าง/ใช้validfixtureจริงและinvalidfixturesสำหรับAPItests

## แบ่งงานที่ควรทำ

| ID | งาน | หลักฐานปิดงาน |
|---|---|---|
| S01 | ร่างContract upload/list/details/download/review/revision พร้อมrole/resource/error matrix | เจ้าของยืนยันURL/DTO/errors/การนำทางก่อนimplement |
| S02 | เลือกmultipart/parser/วิธีตรวจPDF-PPTX และpin dependenciesผ่านreview | valid/invalidcontent, ZIP/PPTXและsizeboundariesมีtests ไม่ยอมรับแค่magic/headerเพราะไฟล์ปลอมชื่อถูก |
| S03 | Repository/UOW/authorizedqueries/parentlocks/atomicinsert/controlledreview | HTTP+PostgreSQLtestsจริง ไม่มีadminfallbackหรือgrantsเพิ่ม |
| S04 | หน้าLeaderupload/history/status/revisionและAdvisorreview | อ่านหลังrefreshได้และไม่มีการเปิดไฟล์ข้ามสิทธิ์ |
| S05 | Browser/negative/error/rollbackregressionและreport | ผ่านบนfixture8001 คืนmetadata/ACL/rowcounts ไม่มีtestdataค้าง |

ยังไม่อยู่ในrequirements.txt: python-multipartและparserPDFตรวจเนื้อหา ไม่เลือกเวอร์ชันหรือเพิ่มdependencyแทนทีมในรอบhandoff ต้องเสนอวิธีตรวจเนื้อหา/ขอบเขตresourceก่อนเลือกlibrary ไม่ถือว่าติดตั้งlibraryแล้วผ่านทุกsecuritycase

## จุดต่อBackendและDB

- Featureใหม่แยกbackend/submission_api.pyและsubmission_store.pyตามแบบปัจจุบันเมื่อContractอนุมัติ Runtimeใช้auth_store.open_auth_connection/active_userและsession/CSRF/Originเดิม
- อ่านProject/ตรวจสิทธิ์จากsessionจริง ไม่ใช้team_id/created_by/submitted_by/reviewed_byที่clientส่งมาเป็นauthority
- ล็อกparentก่อนเขียนchildตามV1 ตั้งapp.actor_user_idแบบtransaction-local ไม่rawSELECTFORUPDATEบนตารางที่appไม่มีUPDATEแล้วเพิ่มgrantsแก้เอง
- INSERTsubmissionและfileภายในUOWเดียว บังคับc_submission_requires_file IMMEDIATEก่อนตอบsuccess หากtransactionก่อนหน้าสั่งIMMEDIATEไว้ต้องกำหนดDEFERREDเฉพาะช่วงatomicwriteอย่างถูกต้อง ไม่ปิดtrigger
- Reviewใช้v1_review_submission(bigint,text,text) ไม่directUPDATE tableเอง resolvedactor/time/snapshotให้DBกำหนด
- เพิ่มrouter/validation/storage/no-storeในmain.py และเพิ่มnewUOWoverrideในauth_browser_server.pyก่อนBrowserPOST
- main.pyปัจจุบันCORSallowGET/POSTเท่านั้น หากเลือกverbอื่นสำหรับreview/updateต้องยืนยันContractและเพิ่มCORS/CSRFtestsพร้อมกัน ไม่เพิ่มmethodsหรือเปลี่ยนAuthsessionpolicyเงียบๆ
- แปลงSQLSTATEเฉพาะconstraint/กรณีที่จำแนกได้ ไม่ใช้P0001หรือ42501ทุกกรณีเป็นinput403/422ทั้งหมด

## สิทธิ์ที่ต้องพิสูจน์ตามG-12

- currentteammembersเห็นประวัติSubmission/ไฟล์Projectตน ผู้ที่ออกทีมสิทธิ์นั้นหมด
- acceptedadvisorของProjectเห็นประวัติ/ไฟล์และตรวจpendingตามกฎ ผู้ถูกเชิญpendingไม่ได้สิทธิ์อ่านsubmission/fileจากroleadvisorเพียงอย่างเดียว
- assignedcommitteeเห็นไฟล์ทุกรอบของProjectตามG-12; อย่าตีความว่าadvisorทุกคนเป็นกรรมการ
- coordinatorเห็นProjectหลังมีรอบที่advisorapproved และเข้าถึงไฟล์เฉพาะรอบapproved ไม่เปิดpending/revisionfilesทั้งหมด
- ยังไม่Login401 ไม่มีresource/ไม่มีสิทธิ์รับรู้404 เห็นแต่ทำไม่ได้403 การตรวจด้วยroute/UIอย่างเดียวไม่แทนBackendauthorization

## Acceptance testsขั้นต่ำ

1. validPDF/PPTX uploadได้พร้อมsnapshot/ไฟล์1รายการ เสียขั้นใดrollbackทั้งหมด ไม่มีorphan/false201
2. bytes0/1/4,000,000/4,000,001, MIME/extension/contentmismatch, multiple/missingfiles, malformed/encrypted/truncatedpayloadตามวิธีตรวจที่ตกลง
3. role/IDspoof/crossProject/expired-revokedsession/CSRF/Origin; pendingadvisor, otheradvisor, exitedmember, coordinatorper-roundfileaccess
4. missingadvisoraccepted, nonleader, pendingรอบเดิม, advisorrevision, committeeincomplete/approved/revision; latestbyidและoldroundimmutable
5. approved/revision_requestedตรวจครั้งเดียว ขอแก้ไขblankไม่ได้ reviewactor/timeถูกDBกำหนด failureตอนtransactionจบไม่ตอบsuccess
6. downloadbyte-for-byteและattachmentfilenameปลอดภัย ไม่อ่านไฟล์ผ่านlocalpathจากfilenameในrequest ไม่มีpublicdownloadURL
7. Browserrefresh/history, uploadbusy/duplicate, 413/validation, responseหายตรวจผลด้วยGETก่อน ไม่autoPOSTretry Desktop/Mobile
8. แยกsingle-sessionraceinjectionจากrealconcurrency ไม่COMMITfixtureเองเพื่อให้สองconnectionเห็นข้อมูล

## รายละเอียดที่ยังต้องยืนยันกับเจ้าของ

- URL/JSONenvelopes/fieldnames/errorcodes/listpagination/IDlookupและreadscopeของแต่ละroute
- parserและเกณฑ์เนื้อหาจริงPDF/PPTX, multipartlimits, filename/headerhandling, encryptedfile/ZIPresource policy
- UXหน้าเลือกไฟล์/history/review/revisionและnavigation ไม่มีDashboard/Notification/ขั้นCoordinatorใหม่โดยอัตโนมัติ

ทีมSควรส่งContract/ACก่อนPRimplementation และบันทึกdependencies/files/tests/ข้อจำกัดใน [Progress Template](../progress/PROGRESS_REPORT_TEMPLATE.md) ไม่เปลี่ยนV1เพื่อหลบข้อผิดพลาด
