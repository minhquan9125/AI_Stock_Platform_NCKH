from datetime import timedelta
from processing.date_parser import parse_vietnamese_datetime


def test_parse_date_with_time_and_timezone():
    value = parse_vietnamese_datetime("29/07/2026 - 09:30")
    assert value.isoformat() == "2026-07-29T09:30:00+07:00"
    assert value.utcoffset() == timedelta(hours=7)


def test_parse_date_without_time():
    assert parse_vietnamese_datetime("29/07/2026").hour == 0


def test_bad_input():
    assert parse_vietnamese_datetime("không rõ") is None
