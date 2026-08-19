"""Cấu hình runtime, có thể ghi đè bằng CLI."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    data_dir: Path = Path("data")
    timeout: float = 20.0
    retries: int = 3
    delay_min: float = 1.5
    delay_max: float = 4.0
    min_relevance_score: float = 5.0
    min_word_count: int = 150
    near_duplicate_threshold: float = 92.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
