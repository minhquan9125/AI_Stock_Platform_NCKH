import json
import logging
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Company:
    ticker: str
    company_name: str | None
    aliases: list[str]
    positive_aliases: list[str]
    excluded_entities: dict[str, str]


class CompanyResolver:
    def __init__(self, path: Path = Path("config/companies.json")):
        self.data = json.loads(path.read_text(encoding="utf-8"))

    def resolve(self, ticker: str) -> Company:
        ticker = ticker.upper()
        item = self.data.get(ticker)
        if not item:
            logging.getLogger(__name__).warning("Chưa có cấu hình doanh nghiệp cho %s; dùng ticker làm alias", ticker)
            positive = [f"cổ phiếu {ticker}", f"mã {ticker}", f"HoSE: {ticker}"]
            return Company(ticker, None, [ticker, *positive], positive, {})
        positive = list(dict.fromkeys(item.get("positive_aliases", item.get("aliases", []))))
        aliases = list(dict.fromkeys([ticker, *item.get("aliases", []), *positive]))
        return Company(ticker, item.get("company_name"), aliases, positive, dict(item.get("excluded_entities", {})))

    @staticmethod
    def queries(company: Company) -> list[str]:
        base = company.positive_aliases[:4]
        return list(dict.fromkeys([*base, *(f"{term} {company.ticker}" for term in ("cổ phiếu", "phân tích", "định giá", "kết quả kinh doanh", "doanh thu", "lợi nhuận", "khuyến nghị"))]))
