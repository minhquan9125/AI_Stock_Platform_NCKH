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
        self.processed = {row["url"] for row in self.processed_store.read_all() if row.get("url")}
        self.failures = {row["url"]: row for row in self.failed_store.read_all() if row.get("url")}
        self.failures = {url: row for url, row in self.failures.items() if url not in self.processed}

    def _write_failures(self) -> None:
        temporary = self.failed_store.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for row in self.failures.values():
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        temporary.replace(self.failed_store.path)

    def success(self, url: str, status: str) -> None:
        self.processed_store.append({"url": url, "status": status, "at": datetime.now().astimezone().isoformat()})
        self.processed.add(url)
        if self.failures.pop(url, None) is not None:
            self._write_failures()

    def fail(self, url: str, error: str) -> None:
        row = {"url": url, "error": error, "attempts": self.failures.get(url, {}).get("attempts", 0) + 1, "at": datetime.now().astimezone().isoformat()}
        self.failures[url] = row
        self._write_failures()

    def save(self, data: dict) -> None:
        self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for path in (self.processed_store.path, self.failed_store.path, self.state_path):
            if path.exists(): path.rename(path.with_name(f"{path.stem}.{stamp}.bak{path.suffix}"))
        self.processed.clear(); self.failures.clear()
