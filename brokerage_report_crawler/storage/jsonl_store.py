import json
from pathlib import Path
from pydantic import BaseModel


class JsonlStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, value: BaseModel | dict) -> None:
        data = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(data, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict]:
        if not self.path.exists(): return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try: rows.append(json.loads(line))
                except json.JSONDecodeError: continue
        return rows

    def replace_all(self, values: list[dict]) -> None:
        """Ghi nguyên tử toàn bộ JSONL, dùng khi merger cập nhật bản ghi đã có."""
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for value in values:
                stream.write(json.dumps(value, ensure_ascii=False) + "\n")
        temporary.replace(self.path)
