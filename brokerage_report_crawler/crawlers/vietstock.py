import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from models import ReportCandidate
from processing.date_parser import parse_date
from processing.metadata_parser import infer_report_type
from processing.text_cleaner import canonicalize_url, clean_text
from .base import BaseCrawler


def parse_finance_reports(
    html: str,
    ticker: str,
    base_url: str = "https://finance.vietstock.vn",
) -> list[ReportCandidate]:
    """Parse các card từ trang Báo cáo phân tích của Vietstock Finance."""
    soup = BeautifulSoup(html, "lxml")
    results: list[ReportCandidate] = []
    for card in soup.select(".edoc-first, .edoc-child"):
        title_node = card.select_one("a.title-link[href*='/bao-cao-phan-tich/']")
        download_node = card.select_one("a[href*='/downloadedoc/']")
        if not title_node or not download_node:
            continue
        title = clean_text(title_node.get_text(" ", strip=True))
        if not re.search(rf"^\s*{re.escape(ticker)}\s*[\(:\-–|]", title, re.I):
            continue
        detail_url = canonicalize_url(urljoin(base_url, title_node["href"]))
        pdf_url = canonicalize_url(urljoin(base_url, download_node["href"]))
        date_node = card.select_one("small i")
        raw_date = clean_text(date_node.get_text(" ", strip=True)) if date_node else None
        broker = None
        for label in card.find_all(["span", "b", "a"]):
            if clean_text(label.get_text(" ", strip=True)).lower() == "nguồn:":
                sibling = label.find_next(["a", "b"])
                if sibling:
                    broker = clean_text(sibling.get_text(" ", strip=True))
                break
        text = clean_text(card.get_text("\n", strip=True))
        results.append(
            ReportCandidate(
                title=title,
                ticker=[ticker],
                source_platform="Vietstock Finance",
                source_page_url=detail_url,
                canonical_source_url=detail_url,
                broker=broker,
                published_at=parse_date(raw_date),
                published_at_raw=raw_date,
                report_type=infer_report_type(title, text),
                description=None,
                pdf_url=pdf_url,
                page_text=text,
            )
        )
    return list({item.canonical_source_url: item for item in results}.values())


class VietstockCrawler(BaseCrawler):
    source_key = "vietstock"
    source_platform = "Vietstock Finance"
    base_url = "https://finance.vietstock.vn"
    listing_url = f"{base_url}/bao-cao-phan-tich"

    def search_reports(
        self,
        ticker: str,
        max_pages: int,
        target_reports: int | None,
    ) -> list[ReportCandidate]:
        landing = self.client.get(self.listing_url)
        soup = BeautifulSoup(landing.text, "lxml")
        token_node = soup.select_one(
            "#__CHART_AjaxAntiForgeryForm input[name='__RequestVerificationToken']"
        )
        if not token_node or not token_node.get("value"):
            raise RuntimeError("vietstock_missing_antiforgery_token")
        token = token_node["value"]
        found: dict[str, ReportCandidate] = {}
        empty_pages = 0
        for page in range(1, max_pages + 1):
            self.pages_scanned = page
            response = self.client.post(
                f"{self.base_url}/View/ChannelEDocumentPage",
                data={
                    "keyword": ticker,
                    "page": page,
                    "pageSize": 50,
                    "__RequestVerificationToken": token,
                },
                headers={
                    "Referer": self.listing_url,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            page_items = parse_finance_reports(response.text, ticker, self.base_url)
            if not page_items:
                empty_pages += 1
                if empty_pages >= 2:
                    self.exhausted = True
                    break
                continue
            before = len(found)
            for item in page_items:
                found[item.canonical_source_url] = item
                if target_reports and len(found) >= target_reports:
                    return list(found.values())
            empty_pages = empty_pages + 1 if len(found) == before else 0
            if empty_pages >= 2:
                self.exhausted = True
                break
        return list(found.values())

    def fetch_detail(self, candidate: ReportCandidate) -> ReportCandidate:
        return candidate
