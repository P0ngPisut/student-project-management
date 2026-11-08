"""Session-authorized V1 advisor invitation workflow."""

from datetime import datetime
import re
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, field_validator

from backend.auth_api import (
    CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, AuthError,
    error_response, require_origin, unauthenticated,
)
from backend.auth_security import session_digest, valid_csrf
from backend.invitation_store import InvitationError, invitation_transaction

Status = Literal["pending", "accepted", "rejected", "cancelled"]


def positive_bigint(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,19}", value) or not 0 < int(value) <= 9223372036854775807:
        raise ValueError("INVALID_ID")
    return str(int(value))


class SendInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    advisor_id: str

    @field_validator("advisor_id")
    @classmethod
    def id_format(cls, value):
        return positive_bigint(value)


class RespondInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    decision: Literal["accepted", "rejected"]


class CancelInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class Candidate(BaseModel):
    id: str
    full_name: str


class TeamInvitation(BaseModel):
    id: str
    advisor: Candidate
    status: Status
    sent_at: datetime
    resolved_at: datetime | None


class ProjectContext(BaseModel):
    team_name: str
    project_name: str
    project_description: str | None


class AdvisorInvitation(BaseModel):
    id: str
    status: Status
    sent_at: datetime
    resolved_at: datetime | None
    project_context: ProjectContext | None


class CandidatesResponse(BaseModel):
    data: list[Candidate]


class TeamHistoryResponse(BaseModel):
    data: list[TeamInvitation]


class TeamInvitationResponse(BaseModel):
    data: TeamInvitation


class AdvisorHistoryResponse(BaseModel):
    data: list[AdvisorInvitation]


class AdvisorInvitationResponse(BaseModel):
    data: AdvisorInvitation


ERRORS = {
    "TEAM_NOT_FOUND": (404, "คุณยังไม่มีทีม"),
    "PROJECT_NOT_FOUND": (404, "ทีมของคุณยังไม่มีโครงงาน"),
    "INVITATION_ACTION_FORBIDDEN": (403, "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่ทำรายการนี้ได้"),
    "ADVISOR_NOT_FOUND": (404, "ไม่พบอาจารย์ที่เชิญได้"),
    "INVITATION_NOT_FOUND": (404, "ไม่พบคำเชิญ"),
    "INVITATION_ALREADY_PENDING": (409, "โครงงานมีคำเชิญที่รอตอบรับอยู่แล้ว"),
    "ADVISOR_ALREADY_ACCEPTED": (409, "โครงงานมีอาจารย์ตอบรับแล้ว ไม่สามารถเปลี่ยนอาจารย์ได้"),
    "INVITATION_ALREADY_RESOLVED": (409, "คำเชิญนี้สิ้นสุดแล้ว กรุณาโหลดประวัติใหม่"),
    "INVITATION_CONFLICT": (409, "ข้อมูลคำเชิญเปลี่ยนแปลง กรุณาโหลดประวัติใหม่"),
}


def get_invitation_uow():
    return invitation_transaction


def actor(request, store, role):
    token = request.cookies.get(SESSION_COOKIE)
    digest = session_digest(token)
    user = store.auth.active_user(digest) if digest is not None else None
    if user is None:
        raise unauthenticated()
    if request.method == "POST" and not valid_csrf(token, request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
        raise AuthError(403, "CSRF_INVALID", "ข้อมูลยืนยันคำขอไม่ถูกต้อง")
    if user["role"] != role:
        raise AuthError(403, "INVITATION_ACCESS_FORBIDDEN", "บทบาทของคุณไม่สามารถใช้หน้านี้ได้")
    return user["id"]


def run(request, uow, role, operation):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            result = operation(store, actor(request, store, role))
    except InvitationError as exc:
        status, message = ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return result


def path_id(value):
    try:
        return positive_bigint(value)
    except ValueError:
        # Never echo an untrusted path/ID through validation output.
        raise AuthError(422, "VALIDATION_ERROR", "รหัสคำเชิญไม่ถูกต้อง") from None


router = APIRouter(tags=["advisor invitations"], dependencies=[Depends(require_origin)])


@router.get("/api/v1/projects/me/advisor-candidates", response_model=CandidatesResponse)
def candidates(request: Request, uow=Depends(get_invitation_uow)):
    return run(request, uow, "student", lambda store, uid: CandidatesResponse(data=store.candidates(uid)))


@router.get("/api/v1/projects/me/advisor-invitations", response_model=TeamHistoryResponse)
def team_history(request: Request, uow=Depends(get_invitation_uow)):
    return run(request, uow, "student", lambda store, uid: TeamHistoryResponse(data=store.team_history(uid)))


@router.post("/api/v1/projects/me/advisor-invitations", status_code=201, response_model=TeamInvitationResponse)
def send(payload: SendInput, request: Request, uow=Depends(get_invitation_uow)):
    return run(request, uow, "student", lambda store, uid: TeamInvitationResponse(data=store.send(uid, payload.advisor_id)))


@router.get("/api/v1/advisor-invitations/me", response_model=AdvisorHistoryResponse)
def advisor_history(request: Request, uow=Depends(get_invitation_uow)):
    return run(request, uow, "advisor", lambda store, uid: AdvisorHistoryResponse(data=store.advisor_history(uid)))


@router.post("/api/v1/advisor-invitations/{invitation_id}/cancel", response_model=TeamInvitationResponse)
def cancel(invitation_id: str, request: Request, payload: CancelInput | None = None, uow=Depends(get_invitation_uow)):
    return run(request, uow, "student", lambda store, uid: TeamInvitationResponse(data=store.resolve(uid, path_id(invitation_id), "cancelled", advisor=False)))


@router.post("/api/v1/advisor-invitations/{invitation_id}/respond", response_model=AdvisorInvitationResponse)
def respond(invitation_id: str, payload: RespondInput, request: Request, uow=Depends(get_invitation_uow)):
    return run(request, uow, "advisor", lambda store, uid: AdvisorInvitationResponse(data=store.resolve(uid, path_id(invitation_id), payload.decision, advisor=True)))


async def invitation_validation_error_handler(request, exc):
    fields = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = location[1] if len(location) > 1 and location[1] in ("advisor_id", "decision") else "body"
        original = error.get("ctx", {}).get("error")
        code = str(original) if original is not None else ""
        if code != "INVALID_ID":
            code = {"missing": "REQUIRED", "extra_forbidden": "UNEXPECTED_FIELD", "json_invalid": "INVALID_JSON"}.get(error["type"], "INVALID_TYPE")
        item = {"field": field, "code": code}
        if item not in fields:
            fields.append(item)
    return error_response(422, "VALIDATION_ERROR", "ข้อมูลคำเชิญไม่ถูกต้อง", fields)
