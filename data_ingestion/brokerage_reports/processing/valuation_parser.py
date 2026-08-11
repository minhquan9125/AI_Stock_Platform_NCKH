import re

PATTERNS = {
    "DCF": r"\bDCF\b|CHIẾT KHẤU DÒNG TIỀN",
    "P_E": r"\bP\s*/\s*E\b",
    "P_B": r"\bP\s*/\s*B\b",
    "EV_EBITDA": r"\bEV\s*/\s*EBITDA\b",
    "SOTP": r"\bSOTP\b|TỔNG GIÁ TRỊ THÀNH PHẦN",
    "DDM": r"\bDDM\b|CHIẾT KHẤU CỔ TỨC",
    "RNAV": r"\bRNAV\b",
}


def parse_valuation_methods(text: str) -> list[str]:
    return [name for name, pattern in PATTERNS.items() if re.search(pattern, text, re.I)]
