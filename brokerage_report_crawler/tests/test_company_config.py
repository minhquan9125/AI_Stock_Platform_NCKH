import json
from pathlib import Path
from main import parser


def test_vn30_group_has_30_fully_configured_tickers():
    companies = json.loads(Path("config/companies.json").read_text(encoding="utf-8"))
    groups = json.loads(Path("config/ticker_groups.json").read_text(encoding="utf-8"))
    tickers = groups["VN30"]["tickers"]
    assert len(tickers) == len(set(tickers)) == 30
    assert set(tickers) == set(companies)
    for ticker in tickers:
        item = companies[ticker]
        assert item["company_name"]
        assert f"HOSE: {ticker}" in item["positive_aliases"]
        assert isinstance(item["excluded_entities"], dict)


def test_cli_accepts_vn30_group():
    args = parser().parse_args(["--group", "VN30", "--target", "5"])
    assert args.group == "VN30"
    assert args.target_reports == 5
