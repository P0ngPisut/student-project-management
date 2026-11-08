"""Content validation for the bounded PDF/PPTX submission upload."""

from io import BytesIO
import json
import unittest

from pptx import Presentation
from pypdf import PdfWriter

from backend.main import create_app
from backend.submission_api import MAX_MULTIPART_BYTES, SubmissionBodyLimitMiddleware
from backend.submission_validation import (
    PDF_MIME, PPTX_MIME, SubmissionFileError, validate_submission_file,
)
from fastapi.testclient import TestClient


def valid_pdf():
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


def valid_pptx():
    output = BytesIO()
    presentation = Presentation()
    presentation.slides.add_slide(presentation.slide_layouts[6])
    presentation.save(output)
    return output.getvalue()


class SubmissionFileValidationTests(unittest.TestCase):
    def test_valid_pdf_and_pptx_are_parsed_and_normalized(self):
        self.assertEqual(validate_submission_file("  topic.PDF  ", PDF_MIME, valid_pdf()),
                         ("topic.PDF", PDF_MIME))
        self.assertEqual(validate_submission_file("topic.pptx", PPTX_MIME, valid_pptx()),
                         ("topic.pptx", PPTX_MIME))

    def test_empty_oversized_unsupported_mismatched_and_fake_files_are_rejected(self):
        cases = [
            (None, PDF_MIME, b"", "FILE_EMPTY"),
            ("topic.pdf", PDF_MIME, b"x" * 4_000_001, "FILE_TOO_LARGE"),
            ("topic.docx", PDF_MIME, valid_pdf(), "FILE_TYPE_UNSUPPORTED"),
            ("topic.pdf", "application/octet-stream", valid_pdf(), "FILE_TYPE_MISMATCH"),
            ("topic.pdf", PDF_MIME, b"%PDF-1.7\nnot a document", "FILE_CONTENT_INVALID"),
            ("topic.pptx", PPTX_MIME, b"PK\x03\x04fake archive", "FILE_CONTENT_INVALID"),
        ]
        for filename, mime, payload, expected in cases:
            with self.subTest(expected=expected), self.assertRaises(SubmissionFileError) as caught:
                validate_submission_file(filename, mime, payload)
            self.assertEqual(caught.exception.code, expected)


class SubmissionBodyLimitTests(unittest.IsolatedAsyncioTestCase):
    def test_openapi_documents_multipart_file_field_and_workflow_routes(self):
        paths = create_app().openapi()["paths"]
        upload = paths["/api/v1/projects/me/submissions"]["post"]["requestBody"]
        schema = upload["content"]["multipart/form-data"]["schema"]
        self.assertEqual(schema["required"], ["file"])
        self.assertEqual(schema["properties"]["file"], {"type": "string", "format": "binary"})
        self.assertIn("/api/v1/projects/me/submissions/eligibility", paths)
        self.assertIn("/api/v1/advisor/submissions", paths)
        self.assertIn("/api/v1/project-submissions/{submission_id}/file", paths)

    async def test_actual_multipart_body_size_is_limited_without_content_length(self):
        requests = [{"type": "http.request", "body": b"x" * (MAX_MULTIPART_BYTES + 1), "more_body": False}]
        responses = []

        async def receive():
            return requests.pop(0)

        async def send(message):
            responses.append(message)

        async def consume_body(scope, body_receive, body_send):
            message = await body_receive()
            self.assertEqual(message["type"], "http.request")
            await body_send({"type": "http.response.start", "status": 200, "headers": []})
            await body_send({"type": "http.response.body", "body": b"unexpected success"})

        middleware = SubmissionBodyLimitMiddleware(consume_body)
        await middleware({
            "type": "http",
            "method": "POST",
            "path": "/api/v1/projects/me/submissions",
            "headers": [],
        }, receive, send)
        self.assertEqual(responses[0]["status"], 413)
        self.assertIn((b"cache-control", b"no-store"), responses[0]["headers"])
        self.assertEqual(json.loads(responses[1]["body"])["error"]["code"], "FILE_TOO_LARGE")

    def test_content_length_rejection_has_cors_and_no_store_without_database_access(self):
        client = TestClient(create_app(), base_url="http://localhost:8000")
        response = client.post("/api/v1/projects/me/submissions",
            headers={"Origin": "http://localhost:3000"},
            content=b"x" * (MAX_MULTIPART_BYTES + 1))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:3000")


if __name__ == "__main__":
    unittest.main()
