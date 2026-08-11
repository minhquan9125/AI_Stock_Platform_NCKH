import re
from dataclasses import dataclass

MAP = {
    "MUA": "BUY", "BUY": "BUY", "KHẢ QUAN": "OUTPERFORM",
    "OUTPERFORM": "OUTPERFORM", "TÍCH LŨY": "ACCUMULATE",
    "ACCUMULATE": "ACCUMULATE", "NẮM GIỮ": "HOLD", "HOLD": "HOLD",
    "TRUNG LẬP": "NEUTRAL", "NEUTRAL": "NEUTRAL",
    "GIẢM TỶ TRỌNG": "REDUCE", "REDUCE": "REDUCE",
    "BÁN": "SELL", "SELL": "SELL", "NOT RATED": "NOT_RATED",
}


@dataclass(slots=True)
class RecommendationData:
    recommendation: str | None
    raw: str | None
    target_price: float | None
    current_price: float | None
    upside_percent: float | None


def _number(value: str | None) -> float | None:
    if not value:
        return None
    compact = value.replace(".", "").replace(",", "")
    try:
        return float(compact)
    except ValueError:
        return None


def parse_recommendation(text: str) -> RecommendationData:
    upper = text.upper()
    matches = [(match.start(), term) for term in MAP for match in re.finditer(rf"(?<!\w){re.escape(term)}(?!\w)", upper)]
    raw = min(matches)[1] if matches else None
    target = re.search(r"(?:GIÁ\s+MỤC\s+TIÊU|TARGET\s+PRICE|\bTP\b)\s*[:\-]?\s*(?:VND|ĐỒNG)?\s*([\d.,]+)", upper)
    current = re.search(r"(?:GIÁ\s+(?:THỊ\s+TRƯỜNG|HIỆN\s+TẠI)|CURRENT\s+PRICE)\s*[:\-]?\s*(?:VND|ĐỒNG)?\s*([\d.,]+)", upper)
    upside = re.search(r"(?:TIỀM\s+NĂNG\s+TĂNG\s+GIÁ|UPSIDE)\s*[:\-]?\s*([\d.,]+)\s*%", upper)
    return RecommendationData(MAP.get(raw), raw, _number(target.group(1)) if target else None, _number(current.group(1)) if current else None, float(upside.group(1).replace(",", ".")) if upside else None)
