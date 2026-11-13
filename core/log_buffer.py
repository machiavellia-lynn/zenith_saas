"""
log_buffer.py — In-process ring buffer of recent application log lines.

Powers the Admin → Log tab (UI v2). The app logs to stderr/journald; this
handler keeps the last N formatted records in memory so /admin/logs can
serve short polling requests. Deliberately NOT a stream: gunicorn runs a
single sync worker, so a held-open SSE/long-poll connection would block
the whole app.
"""
import logging
import threading
from collections import deque
from datetime import datetime

from config import WIB

_MAX_LINES = 2000

_lock = threading.Lock()
_lines = deque(maxlen=_MAX_LINES)
_seq = 0


class RingBufferHandler(logging.Handler):
    """Logging handler that appends formatted records to the ring buffer."""

    def emit(self, record):
        global _seq
        try:
            entry = {
                "ts": datetime.fromtimestamp(record.created, WIB).strftime("%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
        except Exception:
            return
        with _lock:
            _seq += 1
            entry["seq"] = _seq
            _lines.append(entry)


# Single shared handler instance; app.py attaches it to the root logger.
ring_handler = RingBufferHandler()


def get_since(since_seq: int):
    """Return (lines with seq > since_seq, last_seq).

    A client that falls behind the buffer (since_seq older than the
    oldest retained line) simply receives everything retained.
    """
    with _lock:
        last = _seq
        if since_seq <= 0:
            return list(_lines), last
        return [e for e in _lines if e["seq"] > since_seq], last
