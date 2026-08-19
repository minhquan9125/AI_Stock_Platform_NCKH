from pathlib import Path
from processing.cleaner import extract_main_content


def test_cleaner_keeps_main_and_removes_junk():
    html = Path("tests/fixtures/cafef_article.html").read_text(encoding="utf-8")
    text = extract_main_content(html)
    assert "Tập đoàn FPT" in text
    assert "Quảng cáo" not in text and "Menu" not in text and "bad()" not in text
    assert "  " not in text


def test_no_global_paragraph_fallback():
    assert extract_main_content("<p>Nội dung ngoài container</p>") == ""
