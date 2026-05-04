# Graph Report - .  (2026-05-04)

## Corpus Check
- 39 files · ~111,728 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 199 nodes · 324 edges · 23 communities detected
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 52 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 23|Community 23]]

## God Nodes (most connected - your core abstractions)
1. `is_authed()` - 22 edges
2. `compute_analytics_for_date()` - 21 edges
3. `get_db()` - 17 edges
4. `run_weekly_backfill()` - 13 edges
5. `flow()` - 11 edges
6. `process_message()` - 11 edges
7. `parse_joker_message()` - 8 edges
8. `get_scraper_db()` - 8 edges
9. `scraper_main()` - 8 edges
10. `rebuild_all_summaries()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `_startup_backtest()` --calls--> `run_backtest()`  [INFERRED]
  app.py → scraper_daily.py
- `admin_backfill_prices()` --calls--> `get_scraper_db()`  [INFERRED]
  app.py → scraper_daily.py
- `admin_backfill_prices()` --calls--> `backfill_prices()`  [INFERRED]
  app.py → scraper_daily.py
- `admin_backfill_200d()` --calls--> `get_scraper_db()`  [INFERRED]
  app.py → scraper_daily.py
- `admin_recompute_analytics()` --calls--> `get_scraper_db()`  [INFERRED]
  app.py → scraper_daily.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (36): admin_backfill_prices(), admin_fix_date(), admin_recompute_analytics(), flow(), Bulk-fetch Yahoo close prices into eod_summary. 1 request per ticker.      Par, Recompute analytics (gain%, phase, action) for date range after price_close fill, Force-refresh price_close + recompute analytics for a specific date.     Usage:, classify_zenith_v3_1() (+28 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (8): backup_db(), check_db_health(), export_db_dropbox(), get_trade_detail(), Check if current DB is valid/corrupt + diagnose file issues., Push zenith.db ke Dropbox sebagai timestamped backup. Tidak overwrite /zenith.db, Fetch Trade Detail narrative and metrics for a specific ticker on a date., Export entire SQLite database to JSON and upload to Dropbox.     Used for SQLit

### Community 2 - "Community 2"
Cohesion: 0.17
Nodes (14): trigger_backtest(), detect_format(), detect_mf_channel(), parse_freq(), parse_joker_message(), parse_mf_message(), parse_value(), parse_volx() (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.14
Nodes (14): admin_fetch_gains(), api_journal(), api_open_position(), api_ticker_fitness(), check_price_close(), ensure_indexes(), get_db(), last_date() (+6 more)

### Community 4 - "Community 4"
Cohesion: 0.16
Nodes (3): _getTopBar(), topbarDone(), topbarStart()

### Community 5 - "Community 5"
Cohesion: 0.15
Nodes (13): backtest_page(), chart_page(), flow_page(), hub(), ihsg(), is_authed(), journal_page(), kompas100_page() (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.17
Nodes (13): Queue a weekly backfill request — runs in scraper thread, not HTTP thread., Queue full scrape dari awal — fetch semua data dari Telegram., Queue summary rebuild — runs in scraper thread., rebuild_summary(), scrape_from_telegram(), scraper_status(), trigger_weekly(), get_backfill_status() (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.27
Nodes (9): get_scraper_db(), Main async loop: connect to Telegram, listen, and schedule backfill., Dedicated DB connection for scraper thread (separate from Flask)., scraper_main(), main(), scraper_weekly.py — Zenith Weekly Backfill ====================================, Standalone CLI entry point., Scrape messages from the past N days. Skips duplicates via INSERT OR IGNORE. (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.2
Nodes (10): get_message_topic_id(), process_message(), Insert SM/BM rows. Returns count of new rows inserted., Insert MF+/MF- rows. Returns count of new rows inserted., Return True if analytics for date_str should be recomputed now., Extract topic ID from a forum message., Parse and save a single Telegram message. Returns rows saved., save_mf_rows() (+2 more)

### Community 9 - "Community 9"
Cohesion: 0.25
Nodes (8): backfill_prices(), ensure_summary_table(), ensure_trade_journal_table(), Rebuild eod_summary for ALL dates + analytics for recent 15 days., Create eod_summary v4. Drops and recreates if base schema missing,     otherwis, Bulk-fetch Yahoo close prices. One request per ticker covers entire date range., Create trade_journal table — live position tracker., rebuild_all_summaries()

### Community 10 - "Community 10"
Cohesion: 0.33
Nodes (6): admin_backfill_200d(), One-time 200-day price_history backfill for MA200 computation.      Fetches ~3, backfill_price_history_200d(), _fetch_close_history(), Fetch daily close prices between two dates using timestamps. Returns {DD-MM-YYYY, One-time 200-day price_history backfill for MA200 computation.      Chunked in

### Community 11 - "Community 11"
Cohesion: 0.33
Nodes (6): enrich_daily_prices(), Scan all messages from today in all 4 topics, insert missing ones., Aggregate raw data for a date into eod_summary (flow fields only).      full_r, Fetch Yahoo close prices for all tickers on this date (always refreshes)., rebuild_summary_for_date(), run_backfill()

### Community 12 - "Community 12"
Cohesion: 0.4
Nodes (5): get_gains_batch(), parse_date(), DD-MM-YYYY → datetime.date, sector_api(), transactions()

### Community 13 - "Community 13"
Cohesion: 0.4
Nodes (5): _startup_backtest(), _fetch_price_history(), Fetch daily OHLCV from Yahoo for a ticker. Returns {date: {o,h,l,c}}., Pair-based backtest: BUY signal opens position, SELL signal closes it.     Entr, run_backtest()

### Community 14 - "Community 14"
Cohesion: 0.5
Nodes (4): fetch_gain_range(), Hitung % change harga saham dari date_from ke date_to.     Single day  → close, fetch_all_gains_to_db(), Fetch gain% + price dari Yahoo untuk semua ticker di date_str.     Simpan ke eo

### Community 15 - "Community 15"
Cohesion: 0.67
Nodes (3): api_backtest(), get_backtest_result(), Read latest cached backtest result from DB.

### Community 16 - "Community 16"
Cohesion: 0.67
Nodes (3): Bandarmologi Methodology, Wyckoff Phase Classification System, Zenith Platform

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (2): pull_db(), Download zenith.db dari Dropbox shareable link → simpan ke Railway volume.

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (2): download_db(), Download zenith.db for local backup.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (2): date_to_sortkey(), DD-MM-YYYY → YYYYMMDD integer for SQLite sorting.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (2): api_close_position(), Manual override: tutup semua posisi open untuk ticker tertentu.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (2): direct_backfill(), Spawn run_weekly_backfill in its own thread with its own Telegram client.     B

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Smart Money (SM)

## Knowledge Gaps
- **72 isolated node(s):** `Hitung % change harga saham dari date_from ke date_to.     Single day  → close`, `DD-MM-YYYY → datetime.date`, `DD-MM-YYYY → YYYYMMDD integer for SQLite sorting.`, `Thread-local connection reuse with optimized PRAGMAs.`, `Download zenith.db dari Dropbox shareable link → simpan ke Railway volume.` (+67 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 17`** (2 nodes): `pull_db()`, `Download zenith.db dari Dropbox shareable link → simpan ke Railway volume.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (2 nodes): `download_db()`, `Download zenith.db for local backup.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (2 nodes): `date_to_sortkey()`, `DD-MM-YYYY → YYYYMMDD integer for SQLite sorting.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (2 nodes): `api_close_position()`, `Manual override: tutup semua posisi open untuk ticker tertentu.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (2 nodes): `direct_backfill()`, `Spawn run_weekly_backfill in its own thread with its own Telegram client.     B`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Smart Money (SM)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `compute_analytics_for_date()` connect `Community 0` to `Community 2`, `Community 7`, `Community 8`, `Community 9`, `Community 11`?**
  _High betweenness centrality (0.166) - this node is a cross-community bridge._
- **Why does `flow()` connect `Community 0` to `Community 1`, `Community 3`, `Community 12`, `Community 5`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `admin_backfill_prices()` connect `Community 0` to `Community 1`, `Community 9`, `Community 7`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `compute_analytics_for_date()` (e.g. with `admin_backfill_prices()` and `admin_recompute_analytics()`) actually correct?**
  _`compute_analytics_for_date()` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `run_weekly_backfill()` (e.g. with `scraper_main()` and `get_scraper_db()`) actually correct?**
  _`run_weekly_backfill()` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `flow()` (e.g. with `classify_zenith_v3_1()` and `get_watch_flag()`) actually correct?**
  _`flow()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Hitung % change harga saham dari date_from ke date_to.     Single day  → close`, `DD-MM-YYYY → datetime.date`, `DD-MM-YYYY → YYYYMMDD integer for SQLite sorting.` to the rest of the system?**
  _72 weakly-connected nodes found - possible documentation gaps or missing edges._