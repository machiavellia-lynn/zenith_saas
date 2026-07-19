"""
startup.py — Zenith 2.0 Application Startup Orchestrator
RULE: Called once by app.py at startup. All init logic lives here, not in app.py.
"""
import os
import logging

log = logging.getLogger("zenith.startup")


def do_startup(app):
    """Run all startup tasks inside Flask app context."""
    with app.app_context():
        _init_schema()
        _seed_admin()
        _start_scraper()
        _start_price_cache()
        # No startup compute for backtest or portfolio sim: both are in-memory-only
        # caches with zero DB persistence, so warming them here just spent RAM that
        # gets recomputed on the next deploy anyway. /api/portfolio and /admin's
        # "Recompute Portfolio" button self-heal/trigger on demand; only
        # /api/public/performance has no fallback and will 503 until one of those
        # runs post-deploy.


def _init_schema():
    try:
        from core.db_schema import ensure_schema
        ensure_schema()
        log.info("Schema OK")
    except Exception as e:
        log.error("Schema init failed: %s", e)


def _seed_admin():
    """Create initial admin user from ADMIN_INIT_PASSWORD env var if no users exist."""
    import os
    init_password = os.environ.get("ADMIN_INIT_PASSWORD", "").strip()
    if not init_password:
        return
    try:
        from core.db import get_db, fetchone
        from core.auth import register
        conn = get_db()
        if fetchone(conn, "SELECT id FROM users LIMIT 1"):
            return
        if register("admin", init_password, "admin"):
            log.info("Default admin user created")
    except Exception as e:
        log.warning("Admin seed failed: %s", e)


def _start_scraper():
    import config
    if not config.SCRAPER_ENABLED:
        return

    lock_path = "/tmp/zenith2_scraper.lock"
    try:
        if os.path.exists(lock_path):
            try:
                with open(lock_path) as f:
                    old_pid = int(f.read().strip())
                os.kill(old_pid, 0)
            except (ValueError, ProcessLookupError, PermissionError):
                os.remove(lock_path)

        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)

        from scraper.scraper_daily import start_scraper_thread
        start_scraper_thread()
    except FileExistsError:
        log.info("Scraper already running (lock exists), skipping")
    except Exception as e:
        log.error("Scraper start failed: %s", e)


def _start_price_cache():
    try:
        from data.price_cache import start_price_cache_thread
        start_price_cache_thread()
    except Exception as e:
        log.error("Price cache start failed: %s", e)

