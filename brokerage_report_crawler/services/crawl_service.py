"""Điều phối discovery, xử lý và lưu báo cáo theo mục tiêu bản ghi duy nhất."""
from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from config.settings import Settings
from models import ReportCandidate, ReportRecord
from processing.deduplicator import find_duplicate
from processing.metadata_parser import parse_metadata
from processing.pdf_extractor import extract_pdf, validate_pdf_bytes
from processing.ticker_validator import validate_ticker
from storage.csv_store import export_csv
from storage.jsonl_store import JsonlStore
from storage.state_store import StateStore
from .report_merger import ReportMerger


@dataclass(slots=True)
class CrawlResult:
    ticker: str
    target: int
    discovered: int = 0
    accepted_unique: int = 0
    duplicates: int = 0
    rejected: int = 0
    failed: int = 0
    exhausted_sources: list[str] = field(default_factory=list)
    existing_reports: int = 0
    new_accepted: int = 0
    total_unique_reports: int = 0
    pdf_downloaded: int = 0
    needs_ocr: int = 0
    source_discovered: dict[str, int] = field(default_factory=dict)
    skipped_processed: int = 0
    output_jsonl: str = ""
    output_csv: str = ""

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class _Prepared:
    source_key: str
    url: str
    record: dict | None = None
    text: str = ""
    error: str | None = None
    out_of_date: bool = False
    downloaded: bool = False
    needs_ocr: bool = False


class CrawlService:
    def __init__(self, crawlers: dict, client, settings: Settings, companies: dict):
        self.crawlers, self.client, self.settings, self.companies = crawlers, client, settings, companies
        self.log, self.merger = logging.getLogger(__name__), ReportMerger()

    def _download_pdf(self, url: str, ticker: str, broker: str | None, published: datetime | None) -> tuple[Path, str]:
        response = self.client.get(url)
        validate_pdf_bytes(response.content, response.headers.get("Content-Type"))
        digest = hashlib.sha256(response.content).hexdigest()
        directory = self.settings.data_dir / "pdf" / ticker
        directory.mkdir(parents=True, exist_ok=True)
        date_part = published.date().isoformat() if published else "unknown"
        safe_broker = "".join(c for c in (broker or "UNKNOWN") if c.isalnum() or c in "_-")
        path = directory / f"{safe_broker}_{ticker}_{date_part}_{digest[:8]}.pdf"
        if not path.exists():
            path.write_bytes(response.content)
        return path, digest

    def _prepare(self, source_key: str, candidate: ReportCandidate, ticker: str, company: dict,
                 from_date: date | None, to_date: date | None, download_pdf: bool,
                 extract_text: bool) -> _Prepared:
        url = candidate.source_page_url
        try:
            candidate = self.crawlers[source_key].fetch_detail(candidate)
            if candidate.published_at and ((from_date and candidate.published_at.date() < from_date)
                                           or (to_date and candidate.published_at.date() > to_date)):
                return _Prepared(source_key, url, out_of_date=True)
            local_path = None
            pdf_hash = None
            extracted_path = None
            content_hash = None
            page_count = None
            text = candidate.page_text
            downloaded = False
            needs_ocr = False
            if candidate.pdf_url and download_pdf:
                local_path, pdf_hash = self._download_pdf(candidate.pdf_url, ticker, candidate.broker, candidate.published_at)
                downloaded = True
            if local_path and extract_text:
                extracted = extract_pdf(local_path)
                page_count, content_hash = extracted.page_count, extracted.content_hash
                text = extracted.text or text
                extracted_dir = self.settings.data_dir / "extracted" / ticker
                extracted_dir.mkdir(parents=True, exist_ok=True)
                extracted_path = extracted_dir / f"{local_path.stem}.txt"
                if not extracted_path.exists():
                    extracted_path.write_text(extracted.text, encoding="utf-8")
                pages_path = extracted_dir / f"{local_path.stem}.pages.json"
                if not pages_path.exists():
                    pages_path.write_text(json.dumps(extracted.pages, ensure_ascii=False, indent=2), encoding="utf-8")
                needs_ocr = extracted.needs_ocr
            validation = validate_ticker(ticker, company.get("company_name"), company.get("positive_aliases", []),
                                         company.get("excluded_entities", {}), candidate.title, text)
            status = "needs_ocr" if needs_ocr and validation.accepted else ("accepted" if validation.accepted else "rejected")
            recommendation, valuation, analysts = parse_metadata(f"{candidate.title}\n{text}")
            report_id = f"{(candidate.broker or 'unknown').lower()}_{ticker.lower()}_{hashlib.sha256((candidate.canonical_source_url + (pdf_hash or '')).encode()).hexdigest()[:12]}"
            notes = list(validation.notes)
            if candidate.source_platform == "CafeF" and candidate.description is None:
                notes.append("cafef_original_description_unavailable")
            record = ReportRecord(
                report_id=report_id, ticker=candidate.ticker or [ticker], company_name=company.get("company_name"),
                title=candidate.title, description=candidate.description, report_type=candidate.report_type,
                broker=candidate.broker, source_platform=candidate.source_platform, published_at=candidate.published_at,
                published_at_raw=candidate.published_at_raw, analyst=candidate.analyst or analysts,
                recommendation=recommendation.recommendation, recommendation_raw=recommendation.raw,
                target_price=recommendation.target_price, current_price=recommendation.current_price,
                upside_percent=recommendation.upside_percent, valuation_methods=valuation,
                source_page_url=candidate.source_page_url, canonical_source_url=candidate.canonical_source_url,
                pdf_url=candidate.pdf_url, local_pdf_path=str(local_path) if local_path else None,
                pdf_hash=pdf_hash, extracted_text_path=str(extracted_path) if extracted_path else None,
                content_hash=content_hash, page_count=page_count, crawled_at=datetime.now().astimezone(),
                status=status, validation_notes=notes,
            ).model_dump(mode="json")
            return _Prepared(source_key, url, record, text, downloaded=downloaded, needs_ocr=needs_ocr)
        except Exception as exc:
            return _Prepared(source_key, url, error=str(exc))

    def run(self, ticker: str, source_keys: list[str], *, target_reports: int = 100,
            max_pages: int | None = None, from_date: date | None = None, to_date: date | None = None,
            download_pdf: bool = True, extract_text: bool = True, retry_failed: bool = False,
            reset_state: bool = False, workers: int | None = None,
            progress: Callable[[str], None] | None = print) -> CrawlResult:
        ticker = ticker.upper()
        workers = max(1, min(workers or self.settings.workers, 3))
        safety_pages = max_pages or self.settings.safety_max_pages
        company = self.companies.get(ticker, {})
        existing_store = JsonlStore(self.settings.data_dir / "cleaned" / ticker / f"{ticker}_brokerage_reports.jsonl")
        duplicate_store = JsonlStore(self.settings.data_dir / "duplicates" / ticker / f"{ticker}_duplicates.jsonl")
        rejected_store = JsonlStore(self.settings.data_dir / "rejected" / ticker / f"{ticker}_rejected.jsonl")
        failed_store = JsonlStore(self.settings.data_dir / "failed" / ticker / f"{ticker}_failed.jsonl")
        records = existing_store.read_all()
        working = [{**row, "_text": ""} for row in records]
        result = CrawlResult(ticker=ticker, target=target_reports, existing_reports=len(records),
                             accepted_unique=len(records), total_unique_reports=len(records))
        if progress:
            progress(f"{ticker} | Target {target_reports} | Existing {len(records)}")
        if len(records) >= target_reports:
            return self._finish(result, working, records, existing_store)

        states = {key: StateStore(self.settings.data_dir / "state" / ticker / key) for key in source_keys}
        if reset_state:
            for state in states.values():
                state.reset()
        discovered_by_source: dict[str, list[ReportCandidate]] = {}
        with ThreadPoolExecutor(max_workers=min(workers, len(source_keys) or 1)) as pool:
            futures = {pool.submit(self.crawlers[key].search_reports, ticker, safety_pages, None): key for key in source_keys}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    candidates = future.result()
                except Exception as exc:
                    result.failed += 1
                    candidates = []
                    self.log.error("ticker=%s | source=%s | search_failed | %s", ticker, key, exc)
                discovered_by_source[key] = candidates
                result.source_discovered[key] = len(candidates)
                if self.crawlers[key].exhausted:
                    result.exhausted_sources.append(key)
                if progress:
                    progress(f"{self.crawlers[key].source_platform}: {len(candidates)} discovered")

        queue: list[tuple[str, ReportCandidate]] = []
        seen_urls: set[str] = set()
        for key in source_keys:
            candidates = discovered_by_source.get(key, [])
            raw_store = JsonlStore(self.settings.data_dir / "raw" / ticker / key / "discovered_reports.jsonl")
            for candidate in candidates:
                raw_store.append(candidate)
                url = candidate.canonical_source_url
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                state = states[key]
                if url in state.processed and not (retry_failed and url in state.failures):
                    result.skipped_processed += 1
                    continue
                queue.append((key, candidate))
            if retry_failed:
                known = {candidate.source_page_url for candidate in candidates}
                for url in states[key].failures:
                    if url not in known and url not in seen_urls:
                        seen_urls.add(url)
                        queue.append((key, ReportCandidate(title=ticker, ticker=[ticker],
                            source_platform=self.crawlers[key].source_platform, source_page_url=url,
                            canonical_source_url=url, broker=self.crawlers[key].official_broker)))
        result.discovered = len(seen_urls)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(self._prepare, key, candidate, ticker, company, from_date, to_date,
                                   download_pdf, extract_text) for key, candidate in queue]
            for future in as_completed(futures):
                if len(working) >= target_reports:
                    for pending in futures:
                        pending.cancel()
                    break
                prepared = future.result()
                state = states[prepared.source_key]
                if prepared.error:
                    result.failed += 1
                    state.fail(prepared.url, prepared.error)
                    failed_store.append({"ticker": ticker, "source": prepared.source_key, "url": prepared.url,
                                         "error": prepared.error, "at": datetime.now().astimezone().isoformat()})
                    continue
                if prepared.out_of_date:
                    state.success(prepared.url, "out_of_date")
                    continue
                record = prepared.record or {}
                result.pdf_downloaded += int(prepared.downloaded)
                result.needs_ocr += int(prepared.needs_ocr)
                probe = {**record, "_text": prepared.text}
                duplicate = find_duplicate(probe, working, self.settings.near_duplicate_threshold)
                if duplicate.duplicate:
                    result.duplicates += 1
                    working[duplicate.index] = self.merger.merge(working[duplicate.index], probe)
                    duplicate_store.append({**record, "status": "duplicate",
                                            "validation_notes": [*record.get("validation_notes", []), duplicate.reason]})
                    outcome = "duplicate"
                elif record.get("status") in ("accepted", "needs_ocr"):
                    working.append(probe)
                    result.new_accepted += 1
                    outcome = record["status"]
                else:
                    result.rejected += 1
                    rejected_store.append(record)
                    outcome = "rejected"
                state.success(prepared.url, outcome)
                self.log.info("ticker=%s | source=%s | %s | url=%s", ticker, prepared.source_key, outcome, prepared.url)
                result.total_unique_reports = result.accepted_unique = len(working)
                if progress:
                    progress(f"Unique accepted: {len(working)}/{target_reports} | Duplicates: {result.duplicates} | Rejected: {result.rejected} | Failed: {result.failed}")

        for state in states.values():
            state.save(result.model_dump())
        return self._finish(result, working, records, existing_store)

    def _finish(self, result: CrawlResult, working: list[dict], old_records: list[dict], store: JsonlStore) -> CrawlResult:
        persisted = [{key: value for key, value in row.items() if key != "_text"} for row in working]
        if persisted != old_records:
            store.replace_all(persisted)
        result.total_unique_reports = result.accepted_unique = len(persisted)
        export_dir = self.settings.data_dir / "exports" / result.ticker
        export_dir.mkdir(parents=True, exist_ok=True)
        csv_path = export_dir / f"{result.ticker}_brokerage_reports.csv"
        export_csv(persisted, csv_path)
        result.output_jsonl, result.output_csv = str(store.path), str(csv_path)
        (export_dir / "crawl_report.json").write_text(json.dumps(result.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        return result


def crawl_reports(ticker: str, target_reports: int = 100) -> CrawlResult:
    """API tối giản cho frontend; dùng cấu hình an toàn mặc định."""
    from crawlers import CRAWLERS
    from crawlers.http import HttpClient
    settings = Settings()
    client = HttpClient(settings.timeout, settings.retries, settings.delay_min, settings.delay_max, settings.user_agent)
    source_keys = ["cafef", "vietstock"]
    crawlers = {key: CRAWLERS[key](client) for key in source_keys}
    companies = json.loads(Path("config/companies.json").read_text(encoding="utf-8"))
    return CrawlService(crawlers, client, settings, companies).run(
        ticker, source_keys, target_reports=target_reports, workers=settings.workers)
