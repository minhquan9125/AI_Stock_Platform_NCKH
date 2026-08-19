from urllib.parse import quote
from models import ReportCandidate
from .base import BaseCrawler
from .common import parse_detail, parse_listing


class VNDirectCrawler(BaseCrawler):
    source_key = "vndirect"
    source_platform = "VNDirect Research"
    official_broker = "VNDIRECT"
    base_url = "https://www.vndirect.com.vn"

    def search_reports(self, ticker: str, max_pages: int, target_reports: int | None) -> list[ReportCandidate]:
        found: dict[str, ReportCandidate] = {}
        empty_pages = 0
        for page in range(1, max_pages + 1):
            self.pages_scanned = page
            url = f"{self.base_url}/page/{page}/?s={quote(ticker)}"
            before = len(found)
            for item in parse_listing(self.client.get(url).text, self.base_url, self.source_platform, self.official_broker, ticker):
                found[item.canonical_source_url] = item
                if target_reports and len(found) >= target_reports: return list(found.values())
            empty_pages = empty_pages + 1 if len(found) == before else 0
            if empty_pages >= 2:
                self.exhausted = True
                break
        return list(found.values())

    def fetch_detail(self, candidate: ReportCandidate) -> ReportCandidate:
        return parse_detail(candidate, self.client.get(candidate.source_page_url).text, self.base_url, self.official_broker)
