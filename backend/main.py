
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

# Preserve both `uvicorn main:app` from backend and `uvicorn backend.main:app`
# from the repository root without importing the existing database engine.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.auth_api import (
    AuthError, AuthSettings, auth_error_handler, auth_validation_error_handler,
    conflict_error_handler, router, storage_error_handler,
)
from backend.auth_store import EmailConflict, StorageUnavailable
from backend.team_api import router as team_router, team_storage_error_handler, team_validation_error_handler
from backend.project_api import router as project_router, project_storage_error_handler, project_validation_error_handler
from backend.invitation_api import router as invitation_router, invitation_validation_error_handler
from backend.submission_api import (
    SubmissionBodyLimitMiddleware, router as submission_router,
    submission_validation_error_handler, submission_storage_error_handler,
)


def is_team_api_path(path):
    return path.rstrip("/") == "/api/v1/teams" or path.startswith("/api/v1/teams/")


def is_project_api_path(path):
    return path.rstrip("/") == "/api/v1/projects" or path.startswith("/api/v1/projects/")


def is_invitation_api_path(path):
    return (path.rstrip("/") == "/api/v1/advisor-invitations" or path.startswith("/api/v1/advisor-invitations/")
            or path.rstrip("/") in ("/api/v1/projects/me/advisor-candidates", "/api/v1/projects/me/advisor-invitations"))


def is_submission_api_path(path):
    return (path.startswith("/api/v1/project-submissions/")
            or path.startswith("/api/v1/projects/me/submissions")
            or path.rstrip("/") == "/api/v1/advisor/submissions")


async def request_validation_error_handler(request, exc):
    if is_submission_api_path(request.url.path):
        return await submission_validation_error_handler(request, exc)
    if is_invitation_api_path(request.url.path):
        return await invitation_validation_error_handler(request, exc)
    if is_project_api_path(request.url.path):
        return await project_validation_error_handler(request, exc)
    if is_team_api_path(request.url.path):
        return await team_validation_error_handler(request, exc)
    return await auth_validation_error_handler(request, exc)


async def request_storage_error_handler(request, exc):
    if is_submission_api_path(request.url.path):
        return await submission_storage_error_handler(request, exc)
    if is_project_api_path(request.url.path):
        return await project_storage_error_handler(request, exc)
    if is_team_api_path(request.url.path):
        return await team_storage_error_handler(request, exc)
    return await storage_error_handler(request, exc)


def create_app(settings: AuthSettings | None = None):
    app = FastAPI(title="Student Project Management API", version="0.1.0")
    app.state.auth_settings = settings or AuthSettings()
    app.include_router(router)
    app.include_router(team_router)
    app.include_router(project_router)
    app.include_router(invitation_router)
    app.include_router(submission_router)
    app.add_exception_handler(AuthError, auth_error_handler)
    app.add_exception_handler(StorageUnavailable, request_storage_error_handler)
    app.add_exception_handler(EmailConflict, conflict_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)

    @app.middleware("http")
    async def auth_cache_headers(request, call_next):
        response = await call_next(request)
        if (request.url.path.startswith("/api/v1/auth/") or is_team_api_path(request.url.path)
                or is_project_api_path(request.url.path) or is_invitation_api_path(request.url.path)
                or is_submission_api_path(request.url.path)):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(SubmissionBodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware, allow_origins=list(app.state.auth_settings.allowed_origins),
        allow_credentials=True, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.get("/")
    def root():
        return {"message": "Backend is running"}

    return app


app = create_app()
