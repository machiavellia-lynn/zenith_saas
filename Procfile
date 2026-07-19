# MALLOC_* caps glibc per-thread arenas and forces aggressive trim — the app runs
# ~15 background threads (scraper, price-cache, backtest, ThreadPoolExecutors) but
# almost no CPU, so fragmented arenas held peak RSS that Railway bills every minute.
web: MALLOC_ARENA_MAX=2 MALLOC_TRIM_THRESHOLD_=131072 gunicorn --workers 1 app:app --timeout 1000
