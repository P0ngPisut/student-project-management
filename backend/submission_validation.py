"""Content validation for bounded PDF and PPTX project submissions."""

from io import BytesIO
from pathlib import PurePosixPath
import zipfile
import zlib

from lxml.etree import XMLSyntaxError
from pptx import Presentation
from pptx.exc import InvalidXmlError, PackageNotFoundError, PythonPptxError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_FILE_BYTES = 4_000_000
MAX_PPTX_EXPANDED_BYTES = 32_000_000
MAX_PPTX_PARTS = 2_000
ASCII_SPACE = " \t\n\r\f\v"
PDF_MIME = "application/pdf"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class SubmissionFileError(Exception):
    def __init__(self, code: str):
        self.code = code


def _validate_pdf(data: bytes) -> None:
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if len(reader.pages) < 1:
            raise SubmissionFileError("FILE_CONTENT_INVALID")
    except (PdfReadError, ValueError, OSError, KeyError, TypeError, EOFError, IndexError):
        raise SubmissionFileError("FILE_CONTENT_INVALID") from None


def _validate_pptx(data: bytes) -> None:
    try:
        with zipfile.ZipFile(BytesIO(data)) as package:
            parts = package.infolist()
            if (len(parts) > MAX_PPTX_PARTS
                    or sum(part.file_size for part in parts) > MAX_PPTX_EXPANDED_BYTES
                    or any(PurePosixPath(part.filename).is_absolute()
                           or ".." in PurePosixPath(part.filename).parts for part in parts)
                    or not {"[Content_Types].xml", "ppt/presentation.xml"}.issubset(package.namelist())):
                raise SubmissionFileError("FILE_CONTENT_INVALID")
            bad_part = package.testzip()
            if bad_part is not None:
                raise SubmissionFileError("FILE_CONTENT_INVALID")
        presentation = Presentation(BytesIO(data))
        if len(presentation.slides) < 1:
            raise SubmissionFileError("FILE_CONTENT_INVALID")
    except (zipfile.BadZipFile, zipfile.LargeZipFile, InvalidXmlError,
            PackageNotFoundError, PythonPptxError, XMLSyntaxError,
            KeyError, ValueError, OSError, TypeError, RuntimeError,
            NotImplementedError, zlib.error, IndexError):
        raise SubmissionFileError("FILE_CONTENT_INVALID") from None


def validate_submission_file(filename: str | None, content_type: str | None, data: bytes) -> tuple[str, str]:
    if not data:
        raise SubmissionFileError("FILE_EMPTY")
    if len(data) > MAX_FILE_BYTES:
        raise SubmissionFileError("FILE_TOO_LARGE")
    if filename is None:
        raise SubmissionFileError("FILE_NAME_INVALID")

    normalized_name = filename.strip(ASCII_SPACE)
    if (not normalized_name or len(normalized_name) > 255
            or any(ord(char) < 32 or ord(char) == 127 for char in normalized_name)):
        raise SubmissionFileError("FILE_NAME_INVALID")

    extension = normalized_name.rsplit(".", 1)[-1].lower() if "." in normalized_name else ""
    if extension == "pdf":
        if content_type != PDF_MIME:
            raise SubmissionFileError("FILE_TYPE_MISMATCH")
        _validate_pdf(data)
        return normalized_name, PDF_MIME
    if extension == "pptx":
        if content_type != PPTX_MIME:
            raise SubmissionFileError("FILE_TYPE_MISMATCH")
        _validate_pptx(data)
        return normalized_name, PPTX_MIME
    raise SubmissionFileError("FILE_TYPE_UNSUPPORTED")
