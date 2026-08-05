from urllib.parse import quote
from models import ReportCandidate
from .base import BaseCrawler
from .common import parse_detail, parse_listing


class VNDirectCrawler(BaseCrawler):
    source_key = "vndirect"
    source_platform = "VNDirect Research"
    official_broker = "VNDIRECT"
    base_url = "https://www.vndirect.com.vn"

    def search_reports(self, ticker: str, max_pages: int, limit: int | None) -> list[ReportCandidate]:
        found: dict[str, ReportCandidate] = {}
        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/page/{page}/?s={quote(ticker)}"
            for item in parse_listing(self.client.get(url).text, self.base_url, self.source_platform, self.official_broker, ticker):
                found[item.canonical_source_url] = item
                if limit and len(found) >= limit: return list(found.values())
        return list(found.values())

    def fetch_detail(self, candidate: ReportCandidate) -> ReportCandidate:
        return parse_detail(candidate, self.client.get(candidate.source_page_url).text, self.base_url, self.official_broker)
