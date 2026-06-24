# Graph Report - zenith_saas  (2026-06-24)

## Corpus Check
- 52 files · ~116,597 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 669 nodes · 1046 edges · 95 communities detected
- Extraction: 67% EXTRACTED · 33% INFERRED · 0% AMBIGUOUS · INFERRED: 342 edges (avg confidence: 0.78)
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
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]

## God Nodes (most connected - your core abstractions)
1. `is_authed()` - 56 edges
2. `fetchall()` - 37 edges
3. `BSJPAlgo` - 29 edges
4. `get_db()` - 23 edges
5. `execute()` - 22 edges
6. `_compute_one()` - 19 edges
7. `ensure_schema()` - 18 edges
8. `scraper_main()` - 18 edges
9. `flow()` - 16 edges
10. `run_weekly_backfill()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `scraper_daily.py — Zenith 2.0 Telegram Scraper Daemon Realtime listener + sched` --uses--> `BSJPAlgo`  [INFERRED]
  scraper\scraper_daily.py → algo\algo_bsjp.py
- `Return healthy DB connection, silently reconnecting if the link dropped.` --uses--> `BSJPAlgo`  [INFERRED]
  scraper\scraper_daily.py → algo\algo_bsjp.py
- `Parse + save one Telegram message. Returns rows saved.` --uses--> `BSJPAlgo`  [INFERRED]
  scraper\scraper_daily.py → algo\algo_bsjp.py
- `Scan today's messages in all 4 topics and fill any gaps.` --uses--> `BSJPAlgo`  [INFERRED]
  scraper\scraper_daily.py → algo\algo_bsjp.py
- `Signal the scraper loop to process pending requests immediately.` --uses--> `BSJPAlgo`  [INFERRED]
  scraper\scraper_daily.py → algo\algo_bsjp.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (98): Create new user. Returns True on success, False if user exists., register(), Store value under key for ttl seconds., close_db(), execute(), fetchall(), fetchone(), get_db() (+90 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (60): _compute_atr_pct(), compute_bsjp_for_date(), compute_bsjp_range(), _compute_one(), generate_bsjp_signals(), analytics_bsjp.py — BSJP (Beli Sore Jual Pagi) Indicator Computation Reads from:, Run compute_bsjp_for_date for every date in range (DD-MM-YYYY format)., Compute all BSJP indicators for one ticker. ph = oldest-first OHLCV rows. (+52 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (52): compute_analytics_for_date(), compute_analytics_range(), analytics_daily.py — Zenith 2.0 Analytics Orchestration RULE: No HTTP calls. No, Run compute_analytics_for_date for every date in range., For every ticker in eod_summary on date_str:     1. Batch-load 10-day SM/BM hist, summary_rebuild.py — Zenith 2.0 Flow Aggregation Aggregate raw SM/BM/MF data fr, Seed eod_summary rows for ALL active tickers for each trading date in price_hist, Aggregate raw data for date_str into eod_summary (flow fields only).      full (+44 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (41): _days_between(), _dmy_to_ymd(), get_backtest_result(), get_backtest_status(), get_bsjp_result(), get_bsjp_status(), get_ticker_fitness(), algo_backtest.py — Zenith 2.0 Backtest Engine Pair-based backtest: multi-entry B (+33 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (45): is_authed(), get_cached_ihsg(), add_user(), admin_backfill_200d(), admin_backfill_intraday(), admin_backfill_intraday_all(), admin_backfill_ohlcv_daily(), admin_backfill_prices() (+37 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (47): classify_zenith_v3_1(), detect_trade_detail_gate(), get_action(), get_ma_structure(), get_phase_narrative(), get_watch_flag(), algo_wyckoff.py — Zenith Phase Classification Engine v3.1 RULE: Pure functions, Return "ARB_SPRING" if SPRING occurs during extreme drop (>1.5× ATR).     Phase (+39 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (19): _compute_atr_pct_hlc(), True Range ATR% using H/L/C from price_history rows (oldest-first).     TR = max, _make_history(), _make_ph(), _make_row(), tests/test_analytics_daily.py — Unit tests for algo/analytics_daily.py  Strategy, Regression: cc8ab41 — ATR must use H/L/C True Range, not close-to-close., When high/low missing, fallback: H=L=C, so TR = |C - prev_C|. (+11 more)

### Community 7 - "Community 7"
Cohesion: 0.1
Nodes (27): _axis_dates(), _build_stats(), _days_between(), get_portfolio_result(), get_portfolio_status(), _label(), _lots(), _max_drawdown_pct() (+19 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (23): _fetch_batch_quotes(), _fetch_ihsg(), _is_market_open(), price_cache.py — Server-side live price cache. One background thread refreshes e, Fetch live prices for all ~800 IDX tickers in batches of 100., Mon–Fri 09:00–16:15 WIB., Yahoo /v7/finance/quote for up to 100 IDX tickers. Returns {ticker: {price, gain, _refresh_ihsg() (+15 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (19): _create_backtest_cache(), _create_bsjp_results(), _create_bsjp_signals(), _create_corporate_events(), _create_eod_summary(), _create_inst_flow_cache(), _create_ohlcv_cache(), _create_price_history() (+11 more)

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (13): hash_password(), is_admin(), login(), auth.py — Zenith 2.0 Authentication RULE: All auth checks go through functions, Decorator: 403 for non-admin users., Hash password with bcrypt., Verify password against hash., Authenticate user against database. Returns True on success. (+5 more)

### Community 11 - "Community 11"
Cohesion: 0.23
Nodes (13): _addDay(), constructor(), _dim(), _first(), _fmt(), _inRangeWith(), _keyFromDate(), _openCal() (+5 more)

### Community 12 - "Community 12"
Cohesion: 0.16
Nodes (3): _getTopBar(), topbarDone(), topbarStart()

### Community 13 - "Community 13"
Cohesion: 0.27
Nodes (11): _detect_channel_from_header(), detect_format(), detect_mf_channel(), parse_freq(), parse_joker_message(), parse_mf_message(), parse_value(), parse_volx() (+3 more)

### Community 14 - "Community 14"
Cohesion: 0.25
Nodes (3): cache.py — In-memory TTL cache. RULE: Thread-safe, zero external dependencies. U, Thread-safe key→value cache. Each key has its own expiry.      A background daem, TTLCache

### Community 15 - "Community 15"
Cohesion: 0.33
Nodes (5): fetch_corporate_events(), get_upcoming_events(), ds_fundamental.py — DataSectors Fundamental Warnings (Tier 2) PLACEHOLDER: Fetc, Fetch corporate events for ticker from DataSectors API.     Cache results in co, Return events from corporate_events table within N days.     Called by analytic

### Community 16 - "Community 16"
Cohesion: 0.33
Nodes (5): _fetch_from_api(), get_inst_flow(), ds_smartmoney.py — DataSectors Institutional Flow (Tier 3) PLACEHOLDER: Fetch i, Get institutional flow signal for ticker.     Checks inst_flow_cache first (TTL, Hit DataSectors /api/institutional-flow/{symbol}. Returns signal string.

### Community 17 - "Community 17"
Cohesion: 0.33
Nodes (5): enrich_daily_prices_ds(), fetch_close_datasectors(), price_datasectors.py — DataSectors API Price Source (Tier 1) PLACEHOLDER: Not a, Fetch close price for ticker on date_str from DataSectors API.     Endpoint: /a, Replace enrich_daily_prices() in price_fetch.py with DataSectors source.

### Community 18 - "Community 18"
Cohesion: 0.5
Nodes (1): poc_broker_idx.py — IDX Broker Data POC Tests IDX unofficial endpoints to unders

### Community 19 - "Community 19"
Cohesion: 0.67
Nodes (1): app.py — Zenith 2.0 Entry Point RULE: Flask init + register blueprints only. Ze

### Community 20 - "Community 20"
Cohesion: 0.67
Nodes (1): poc_broker_idx3.py — Cari per-stock per-broker endpoint IDX IDX website menampil

### Community 21 - "Community 21"
Cohesion: 0.67
Nodes (3): Bandarmologi Methodology, Wyckoff Phase Classification System, Zenith Platform

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): config.py — Zenith 2.0 Central Configuration Single source of truth for all con

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): poc_broker_idx2.py — Investigate IDX statistical files

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): poc_broker_pdf.py — Parse IDX Daily Statistics PDF Cek apakah PDF punya tabel br

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Hitung % change harga saham dari date_from ke date_to.     Single day  → close

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): DD-MM-YYYY → datetime.date

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): DD-MM-YYYY → YYYYMMDD integer for SQLite sorting.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Thread-local connection reuse with optimized PRAGMAs.

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Download zenith.db dari Dropbox shareable link → simpan ke Railway volume.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Queue a weekly backfill request — runs in scraper thread, not HTTP thread.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Queue full scrape dari awal — fetch semua data dari Telegram.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Queue summary rebuild — runs in scraper thread.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Per-ticker backtest stats from cached results.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Bulk-fetch Yahoo close prices into eod_summary. 1 request per ticker.      Par

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): One-time 200-day price_history backfill for MA200 computation.      Fetches ~3

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Recompute analytics (gain%, phase, action) for date range after price_close fill

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Check if current DB is valid/corrupt + diagnose file issues.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Check price_close data status.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Force-refresh price_close + recompute analytics for a specific date.     Usage:

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Download zenith.db for local backup.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Track page views and active sessions for authenticated users.

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Spawn run_weekly_backfill in its own thread with its own Telegram client.     B

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Manual override: buka posisi baru di trade_journal.

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Manual override: tutup semua posisi open untuk ticker tertentu.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Fetch gain% dari Yahoo untuk tanggal tertentu, simpan ke eod_summary.      Mod

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Push zenith.db ke Dropbox sebagai timestamped backup. Tidak overwrite /zenith.db

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Fetch Trade Detail narrative and metrics for a specific ticker on a date.

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Export entire SQLite database to JSON and upload to Dropbox.     Used for SQLit

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): logic.py — Zenith Phase Classification Engine v3.1 ============================

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Classify Wyckoff phase using Zenith v3.1 logic.      Parameters     ---------

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Derive trading action from phase with 3 safety gates (v3.1).      Gate A — Sup

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Return "ARB_SPRING" if SPRING occurs during extreme drop (>1.5× ATR).     Phase

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Detect which (if any) Gate condition is active for Trade Detail display.

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Simple Moving Average. closes = chronological list (oldest first).     Returns

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): Wilder RSI-14. closes = chronological (oldest first), needs ≥ 15 values.

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Consecutive Momentum: days close above (+N) or below (-N) MA5.     Returns None

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): Classify MA alignment into 8 structure types per Zenith v3.1 catalog.      gap

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Return Phase × MA Structure narrative, with optional Gate override.

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): scraper.py — Zenith Unified Scraper ==================================== Runs

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): Parse SM/BM message. Returns list of row dicts.

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): Parse MF+/MF- message. Returns list of row dicts.

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): Dedicated DB connection for scraper thread (separate from Flask).

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): Insert SM/BM rows. Returns count of new rows inserted.

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): Insert MF+/MF- rows. Returns count of new rows inserted.

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): Return True if analytics for date_str should be recomputed now.

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): Extract topic ID from a forum message.

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): Parse and save a single Telegram message. Returns rows saved.

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): Create eod_summary v4. Drops and recreates if base schema missing,     otherwis

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): Aggregate raw data for a date into eod_summary (flow fields only).      full_r

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): Fetch Yahoo close prices for all tickers on this date (always refreshes).

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): Fetch daily close prices between two dates using timestamps. Returns {DD-MM-YYYY

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): Bulk-fetch Yahoo close prices. One request per ticker covers entire date range.

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): One-time 200-day price_history backfill for MA200 computation.      Chunked in

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Fetch gain% + price dari Yahoo untuk semua ticker di date_str.     Simpan ke eo

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): Create trade_journal table — live position tracker.

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): Insert new open position ke trade_journal.

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): Tutup SEMUA open position untuk ticker ini.

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): Cek semua open position — close jika loss >= threshold vs harga close hari ini.

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): Compute SRI/MES/VolxGap/RPR/Phase/Action/Watch for all tickers on date_str.

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): Rebuild eod_summary for ALL dates + analytics for recent 15 days.

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): Scan all messages from today in all 4 topics, insert missing ones.

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (1): Called from HTTP thread to request a backfill. Non-blocking.

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): Called from HTTP thread to request a full summary rebuild. Non-blocking.

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (1): Called from HTTP thread to check backfill/rebuild/backtest progress.

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (1): Main async loop: connect to Telegram, listen, and schedule backfill.

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (1): Start scraper in a daemon thread with its own asyncio event loop.

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (1): Read latest cached backtest result from DB.

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): Fetch daily OHLCV from Yahoo for a ticker. Returns {date: {o,h,l,c}}.

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (1): Compute phase+action for backtest engine. Uses centralised logic.py.

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): Pair-based backtest: BUY signal opens position, SELL signal closes it.     Entr

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): scraper_weekly.py — Zenith Weekly Backfill ====================================

### Community 100 - "Community 100"
Cohesion: 1.0
Nodes (1): Scrape messages from the past N days. Skips duplicates via INSERT OR IGNORE.

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): Standalone CLI entry point.

### Community 102 - "Community 102"
Cohesion: 1.0
Nodes (1): Smart Money (SM)

## Knowledge Gaps
- **225 isolated node(s):** `app.py — Zenith 2.0 Entry Point RULE: Flask init + register blueprints only. Ze`, `config.py — Zenith 2.0 Central Configuration Single source of truth for all con`, `poc_broker_idx.py — IDX Broker Data POC Tests IDX unofficial endpoints to unders`, `poc_broker_idx2.py — Investigate IDX statistical files`, `poc_broker_idx3.py — Cari per-stock per-broker endpoint IDX IDX website menampil` (+220 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 18`** (4 nodes): `poc_broker_idx.py`, `fetch()`, `poc_broker_idx.py — IDX Broker Data POC Tests IDX unofficial endpoints to unders`, `show()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (3 nodes): `app.py`, `handle_unhandled_exception()`, `app.py — Zenith 2.0 Entry Point RULE: Flask init + register blueprints only. Ze`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (3 nodes): `poc_broker_idx3.py`, `fetch()`, `poc_broker_idx3.py — Cari per-stock per-broker endpoint IDX IDX website menampil`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (2 nodes): `config.py`, `config.py — Zenith 2.0 Central Configuration Single source of truth for all con`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (2 nodes): `poc_broker_idx2.py`, `poc_broker_idx2.py — Investigate IDX statistical files`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (2 nodes): `poc_broker_pdf.py`, `poc_broker_pdf.py — Parse IDX Daily Statistics PDF Cek apakah PDF punya tabel br`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Hitung % change harga saham dari date_from ke date_to.     Single day  → close`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `DD-MM-YYYY → datetime.date`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `DD-MM-YYYY → YYYYMMDD integer for SQLite sorting.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Thread-local connection reuse with optimized PRAGMAs.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Download zenith.db dari Dropbox shareable link → simpan ke Railway volume.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Queue a weekly backfill request — runs in scraper thread, not HTTP thread.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Queue full scrape dari awal — fetch semua data dari Telegram.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Queue summary rebuild — runs in scraper thread.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Per-ticker backtest stats from cached results.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Bulk-fetch Yahoo close prices into eod_summary. 1 request per ticker.      Par`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `One-time 200-day price_history backfill for MA200 computation.      Fetches ~3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Recompute analytics (gain%, phase, action) for date range after price_close fill`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Check if current DB is valid/corrupt + diagnose file issues.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Check price_close data status.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Force-refresh price_close + recompute analytics for a specific date.     Usage:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Download zenith.db for local backup.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Track page views and active sessions for authenticated users.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Spawn run_weekly_backfill in its own thread with its own Telegram client.     B`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Manual override: buka posisi baru di trade_journal.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Manual override: tutup semua posisi open untuk ticker tertentu.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Fetch gain% dari Yahoo untuk tanggal tertentu, simpan ke eod_summary.      Mod`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Push zenith.db ke Dropbox sebagai timestamped backup. Tidak overwrite /zenith.db`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Fetch Trade Detail narrative and metrics for a specific ticker on a date.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Export entire SQLite database to JSON and upload to Dropbox.     Used for SQLit`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `logic.py — Zenith Phase Classification Engine v3.1 ============================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Classify Wyckoff phase using Zenith v3.1 logic.      Parameters     ---------`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Derive trading action from phase with 3 safety gates (v3.1).      Gate A — Sup`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Return "ARB_SPRING" if SPRING occurs during extreme drop (>1.5× ATR).     Phase`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Detect which (if any) Gate condition is active for Trade Detail display.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Simple Moving Average. closes = chronological list (oldest first).     Returns`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `Wilder RSI-14. closes = chronological (oldest first), needs ≥ 15 values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Consecutive Momentum: days close above (+N) or below (-N) MA5.     Returns None`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `Classify MA alignment into 8 structure types per Zenith v3.1 catalog.      gap`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Return Phase × MA Structure narrative, with optional Gate override.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `scraper.py — Zenith Unified Scraper ==================================== Runs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `Parse SM/BM message. Returns list of row dicts.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `Parse MF+/MF- message. Returns list of row dicts.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `Dedicated DB connection for scraper thread (separate from Flask).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `Insert SM/BM rows. Returns count of new rows inserted.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `Insert MF+/MF- rows. Returns count of new rows inserted.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `Return True if analytics for date_str should be recomputed now.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `Extract topic ID from a forum message.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `Parse and save a single Telegram message. Returns rows saved.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `Create eod_summary v4. Drops and recreates if base schema missing,     otherwis`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `Aggregate raw data for a date into eod_summary (flow fields only).      full_r`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `Fetch Yahoo close prices for all tickers on this date (always refreshes).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `Fetch daily close prices between two dates using timestamps. Returns {DD-MM-YYYY`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `Bulk-fetch Yahoo close prices. One request per ticker covers entire date range.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `One-time 200-day price_history backfill for MA200 computation.      Chunked in`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Fetch gain% + price dari Yahoo untuk semua ticker di date_str.     Simpan ke eo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `Create trade_journal table — live position tracker.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `Insert new open position ke trade_journal.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `Tutup SEMUA open position untuk ticker ini.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `Cek semua open position — close jika loss >= threshold vs harga close hari ini.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `Compute SRI/MES/VolxGap/RPR/Phase/Action/Watch for all tickers on date_str.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `Rebuild eod_summary for ALL dates + analytics for recent 15 days.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `Scan all messages from today in all 4 topics, insert missing ones.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `Called from HTTP thread to request a backfill. Non-blocking.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `Called from HTTP thread to request a full summary rebuild. Non-blocking.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `Called from HTTP thread to check backfill/rebuild/backtest progress.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (1 nodes): `Main async loop: connect to Telegram, listen, and schedule backfill.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `Start scraper in a daemon thread with its own asyncio event loop.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `Read latest cached backtest result from DB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `Fetch daily OHLCV from Yahoo for a ticker. Returns {date: {o,h,l,c}}.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `Compute phase+action for backtest engine. Uses centralised logic.py.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): `Pair-based backtest: BUY signal opens position, SELL signal closes it.     Entr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `scraper_weekly.py — Zenith Weekly Backfill ====================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 100`** (1 nodes): `Scrape messages from the past N days. Skips duplicates via INSERT OR IGNORE.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `Standalone CLI entry point.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 102`** (1 nodes): `Smart Money (SM)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fetchall()` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 7`?**
  _High betweenness centrality (0.177) - this node is a cross-community bridge._
- **Why does `flow()` connect `Community 0` to `Community 8`, `Community 4`, `Community 5`?**
  _High betweenness centrality (0.152) - this node is a cross-community bridge._
- **Why does `_compute_one()` connect `Community 5` to `Community 1`, `Community 2`, `Community 6`?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._
- **Are the 55 inferred relationships involving `is_authed()` (e.g. with `_require_admin()` and `admin_page()`) actually correct?**
  _`is_authed()` has 55 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `fetchall()` (e.g. with `run_backtest()` and `run_bsjp_backtest()`) actually correct?**
  _`fetchall()` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `BSJPAlgo` (e.g. with `algo_backtest.py — Zenith 2.0 Backtest Engine Pair-based backtest: multi-entry B` and `Convert DD-MM-YYYY to YYYYMMDD for correct string comparison.`) actually correct?**
  _`BSJPAlgo` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `get_db()` (e.g. with `_seed_admin()` and `login()`) actually correct?**
  _`get_db()` has 20 INFERRED edges - model-reasoned connections that need verification._