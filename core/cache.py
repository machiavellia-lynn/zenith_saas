"""
cache.py — In-memory TTL cache.
RULE: Thread-safe, zero external dependencies. Use for read-heavy, short-lived data.
"""
import threading
import time


class TTLCache:
    """Thread-safe key→value cache. Each key has its own expiry."""

    def __init__(self):
        self._store = {}
        self._lock  = threading.Lock()

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
