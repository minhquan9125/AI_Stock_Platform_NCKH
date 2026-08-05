import argparse
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path
from config.settings import Settings
from crawlers import CRAWLERS
from crawlers.http import HttpClient
from services.crawl_service import CrawlService

if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"): sys.stderr.reconfigure(encoding="utf-8")


def ticker_type(value: str) -> str:
    value = value.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", value):
        raise argparse.ArgumentTypeError(f"ticker không hợp lệ: {value}")
    return value


def positive(value: str) -> int:
    result = int(value)
    if result <= 0: raise argparse.ArgumentTypeError("giá trị phải > 0")
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Crawler báo cáo phân tích công ty chứng khoán")
    group = result.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticker", type=ticker_type)
    group.add_argument("--tickers", nargs="+", type=ticker_type)
    result.add_argument("--limit", type=positive)
    result.add_argument("--max-pages", type=positive, default=5)
    result.add_argument("--from-date", type=date.fromisoformat)
    result.add_argument("--to-date", type=date.fromisoformat)
    result.add_argument("--sources", nargs="+", choices=sorted(CRAWLERS), default=sorted(CRAWLERS))
    result.add_argument("--download-pdf", action="store_true")
    result.add_argument("--extract-pdf", action="store_true")
    result.add_argument("--retry-failed", action="store_true")
    result.add_argument("--reset-state", action="store_true")
    result.add_argument("--delay-min", type=float, default=1.5)
    result.add_argument("--delay-max", type=float, default=4.0)
    result.add_argument("--workers", type=positive, default=1)
    result.add_argument("--verbose", action="store_true")
    return result


def setup_logging(verbose: bool) -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler("logs/crawler.log", encoding="utf-8")], force=True)


def main() -> int:
    cli = parser(); args = cli.parse_args()
    if args.from_date and args.to_date and args.from_date > args.to_date: cli.error("--from-date không được lớn hơn --to-date")
    if args.delay_min < 0 or args.delay_max < args.delay_min: cli.error("delay không hợp lệ")
    if args.workers > 3: cli.error("--workers tối đa 3")
    if args.extract_pdf and not args.download_pdf: cli.error("--extract-pdf yêu cầu --download-pdf")
    setup_logging(args.verbose)
    settings = Settings(delay_min=args.delay_min, delay_max=args.delay_max)
    client = HttpClient(settings.timeout, settings.retries, settings.delay_min, settings.delay_max, settings.user_agent)
    crawlers = {key: CRAWLERS[key](client) for key in args.sources}
    companies = json.loads(Path("config/companies.json").read_text(encoding="utf-8"))
    service = CrawlService(crawlers, client, settings, companies)
    for symbol in ([args.ticker] if args.ticker else args.tickers):
        if symbol not in companies: logging.warning("ticker=%s | chưa có tên doanh nghiệp trong companies.json", symbol)
        report = service.run(symbol, args.sources, limit=args.limit, max_pages=args.max_pages, from_date=args.from_date, to_date=args.to_date, download_pdf=args.download_pdf, extract_text=args.extract_pdf, retry_failed=args.retry_failed, reset_state=args.reset_state)
        print("\n".join(f"{key}: {value}" for key, value in report.items()))
    return 0


if __name__ == "__main__": raise SystemExit(main())
