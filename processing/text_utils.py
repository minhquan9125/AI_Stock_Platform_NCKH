"""Tiện ích URL và văn bản."""
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {"fbclid", "gclid", "ref", "source", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}


def normalize_whitespace(text: str | None) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text or "")).strip()


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING))
    path = re.sub(r"/+", "/", parts.path).rstrip("/") or "/"
    return urlunsplit(("https" if parts.scheme in {"http", "https"} else parts.scheme, host, path, query, ""))


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\wÀ-ỹ]+\b", text, flags=re.UNICODE))
