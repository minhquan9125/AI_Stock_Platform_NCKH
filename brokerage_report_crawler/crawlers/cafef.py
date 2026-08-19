"""Crawler kho Báo cáo phân tích CafeF."""

from __future__ import annotations

import json
import logging
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import ReportCandidate
from processing.date_parser import parse_date
from processing.metadata_parser import infer_report_type
from processing.text_cleaner import canonicalize_url, clean_text

from .base import BaseCrawler
from .common import detect_broker

LOG = logging.getLogger(__name__)


def find_cafef_pdf_url(html: str) -> str | None:
    """Ưu tiên URL PDF có sẵn trong HTML/state trước khi dùng trình duyệt."""
    match = re.search(
        r'https?://[^"\\s<>]+/DuLieuDownload/PhanTichBaoCao/[^"\\s<>]+\.pdf(?:\?[^"\\s<>]*)?',
        html,
        re.I,
    )
    return canonicalize_url(match.group(0).replace("&amp;", "&")) if match else None


def parse_cafef_detail(html: str, page_url: str) -> ReportCandidate:
    """Parse metadata nguồn gốc; không dùng phần ``Tóm tắt AI`` làm mô tả gốc."""
    soup = BeautifulSoup(html, "lxml")
    title_node = soup.select_one(".bcpt_detail_1_news .item-first-content-title")
    if not title_node:
        raise ValueError("cafef_report_detail_not_found")
    title = clean_text(title_node.get("title") or title_node.get_text(" ", strip=True))
    fields: dict[str, str] = {}
    links: dict[str, str] = {}
    for row in soup.select(".bcpt_detail_1_news .item-first-content-body-item"):
        left = row.select_one(".item-first-content-body-item-left")
        right = row.select_one(".item-first-content-body-item-right")
        if not left or not right:
            continue
        key = clean_text(left.get_text(" ", strip=True)).rstrip(":").lower()
        fields[key] = clean_text(right.get_text(" ", strip=True))
        link = right.select_one("a[href]")
        if link:
            links[key] = urljoin(page_url, link["href"])
    ticker = fields.get("mã ck", "").upper()
    raw_date = fields.get("ngày phát hành")
    broker_text = fields.get("nguồn báo cáo")
    canonical = soup.select_one("link[rel='canonical']")
    canonical_url = canonicalize_url(canonical["href"] if canonical else page_url)
    return ReportCandidate(
        title=title,
        ticker=[ticker] if ticker else [],
        source_platform="CafeF",
        source_page_url=canonical_url,
        canonical_source_url=canonical_url,
        broker=detect_broker(broker_text or "", links.get("nguồn báo cáo", "")),
        published_at=parse_date(raw_date),
        published_at_raw=raw_date,
        report_type=infer_report_type(title, fields.get("loại báo cáo", "")),
        description=None,
        page_text="\n".join(value for value in fields.values() if value),
    )


def resolve_cafef_pdf_url(page_url: str, timeout: int = 15) -> str | None:
    """Lấy URL PDF qua nút Blazor; chỉ dùng browser khi HTML không công khai URL."""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as ec
    except ImportError:
        LOG.warning("cafef_pdf_requires_selenium | url=%s", page_url)
        return None

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(page_url)
        button = WebDriverWait(driver, timeout).until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, ".bcpt_detail_1_news .bcpt-tai-ve-btn"))
        )
        driver.get_log("performance")
        button.click()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for entry in driver.get_log("performance"):
                message = json.loads(entry["message"])["message"]
                if message.get("method") != "Network.responseReceived":
                    continue
                response = message["params"]["response"]
                url = response.get("url", "")
                mime = response.get("mimeType", "").lower()
                if mime == "application/pdf" or re.search(r"\.pdf(?:$|\?)", url, re.I):
                    return canonicalize_url(url)
            time.sleep(0.25)
    except Exception as exc:
        LOG.warning("cafef_pdf_url_unresolved | url=%s | error=%s", page_url, exc)
    finally:
        driver.quit()
    return None


class CafeFCrawler(BaseCrawler):
    source_key = "cafef"
    source_platform = "CafeF"
    base_url = "https://cafef.vn"
    listing_url = f"{base_url}/du-lieu/phan-tich-bao-cao.chn"

    def search_reports(
        self, ticker: str, max_pages: int, target_reports: int | None
    ) -> list[ReportCandidate]:
        # Kết hợp kho mới và lịch sử theo mã; dừng sau hai trang không có URL mới.
        found: dict[str, ReportCandidate] = {}
        empty_pages = 0
        ticker_pattern = re.compile(rf"(?<![A-Z0-9]){re.escape(ticker)}(?![A-Z0-9])", re.I)
        for page in range(1, max_pages + 1):
            self.pages_scanned = page
            before = len(found)
            urls = [f"{self.listing_url}?keyword={ticker}&page={page}"]
            urls.extend(
                f"{self.base_url}/du-lieu/DuLieu.aspx?cat_id=1009&san={exchange}&symbol={ticker}&page={page}"
                for exchange in ("hose", "hnx", "upcom")
            )
            for url in urls:
                soup = BeautifulSoup(self.client.get(url).text, "lxml")
                for node in soup.select("a[href*='/du-lieu/report/']"):
                    title = clean_text(node.get("title") or node.get_text(" ", strip=True))
                    if not ticker_pattern.search(title):
                        continue
                    detail_url = canonicalize_url(urljoin(self.base_url, node["href"]))
                    found.setdefault(detail_url, ReportCandidate(
                        title=title, ticker=[ticker], source_platform=self.source_platform,
                        source_page_url=detail_url, canonical_source_url=detail_url,
                    ))
                    if target_reports and len(found) >= target_reports:
                        return list(found.values())
            empty_pages = empty_pages + 1 if len(found) == before else 0
            if empty_pages >= 2:
                self.exhausted = True
                break
        return list(found.values())

    def fetch_detail(self, candidate: ReportCandidate) -> ReportCandidate:
        html = self.client.get(candidate.source_page_url).text
        parsed = parse_cafef_detail(html, candidate.source_page_url)
        parsed.pdf_url = find_cafef_pdf_url(html) or resolve_cafef_pdf_url(candidate.source_page_url)
        return parsed
