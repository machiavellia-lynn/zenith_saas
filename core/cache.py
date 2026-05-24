"""
cache.py — In-memory TTL cache.
RULE: Thread-safe, zero external dependencies. Use for read-heavy, short-lived data.
"""
import threading
import time


class TTLCache:
    """Thread-safe key→value cache. Each key has its own expiry.

    A background daemon thread purges expired entries every 60 s so RAM is
    released without waiting for a matching get() call.
    """

    def __init__(self):
        self._store = {}
        self._lock  = threading.Lock()
        self._start_purge_thread()

    def _start_purge_thread(self):
        def _loop():
            while True:
                time.sleep(60)
                self._purge_expired()
        threading.Thread(target=_loop, daemon=True, name="ttlcache-purge").start()

    def _purge_expired(self):
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._store.items() if v["exp"] <= now]
            for k in expired:
                del self._store[k]

    def get(self, key):
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if time.time() < entry["exp"]:
                return entry["val"]
            del self._store[key]
            return None

    def set(self, key, value, ttl: int):
        """Store value under key for ttl seconds."""
        with self._lock:
            self._store[key] = {"val": value, "exp": time.time() + ttl}

    def delete(self, key):
        with self._lock:
            self._store.pop(key, None)
