"""Chấm mức liên quan bằng quy tắc minh bạch."""
import re
from dataclasses import dataclass
from .text_utils import word_count

FINANCIAL = ("cổ phiếu", "mã chứng khoán", "doanh thu", "lợi nhuận", "eps", "p/e", "p/b", "roe", "roa", "định giá", "giá mục tiêu", "khuyến nghị", "kết quả kinh doanh", "báo cáo tài chính", "cổ tức", "phát hành", "tăng trưởng", "dòng tiền", "thanh khoản", "nhà đầu tư")
NUMERIC = re.compile(r"\b(EPS|P/E|P/B|ROE|ROA)\b|\d+(?:[.,]\d+)?\s*(?:%|tỷ|triệu|đồng)", re.I)
EXCHANGE_TICKER = re.compile(r"\b(?:HOSE|HNX|UPCOM)\s*:\s*([A-Z]{3})\b", re.I)


@dataclass(slots=True)
class RelevanceResult:
    score: float
    accepted: bool
    reasons: list[str]
    matched_aliases: list[str]
    excluded_matches: list[str]
    multi_company: bool


def _token(text: str, value: str) -> bool:
    return bool(re.search(rf"(?<![\w]){re.escape(value)}(?![\w])", text, re.I))


def calculate_relevance(
    ticker: str,
    company_name: str | None,
    aliases: list[str],
    title: str,
    summary: str | None,
    content: str,
    threshold: float = 5,
    min_words: int = 150,
    positive_aliases: list[str] | None = None,
    excluded_entities: dict[str, str] | None = None,
) -> RelevanceResult:
    score, reasons = 0.0, []
    summary, title = summary or "", title or ""
    positive_aliases = positive_aliases or [alias for alias in aliases if alias.upper() != ticker.upper()]
    excluded_entities = excluded_entities or {}
    lead = content[:1200]
    prominent_text = " ".join((title, summary, lead))
    full_text = " ".join((title, summary, content))
    positive_text = full_text
    positive_prominent_text = prominent_text
    for excluded_name in excluded_entities:
        positive_text = re.sub(re.escape(excluded_name), " ", positive_text, flags=re.I)
        positive_prominent_text = re.sub(re.escape(excluded_name), " ", positive_prominent_text, flags=re.I)
    matched = [alias for alias in dict.fromkeys(aliases) if _token(" ".join((title, summary, content)), alias)]
    matched_positive = [alias for alias in dict.fromkeys(positive_aliases) if _token(positive_text, alias)]
    excluded_matches = [name for name in excluded_entities if _token(prominent_text, name)]
    parent_prominent = [alias for alias in positive_aliases if _token(positive_prominent_text, alias)]
    if _token(title, ticker): score += 1; reasons.append("ticker_in_title:+1")
    if company_name and company_name.lower() in title.lower(): score += 4; reasons.append("company_in_title:+4")
    important = [a for a in positive_aliases if len(a) > 3 and _token(title, a)]
    if important: score += 3; reasons.append("alias_in_title:+3")
    if _token(summary, ticker): score += 1; reasons.append("ticker_in_summary:+1")
    if company_name and company_name.lower() in summary.lower(): score += 2; reasons.append("company_in_summary:+2")
    if matched_positive: score += min(3, len(matched_positive)); reasons.append(f"positive_entity:+{min(3, len(matched_positive))}")
    occurrences = len(re.findall(rf"(?<![\w]){re.escape(ticker)}(?![\w])", content, re.I))
    if occurrences: score += min(3, occurrences); reasons.append(f"ticker_content:+{min(3, occurrences)}")
    financial_hits = sum(1 for term in FINANCIAL if term in f"{title} {summary} {content}".lower())
    if financial_hits: score += 2; reasons.append("financial_terms:+2")
    if NUMERIC.search(f"{title} {summary} {content}"): score += 2; reasons.append("financial_metrics:+2")
    listed = set(re.findall(r"(?<![\w])[A-Z]{3}(?![\w])", content))
    if len(listed) >= 8: score -= 3; reasons.append("many_tickers:-3")
    explicit_others = {value.upper() for value in EXCHANGE_TICKER.findall(f"{title} {summary} {content}") if value.upper() != ticker.upper()}
    target_named = bool(company_name and company_name.lower() in f"{title} {summary} {content}".lower())
    if explicit_others and not target_named:
        score -= 7
        reasons.append(f"other_explicit_ticker:-7:{','.join(sorted(explicit_others))}")
    listed_entities = set(EXCHANGE_TICKER.findall(full_text.upper()))
    multi_company = len(listed_entities) >= 4 or len(listed) >= 8
    if multi_company:
        score -= 3
        reasons.append("multi_company_news:-3")
    hard_excluded = bool(excluded_matches and not parent_prominent)
    if hard_excluded:
        score -= 20
        reasons.append("excluded_entity:-20:" + ",".join(excluded_matches))
    if not matched_positive:
        score -= 4
        reasons.append("no_positive_entity:-4")
    count = word_count(content)
    if count < min_words: score -= 5; reasons.append("content_too_short:-5")
    if occurrences == 1 and not _token(title + " " + summary, ticker): score -= 3; reasons.append("single_weak_mention:-3")
    accepted = score >= threshold and count >= min_words and not hard_excluded
    return RelevanceResult(score, accepted, reasons, matched, excluded_matches, multi_company)
