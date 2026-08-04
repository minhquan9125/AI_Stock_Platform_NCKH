from pathlib import Path
from crawlers.common import parse_listing
from crawlers.vietstock import parse_finance_reports


def fixture(name):
    return Path("tests/fixtures", name).read_text(encoding="utf-8")


def test_vietstock_listing_distinguishes_platform_and_broker():
    rows = parse_finance_reports(fixture("vietstock_listing.html"), "FPT")
    assert len(rows) == 1
    assert rows[0].source_platform == "Vietstock Finance"
    assert rows[0].broker == "NSI"
    assert rows[0].pdf_url.endswith("/downloadedoc/18989")
    assert "/bao-cao-phan-tich/18989/" in rows[0].canonical_source_url


def test_ssi_listing():
    rows = parse_listing(fixture("ssi_listing.html"), "https://www.ssi.com.vn", "SSI Research", "SSI", "FPT")
    assert rows[0].broker == "SSI" and rows[0].pdf_url.endswith("/files/fpt.pdf")


def test_vndirect_listing():
    rows = parse_listing(fixture("vndirect_listing.html"), "https://www.vndirect.com.vn", "VNDirect Research", "VNDIRECT", "FPT")
    assert rows[0].report_type == "INITIATION_REPORT"
