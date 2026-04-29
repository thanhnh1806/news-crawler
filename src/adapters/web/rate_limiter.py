"""Domain rate limiter — implements IRateLimiter.
Depends on: threading, time (stdlib)."""
import time
import threading
from typing import Dict
from urllib.parse import urlparse

try:
    from src.application.ports.outbound.outbound_ports import IRateLimiter
except ImportError:
    from application.ports.outbound.outbound_ports import IRateLimiter


class DomainRateLimiter:
    """Thread-safe per-domain rate limiter.
    Ensures minimum delay between consecutive requests to the same domain."""

    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self._last_request: Dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, url: str) -> None:
        """Block until min_interval has passed since last request to this domain."""
        domain = urlparse(url).netloc
        with self._lock:
            now = time.monotonic()
            last = self._last_request.get(domain, 0)
            wait_time = self.min_interval - (now - last)
        if wait_time > 0:
            time.sleep(wait_time)
        with self._lock:
            self._last_request[domain] = time.monotonic()
