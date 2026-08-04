import fitz
import pytest
from processing.pdf_extractor import InvalidPdfError, extract_pdf, validate_pdf_bytes


def test_extract_text_pdf(tmp_path):
    path = tmp_path / "report.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "HOSE: FPT BUY Target price 101600 VND")
    document.save(path)
    document.close()
    result = extract_pdf(path)
    assert "HOSE: FPT" in result.text
    assert result.page_count == 1
    assert result.content_hash
    assert not result.needs_ocr


def test_scanned_pdf_needs_ocr(tmp_path):
    path = tmp_path / "scan.pdf"
    document = fitz.open(); document.new_page(); document.save(path); document.close()
    assert extract_pdf(path).needs_ocr


def test_fake_pdf_is_rejected():
    with pytest.raises(InvalidPdfError, match="magic"):
        validate_pdf_bytes(b"<html>blocked</html>", "text/html")
