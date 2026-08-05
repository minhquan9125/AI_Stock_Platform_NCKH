import json
import re
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from models import ReportCandidate
from processing.date_parser import parse_date
from processing.metadata_parser import infer_report_type
from processing.text_cleaner import canonicalize_url, clean_text


def detect_broker(text: str, url: str, configured: str | None = None) -> str | None:
    brokers = json.loads(Path("config/brokers.json").read_text(encoding="utf-8"))
    text_lower, url_lower = text.lower(), url.lower()
    # Các kho tổng hợp thường ghi tên đầy đủ kèm mã broker ở cuối: "... - VIX".
    codes = re.findall(r"(?:^|[\s\-–(])([A-Z]{2,10})(?:$|[\s)])", text.upper())
    for code in reversed(codes):
        if code in brokers:
            return code
    for broker, item in brokers.items():
        if any(alias.lower() in text_lower for alias in item["aliases"]):
            return broker
    for broker, item in brokers.items():
        if any(domain in url_lower for domain in item["official_domains"]):
            return broker
    return configured


def parse_listing(html: str, base_url: str, platform: str, broker: str | None, ticker: str) -> list[ReportCandidate]:
    soup = BeautifulSoup(html, "lxml")
    results: list[ReportCandidate] = []
    selectors = "article, .item, .news-item, .report-item, .research-item, .post, li"
    for item in soup.select(selectors):
        link = item.select_one("h1 a, h2 a, h3 a, h4 a, a[href]")
        if not link or not link.get("href"):
            continue
        title = clean_text(link.get_text(" ", strip=True))
        text = clean_text(item.get_text(" ", strip=True))
        if not re.search(rf"(?<!\w){re.escape(ticker)}(?!\w)", f"{title} {text}", re.I):
            continue
        page_url = canonicalize_url(urljoin(base_url, link["href"]))
        pdf = item.select_one("a[href$='.pdf'], a[href*='downloadedoc'], a[href*='download']")
        pdf_url = canonicalize_url(urljoin(base_url, pdf["href"])) if pdf and pdf.get("href") else (page_url if "downloadedoc" in page_url else None)
        date_node = item.select_one("time, .date, .post-date, .created-date")
        raw_date = clean_text(date_node.get("datetime") or date_node.get_text(" ", strip=True)) if date_node else None
        results.append(ReportCandidate(title=title, ticker=[ticker], source_platform=platform, source_page_url=page_url, canonical_source_url=page_url, broker=detect_broker(text, page_url, broker), published_at=parse_date(raw_date), published_at_raw=raw_date, report_type=infer_report_type(title, text), pdf_url=pdf_url, page_text=text))
    unique = {item.canonical_source_url: item for item in results}
    return list(unique.values())


def parse_detail(candidate: ReportCandidate, html: str, base_url: str, official_broker: str | None) -> ReportCandidate:
    soup = BeautifulSoup(html, "lxml")
    text = clean_text(soup.get_text("\n", strip=True))
    pdf = soup.select_one("a[href$='.pdf'], a[href*='downloadedoc'], a[href*='download']")
    if pdf and pdf.get("href"):
        candidate.pdf_url = canonicalize_url(urljoin(base_url, pdf["href"]))
    candidate.page_text = text
    candidate.broker = detect_broker(text, candidate.pdf_url or candidate.source_page_url, official_broker)
    candidate.report_type = infer_report_type(candidate.title, text)
    return candidate
