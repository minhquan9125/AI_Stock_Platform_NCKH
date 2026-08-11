from processing.ticker_validator import validate_ticker

POSITIVE = ["Tập đoàn FPT", "FPT Corporation", "Công ty Cổ phần FPT", "HOSE: FPT", "cổ phiếu FPT", "mã FPT"]
EXCLUDED = {"FPT Retail": "FRT", "FPT Telecom": "FOX", "FPT Securities": "FTS", "Chứng khoán FPT": "FTS", "FPT Online": "FOC"}


def validate(title, text):
    return validate_ticker("FPT", "Công ty Cổ phần FPT", POSITIVE, EXCLUDED, title, text)


def test_accepts_explicit_fpt():
    assert validate("Báo cáo FPT", "CÔNG TY CỔ PHẦN FPT – HOSE: FPT").accepted


def test_rejects_fpt_retail():
    result = validate("FPT Retail cập nhật KQKD", "FPT Retail – HOSE: FRT " * 30)
    assert not result.accepted
    assert any(note.startswith("excluded_entity") for note in result.notes)


def test_rejects_bare_ticker_filename():
    assert not validate("FPT_report.pdf", "Nội dung không xác định doanh nghiệp").accepted


def test_accepts_exact_ticker_report_heading_with_repeated_pdf_evidence():
    assert validate("FPT: Cập nhật KQKD", "FPT ghi nhận doanh thu. FPT có lợi nhuận tăng. FPT được định giá bằng P/E.").accepted


def test_accepts_ssi_parenthesized_report_heading():
    assert validate("FPT (MUA, Giá mục tiêu: 101.600 đồng)", "SSI duy trì khuyến nghị MUA với FPT.").accepted
