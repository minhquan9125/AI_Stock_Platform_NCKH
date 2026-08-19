"""Crawler CafeF dựa trên requests, có parser độc lập để test offline."""
import json
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
from models import RawArticle
from processing.cleaner import extract_main_content
from processing.date_parser import parse_vietnamese_datetime
from processing.text_utils import canonicalize_url, normalize_whitespace
from .base import BaseArticleCrawler
from .http import HttpClient


class CafeFArticleCrawler(BaseArticleCrawler):
    source_name = "CafeF"
    base_url = "https://cafef.vn"

    def __init__(self, client: HttpClient):
        self.client = client

    def search_articles(self, ticker: str, queries: list[str], max_pages: int, limit: int | None = None) -> list[str]:
        found: dict[str, None] = {}
        for query in queries:
            for page in range(1, max_pages + 1):
                url = f"{self.base_url}/tim-kiem/trang-{page}.chn?keywords={quote(query)}"
                soup = BeautifulSoup(self.client.get(url).text, "lxml")
                before = len(found)
                for item in soup.select("div.item, div.tlitem, .list-search .item, .timeline .item"):
                    link = item.select_one("h3 a, h4 a, a[href]")
                    if not link or not link.get("href"): continue
                    full = canonicalize_url(urljoin(self.base_url, link["href"]))
                    if full.endswith(".chn") and full.split("/")[2].endswith("cafef.vn"): found[full] = None
                    if limit and len(found) >= limit: return list(found)
                if len(found) == before: break
        return list(found)

    def parse_article(self, url: str) -> RawArticle:
        response = self.client.get(url)
        html, soup = response.text, BeautifulSoup(response.text, "lxml")
        def text(selector: str) -> str | None:
            node = soup.select_one(selector)
            return normalize_whitespace(node.get_text(" ", strip=True)) if node else None
        title = text("h1.title, h1.article-title, h1") or ""
        raw_date = text("span.pdate, span.date-and-time, .author .time, span.time")
        summary = text("h2.sapo, div.sapo, [itemprop='description']")
        author = text("[itemprop='author'], .author-name, .detail-author")
        category = text(".breadcrumb a:last-child, .cat")
        thumbnail = None
        image = soup.select_one("meta[property='og:image']")
        if image: thumbnail = image.get("content")
        for node in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(node.string or "{}")
                candidates = data if isinstance(data, list) else [data]
                for item in candidates:
                    if isinstance(item, dict):
                        title = title or normalize_whitespace(item.get("headline"))
                        raw_date = raw_date or item.get("datePublished")
                        author_data = item.get("author")
                        if not author and isinstance(author_data, dict): author = author_data.get("name")
            except (json.JSONDecodeError, TypeError): pass
        return RawArticle(source_name=self.source_name, source_url=url, canonical_url=canonicalize_url(response.url), title=title, summary=summary, content=extract_main_content(html), published_at=parse_vietnamese_datetime(raw_date), published_at_raw=raw_date, author=author, category=category, thumbnail_url=thumbnail, raw_html=html)
