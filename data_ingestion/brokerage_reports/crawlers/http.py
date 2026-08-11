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

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        error = None
        for attempt in range(self.retries):
            time.sleep(random.uniform(self.delay_min, self.delay_max))
            try:
                response = self.session.request(method, url, timeout=self.timeout, allow_redirects=True, **kwargs)
                self.log.debug("HTTP %s | %s", response.status_code, url)
                if response.status_code == 429:
                    time.sleep(max(10, 2 ** (attempt + 2)))
                    continue
                if response.status_code >= 500:
                    time.sleep(2 ** (attempt + 1))
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                error = exc
                if attempt + 1 < self.retries:
                    time.sleep(2 ** (attempt + 1))
        raise RuntimeError(f"request_failed:{url}:{error}")

    def get(self, url: str) -> requests.Response:
        return self.request("GET", url)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)
