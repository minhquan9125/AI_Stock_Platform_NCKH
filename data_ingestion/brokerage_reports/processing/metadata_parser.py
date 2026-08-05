import re
from .recommendation_parser import RecommendationData, parse_recommendation
from .valuation_parser import parse_valuation_methods


def infer_report_type(title: str, text: str = "") -> str:
    value = f"{title} {text[:1000]}".lower()
    if "báo cáo lần đầu" in value or "initiation" in value: return "INITIATION_REPORT"
    if "cập nhật kqkd" in value or "earnings update" in value or "kết quả kinh doanh" in value: return "EARNINGS_UPDATE"
    if "báo cáo ngành" in value or "sector report" in value: return "INDUSTRY_REPORT"
    if "vĩ mô" in value or "macro" in value: return "MACRO_REPORT"
    if "chiến lược" in value or "strategy" in value: return "MARKET_STRATEGY"
    if "kỹ thuật" in value or "technical" in value: return "TECHNICAL_REPORT"
    if "daily" in value or "bản tin ngày" in value: return "DAILY_REPORT"
    if re.search(r"\b[A-Z]{3}\b", title): return "COMPANY_REPORT"
    return "OTHER"


def parse_analysts(text: str) -> list[str]:
    matches = re.findall(r"(?:CHUYÊN VIÊN PHÂN TÍCH|ANALYST)\s*[:\-]?\s*([^\n|]{3,80})", text, re.I)
    return list(dict.fromkeys(value.strip() for value in matches))


def parse_metadata(text: str) -> tuple[RecommendationData, list[str], list[str]]:
    return parse_recommendation(text), parse_valuation_methods(text), parse_analysts(text[:5000])
