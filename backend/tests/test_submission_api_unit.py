"""HTTP upload-boundary tests using an isolated in-memory repository double."""

from contextlib import contextmanager
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from backend.main import create_app
from backend.submission_api import get_submission_uow
from backend.submission_validation import MAX_FILE_BYTES, PDF_MIME
from backend.tests.test_submission_validation import valid_pdf

ORIGIN = {"Origin": "http://localhost:3000"}
USER = {"id": "301", "full_name": "Submission fixture", "email": "fixture@example.test", "role": "student"}


class FakeAuth:
    def active_user(self, digest):
        return USER


class FakeStore:
    def __init__(self):
        self.auth = FakeAuth()
        self.uploads = []

    def submit(self, actor, filename, mime_type, data):
        self.uploads.append((actor, filename, mime_type, data))
        return {
            "id": "701", "project_id": "401", "submitted_by": actor,
            "submitted_at": datetime(2026, 11, 7, tzinfo=timezone.utc),
            "snapshot_name": "Submission fixture", "snapshot_description": None,
            "status": "pending_review", "reviewed_by": None, "reviewed_at": None,
            "review_comment": None, "original_filename": filename, "mime_type": mime_type,
            "team_name": "Submission team",
        }


class SubmissionUploadHTTPTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()

        @contextmanager
        def fake_uow():
            yield self.store

        self.app = create_app()
        self.app.dependency_overrides[get_submission_uow] = lambda: fake_uow
        self.client = TestClient(self.app, base_url="http://localhost:8000")
        self.client.cookies.set(SESSION_COOKIE, "session-fixture")
        self.client.cookies.set(CSRF_COOKIE, "csrf-fixture")

    def tearDown(self):
        self.client.close()

    def post_file(self, filename="proposal.pdf", data=None, mime=PDF_MIME):
        return self.client.post("/api/v1/projects/me/submissions",
            headers={**ORIGIN, CSRF_HEADER: "csrf-fixture"},
            files={"file": (filename, valid_pdf() if data is None else data, mime)})

    def test_valid_file_is_streamed_into_repository_and_returns_public_dto(self):
        payload = valid_pdf()
        with patch("backend.submission_api.session_digest", return_value="digest"), \
                patch("backend.submission_api.valid_csrf", return_value=True):
            response = self.post_file(data=payload)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["data"]["id"], "701")
        self.assertEqual(self.store.uploads[0][0:3], ("301", "proposal.pdf", PDF_MIME))
        self.assertEqual(self.store.uploads[0][3], payload)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_invalid_or_over_limit_uploads_are_rejected_without_repository_write(self):
        with patch("backend.submission_api.session_digest", return_value="digest"), \
                patch("backend.submission_api.valid_csrf", return_value=True):
            invalid = self.post_file("fake.pdf", b"%PDF-1.7\nnot a document")
            too_large = self.post_file("large.pdf", b"x" * (MAX_FILE_BYTES + 1))
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json()["error"]["code"], "FILE_CONTENT_INVALID")
        self.assertEqual(too_large.status_code, 413)
        self.assertEqual(too_large.json()["error"]["code"], "FILE_TOO_LARGE")
        self.assertEqual(self.store.uploads, [])

    def test_session_is_revalidated_after_file_is_parsed(self):
        calls = 0

        class RevokedAuth:
            def active_user(self, digest):
                nonlocal calls
                calls += 1
                return USER if calls == 1 else None

        self.store.auth = RevokedAuth()
        with patch("backend.submission_api.session_digest", return_value="digest"), \
                patch("backend.submission_api.valid_csrf", return_value=True):
            response = self.post_file()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.store.uploads, [])


if __name__ == "__main__":
    unittest.main()
