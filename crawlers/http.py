"""HTTP client lịch sự: session, timeout, backoff và rate-limit."""
import logging
import random
import time
import requests


class HttpClient:
    def __init__(self, timeout: float, retries: int, delay_min: float, delay_max: float, user_agent: str):
        self.timeout, self.retries = timeout, retries
        self.delay_min, self.delay_max = delay_min, delay_max
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7"})
        self.log = logging.getLogger(__name__)

    def get(self, url: str) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            if attempt or self.delay_min: time.sleep(random.uniform(self.delay_min, self.delay_max))
            try:
                response = self.session.get(url, timeout=self.timeout)
                self.log.debug("HTTP %s %s", response.status_code, url)
                if response.status_code == 404: response.raise_for_status()
                if response.status_code == 429:
                    wait = max(10.0, 2 ** (attempt + 2)); self.log.warning("429; chờ %.1fs | %s", wait, url); time.sleep(wait)
                elif response.status_code in {403}: response.raise_for_status()
                elif response.status_code >= 500: time.sleep(2 ** (attempt + 1))
                else: response.raise_for_status(); return response
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                last_error = exc
                if attempt + 1 < self.retries: time.sleep(2 ** (attempt + 1))
        raise RuntimeError(f"Không tải được {url}: {last_error}")
