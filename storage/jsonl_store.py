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
        result = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try: result.append(json.loads(line))
                except json.JSONDecodeError: continue
        return result
