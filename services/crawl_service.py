"""Luồng Search → Raw → Cleaned → Relevance → Dedup → Storage."""
import hashlib
import json
import logging
from datetime import date, datetime
from pathlib import Path
from config.settings import Settings
from models import ArticleRecord
from processing.classifier import classify
from processing.deduplicator import Deduplicator, content_hash
from processing.relevance import calculate_relevance
from processing.text_utils import word_count
from storage.csv_store import export_csv
from storage.jsonl_store import JsonlStore
from storage.state_store import StateStore
from .company_resolver import Company, CompanyResolver


class CrawlService:
    def __init__(self, crawler, settings: Settings):
        self.crawler, self.settings = crawler, settings
        self.log = logging.getLogger(__name__)

    def run(self, company: Company, *, limit: int | None, max_pages: int, from_date: date | None, to_date: date | None, retry_failed: bool, reset_state: bool, save_raw_html: bool) -> dict:
        ticker, data = company.ticker, self.settings.data_dir
        state = StateStore(data / "state" / ticker)
        if reset_state: state.reset()
        accepted_store = JsonlStore(data / "cleaned" / ticker / f"{ticker}_articles.jsonl")
        rejected_store = JsonlStore(data / "rejected" / ticker / f"{ticker}_rejected.jsonl")
        failed_store = JsonlStore(data / "failed" / ticker / f"{ticker}_failed.jsonl")
        existing = accepted_store.read_all()
        dedup = Deduplicator(self.settings.near_duplicate_threshold)
        for item in existing: dedup.add(item.get("canonical_url", ""), item.get("content", ""))
        try:
            urls = self.crawler.search_articles(ticker, CompanyResolver.queries(company), max_pages, limit)
        except Exception as exc:
            self.log.error("ticker=%s | source=cafef | search_failed | %s", ticker, exc)
            urls = []
            search_error = str(exc)
        else:
            search_error = None
        if retry_failed:
            urls = list(dict.fromkeys([*state.failures, *urls]))
        stats = {"ticker": ticker, "urls_discovered": len(urls), "urls_skipped_as_processed": 0, "articles_downloaded": 0, "accepted": 0, "rejected": 0, "duplicates": 0, "failed": int(search_error is not None)}
        if search_error:
            stats["search_error"] = search_error
        for url in urls:
            if url in state.processed and not (retry_failed and url in state.failures):
                stats["urls_skipped_as_processed"] += 1; continue
            try:
                raw = self.crawler.parse_article(url); stats["articles_downloaded"] += 1
                if save_raw_html and raw.raw_html:
                    raw_dir = data / "raw" / ticker / "html"; raw_dir.mkdir(parents=True, exist_ok=True)
                    raw_name = hashlib.sha256(raw.canonical_url.encode()).hexdigest()[:16] + ".html"
                    (raw_dir / raw_name).write_text(raw.raw_html, encoding="utf-8")
                if raw.published_at and ((from_date and raw.published_at.date() < from_date) or (to_date and raw.published_at.date() > to_date)):
                    state.mark_processed(url, "out_of_date"); continue
                relevant = calculate_relevance(
                    ticker, company.company_name, company.aliases, raw.title,
                    raw.summary, raw.content, self.settings.min_relevance_score,
                    self.settings.min_word_count, company.positive_aliases,
                    company.excluded_entities,
                )
                unique, duplicate_reason = dedup.add(raw.canonical_url, raw.content)
                document_type, events = classify(" ".join((raw.title, raw.summary or "", raw.content)), relevant.multi_company)
                date_part = raw.published_at.strftime("%Y%m%d") if raw.published_at else "unknown"
                record = ArticleRecord(article_id=f"cafef_{ticker.lower()}_{date_part}_{hashlib.sha256(raw.canonical_url.encode()).hexdigest()[:8]}", ticker=[ticker], company_name=company.company_name, title=raw.title, summary=raw.summary, content=raw.content, published_at=raw.published_at, published_at_raw=raw.published_at_raw, crawled_at=datetime.now().astimezone(), source_name=raw.source_name, source_url=raw.source_url, canonical_url=raw.canonical_url, author=raw.author, category=raw.category, thumbnail_url=raw.thumbnail_url, document_type=document_type, event_types=events, matched_aliases=relevant.matched_aliases, relevance_score=relevant.score, relevance_reasons=relevant.reasons + ([duplicate_reason] if duplicate_reason else []), content_hash=content_hash(raw.content), word_count=word_count(raw.content), status="accepted" if relevant.accepted and unique else ("duplicate" if not unique else "rejected"))
                if not unique: stats["duplicates"] += 1; rejected_store.append(record)
                elif relevant.accepted: stats["accepted"] += 1; accepted_store.append(record)
                else: stats["rejected"] += 1; rejected_store.append(record)
                state.mark_processed(url, record.status)
                self.log.info("ticker=%s | source=cafef | %s | score=%s | url=%s", ticker, record.status, record.relevance_score, url)
            except Exception as exc:
                stats["failed"] += 1; state.mark_failed(url, str(exc)); failed_store.append({"url": url, "error": str(exc), "ticker": ticker, "at": datetime.now().astimezone().isoformat()}); self.log.exception("ticker=%s | source=cafef | failed | url=%s", ticker, url)
        records = accepted_store.read_all()
        export_path = data / "exports" / ticker
        export_csv(records, export_path / f"{ticker}_articles.csv")
        stats.update({"output_jsonl": str(accepted_store.path), "output_csv": str(export_path / f"{ticker}_articles.csv")})
        export_path.mkdir(parents=True, exist_ok=True)
        (export_path / "crawl_report.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        state.save_report(stats)
        return stats
