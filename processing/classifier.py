"""Phân loại tài liệu/sự kiện không phụ thuộc LLM."""
def classify(text: str, multi_company: bool = False) -> tuple[str, list[str]]:
    if multi_company:
        return "MULTI_COMPANY_NEWS", []
    value = text.lower()
    rules = [
        (("khuyến nghị", "giá mục tiêu"), "BROKER_RECOMMENDATION", "BROKER_RECOMMENDATION"),
        (("kết quả kinh doanh", "lợi nhuận", "doanh thu"), "EARNINGS", "EARNINGS_REPORT"),
        (("cổ tức",), "DIVIDEND", "DIVIDEND"),
        (("phát hành", "chào bán"), "CORPORATE_DISCLOSURE", "SHARE_ISSUANCE"),
        (("mua bán sáp nhập", "m&a"), "GENERAL_NEWS", "M_AND_A"),
        (("bổ nhiệm", "từ nhiệm"), "CORPORATE_DISCLOSURE", "LEADERSHIP_CHANGE"),
    ]
    for terms, doc, event in rules:
        if any(term in value for term in terms):
            return doc, [event]
    if "cổ phiếu" in value or "định giá" in value:
        return "COMPANY_ANALYSIS", []
    return "GENERAL_NEWS", []
