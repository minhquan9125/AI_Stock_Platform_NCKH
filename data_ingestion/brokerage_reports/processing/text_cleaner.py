import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {"fbclid", "gclid", "ref", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}


def clean_text(value: str | None) -> str:
    return re.sub(r"[ \t]+", " ", unicodedata.normalize("NFC", value or "")).replace("\r\n", "\n").strip()


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING))
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.")
    return urlunsplit(("https" if parts.scheme in {"http", "https"} else parts.scheme, host, re.sub(r"/+", "/", parts.path).rstrip("/") or "/", query, ""))
