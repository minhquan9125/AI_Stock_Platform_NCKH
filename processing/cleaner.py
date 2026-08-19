"""Trích xuất và làm sạch đúng vùng nội dung bài."""
import json
from bs4 import BeautifulSoup, Tag
from .text_utils import normalize_whitespace

BODY_SELECTORS = ("div.detail-content", "div.contentdetail", "#mainContent", "article", "[itemprop='articleBody']")
JUNK_SELECTORS = ("script", "style", "noscript", "iframe", ".ads", ".advertisement", ".relate-link", ".link-content-footer", ".social", ".comment", ".tindng")


def extract_jsonld_body(soup: BeautifulSoup) -> str:
    for node in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(node.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("articleBody"):
                    return normalize_whitespace(item["articleBody"])
                if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                    for child in item["@graph"]:
                        if isinstance(child, dict) and child.get("articleBody"):
                            return normalize_whitespace(child["articleBody"])
        except (json.JSONDecodeError, TypeError):
            continue
    return ""


def clean_container(container: Tag) -> str:
    for selector in JUNK_SELECTORS:
        for node in container.select(selector):
            node.decompose()
    blocks, seen = [], set()
    for node in container.select("h2, h3, p, li, figcaption"):
        text = normalize_whitespace(node.get_text(" ", strip=True))
        if len(text) >= 2 and text not in seen:
            seen.add(text)
            blocks.append(text)
    return "\n\n".join(blocks)


def extract_main_content(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    body = extract_jsonld_body(soup)
    if body:
        return body
    for selector in BODY_SELECTORS:
        container = soup.select_one(selector)
        if container:
            body = clean_container(container)
            if body:
                return body
    return ""
