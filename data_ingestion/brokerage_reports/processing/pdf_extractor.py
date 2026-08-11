import hashlib
from dataclasses import dataclass
from pathlib import Path
import fitz
import pdfplumber


class InvalidPdfError(ValueError):
    """Response không phải tài liệu PDF hợp lệ."""


def validate_pdf_bytes(data: bytes, content_type: str | None = None) -> None:
    if not data.startswith(b"%PDF-"):
        raise InvalidPdfError("file_missing_pdf_magic_bytes")
    if content_type and "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
        raise InvalidPdfError(f"invalid_pdf_content_type:{content_type}")


@dataclass(slots=True)
class ExtractedPdf:
    text: str
    pages: list[str]
    page_count: int
    content_hash: str
    needs_ocr: bool


def extract_pdf(path: Path) -> ExtractedPdf:
    try:
        with fitz.open(path) as document:
            pages = [page.get_text("text").strip() for page in document]
    except (fitz.FileDataError, RuntimeError, ValueError):
        with pdfplumber.open(path) as document:
            pages = [(page.extract_text() or "").strip() for page in document.pages]
    text = "\n\n".join(pages).strip()
    return ExtractedPdf(text, pages, len(pages), hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "", len(text) < max(20, len(pages) * 10))
