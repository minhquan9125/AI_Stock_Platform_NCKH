from datetime import datetime
from dateutil import parser
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        result = parser.parse(value, dayfirst=True, fuzzy=True)
        return result.replace(tzinfo=VN_TZ) if result.tzinfo is None else result.astimezone(VN_TZ)
    except (ValueError, OverflowError):
        return None
