from pathlib import Path
from crawlers.cafef import CafeFArticleCrawler


class Response:
    text = Path("tests/fixtures/cafef_article.html").read_text(encoding="utf-8")
    url = "https://cafef.vn/fpt.chn"


class Client:
    def get(self, url): return Response()


def test_parser_offline_fixture():
    article = CafeFArticleCrawler(Client()).parse_article(Response.url)
    assert article.title == "FPT báo lãi tăng trưởng mạnh"
    assert article.published_at.isoformat() == "2026-07-29T09:30:00+07:00"
    assert "Quảng cáo" not in article.content
