from abc import ABC, abstractmethod
from models import ReportCandidate
from .http import HttpClient


class BaseCrawler(ABC):
    source_key: str
    source_platform: str
    official_broker: str | None = None

    def __init__(self, client: HttpClient):
        self.client = client
        self.exhausted = False
        self.pages_scanned = 0

    @abstractmethod
    def search_reports(self, ticker: str, max_pages: int, target_reports: int | None) -> list[ReportCandidate]:
        """Tìm và parse metadata báo cáo từ nguồn."""

    def fetch_detail(self, candidate: ReportCandidate) -> ReportCandidate:
        return candidate
