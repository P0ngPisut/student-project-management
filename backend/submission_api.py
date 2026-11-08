"""HTTP endpoints for project submission, review and authorized file download."""

from datetime import datetime
import re
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, field_validator
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException

from backend.auth_api import (
    CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, AuthError,
    error_response, require_origin, unauthenticated,
)
from backend.auth_security import session_digest, valid_csrf
from backend.submission_store import SubmissionError, submission_transaction
from backend.submission_validation import MAX_FILE_BYTES, SubmissionFileError, validate_submission_file

Status = Literal["pending_review", "approved", "revision_requested"]
MAX_MULTIPART_BYTES = MAX_FILE_BYTES + 65_536


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    decision: Literal["approved", "revision_requested"]
    comment: str | None = None

    @field_validator("comment")
    @classmethod
    def comment_format(cls, value):
        if value is None:
            return None
        if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("REVIEW_COMMENT_INVALID")
        value = value.strip(" \t\n\r\f\v")
        return value or None


class Submission(BaseModel):
    id: str
    project_id: str
    submitted_by: str
    submitted_at: datetime
    snapshot_name: str
    snapshot_description: str | None
    status: Status
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_comment: str | None
    original_filename: str
    mime_type: str
    team_name: str


class SubmissionResponse(BaseModel):
    data: Submission


class SubmissionListResponse(BaseModel):
    data: list[Submission]


class SubmissionEligibility(BaseModel):
    can_submit: bool


class SubmissionEligibilityResponse(BaseModel):
    data: SubmissionEligibility


ERRORS = {
    "TEAM_NOT_FOUND": (404, "คุณยังไม่มีทีม"),
    "PROJECT_NOT_FOUND": (404, "ไม่พบโครงงานของทีม"),
    "SUBMISSION_NOT_FOUND": (404, "ไม่พบรายการส่งที่คุณมีสิทธิ์เข้าถึง"),
    "SUBMISSION_ACTION_FORBIDDEN": (403, "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่ส่งโครงงานได้"),
    "ACCEPTED_ADVISOR_REQUIRED": (409, "ต้องมีอาจารย์ที่ปรึกษาตอบรับก่อนส่งโครงงาน"),
    "SUBMISSION_PENDING": (409, "มีรายการส่งที่กำลังรอตรวจอยู่แล้ว"),
    "SUBMISSION_PHASE_CLOSED": (409, "ยังไม่สามารถส่งรอบใหม่ในขั้นตอนนี้ได้"),
    "SUBMISSION_ALREADY_REVIEWED": (409, "รายการนี้ได้รับการตรวจแล้ว"),
}
FILE_ERRORS = {
    "FILE_EMPTY": (422, "ไฟล์ว่างเปล่า"),
    "FILE_TOO_LARGE": (413, "ไฟล์ต้องมีขนาดไม่เกิน 4,000,000 ไบต์"),
    "FILE_NAME_INVALID": (422, "ชื่อไฟล์ไม่ถูกต้อง"),
    "FILE_TYPE_UNSUPPORTED": (422, "รองรับเฉพาะไฟล์ PDF หรือ PPTX"),
    "FILE_TYPE_MISMATCH": (422, "ชนิดไฟล์ไม่ตรงกับนามสกุลหรือเนื้อหา"),
    "FILE_CONTENT_INVALID": (422, "ไม่สามารถอ่านเนื้อหาไฟล์ได้ หรือไฟล์ไม่ใช่เอกสารที่สมบูรณ์"),
}
router = APIRouter(tags=["project submissions"], dependencies=[Depends(require_origin)])


def get_submission_uow():
    return submission_transaction


def actor(request, store, *, write=False, roles=None):
    token = request.cookies.get(SESSION_COOKIE)
    digest = session_digest(token)
    user = store.auth.active_user(digest) if digest is not None else None
    if user is None:
        raise unauthenticated()
    if write and not valid_csrf(token, request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
        raise AuthError(403, "CSRF_INVALID", "ข้อมูลยืนยันคำขอไม่ถูกต้อง")
    if roles is not None and user["role"] not in roles:
        raise AuthError(403, "SUBMISSION_ACCESS_FORBIDDEN", "บทบาทของคุณไม่สามารถทำรายการนี้ได้")
    return user


def run(request, uow, operation, *, write=False, roles=None):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            user = actor(request, store, write=write, roles=roles)
            result = operation(store, user)
    except SubmissionError as exc:
        status, message = ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return result


class SubmissionBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    @staticmethod
    async def too_large(send):
        body = ('{"error":{"code":"FILE_TOO_LARGE","message":"'
                + FILE_ERRORS["FILE_TOO_LARGE"][1] + '"}}').encode("utf-8")
        await send({"type": "http.response.start", "status": 413, "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
        ]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope["method"] != "POST"
                or scope["path"] != "/api/v1/projects/me/submissions"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", ()))
        content_length = headers.get(b"content-length")
        if content_length is not None and content_length.isdigit() and int(content_length) > MAX_MULTIPART_BYTES:
            await self.too_large(send)
            return

        size = 0
        exceeded = False
        response_started = False

        async def bounded_receive():
            nonlocal size, exceeded
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                remaining = MAX_MULTIPART_BYTES - size
                if len(body) > remaining:
                    message = dict(message)
                    message["body"] = body[:remaining]
                    message["more_body"] = False
                    size = MAX_MULTIPART_BYTES
                    exceeded = True
                else:
                    size += len(body)
            return message

        async def bounded_send(message):
            nonlocal response_started
            if exceeded:
                if message["type"] == "http.response.start" and not response_started:
                    response_started = True
                    await self.too_large(send)
                return
            await send(message)

        await self.app(scope, bounded_receive, bounded_send)


def path_id(value: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]{0,18}", value) or int(value) > 9223372036854775807:
        raise AuthError(422, "VALIDATION_ERROR", "รหัสรายการส่งไม่ถูกต้อง")
    return int(value)


def file_error_response(exc: SubmissionFileError):
    status, message = FILE_ERRORS[exc.code]
    return error_response(status, exc.code, message)


@router.get("/api/v1/projects/me/submissions", response_model=SubmissionListResponse)
def team_history(request: Request, uow=Depends(get_submission_uow)):
    result = run(request, uow, lambda store, user: store.team_history(user["id"]), roles={"student"})
    return SubmissionListResponse(data=result)


@router.get("/api/v1/projects/me/submissions/eligibility", response_model=SubmissionEligibilityResponse)
def team_eligibility(request: Request, uow=Depends(get_submission_uow)):
    result = run(request, uow, lambda store, user: {"can_submit": store.eligibility(user["id"])},
                 roles={"student"})
    return SubmissionEligibilityResponse(data=result)


@router.post(
    "/api/v1/projects/me/submissions",
    status_code=201,
    response_model=SubmissionResponse,
    openapi_extra={"requestBody": {
        "required": True,
        "content": {"multipart/form-data": {"schema": {
            "type": "object",
            "required": ["file"],
            "properties": {"file": {"type": "string", "format": "binary"}},
        }}},
    }},
)
async def submit(request: Request, uow=Depends(get_submission_uow)):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            user = actor(request, store, write=True, roles={"student"})
        try:
            form = await request.form(max_files=1, max_fields=0, max_part_size=MAX_FILE_BYTES)
        except (MultiPartException, StarletteHTTPException):
            raise AuthError(422, "VALIDATION_ERROR", "ข้อมูลอัปโหลดไม่ถูกต้อง") from None
        try:
            files = [value for key, value in form.multi_items() if key == "file" and isinstance(value, UploadFile)]
            if len(files) != 1 or len(form) != 1:
                raise AuthError(422, "VALIDATION_ERROR", "กรุณาส่งไฟล์หนึ่งไฟล์ในช่อง file เท่านั้น")
            upload = files[0]
            data = bytearray()
            while True:
                chunk = await upload.read(64 * 1024)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_FILE_BYTES:
                    raise AuthError(413, "FILE_TOO_LARGE", FILE_ERRORS["FILE_TOO_LARGE"][1])
            filename, mime_type = validate_submission_file(upload.filename, upload.content_type, bytes(data))
        finally:
            await form.close()
        with uow() as store:
            current_user = actor(request, store, write=True, roles={"student"})
            if current_user["id"] != user["id"]:
                raise unauthenticated()
            result = store.submit(user["id"], filename, mime_type, bytes(data))
        return SubmissionResponse(data=result)
    except SubmissionError as exc:
        status, message = ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    except SubmissionFileError as exc:
        return file_error_response(exc)


@router.get("/api/v1/advisor/submissions", response_model=SubmissionListResponse)
def advisor_inbox(request: Request, uow=Depends(get_submission_uow)):
    result = run(request, uow, lambda store, user: store.advisor_inbox(user["id"]), roles={"advisor"})
    return SubmissionListResponse(data=result)


@router.get("/api/v1/project-submissions/{submission_id}", response_model=SubmissionResponse)
def detail(submission_id: str, request: Request, uow=Depends(get_submission_uow)):
    result = run(request, uow,
        lambda store, user: store.detail(user["id"], user["role"], path_id(submission_id)))
    return SubmissionResponse(data=result)


@router.get("/api/v1/project-submissions/{submission_id}/file")
def download(submission_id: str, request: Request, uow=Depends(get_submission_uow)):
    payload = run(request, uow,
        lambda store, user: store.file(user["id"], user["role"], path_id(submission_id)))
    data, _, mime_type = payload
    suffix = "pdf" if mime_type == "application/pdf" else "pptx"
    return Response(
        content=data,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="submission-{submission_id}.{suffix}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(len(data)),
        },
    )


@router.post("/api/v1/project-submissions/{submission_id}/review", response_model=SubmissionResponse)
def review(submission_id: str, payload: ReviewInput, request: Request, uow=Depends(get_submission_uow)):
    if payload.decision == "revision_requested" and not payload.comment:
        raise AuthError(422, "VALIDATION_ERROR", "การขอแก้ไขต้องระบุความเห็น")
    result = run(request, uow, lambda store, user: store.review(
        user["id"], path_id(submission_id), payload.decision, payload.comment),
        write=True, roles={"advisor"})
    return SubmissionResponse(data=result)


async def submission_validation_error_handler(request, exc):
    fields = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = location[1] if len(location) > 1 and location[1] in ("decision", "comment") else "body"
        original = error.get("ctx", {}).get("error")
        code = str(original) if original is not None else ""
        if code != "REVIEW_COMMENT_INVALID":
            code = {"missing": "REQUIRED", "extra_forbidden": "UNEXPECTED_FIELD",
                    "json_invalid": "INVALID_JSON"}.get(error["type"], "INVALID_TYPE")
        item = {"field": field, "code": code}
        if item not in fields:
            fields.append(item)
    return error_response(422, "VALIDATION_ERROR", "ข้อมูลการตรวจไม่ถูกต้อง", fields)


async def submission_storage_error_handler(request, exc):
    return error_response(500, "INTERNAL_ERROR", "ระบบส่งโครงงานยังไม่พร้อมใช้งาน กรุณาลองอีกครั้ง")
