import hashlib
import json
import logging
from datetime import date, datetime
from pathlib import Path
from config.settings import Settings
from models import ReportRecord
from processing.deduplicator import find_duplicate
from processing.metadata_parser import parse_metadata
from processing.pdf_extractor import extract_pdf, validate_pdf_bytes
from processing.ticker_validator import validate_ticker
from storage.csv_store import export_csv
from storage.jsonl_store import JsonlStore
from storage.state_store import StateStore
from .report_merger import ReportMerger


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

    def run(self, ticker: str, source_keys: list[str], *, limit: int | None, max_pages: int, from_date: date | None, to_date: date | None, download_pdf: bool, extract_text: bool, retry_failed: bool, reset_state: bool) -> dict:
        company = self.companies.get(ticker, {})
        existing_store = JsonlStore(self.settings.data_dir / "cleaned" / ticker / f"{ticker}_brokerage_reports.jsonl")
        duplicate_store = JsonlStore(self.settings.data_dir / "duplicates" / ticker / f"{ticker}_duplicates.jsonl")
        failed_store = JsonlStore(self.settings.data_dir / "failed" / ticker / f"{ticker}_failed.jsonl")
        records = existing_store.read_all()
        working = [{**row, "_text": ""} for row in records]
        stats = {"ticker": ticker, "sources": source_keys, "reports_discovered": 0, "pdf_downloaded": 0, "accepted": 0, "duplicates": 0, "rejected": 0, "failed": 0, "needs_ocr": 0}
        existing_count = len(working)
        for source_key in source_keys:
            crawler = self.crawlers[source_key]
            state = StateStore(self.settings.data_dir / "state" / ticker / source_key)
            if reset_state: state.reset()
            try:
                candidates = crawler.search_reports(ticker, max_pages, limit)
            except Exception as exc:
                stats["failed"] += 1; self.log.error("ticker=%s | source=%s | search_failed | %s", ticker, source_key, exc); continue
            if retry_failed:
                known = {item.source_page_url for item in candidates}
                for url in state.failures:
                    if url not in known:
                        from models import ReportCandidate
                        candidates.append(ReportCandidate(title=ticker, source_platform=crawler.source_platform, source_page_url=url, canonical_source_url=url, broker=crawler.official_broker))
            stats["reports_discovered"] += len(candidates)
            raw_store = JsonlStore(self.settings.data_dir / "raw" / ticker / source_key / "discovered_reports.jsonl")
            for candidate in candidates:
                raw_store.append(candidate)
            for candidate in candidates:
                url = candidate.source_page_url
                if url in state.processed and not (retry_failed and url in state.failures):
                    continue
                try:
                    candidate = crawler.fetch_detail(candidate)
                    if candidate.published_at and ((from_date and candidate.published_at.date() < from_date) or (to_date and candidate.published_at.date() > to_date)):
                        state.success(url, "out_of_date"); continue
                    local_path = None; pdf_hash = None; extracted_path = None; content_hash = None; page_count = None
                    text = candidate.page_text
                    status = "accepted"
                    pdf_note = None
                    if candidate.pdf_url and download_pdf:
                        try:
                            local_path, pdf_hash = self._download_pdf(candidate.pdf_url, ticker, candidate.broker, candidate.published_at)
                            stats["pdf_downloaded"] += 1
                        except Exception as pdf_exc:
                            # Không tải được PDF gốc (vd nguồn yêu cầu đăng nhập như
                            # SSI Research, mạng lỗi tạm thời...) KHÔNG được làm mất
                            # toàn bộ record - vẫn giữ lại metadata đã cào được từ
                            # trang danh sách (candidate.page_text) và đánh dấu rõ lý do
                            # thay vì rơi vào except chung ở dưới và mất sạch dữ liệu.
                            pdf_note = f"pdf_download_failed:{pdf_exc}"
                            self.log.warning("ticker=%s | source=%s | pdf_download_failed | url=%s | %s", ticker, source_key, candidate.pdf_url, pdf_exc)
                    if local_path and extract_text:
                        extracted = extract_pdf(local_path)
                        page_count, content_hash = extracted.page_count, extracted.content_hash
                        text = extracted.text or text
                        extracted_dir = self.settings.data_dir / "extracted" / ticker; extracted_dir.mkdir(parents=True, exist_ok=True)
                        extracted_path = extracted_dir / f"{local_path.stem}.txt"
                        if not extracted_path.exists(): extracted_path.write_text(extracted.text, encoding="utf-8")
                        pages_path = extracted_dir / f"{local_path.stem}.pages.json"
                        if not pages_path.exists():
                            pages_path.write_text(json.dumps(extracted.pages, ensure_ascii=False, indent=2), encoding="utf-8")
                        if extracted.needs_ocr: status = "needs_ocr"; stats["needs_ocr"] += 1
                    validation = validate_ticker(ticker, company.get("company_name"), company.get("positive_aliases", []), company.get("excluded_entities", {}), candidate.title, text)
                    if not validation.accepted:
                        status = "rejected"; stats["rejected"] += 1
                    recommendation, valuation, analysts = parse_metadata(f"{candidate.title}\n{text}")
                    report_id = f"{(candidate.broker or 'unknown').lower()}_{ticker.lower()}_{hashlib.sha256((candidate.canonical_source_url + (pdf_hash or '')).encode()).hexdigest()[:12]}"
                    notes = list(validation.notes)
                    if candidate.source_platform == "CafeF" and candidate.description is None:
                        notes.append("cafef_original_description_unavailable")
                    if pdf_note:
                        notes.append(pdf_note)
                    record = ReportRecord(report_id=report_id, ticker=candidate.ticker or [ticker], company_name=company.get("company_name"), title=candidate.title, description=candidate.description, report_type=candidate.report_type, broker=candidate.broker, source_platform=candidate.source_platform, published_at=candidate.published_at, published_at_raw=candidate.published_at_raw, analyst=candidate.analyst or analysts, recommendation=recommendation.recommendation, recommendation_raw=recommendation.raw, target_price=recommendation.target_price, current_price=recommendation.current_price, upside_percent=recommendation.upside_percent, valuation_methods=valuation, source_page_url=candidate.source_page_url, canonical_source_url=candidate.canonical_source_url, pdf_url=candidate.pdf_url, local_pdf_path=str(local_path) if local_path else None, pdf_hash=pdf_hash, extracted_text_path=str(extracted_path) if extracted_path else None, content_hash=content_hash, page_count=page_count, crawled_at=datetime.now().astimezone(), status=status, validation_notes=notes).model_dump(mode="json")
                    probe = {**record, "_text": text}
                    duplicate = find_duplicate(probe, working, self.settings.near_duplicate_threshold)
                    if duplicate.duplicate:
                        outcome = "duplicate"
                        stats["duplicates"] += 1
                        old = working[duplicate.index]
                        merged = self.merger.merge(old, probe)
                        working[duplicate.index] = merged
                        duplicate_store.append({**record, "status": "duplicate", "validation_notes": [*record["validation_notes"], duplicate.reason]})
                    elif status == "accepted":
                        outcome = "accepted"
                        stats["accepted"] += 1; working.append(probe)
                    else:
                        outcome = status
                        failed_store.append(record)
                    state.success(url, status)
                    self.log.info("ticker=%s | source=%s | %s | url=%s", ticker, source_key, outcome, url)
                except Exception as exc:
                    stats["failed"] += 1; state.fail(url, str(exc)); failed_store.append({"ticker": ticker, "source": source_key, "url": url, "error": str(exc), "at": datetime.now().astimezone().isoformat()}); self.log.exception("ticker=%s | source=%s | failed | url=%s", ticker, source_key, url)
            state.save(stats)
        # Merger có thể đổi canonical URL của một record cũ sang nguồn broker chính thức,
        # vì vậy phải persist cả cập nhật mirror thay vì chỉ append record mới.
        persisted = [{key: value for key, value in row.items() if key != "_text"} for row in working]
        if persisted != records:
            existing_store.replace_all(persisted)
        all_rows = existing_store.read_all()
        export_dir = self.settings.data_dir / "exports" / ticker; export_dir.mkdir(parents=True, exist_ok=True)
        export_csv(all_rows, export_dir / f"{ticker}_brokerage_reports.csv")
        stats.update({"output_jsonl": str(existing_store.path), "output_csv": str(export_dir / f"{ticker}_brokerage_reports.csv")})
        (export_dir / "crawl_report.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        return stats
