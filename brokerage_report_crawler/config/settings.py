from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    data_dir: Path = Path("data")
    timeout: float = 30.0
    retries: int = 3
    delay_min: float = 0.2
    delay_max: float = 0.6
    workers: int = 3
    safety_max_pages: int = 50
    empty_page_limit: int = 2
    near_duplicate_threshold: float = 92.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
