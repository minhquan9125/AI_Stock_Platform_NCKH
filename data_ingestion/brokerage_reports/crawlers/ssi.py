from urllib.parse import quote
import re
from bs4 import BeautifulSoup
from models import ReportCandidate
from processing.date_parser import parse_date
from processing.metadata_parser import infer_report_type
from processing.text_cleaner import canonicalize_url, clean_text
from .base import BaseCrawler


class SSICrawler(BaseCrawler):
    source_key = "ssi"
    source_platform = "SSI Research"
    official_broker = "SSI"
    base_url = "https://www.ssi.com.vn"

    def search_reports(self, ticker: str, max_pages: int, limit: int | None) -> list[ReportCandidate]:
        found: dict[str, ReportCandidate] = {}
        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/khach-hang-ca-nhan/bao-cao-cong-ty?keyword={quote(ticker)}&page={page}"
            soup = BeautifulSoup(self.client.get(url).text, "lxml")
            for node in soup.select(".chart__content__item"):
                title_node = node.select_one("a.titlePost")
                download = node.select_one(".chart__content__item__time a[href]")
                if not title_node or not download:
                    continue
                title = clean_text(title_node.get_text(" ", strip=True))
                if not re.search(rf"^\s*{re.escape(ticker)}\s*[\(:\-–|]", title, re.I):
                    continue
                pdf_url = canonicalize_url(download["href"])
                date_node = node.select_one(".chart__content__item__time span")
                raw_date = clean_text(date_node.get_text(" ", strip=True)) if date_node else None
                text = clean_text(node.get_text("\n", strip=True))
                item = ReportCandidate(
                    title=title, ticker=[ticker], source_platform=self.source_platform,
                    source_page_url=pdf_url, canonical_source_url=pdf_url,
                    broker=self.official_broker, published_at=parse_date(raw_date),
                    published_at_raw=raw_date,
                    report_type=infer_report_type(title, text),
                    pdf_url=pdf_url, page_text=text,
                )
                found[item.canonical_source_url] = item
                if limit and len(found) >= limit: return list(found.values())
        return list(found.values())

    def fetch_detail(self, candidate: ReportCandidate) -> ReportCandidate:
        return candidate
