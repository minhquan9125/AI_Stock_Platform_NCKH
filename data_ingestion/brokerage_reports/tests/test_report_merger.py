from services.report_merger import ReportMerger


def report(source, url):
    return {
        "broker": "SSI",
        "source_platform": source,
        "canonical_source_url": url,
        "mirror_urls": [],
        "pdf_hash": "same-pdf",
    }


def test_official_source_wins_and_aggregators_become_mirrors():
    merger = ReportMerger()
    merged = merger.merge(
        report("CafeF", "https://cafef.vn/report/1"),
        report("Vietstock Finance", "https://finance.vietstock.vn/report/1"),
    )
    merged = merger.merge(
        merged,
        report("SSI Research", "https://www.ssi.com.vn/research/1"),
    )
    assert merged["canonical_source_url"] == "https://www.ssi.com.vn/research/1"
    assert set(merged["mirror_urls"]) == {
        "https://cafef.vn/report/1",
        "https://finance.vietstock.vn/report/1",
    }
