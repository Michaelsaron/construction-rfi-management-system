"""Login / password-reset throttling (application layer).

nginx already limits /api/auth/ per IP. This adds what nginx cannot do:
  * per-ACCOUNT lockout after repeated failures (stops slow, distributed guessing of one password), and
  * a per-IP ceiling on FAILED attempts (password spraying across accounts), which also applies when the
    API is reached without nginx. Successful sign-ins are not counted, so a shared office IP is not blocked.

State is kept in process memory. The backend runs as a single uvicorn process, so this is exact; with
several workers/replicas each keeps its own counters (limits become per-process) - see docs/deployment.
A restart clears the counters. Unknown e-mails are throttled exactly like real ones (no enumeration).
"""
import threading
import time
from collections import defaultdict, deque


class SlidingWindow:
    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float):
        q = self._hits[key]
        while q and q[0] <= now - window:
            q.popleft()
        if not q:
            self._hits.pop(key, None)
        return q

    def retry_after(self, key: str) -> int:
        """Seconds until `key` is unlocked (0 = not locked)."""
        with self._lock:
            until = self._locked_until.get(key, 0)
            now = time.monotonic()
            if until <= now:
                self._locked_until.pop(key, None)
                return 0
            return int(until - now) + 1

    def hit(self, key: str, limit: int, window: float, lockout: float | None = None) -> int:
        """Record one event. Returns the retry-after seconds if this hit reaches the limit, else 0."""
        now = time.monotonic()
        with self._lock:
            self._prune(key, window, now)
            q = self._hits[key]
            q.append(now)
            if len(q) >= limit:
                self._locked_until[key] = now + (lockout if lockout is not None else window)
                q.clear()
                return int(lockout if lockout is not None else window)
            return 0

    def count(self, key: str, window: float) -> int:
        with self._lock:
            return len(self._prune(key, window, time.monotonic()))

    def reset(self, key: str):
        with self._lock:
            self._hits.pop(key, None)
            self._locked_until.pop(key, None)

    def clear(self):
        with self._lock:
            self._hits.clear()
            self._locked_until.clear()


limiter = SlidingWindow()


def client_ip(request, trust_proxy: bool) -> str:
    """The visitor IP. Proxy headers are trusted only when the API is reachable solely through our nginx."""
    if trust_proxy:
        ip = request.headers.get('x-real-ip') or (request.headers.get('x-forwarded-for') or '').split(',')[0].strip()
        if ip:
            return ip
    return request.client.host if request.client else 'unknown'
