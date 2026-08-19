"""CLI crawler bài viết chứng khoán."""
import argparse
import logging
import re
import sys
from datetime import date
from pathlib import Path
from config.settings import Settings
from crawlers import CafeFArticleCrawler
from crawlers.http import HttpClient
from services.company_resolver import CompanyResolver
from services.crawl_service import CrawlService

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def positive(value: str) -> int:
    parsed = int(value)
    if parsed <= 0: raise argparse.ArgumentTypeError("giá trị phải lớn hơn 0")
    return parsed


def ticker(value: str) -> str:
    value = value.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", value): raise argparse.ArgumentTypeError(f"ticker không hợp lệ: {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawler bài viết chứng khoán đa nguồn (hiện hỗ trợ CafeF)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticker", type=ticker)
    group.add_argument("--tickers", nargs="+", type=ticker)
    parser.add_argument("--limit", type=positive)
    parser.add_argument("--max-pages", type=positive, default=20)
    parser.add_argument("--from-date", type=date.fromisoformat)
    parser.add_argument("--to-date", type=date.fromisoformat)
    parser.add_argument("--min-relevance-score", type=float, default=5)
    parser.add_argument("--min-word-count", type=positive, default=150)
    parser.add_argument("--delay-min", type=float, default=1.5)
    parser.add_argument("--delay-max", type=float, default=4)
    parser.add_argument("--workers", type=positive, default=1, help="Dự phòng mở rộng; CafeF hiện chạy tuần tự, tối đa 3")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--reset-state", action="store_true")
    parser.add_argument("--save-raw-html", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def configure_logging(verbose: bool) -> None:
    Path("logs").mkdir(exist_ok=True)
    handlers = [logging.StreamHandler(), logging.FileHandler("logs/crawler.log", encoding="utf-8")]
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", handlers=handlers, force=True)


def main() -> int:
    parser = build_parser(); args = parser.parse_args()
    if args.from_date and args.to_date and args.from_date > args.to_date: parser.error("--from-date không được lớn hơn --to-date")
    if args.delay_min < 0 or args.delay_max < args.delay_min: parser.error("delay phải không âm và delay-max >= delay-min")
    if args.workers > 3: parser.error("--workers tối đa là 3")
    configure_logging(args.verbose)
    settings = Settings(delay_min=args.delay_min, delay_max=args.delay_max, min_relevance_score=args.min_relevance_score, min_word_count=args.min_word_count)
    client = HttpClient(settings.timeout, settings.retries, settings.delay_min, settings.delay_max, settings.user_agent)
    service, resolver = CrawlService(CafeFArticleCrawler(client), settings), CompanyResolver()
    for symbol in ([args.ticker] if args.ticker else args.tickers):
        report = service.run(resolver.resolve(symbol), limit=args.limit, max_pages=args.max_pages, from_date=args.from_date, to_date=args.to_date, retry_failed=args.retry_failed, reset_state=args.reset_state, save_raw_html=args.save_raw_html)
        print("\n".join(f"{key}: {value}" for key, value in report.items()))
    return 0


if __name__ == "__main__": raise SystemExit(main())
