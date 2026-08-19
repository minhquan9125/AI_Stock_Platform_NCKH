from processing.deduplicator import Deduplicator, content_hash
from processing.text_utils import canonicalize_url


def test_tracking_url_normalization():
    assert canonicalize_url("http://m.cafef.vn/a.chn?utm_source=x#top") == "https://cafef.vn/a.chn"


def test_url_and_content_duplicates():
    dedup = Deduplicator()
    assert dedup.add("https://cafef.vn/a.chn", "nội dung một")[0]
    assert dedup.add("https://cafef.vn/a.chn?utm_source=x", "khác")[1] == "duplicate_url"
    assert dedup.add("https://cafef.vn/b.chn", "nội dung một")[1] == "duplicate_content"
    assert content_hash(" a  b ") == content_hash("a b")


def test_near_duplicate():
    dedup = Deduplicator(80)
    dedup.add("https://cafef.vn/a.chn", "FPT doanh thu tăng mạnh trong năm nay")
    assert dedup.add("https://cafef.vn/b.chn", "FPT doanh thu tăng rất mạnh trong năm nay")[1] == "near_duplicate"


def test_same_event_with_reordered_boilerplate_is_near_duplicate():
    first = ("Tập đoàn FPT công bố lợi nhuận quý 2 đạt 2.000 tỷ đồng, tăng 20%. " * 20) + "Theo CafeF."
    second = "Theo thông tin doanh nghiệp. " + ("Lợi nhuận quý 2 của Tập đoàn FPT đạt 2.000 tỷ đồng và tăng 20%. " * 20)
    dedup = Deduplicator(80)
    assert dedup.add("https://cafef.vn/event-a.chn", first)[0]
    assert dedup.add("https://cafef.vn/event-b.chn", second)[1] == "near_duplicate"
