
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


def create_app(settings: AuthSettings | None = None):
    app = FastAPI(title="Student Project Management API", version="0.1.0")
    app.state.auth_settings = settings or AuthSettings()
    app.include_router(router)
    app.add_exception_handler(AuthError, auth_error_handler)
    app.add_exception_handler(StorageUnavailable, storage_error_handler)
    app.add_exception_handler(EmailConflict, conflict_error_handler)
    app.add_exception_handler(RequestValidationError, auth_validation_error_handler)

    @app.middleware("http")
    async def auth_cache_headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/auth/"):
            response.headers["Cache-Control"] = "no-store"
        return response

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
