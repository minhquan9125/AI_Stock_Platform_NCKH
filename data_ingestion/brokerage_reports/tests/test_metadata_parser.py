from processing.date_parser import parse_date
from processing.metadata_parser import infer_report_type, parse_analysts
from processing.valuation_parser import parse_valuation_methods


def test_report_types():
    assert infer_report_type("FPT - Báo cáo lần đầu") == "INITIATION_REPORT"
    assert infer_report_type("FPT - Cập nhật KQKD") == "EARNINGS_UPDATE"
    assert infer_report_type("Báo cáo ngành ngân hàng") == "INDUSTRY_REPORT"


def test_date_parser_timezone():
    assert parse_date("06/02/2026").isoformat() == "2026-02-06T00:00:00+07:00"
    assert parse_date("không rõ") is None


def test_analyst_and_valuation():
    text = "Chuyên viên phân tích: Nguyễn Văn A\nĐịnh giá bằng DCF, P/E và SOTP."
    assert parse_analysts(text) == ["Nguyễn Văn A"]
    assert parse_valuation_methods(text) == ["DCF", "P_E", "SOTP"]
