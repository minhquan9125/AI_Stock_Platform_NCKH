from dataclasses import dataclass
from rapidfuzz.fuzz import ratio, token_set_ratio


@dataclass(slots=True)
class DuplicateMatch:
    duplicate: bool
    reason: str | None = None
    index: int | None = None


def find_duplicate(candidate: dict, existing: list[dict], threshold: float = 92) -> DuplicateMatch:
    for index, old in enumerate(existing):
        if candidate.get("pdf_hash") and candidate["pdf_hash"] == old.get("pdf_hash"):
            return DuplicateMatch(True, "duplicate_pdf_hash", index)
        if candidate.get("content_hash") and candidate["content_hash"] == old.get("content_hash"):
            return DuplicateMatch(True, "duplicate_content_hash", index)
        if candidate.get("canonical_source_url") == old.get("canonical_source_url"):
            return DuplicateMatch(True, "duplicate_canonical_url", index)
        same_meta = all(candidate.get(k) == old.get(k) for k in ("ticker", "broker", "published_at"))
        title_score = ratio(candidate.get("title", ""), old.get("title", ""))
        text_score = token_set_ratio(candidate.get("_text", "")[:4000], old.get("_text", "")[:4000])
        if same_meta and title_score >= 85:
            return DuplicateMatch(True, "duplicate_metadata", index)
        same_broker = candidate.get("broker") == old.get("broker")
        if same_broker and max(title_score, text_score) >= threshold and candidate.get("ticker") == old.get("ticker"):
            return DuplicateMatch(True, "near_duplicate", index)
    return DuplicateMatch(False)
