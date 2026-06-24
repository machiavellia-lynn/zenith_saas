"""
startup.py — Zenith 2.0 Application Startup Orchestrator
RULE: Called once by app.py at startup. All init logic lives here, not in app.py.
"""
import os
import logging
import threading
import time

log = logging.getLogger("zenith.startup")


def do_startup(app):
    """Run all startup tasks inside Flask app context."""
    with app.app_context():
        _init_schema()
        _seed_admin()
        _start_scraper()
        _start_price_cache()
        _start_backtest()
        _start_portfolio_sim()


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


def _start_backtest():
    def _run():
        from algo.algo_backtest import run_backtest, run_bsjp_backtest
        from core.db import get_db
        try:
            conn = get_db()
            run_backtest(conn, days=0)
            log.info("Startup Wyckoff backtest OK")
        except Exception as e:
            log.warning("Startup Wyckoff backtest failed: %s", e)
        try:
            conn = get_db()
            run_bsjp_backtest(conn)
            log.info("Startup BSJP backtest OK")
        except Exception as e:
            log.warning("Startup BSJP backtest failed: %s", e)

    threading.Thread(target=_run, daemon=True, name="startup-backtest").start()


def _start_portfolio_sim():
    """Pre-warm portfolio simulation at startup so /portfolio loads instantly."""
    def _run():
        time.sleep(10)   # let backtest + scraper settle first
        try:
            from algo.algo_portfolio import request_portfolio_sim
            request_portfolio_sim(date_from=None, date_to=None)
            log.info("Startup portfolio sim triggered")
        except Exception as e:
            log.warning("Startup portfolio sim failed: %s", e)

    threading.Thread(target=_run, daemon=True, name="startup-portfolio").start()
