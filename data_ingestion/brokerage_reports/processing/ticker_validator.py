import re
from dataclasses import dataclass


@dataclass(slots=True)
class TickerValidation:
    accepted: bool
    score: int
    notes: list[str]


def _contains(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.I))


def validate_ticker(ticker: str, company_name: str | None, positive_aliases: list[str], excluded_entities: dict[str, str], title: str, page_text: str) -> TickerValidation:
    lead = f"{title}\n{page_text[:10000]}"
    scrubbed = lead
    excluded = [name for name in excluded_entities if _contains(lead, name)]
    for name in excluded_entities:
        scrubbed = re.sub(re.escape(name), " ", scrubbed, flags=re.I)
    positives = [alias for alias in positive_aliases if _contains(scrubbed, alias)]
    explicit = bool(re.search(rf"\b(?:HOSE|HNX|UPCOM)\s*[:\-]\s*{re.escape(ticker)}\b", scrubbed, re.I))
    title_explicit = bool(re.search(rf"^\s*{re.escape(ticker)}\s*[\(:\-–|]", title, re.I))
    ticker_mentions = len(re.findall(rf"(?<!\w){re.escape(ticker)}(?!\w)", scrubbed, re.I))
    parent_clear = explicit or bool(positives) or bool(company_name and _contains(scrubbed, company_name)) or (title_explicit and ticker_mentions >= 2)
    score, notes = 0, []
    if explicit: score += 6; notes.append("explicit_exchange_ticker")
    if title_explicit and ticker_mentions >= 2: score += 4; notes.append("ticker_title_and_report_evidence")
    if positives: score += 4; notes.append("positive_alias:" + ",".join(positives))
    if ticker_mentions >= 2: score += 2; notes.append("ticker_repeated")
    if excluded and not parent_clear: score -= 20; notes.append("excluded_entity:" + ",".join(excluded))
    if not parent_clear: notes.append("missing_positive_company_evidence")
    return TickerValidation(parent_clear and score >= 4 and not (excluded and not parent_clear), score, notes)
