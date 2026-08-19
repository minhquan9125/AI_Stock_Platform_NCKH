"""State theo ticker; reset có backup để không mất dữ liệu cũ."""
import json
from datetime import datetime
from pathlib import Path
from .jsonl_store import JsonlStore


class StateStore:
    def __init__(self, root: Path):
        self.root = root
        self.processed_store = JsonlStore(root / "processed_urls.jsonl")
        self.failed_store = JsonlStore(root / "failed_urls.jsonl")
        self.state_path = root / "crawl_state.json"
        self.processed = {x.get("url") for x in self.processed_store.read_all()}
        self.failures = {x.get("url"): x for x in self.failed_store.read_all()}
        self.failures = {url: item for url, item in self.failures.items() if url and url not in self.processed}

    def _persist_failures(self) -> None:
        self.failed_store.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.failed_store.path.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for item in self.failures.values():
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
        temporary.replace(self.failed_store.path)

    def mark_processed(self, url: str, status: str) -> None:
        self.processed_store.append({"url": url, "status": status, "at": datetime.now().astimezone().isoformat()})
        self.processed.add(url)
        if url in self.failures:
            self.failures.pop(url)
            self._persist_failures()

    def mark_failed(self, url: str, error: str) -> None:
        attempts = int(self.failures.get(url, {}).get("attempts", 0)) + 1
        item = {"url": url, "error": error, "attempts": attempts, "at": datetime.now().astimezone().isoformat()}
        self.failures[url] = item
        self._persist_failures()

    def save_report(self, report: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for path in (self.processed_store.path, self.failed_store.path, self.state_path):
            if path.exists(): path.rename(path.with_name(f"{path.stem}.{stamp}.bak{path.suffix}"))
        self.processed.clear(); self.failures.clear()
