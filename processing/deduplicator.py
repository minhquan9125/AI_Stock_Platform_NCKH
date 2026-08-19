"""Ba lớp chống trùng: URL, SHA-256, fuzzy near-duplicate."""
import hashlib
from rapidfuzz.fuzz import ratio, token_set_ratio
from .text_utils import canonicalize_url, normalize_whitespace


def content_hash(content: str) -> str:
    return hashlib.sha256(normalize_whitespace(content).encode("utf-8")).hexdigest()


class Deduplicator:
    def __init__(self, threshold: float = 92):
        self.threshold = threshold
        self.urls: set[str] = set()
        self.hashes: set[str] = set()
        self.contents: list[str] = []

    def add(self, url: str, content: str) -> tuple[bool, str | None]:
        url, normalized = canonicalize_url(url), normalize_whitespace(content)
        digest = content_hash(normalized)
        if url in self.urls: return False, "duplicate_url"
        if digest in self.hashes: return False, "duplicate_content"
        for old in self.contents:
            direct = ratio(normalized, old)
            event_overlap = token_set_ratio(normalized[:2500], old[:2500])
            if max(direct, event_overlap) >= self.threshold:
                return False, "near_duplicate"
        self.urls.add(url); self.hashes.add(digest); self.contents.append(normalized)
        return True, None
