import json
from pathlib import Path
from urllib.parse import urlsplit


class ReportMerger:
    def __init__(self, brokers_path: Path = Path("config/brokers.json")):
        self.brokers = json.loads(brokers_path.read_text(encoding="utf-8"))

    def is_official(self, report: dict) -> bool:
        broker = report.get("broker")
        domains = self.brokers.get(broker or "", {}).get("official_domains", [])
        host = urlsplit(report.get("canonical_source_url") or "").netloc.lower()
        return any(host == domain or host.endswith("." + domain) for domain in domains)

    def merge(self, primary: dict, mirror: dict) -> dict:
        if self.is_official(mirror) and not self.is_official(primary):
            primary, mirror = mirror, primary
        mirrors = [*primary.get("mirror_urls", []), mirror.get("canonical_source_url"), *mirror.get("mirror_urls", [])]
        primary["mirror_urls"] = list(dict.fromkeys(url for url in mirrors if url and url != primary.get("canonical_source_url")))
        if primary.get("report_type") in (None, "OTHER") and mirror.get("report_type") not in (None, "OTHER"):
            primary["report_type"] = mirror["report_type"]
        for key in (
            "broker", "description", "published_at", "published_at_raw",
            "pdf_url", "local_pdf_path", "pdf_hash", "extracted_text_path",
            "content_hash", "page_count",
        ):
            if not primary.get(key) and mirror.get(key):
                primary[key] = mirror[key]
        return primary
