from processing.deduplicator import find_duplicate


def base(**values):
    data = {"ticker": ["FPT"], "broker": "SSI", "published_at": "2026-01-01", "title": "FPT cập nhật", "canonical_source_url": "https://x/a", "pdf_hash": None, "content_hash": None, "_text": "Tập đoàn FPT báo cáo lợi nhuận"}
    data.update(values)
    return data


def test_same_pdf_hash_with_different_urls_is_duplicate():
    old = base(pdf_hash="abc", canonical_source_url="https://ssi.com.vn/a")
    new = base(pdf_hash="abc", canonical_source_url="https://vietstock.vn/b")
    result = find_duplicate(new, [old])
    assert result.duplicate and result.reason == "duplicate_pdf_hash"


def test_same_content_hash_is_duplicate():
    assert find_duplicate(base(content_hash="same"), [base(content_hash="same")]).reason == "duplicate_content_hash"


def test_near_duplicate_text():
    old = base(title="FPT cập nhật KQKD quý 2", _text="Tập đoàn FPT lợi nhuận tăng 20% " * 20)
    new = base(title="Cập nhật kết quả kinh doanh quý 2 FPT", canonical_source_url="https://x/b", _text="Lợi nhuận Tập đoàn FPT tăng 20% " * 20)
    assert find_duplicate(new, [old], 80).duplicate


def test_different_brokers_are_not_fuzzy_merged():
    old = base(broker="SSI", title="FPT khuyến nghị MUA", _text="Tập đoàn FPT lợi nhuận tăng " * 30)
    new = base(broker="KBSV", title="FPT khuyến nghị MUA", canonical_source_url="https://x/b", _text="Tập đoàn FPT lợi nhuận tăng " * 30)
    assert not find_duplicate(new, [old], 80).duplicate
