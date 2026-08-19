"""Parse thời gian Việt Nam mà không làm mất phần giờ."""
import re
from datetime import datetime
from dateutil import parser as dateutil_parser
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def parse_vietnamese_datetime(value: str | None) -> datetime | None:
    if not value or not value.strip():
        return None
    text = re.sub(r"(?i)\b(thứ\s+\w+|GMT\+7)\b[,]?", " ", value).strip()
    formats = ("%d/%m/%Y - %H:%M", "%d/%m/%Y %H:%M", "%H:%M %d/%m/%Y", "%d/%m/%Y", "%d-%m-%Y - %H:%M", "%Y-%m-%dT%H:%M:%S%z")
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=VN_TZ) if parsed.tzinfo is None else parsed.astimezone(VN_TZ)
        except ValueError:
            pass
    try:
        parsed = dateutil_parser.parse(text, dayfirst=True, fuzzy=True)
        return parsed.replace(tzinfo=VN_TZ) if parsed.tzinfo is None else parsed.astimezone(VN_TZ)
    except (ValueError, OverflowError):
        return None
