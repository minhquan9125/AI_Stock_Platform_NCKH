import logging
import random
import threading
import time
from urllib.parse import urlsplit
import requests


class HttpClient:
    def __init__(self, timeout: float, retries: int, delay_min: float, delay_max: float, user_agent: str):
        self.timeout, self.retries = timeout, retries
        self.delay_min, self.delay_max = delay_min, delay_max
        self.user_agent = user_agent
        self._local = threading.local()
        self._domain_locks: dict[str, threading.Lock] = {}
        self._domain_last_request: dict[str, float] = {}
        self._locks_guard = threading.Lock()
        self.log = logging.getLogger(__name__)

    def _session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            session = requests.Session()
            session.headers.update({"User-Agent": self.user_agent, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7"})
            self._local.session = session
        return self._local.session

    def _polite_wait(self, url: str) -> None:
        domain = urlsplit(url).netloc.lower()
        with self._locks_guard:
            lock = self._domain_locks.setdefault(domain, threading.Lock())
        with lock:
            interval = random.uniform(self.delay_min, self.delay_max)
            remaining = interval - (time.monotonic() - self._domain_last_request.get(domain, 0.0))
            if remaining > 0:
                time.sleep(remaining)
            self._domain_last_request[domain] = time.monotonic()

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        error = None
        for attempt in range(self.retries):
            try:
                self._polite_wait(url)
                response = self._session().request(method, url, timeout=self.timeout, allow_redirects=True, **kwargs)
                self.log.debug("HTTP %s | %s", response.status_code, url)
                if response.status_code == 429:
                    time.sleep(max(5, 2 ** (attempt + 2)))
                    continue
                if response.status_code >= 500:
                    time.sleep(2 ** (attempt + 1))
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                error = exc
        raise RuntimeError(f"request_failed:{url}:{error}")

    def get(self, url: str) -> requests.Response:
        return self.request("GET", url)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)
