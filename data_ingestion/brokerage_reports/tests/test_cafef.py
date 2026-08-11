from crawlers.cafef import parse_cafef_detail


HTML = """
<html><head><link rel="canonical" href="https://cafef.vn/du-lieu/report/fpt-x.chn"></head>
<body><div class="bcpt_detail_1_news">
  <div class="item-first-content-title" title="FPT - OUTPERFORM - Cập nhật KQKD"></div>
  <div class="item-first-content-body-item"><div class="item-first-content-body-item-left">Mã CK:</div><div class="item-first-content-body-item-right">FPT</div></div>
  <div class="item-first-content-body-item"><div class="item-first-content-body-item-left">Nguồn báo cáo:</div><div class="item-first-content-body-item-right"><a href="https://www.bvsc.com.vn">BVSC</a></div></div>
  <div class="item-first-content-body-item"><div class="item-first-content-body-item-left">Loại báo cáo:</div><div class="item-first-content-body-item-right">Cập nhật doanh nghiệp - Khuyến nghị</div></div>
  <div class="item-first-content-body-item"><div class="item-first-content-body-item-left">Ngày phát hành:</div><div class="item-first-content-body-item-right">26/06/2026</div></div>
  <div class="item-child-content-summary-ai">Nội dung do AI tạo, không được lấy.</div>
</div></body></html>
"""


def test_parse_cafef_metadata_and_ignore_ai_summary():
    report = parse_cafef_detail(HTML, "https://cafef.vn/du-lieu/report/fpt-x.chn")
    assert report.ticker == ["FPT"]
    assert report.broker == "BVS"
    assert report.published_at.date().isoformat() == "2026-06-26"
    assert report.description is None
    assert "Nội dung do AI tạo" not in report.page_text
