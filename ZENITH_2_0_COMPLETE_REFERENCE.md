# Zenith 2.0 — Complete Reference

> **Tujuan dokumen ini**: Memberikan pemahaman penuh tentang arsitektur, data flow, algoritma, dan kode Zenith 2.0 kepada siapa pun yang membacanya — tanpa perlu bertanya lagi.

---

## Daftar Isi

1. [Gambaran Umum](#1-gambaran-umum)
2. [Stack & Deployment](#2-stack--deployment)
3. [Struktur Direktori](#3-struktur-direktori)
4. [Arsitektur Sistem](#4-arsitektur-sistem)
5. [Database Schema](#5-database-schema)
6. [Konfigurasi (config.py)](#6-konfigurasi-configpy)
7. [Alur Data End-to-End](#7-alur-data-end-to-end)
8. [Scraper Engine](#8-scraper-engine)
9. [Algoritma Inti](#9-algoritma-inti)
10. [Analytics Pipeline](#10-analytics-pipeline)
11. [HTTP Routes & API](#11-http-routes--api)
12. [Layer Autentikasi](#12-layer-autentikasi)
13. [Price Fetching](#13-price-fetching)
14. [Backtest Engine](#14-backtest-engine)
15. [Trade Journal](#15-trade-journal)
16. [Caching Strategy](#16-caching-strategy)
17. [Startup & Inisialisasi](#17-startup--inisialisasi)
18. [Environment Variables](#18-environment-variables)
19. [Dependency Graph](#19-dependency-graph)
20. [Aturan Desain (Design Rules)](#20-aturan-desain-design-rules)
21. [Fitur Belum Aktif (Placeholder)](#21-fitur-belum-aktif-placeholder)

---

## 1. Gambaran Umum

Zenith 2.0 adalah platform analisis pasar saham Indonesia yang fokus pada **institutional money flow** — melacak pergerakan *Smart Money* (SM) vs *Bad Money* (BM) melalui parsing pesan Telegram dari grup BST.

**Fungsi utama:**
- Scrape pesan Telegram secara realtime dan terjadwal
- Parse data transaksi SM/BM/MF+/MF- dari format pesan terstruktur
- Agregasi ke database harian (eod_summary)
- Klasifikasi fase Wyckoff menggunakan algoritma Zenith v3.1
- Tampilkan sinyal (phase, action, narrative) lewat web dashboard

**Bahasa & Framework:**
- Backend: Python 3.x + Flask
- Database: PostgreSQL
- Scraper: Telethon (Telegram MTProto)
- Frontend: HTML/CSS/JS (Jinja2 templates)
- Deployment: Railway

---

## 2. Stack & Deployment

| Komponen | Detail |
|---|---|
| Web server | Flask (port 5000) |
| Database | PostgreSQL (Railway managed) |
| Scraper | Telethon async daemon (background thread) |
| Session | Flask-Session (filesystem, `/tmp/zenith_2_0_sessions/`) |
| Harga saham | Yahoo Finance (sementara, belum ada paid API) |
| Deployment | Railway — auto-deploy dari branch `main` |
| Timezone | WIB (UTC+7) untuk semua operasi jadwal |

**Penting**: Zenith 1.0 dan 2.0 berjalan **bersamaan** di Railway, sehingga session dikonfigurasi terpisah (`SESSION_DIR` berbeda antar versi).

---

## 3. Struktur Direktori

```
zenith_saas/
├── app.py                    # Flask app factory, register blueprints
├── startup.py                # Inisialisasi DB, seed admin, start scraper
├── config.py                 # Semua konstanta, env vars, sector mapping
│
├── core/
│   ├── db.py                 # Koneksi PostgreSQL, helper query
│   ├── db_schema.py          # DDL: semua CREATE TABLE & index
│   ├── auth.py               # Login, register, session, decorator
│   ├── utils.py              # Pure utility functions (parse date, format IDR)
│   └── cache.py              # Thread-safe TTL in-memory cache
│
├── algo/
│   ├── algo_wyckoff.py       # Zenith phase classification v3.1 (pure functions)
│   ├── analytics_daily.py    # Orchestrator: hitung analytics per date
│   ├── summary_rebuild.py    # Rebuild eod_summary dari raw_messages
│   ├── algo_backtest.py      # Multi-entry backtest engine
│   └── indicators.py         # MA, RSI14, CM streak (pure functions)
│
├── data/
│   ├── price_fetch.py        # Fetch harga dari Yahoo Finance
│   ├── journal.py            # Trade journal CRUD
│   ├── ds_smartmoney.py      # [PLACEHOLDER] DataSectors institutional flow
│   ├── ds_fundamental.py     # [PLACEHOLDER] DataSectors corporate events
│   └── price_datasectors.py  # [PLACEHOLDER] DataSectors price source
│
├── scraper/
│   ├── scraper_daily.py      # Daemon: realtime listener + jadwal harian
│   ├── scraper_parser.py     # Pure parser pesan Telegram (SM/BM/MF format)
│   ├── scraper_saver.py      # Insert rows ke raw_messages / raw_mf_messages
│   └── scraper_weekly.py     # Backfill histori N hari
│
├── routes/
│   ├── routes_main.py        # Halaman: /, /hub, /chart, /flow, /health
│   ├── routes_flow.py        # API: /api/flow, /api/transactions, /api/overlay, /api/ohlcv
│   ├── routes_sector.py      # Halaman + API: /sector, /api/sector
│   ├── routes_backtest.py    # Halaman + API: /backtest, /api/backtest, /api/ticker-fitness
│   ├── routes_journal.py     # Halaman + API: /journal, /api/journal/*
│   └── routes_admin.py       # Admin panel: /admin, semua endpoint operasional
│
└── tests/                    # Unit tests (terpisah)
```

---

## 4. Arsitektur Sistem

```
┌──────────────────────────────────────────────────────────────────┐
│                        RAILWAY SERVER                            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Main Thread: Flask HTTP Server (port 5000)              │    │
│  │  Routes: main / flow / sector / backtest / journal / admin│   │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  ┌───────────────────────────▼─────────────────────────────┐    │
│  │  Daemon Thread: Telegram Scraper                         │    │
│  │  ┌─────────────────┐  ┌──────────────────────────────┐  │    │
│  │  │ Realtime Listener│  │ Scheduled Passes (WIB)       │  │    │
│  │  │ NewMessage event │  │ 12:10 Midday Pass            │  │    │
│  │  │ (SM/BM/MF+/MF-) │  │ 15:30 First Backfill         │  │    │
│  │  └─────────────────┘  │ 16:30 Second Pass + Backtest  │  │    │
│  │                        └──────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  ┌───────────────────────────▼─────────────────────────────┐    │
│  │  PostgreSQL Database                                     │    │
│  │  raw_messages → eod_summary → analytics fields           │    │
│  │  price_history (210d OHLCV dari Yahoo Finance)           │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Database Schema

### 5.1 `users` — Autentikasi
```sql
id           SERIAL PRIMARY KEY
username     VARCHAR(255) UNIQUE NOT NULL
password_hash VARCHAR(255) NOT NULL   -- bcrypt
role         VARCHAR(50) DEFAULT 'guest'  -- 'admin' atau 'guest'
created_at   TIMESTAMP DEFAULT NOW()
```
Index: `idx_users_username`

---

### 5.2 `raw_messages` — Transaksi SM/BM dari Telegram
```sql
id                SERIAL PRIMARY KEY
message_id        BIGINT              -- ID pesan Telegram
channel           TEXT                -- 'smart' atau 'bad'
date              TEXT                -- format: DD-MM-YYYY
time              TEXT                -- format: HH.MM
tx_count          INTEGER
ticker            TEXT NOT NULL
price             REAL
gain_pct          REAL                -- perubahan harga hari ini (%)
freq              INTEGER
value_raw         TEXT                -- "1.5T", "500rb", dsb
value_numeric     REAL                -- dalam Juta Rupiah
avg_mf_raw        TEXT
avg_mf_numeric    REAL
mf_delta_raw      TEXT
mf_delta_numeric  REAL                -- net money flow, sign = arah
vol_x             REAL                -- volume multiplier
signal            TEXT
UNIQUE (message_id, ticker)           -- deduplication
```
Index: `idx_raw_date`, `idx_raw_ticker_date`

---

### 5.3 `raw_mf_messages` — Mutual Fund Flow (MF+/MF-)
```sql
id                SERIAL PRIMARY KEY
message_id        BIGINT
channel           TEXT                -- 'mf_plus' atau 'mf_minus'
date              TEXT
time              TEXT
tx_count          INTEGER
ticker            TEXT NOT NULL
price             REAL
gain_pct          REAL
val_raw           TEXT
val_numeric       REAL
mf_raw            TEXT
mf_numeric        REAL
mft_raw           TEXT
mft_numeric       REAL
cm_delta_raw      TEXT
cm_delta_numeric  REAL                -- clean money delta
signal            TEXT
UNIQUE (message_id, ticker)
```
Index: `idx_mf_date`, `idx_mf_ticker_date`

---

### 5.4 `eod_summary` — Tabel Fakta Utama (Flow + Analytics)
> Ini adalah tabel terpenting. Semua halaman web membaca dari sini.

```sql
-- Primary Key
date             TEXT NOT NULL        -- DD-MM-YYYY
ticker           TEXT NOT NULL

-- Flow fields (diisi oleh summary_rebuild.py)
sm_val           REAL DEFAULT 0       -- total SM value (Juta)
bm_val           REAL DEFAULT 0       -- total BM value (Juta)
tx_count         INTEGER DEFAULT 0
tx_sm            INTEGER DEFAULT 0    -- jumlah transaksi SM
tx_bm            INTEGER DEFAULT 0    -- jumlah transaksi BM
mf_plus          REAL                 -- total MF+ value
mf_minus         REAL                 -- total MF- value
vwap_sm          REAL                 -- VWAP SM (price-weighted avg)
vwap_bm          REAL                 -- VWAP BM

-- Analytics fields (diisi oleh analytics_daily.py)
price_close      REAL                 -- harga penutupan
price_change_pct REAL                 -- perubahan % dari hari sebelumnya
sri              REAL                 -- SM Relative Intensity
mes              REAL                 -- Market Exhaustion Score (BM %)
volx_gap         REAL                 -- (close - vwap_sm) / vwap_sm * 100
rpr              REAL                 -- Sell Pressure Ratio (tx_bm / total_tx)
atr_pct          REAL                 -- ATR 14 hari sebagai % harga
sm_sma10         REAL                 -- SMA10 sm_val
bm_sma10         REAL                 -- SMA10 bm_val
ma5, ma13, ma34, ma200  REAL          -- Moving averages
rsi14            REAL                 -- RSI 14 hari
cm_streak        INTEGER              -- Consecutive Momentum streak
ma_structure     TEXT                 -- 8 tipe struktur MA
phase            TEXT                 -- SOS/SPRING/ABSORB/ACCUM/UPTHRUST/DISTRI/NEUTRAL
action           TEXT                 -- BUY/SELL/HOLD
watch            TEXT                 -- ARB_SPRING atau NULL
trade_gate       TEXT                 -- Gate A / Gate B / Gate C atau NULL
narrative        TEXT                 -- Narasi trading Indonesia (panjang)

PRIMARY KEY (date, ticker)
```
Index: `idx_eod_date`, `idx_eod_ticker`

---

### 5.5 `ticker_universe` — Master Daftar Saham untuk BSJP
```sql
ticker          TEXT PRIMARY KEY
is_active       BOOLEAN DEFAULT TRUE
created_at      TIMESTAMP DEFAULT NOW()
```
Index: `idx_ticker_active`
> Auto-seeded dari eod_summary dan price_history. Baru ticker daftar otomatis ke sini via scraper_saver._register_tickers().

---

### 5.6 `price_history` — OHLCV Harian + BSJP Indicators (dari Yahoo Finance)
```sql
-- Primary OHLCV
date    TEXT NOT NULL           -- YYYY-MM-DD (format berbeda dari eod_summary!)
ticker  TEXT NOT NULL
open    REAL
high    REAL
low     REAL
close   REAL NOT NULL
volume  BIGINT

-- BSJP Indicators (19 columns, diisi oleh analytics_bsjp.py)
ma5, ma13, ma34, ma50, ma200    REAL     -- Moving averages
atr_pct                         REAL     -- ATR 14 hari sebagai % harga
bb_upper, bb_mid, bb_lower      REAL     -- Bollinger Bands 20 ± 2σ
bb_width                        REAL     -- Band width = upper - lower
close_pos                       REAL     -- Close position dalam [0,1] dari low ke high
prev_high_break                 BOOLEAN  -- Apakah close hari ini > high kemarin
ma5_price_streak                INTEGER  -- +N atau -N: hari consecutive di atas/bawah MA5
is_sideways                     BOOLEAN  -- Apakah sideways (flat market)
daily_value                     REAL     -- close × volume
prev_close_below_ma5            BOOLEAN  -- Apakah close kemarin < MA5
prev_close_below_bb_lower       BOOLEAN  -- Apakah close kemarin < BB lower
days_since_near_ma50            INTEGER  -- Hari terakhir close dekat MA50 (±2%)
days_since_near_bb_mid          INTEGER  -- Hari terakhir close dekat BB midline (±2%)

PRIMARY KEY (date, ticker)
```
Index: `idx_ph_ticker`, `idx_ph_ticker_date`
> Catatan: 
> - `price_history.date` menggunakan format YYYY-MM-DD, sedangkan `eod_summary.date` menggunakan DD-MM-YYYY.
> - BSJP indicators hanya untuk price-based analysis (no Telegram data needed).
> - Diisi setelah eod_summary pada setiap hari via `compute_bsjp_for_date()`.

---

### 5.7 `trade_journal` — Catatan Perdagangan Manual
```sql
id           SERIAL PRIMARY KEY
ticker       TEXT NOT NULL
entry_phase  TEXT                -- fase saat beli (SOS, SPRING, dll)
entry_date   TEXT NOT NULL
buy_price    REAL NOT NULL
status       TEXT DEFAULT 'open'  -- 'open' atau 'closed'
exit_date    TEXT
sell_price   REAL
gain_pct     REAL
hold_days    INTEGER
exit_reason  TEXT
created_at   TEXT
updated_at   TEXT
```
Index: `idx_journal_ticker_status`, `idx_journal_entry_date`

---

### 5.8 `price_history_15m` — Intraday 15m Candles (dari Yahoo Finance)
```sql
datetime  TEXT NOT NULL           -- YYYY-MM-DD HH:MM (format WIB)
ticker    TEXT NOT NULL
open      REAL
high      REAL
low       REAL
close     REAL NOT NULL
volume    BIGINT
PRIMARY KEY (datetime, ticker)
```
Index: `idx_ph15m_ticker`
> Catatan:
> - Diisi via `backfill_intraday_15m(date_from, date_to)` di admin panel
> - Yahoo Finance membatasi 15m data max ~60 hari kebelakang
> - Digunakan BSJP backtest untuk mengetahui exact timing SL/TP hits during market hours
> - User trigger per small range (2–3 hari) untuk menghindari bottleneck

---

### 5.9 `backtest_cache` — Cache Hasil Backtest
```sql
id          SERIAL PRIMARY KEY
run_id      TEXT UNIQUE
days        INTEGER
date_from   TEXT
date_to     TEXT
result      TEXT    -- JSON serialized
computed_at TEXT
```

---

### 5.10 Tabel Placeholder (DataSectors — Belum Aktif)
- `ohlcv_cache` — (ticker, date) PK, OHLCV dari DataSectors
- `corporate_events` — (ticker, event_type, event_date) PK, dividen/split/rights
- `inst_flow_cache` — ticker PK, signal ACCUMULATION/DISTRIBUTION/NEUTRAL

---

## 6. Konfigurasi (config.py)

```python
# Environment
IS_RAILWAY = bool(RAILWAY_ENVIRONMENT atau RAILWAY_PROJECT_ID)

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://...localhost.../zenith")

# Flask
FLASK_SECRET = os.environ.get("FLASK_SECRET", "zenith-secret-key-dev")
SESSION_DIR  = os.environ.get("SESSION_DIR", "/tmp/zenith_2_0_sessions/")

# Cache TTL
CACHE_TTL      = 86400   # 24 jam di Railway, 5 menit lokal
FLOW_CACHE_TTL = 60      # route-level cache
GAIN_CACHE_TTL = 300     # cache harga/gain (5 menit)

# Timezone
WIB = timezone(timedelta(hours=7))

# Telegram
TG_API_ID         = int(os.environ.get("TG_API_ID", "0"))
TG_API_HASH       = os.environ.get("TG_API_HASH", "")
TG_SESSION_PATH   = os.environ.get("TG_SESSION_PATH", "/data/session_joker_2")
TG_GROUP_ID       = -1002717915373
TG_TOPIC_SMART    = 192528
TG_TOPIC_BAD      = 219042
TG_TOPIC_MF_PLUS  = 1025256
TG_TOPIC_MF_MINUS = 1025260

# Jadwal Scraper (WIB)
MIDDAY_HOUR    = 12  MIDDAY_MINUTE    = 10   # Pass tengah hari
BACKFILL_HOUR  = 15  BACKFILL_MINUTE  = 30   # First backfill
RECOMPUTE_HOUR = 16  RECOMPUTE_MINUTE = 30   # Second pass + backtest

# Yahoo Finance
INTERVAL_MAP = {
    "5m":  {"interval": "5m",  "days": 59},
    "15m": {"interval": "15m", "days": 59},
    "30m": {"interval": "30m", "days": 59},
    "1h":  {"interval": "60m", "days": 720},
    "1d":  {"interval": "1d",  "days": 99999},
}

# DataSectors (belum aktif)
DS_API_KEY  = os.environ.get("DATASECTORS_API_KEY", "")
DS_ENABLED  = bool(DS_API_KEY)
DS_BASE_URL = "https://api.datasectors.com"

# Sektors: 11 sektor dengan ratusan ticker masing-masing
SECTORS = {
    "Energy": [...],
    "Basic Materials": [...],
    "Industrials": [...],
    "Consumer Non-Cyclicals": [...],
    "Consumer Cyclicals": [...],
    "Healthcare": [...],
    "Financials": [...],
    "Property": [...],
    "Technology": [...],
    "Infrastructure": [...],
    "Transport": [...],
}
```

---

## 7. Alur Data End-to-End

### 7.1 Alur Realtime (saat pesan Telegram masuk)

```
Telegram Channel (BST Group)
        │
        ▼
TelegramClient.on(NewMessage) ← scraper_daily.py
        │
        ▼
get_message_topic_id()
→ route ke TOPIC_SMART, TOPIC_BAD, TOPIC_MF_PLUS, TOPIC_MF_MINUS
        │
        ├─ SM/BM → parse_joker_message() ← scraper_parser.py
        └─ MF+/MF- → parse_mf_message()  ← scraper_parser.py
        │
        ▼
save_sm_bm_rows() atau save_mf_rows()  ← scraper_saver.py
→ INSERT INTO raw_messages / raw_mf_messages
→ ON CONFLICT (message_id, ticker) DO NOTHING  ← deduplication
        │
        ▼
rebuild_summary_for_date(conn, date_str)  ← summary_rebuild.py
→ Agregasi raw_messages → UPDATE eod_summary (flow fields saja)
        │
        ▼
compute_analytics_for_date(conn, date_str)  ← analytics_daily.py
→ Throttled: max 1x per 60 detik per tanggal
→ Batch load 3 queries:
   - 10-day SM/BM history
   - 210-day OHLCV dari price_history
   - prev_close dari price_history
→ Hitung per ticker: SRI, RSM, RPR, VolxGap, ATR%, MA, RSI14, CM
→ classify_zenith_v3_1() → phase
→ get_action() → action
→ get_watch_flag() → watch
→ detect_trade_detail_gate() → trade_gate
→ get_phase_narrative() → narrative (panjang, Bahasa Indonesia)
→ UPDATE eod_summary (flow + 9 Wyckoff analytics fields)
        │
        ▼
compute_bsjp_for_date(conn, date_str)  ← analytics_bsjp.py
→ Batch load 210-day OHLCV untuk semua ticker di ticker_universe
→ Compute 19 BSJP indicators: MA5/13/34/50/200, ATR%, BB, streak, sideways, dll
→ UPDATE price_history (19 BSJP columns)
        │
        ▼
Web Dashboard membaca eod_summary (Telegram) + price_history (BSJP indicators)
→ /api/flow → list ticker dengan phase, action, narrative (dari eod_summary)
→ BSJP strategy uses price_history indicators
```

---

### 7.2 Jadwal Harian (Scheduled Passes)

```
12:10 WIB — Midday Pass
    └─ run_backfill(client, conn)
        ├─ Scan pesan hari ini dari 4 topik
        ├─ Save baru, rebuild summary, compute analytics
        ├─ enrich_daily_ohlcv() → update price_history (OHLCV + BSJP indicators)
        └─ compute_bsjp_for_date() → fill BSJP columns di price_history

15:30 WIB — First Backfill Pass
    └─ (sama seperti midday pass)

16:30 WIB — Second Analytics Pass
    └─ run_backfill(client, conn)
    └─ compute_bsjp_for_date()  ← recompute BSJP dengan data final hari ini
    └─ run_backtest(conn, days=0)  ← setelah second_pass selesai
```

---

### 7.3 Admin Operations

```
Fix All (request_fix_all):
    Step 1: rebuild_all_summaries()        ← agregasi semua raw data
    Step 2: backfill_price_history_ohlcv() ← fetch 210d OHLCV dari Yahoo
    Step 3: sync_eod_prices_from_history() ← copy price_history → eod_summary
    Step 4: compute_analytics_for_date()   ← loop semua tanggal, recompute (Wyckoff + flow)
    Step 5: compute_bsjp_for_date()        ← loop semua tanggal, compute BSJP indicators

Weekly Backfill (request_backfill):
    run_weekly_backfill(client, conn, days=N)
    → Scan histori N hari dari 4 topik
    → Stop per topik setelah 100 pesan lama berturut-turut
    → rebuild + price backfill + analytics + BSJP
```

---

## 8. Scraper Engine

### 8.1 `scraper_parser.py` — Pure Parser

Parser mendukung **3 format SM/BM** berbeda (A, B, C) berdasarkan struktur kolom:

| Format | Ciri | Contoh Kolom |
|---|---|---|
| A | Ada kolom `Freq` | Tx \| Ticker \| Price \| Gain \| Freq \| Val \| MF \| VolX |
| B | Standard | Tx \| Ticker \| Price \| Gain \| Val \| AvgMF \| MF \| VolX |
| C | Ticker di depan | Ticker \| Tx \| Price \| ... |

**Parsing Nilai:**
- `"1.5T"` → `1_500_000` (Juta)
- `"500rb"` → `0.5` (Juta)
- `"1.2M"` → `1_200` (Juta)
- `"50"` (plain) → `50` (Juta)

**Emoji Signal Mapping** (dari pesan):
- 💦 → SM aktif / kuat
- 🌟 → sinyal istimewa
- 💧 → SM tipis
- 🔥 → BM agresif
- 🥵 → distribusi kuat
- ⭐ → watch

**MF+ / MF- Format** berbeda: regex terpisah untuk mutual fund flow, mengekstrak `val`, `mf`, `mft`, `cm_delta`.

---

### 8.2 `scraper_saver.py` — DB Insert

```python
_register_tickers(conn, rows)
→ Upsert setiap ticker ke ticker_universe
→ ON CONFLICT (ticker) DO NOTHING
→ Dipanggil dari save_sm_bm_rows() dan save_mf_rows()
→ Memastikan setiap ticker baru auto-tracked oleh BSJP scanner

save_sm_bm_rows(conn, message_id, rows)
→ _register_tickers(conn, rows)  ← auto-register
→ INSERT INTO raw_messages ... ON CONFLICT (message_id, ticker) DO NOTHING
→ Return: jumlah rows baru yang tersimpan

save_mf_rows(conn, message_id, rows)
→ _register_tickers(conn, rows)  ← auto-register
→ INSERT INTO raw_mf_messages ... ON CONFLICT DO NOTHING
```

> Caller (scraper_daily.py) mengontrol commit — bukan saver.

---

### 8.3 `scraper_daily.py` — Daemon

**Retry on crash:**
```
Crash → delay 10s → 30s → 70s → 150s → 300s (max) → retry
```

**DB Reconnect Guard:**
```python
def _ensure_conn(conn):
    conn.cursor().execute("SELECT 1")  # health check
    if gagal → close → reconnect
```

**Analytics Throttle:**
```python
ANALYTICS_THROTTLE_SECS = 60
# Recompute analytics max 1x per 60 detik per tanggal
# Mencegah recompute berulang saat burst pesan masuk bersamaan
```

**Request Queue** (dikirim dari Admin panel):
- `_backfill_request` — trigger manual backfill N hari
- `_rebuild_request` — trigger rebuild semua summary
- `_recompute_request` — trigger recompute semua analytics
- `_backtest_request` — trigger nightly backtest
- `fix_all_request` — jalankan semua step dari nol

---

## 9. Algoritma Inti

### 9.1 `classify_zenith_v3_1()` — Phase Classification

**Input:**
| Parameter | Keterangan |
|---|---|
| `sri` | SM Relative Intensity = `sm_val / avg(sm_val, 10 hari)` |
| `rsm` | SM % dari total flow = `sm_val / (sm_val + bm_val) * 100` |
| `rpr` | Sell Pressure Ratio = `tx_bm / (tx_sm + tx_bm)` |
| `pchg` | Price change % hari ini (dari price_history) |
| `bm_val` | Nilai BM hari ini (Juta) |
| `bm_sma10` | Rata-rata BM 10 hari |
| `atr_pct` | ATR 14 hari sebagai % harga (default 2.5 jika kosong) |

**Threshold ATR-based:**
```
th_up   = max(atr * 0.8, 1.0)   → naik signifikan (min 1%)
th_down = max(atr * 0.4, 0.5)   → turun signifikan (min 0.5%)
th_flat = atr * 0.5              → zona flat
```

**BM Activity Gate:**
```
bm_sma10 == 0 → gate open (ticker baru/tidak aktif)
bm_gate = bm_val > bm_sma10 * 0.5  → BM hari ini ≥ 50% rata-rata
```

**Urutan Klasifikasi (prioritas atas ke bawah):**

| Fase | Kondisi |
|---|---|
| **SOS** | `pchg > th_up` AND (`(rsm>65 AND sri>3.0)` OR `(rsm>60 AND sri>4.0)`) |
| **UPTHRUST** | `pchg > th_up` AND `rsm<40` AND `rpr>0.6` |
| **ABSORB** | `sri>2.0` AND `rsm>65` AND `pchg > -th_down` AND `abs(pchg) < th_flat` |
| **SPRING** | `pchg < -th_down` AND `rsm>60` AND `sri>1.5` |
| **DISTRI** | `rsm<40` AND `pchg < -(th_down*0.5)` AND `rpr>0.4` AND `bm_gate` |
| **ACCUM** | `rsm>60` AND `sri>1.0` |
| **DISTRI (fallback)** | `rsm<35` AND `rpr>0.5` AND `bm_gate` |
| **NEUTRAL** | (default jika tidak ada yang cocok) |

> Jika `pchg is None` → langsung return `"NEUTRAL"`

---

### 9.2 `get_action()` — Derive BUY/SELL/HOLD

```
SELL_PHASES = (UPTHRUST, DISTRI) → langsung SELL
BUY_PHASES  = (SOS, SPRING, ABSORB, ACCUM)
Lainnya     → HOLD

Filter Quality SM:
  sri > 0 AND sri < 1.4 → HOLD (intensitas SM kurang)
  rsm > 0 AND rsm < 70% → HOLD (SM tidak dominan)

Gate A (Supply):
  bm_sma10 > 0 AND bm_val > bm_sma10 * 1.1 → HOLD
  (BM hari ini ≥ 110% rata-rata normal = tekanan jual signifikan)

Gate B (ARB Safety):
  watch_flag == "ARB_SPRING" → HOLD (SPRING ekstrim, risiko tinggi)

Gate C (Anti-Pucuk):
  SOS:    pchg ≥ max(atr * 2.5, 6.0%) → HOLD
  Others: pchg ≥ max(atr * 2.75, 5.5%) → HOLD

Jika lolos semua → BUY
```

---

### 9.3 `get_watch_flag()` — ARB Warning

```python
if phase == "SPRING" AND pchg < -(atr * 1.5):
    return "ARB_SPRING"
return None
```

Fase tetap SPRING, tapi frontend tampilkan ⚠️ WATCH.

---

### 9.4 `detect_trade_detail_gate()` — Gate Active Check

```
Gate A: bm_val > bm_sma10 * 1.1  → "Gate A"
Gate B: phase == "SPRING" AND pchg < -(atr*1.5)  → "Gate B"
Gate C: action == "BUY" AND pchg ≥ max(atr*3.0, 6%)  → "Gate C"
None jika tidak ada
```

---

### 9.5 `get_ma_structure()` — 8 Tipe Struktur MA

**Input:** price, ma5, ma13, ma34, ma200

**Logika:**
```
gap = (max(ma5,ma13,ma34) - min(ma5,ma13,ma34)) / min * 100

gap < 3%:
  price > ma200 → "Cluster on Macro Uptrend"
  price ≤ ma200 → "Cluster on Macro Downtrend"

gap ≥ 3%, aligned_up (ma5>ma13>ma34):
  price > ma200 → "Strong Uptrend"
  price ≤ ma200 → "Transitional Uptrend"

gap ≥ 3%, aligned_down (ma5<ma13<ma34):
  price > ma200 → "Transitional Correction"
  price ≤ ma200 → "Strong Downtrend"

gap ≥ 3%, messy (crossed):
  price > ma200 → "Bullish Messy"
  price ≤ ma200 → "Bearish Messy"
```

---

### 9.6 `get_phase_narrative()` — 56 Narasi Trading

56 kombinasi: **7 phase × 8 MA structure**. Setiap kombinasi punya narasi panjang dalam Bahasa Indonesia dengan saran trading spesifik.

Jika ada Gate aktif, narasi Gate **override** narasi fase:
- **Gate A**: "Active Supply — Terdeteksi tekanan jual dari Bad Money..."
- **Gate B**: "Extreme Panic / Risiko ARB — Terdeteksi SPRING namun penurunan >1.5× ATR..."
- **Gate C**: "Profit Taking Zone — Signal BUY valid tapi harga sudah naik ≥3× ATR..."

---

### 9.7 `indicators.py` — Technical Indicators

```python
compute_ma(closes, n)     → simple moving average n hari
compute_rsi14(closes)     → Wilder RSI-14 (butuh min 15 candle)
compute_cm_streak(closes, ma5)
    → +N: harga di atas ma5 selama N hari
    → -N: harga di bawah ma5 selama N hari
```

---

## 10. Analytics Pipeline

Dibagi jadi 2 modul terpisah:
1. **analytics_daily.py** — Wyckoff + flow analysis (untuk Telegram tickers)
2. **analytics_bsjp.py** — Price-only BSJP indicators (untuk all tickers di ticker_universe)

---

### 10.1 `analytics_daily.py` — `compute_analytics_for_date(conn, date_str)`

**Tujuan:** Hitung Wyckoff phase dan flow metrics untuk tickers dengan SM/BM Telegram.

**Step 1 — Batch Load (3 queries saja untuk semua ticker):**
```sql
-- Query 1: 10-day SM/BM history dari eod_summary
SELECT ticker, sm_val, bm_val, tx_count, tx_sm, tx_bm, price_close, volx_gap
FROM eod_summary
WHERE ticker = ANY(%s) AND date <= %s
ORDER BY ticker, date DESC
→ ambil max 10 baris per ticker

-- Query 2: 210-day OHLCV dari price_history
SELECT ticker, high, low, close
FROM price_history
WHERE ticker = ANY(%s) AND date <= %s
ORDER BY ticker, date DESC
→ ambil max 210 baris per ticker

-- Query 3: prev_close dari price_history
SELECT DISTINCT ON (ticker) ticker, close
FROM price_history
WHERE ticker = ANY(%s) AND date < %s
ORDER BY ticker, date DESC
```

**Step 2 — Compute Per Ticker (Python, no DB):**
```
price_change_pct = (price_close - prev_close) / prev_close * 100
rsm = sm_val / (sm_val + abs(bm_val)) * 100
sri = sm_val / avg(sm_val_10_days)
mes = abs(bm_val) / (sm_val + abs(bm_val)) * 100
rpr = tx_bm / tx_total
volx_gap = (price_close - vwap_sm) / vwap_sm * 100
sm_sma10 = sum(sm_vals[-10:]) / n
bm_sma10 = sum(abs(bm_vals[-10:])) / n
atr_pct  = 14-period ATR% dari HLC (True Range / prev_close * 100)
ma5, ma13, ma34, ma200 = simple moving averages
rsi14    = Wilder RSI-14
cm_streak = consecutive days above/below ma5
```

**Step 3 — Classify Wyckoff & Write:**
```
phase, action, watch → algo_wyckoff
trade_gate → detect_trade_detail_gate
ma_structure → get_ma_structure
narrative → get_phase_narrative

UPDATE eod_summary SET
    sri, mes, volx_gap, rpr, atr_pct,
    price_close, price_change_pct,
    sm_sma10, bm_sma10,
    ma5, ma13, ma34, ma200,
    rsi14, cm_streak, ma_structure,
    phase, action, watch, trade_gate, narrative,
    ma50, bb_upper, bb_mid, bb_lower, bb_width, is_sideways, close_pos, prev_high_break, mf_ratio
WHERE date = %s AND ticker = %s
```

**Note:** Ma50, BB, sideways, close_pos, prev_high_break, mf_ratio juga dihitung untuk Wyckoff context.

---

### 10.2 `analytics_bsjp.py` — `compute_bsjp_for_date(conn, date_str)`

**Tujuan:** Hitung BSJP indicators (price-only) untuk semua ticker di ticker_universe.

**Fitur:**
- Batch-load 210-day OHLCV dari price_history untuk semua ticker (is_active=TRUE)
- Compute 19 BSJP indicators per ticker
- Per-ticker exception handling (satu failure tidak stop batch)
- Write ke price_history (tidak ke eod_summary)

**Compute (19 columns):**
```
MA: ma5, ma13, ma34, ma50, ma200 = simple moving averages

ATR: atr_pct = 14-period average True Range sebagai % harga

Bollinger Bands (20 ± 2σ):
  bb_upper = sma20 + 2*stdev
  bb_mid   = sma20
  bb_lower = sma20 - 2*stdev
  bb_width = upper - lower

Price Position:
  close_pos = (close - low) / (high - low)  ∈ [0,1]
  prev_high_break = bool(today.close > yesterday.high)

Momentum:
  ma5_price_streak = +N (N hari di atas MA5) atau -N (di bawah)
  is_sideways = bool(bb_width < threshold AND ma5 ≈ ma34)

Daily Value:
  daily_value = close × volume

Previous Day Flags:
  prev_close_below_ma5 = bool(yesterday.close < MA5)
  prev_close_below_bb_lower = bool(yesterday.close < BB lower)

Near Level Metrics:
  days_since_near_ma50 = hari terakhir close ≈ MA50 (±2%)
  days_since_near_bb_mid = hari terakhir close ≈ BB mid (±2%)
```

**Database Write:**
```
UPDATE price_history SET
    ma5, ma13, ma34, ma50, ma200, atr_pct,
    bb_upper, bb_mid, bb_lower, bb_width,
    close_pos, prev_high_break,
    ma5_price_streak, is_sideways,
    daily_value,
    prev_close_below_ma5, prev_close_below_bb_lower,
    days_since_near_ma50, days_since_near_bb_mid
WHERE date = %s AND ticker = %s
```

**Data Convention:**
- `ph` (price_history) list selalu dalam format **oldest-first** (ph[0] = 210 hari lalu, ph[-1] = hari ini)
- Semua indicator function expect oldest-first lists
- Reverse setelah query (query returns newest-first, manual reverse)

---

## 11. HTTP Routes & API

### 11.1 `routes_main.py`

| Method | Path | Auth | Keterangan |
|---|---|---|---|
| GET | `/` | No | Login page (redirect ke /hub jika sudah login) |
| POST | `/` | No | Proses login |
| GET | `/logout` | Yes | Clear session |
| GET | `/hub` | Yes | Dashboard utama |
| GET | `/chart` | Yes | Halaman chart |
| GET | `/flow` | Yes | Halaman flow |
| GET | `/health` | No | Status DB + scraper (JSON) |
| GET | `/api/last-date` | Yes | Tanggal terbaru di eod_summary |
| GET | `/api/ihsg` | Yes | Harga + gain% JKSE dari Yahoo |

---

### 11.2 `routes_flow.py`

#### `GET /api/flow`
**Query params:** `date_from`, `date_to`, `kompas100` (filter Kompas100), `sector`

**Logic:**
1. Query `eod_summary` untuk range tanggal → agregasi SM/BM per ticker
2. Load analytics_map (cache 5 mnt hari ini, 30 mnt historis)
3. Hitung gain: single-day → dari `price_change_pct`; multi-day → dari `price_history`
4. Klasifikasi phase/action/watch real-time dari analytics_map
5. Sort by `clean_money` (SM - BM) desc

**Response per ticker:**
```json
{
  "ticker": "BBRI",
  "sm_val": 1234.56,
  "bm_val": 567.89,
  "clean_money": 666.67,
  "rsm": 68.5,
  "rpr": 0.32,
  "gain_pct": 2.1,
  "price": 4500,
  "phase": "SOS",
  "action": "BUY",
  "watch": null,
  "sri": 2.4,
  "mes": 31.5,
  "volx_gap": 1.2,
  "atr_pct": 1.8,
  "ma5": 4420, "ma13": 4300, "ma34": 4100, "ma200": 3800,
  "rsi14": 62.3,
  "cm_streak": 4,
  "ma_structure": "Strong Uptrend",
  "narrative": "Strongest Momentum — ...",
  "bm_sma10": 500.0,
  ...
}
```

---

#### `GET /api/transactions`
**Query params:** `ticker`, `date_from`, `date_to`

Membaca dari `raw_messages`, split ke `sm` (channel='smart') dan `bm` (channel='bad'):
```json
{
  "ticker": "BBRI",
  "sm": [{"date": "15-05-2026", "time": "09.30", "price": 4500, "gain_pct": 1.2, "mf": "+150rb", "signal": "💦"}],
  "bm": [...],
  "sm_count": 5,
  "bm_count": 3
}
```

---

#### `GET /api/overlay`
**Query params:** `ticker`, `tf` (5m, 15m, 30m, 1h, 1d)

Membaca `raw_messages`, bucket by timeframe, return cumulative SM/BM/CM:
```json
{
  "points": [
    {"time": 1715734200, "sm": 50.2, "bm": 30.1, "cm": 20.1, "cum_sm": 50.2, "cum_bm": 30.1, "cum_cm": 20.1}
  ]
}
```

---

#### `GET /api/ohlcv`
**Query params:** `ticker`, `tf`

Fetch OHLCV dari Yahoo Finance secara langsung (tidak dari DB).

---

### 11.3 `routes_sector.py`

#### `GET /api/sector`
**Query params:** `date_from`, `date_to`

Agregasi SM/BM/MF per sektor berdasarkan mapping `SECTORS` di config.py. Response per sektor dengan total SM, BM, MF+, MF-, clean_money, gain%.

---

### 11.4 `routes_backtest.py`

#### `GET /api/backtest`
**Query params:** `run=1` (trigger), `status=1` (poll status), `days=30`, `date_from`, `date_to`

Jika hasil tersedia di `backtest_cache` → return langsung.
Jika trigger `run=1` → delegate ke scraper daemon queue.

**Response:**
```json
{
  "status": "done",
  "leaderboard": [
    {"phase": "SOS", "win_rate": 65.2, "avg_profit": 3.1, "profit_factor": 2.1, "count": 87}
  ],
  "overall": {"total": 350, "wins": 228, "win_rate": 65.1, "profit_factor": 1.9}
}
```

---

#### `GET /api/ticker-fitness`
**Query params:** `ticker`

Return statistik backtest per ticker: win rate per fase, profit factor, trade history.

---

### 11.5 `routes_journal.py`

| Method | Path | Keterangan |
|---|---|---|
| GET | `/api/journal` | Semua trades (open + closed) |
| POST | `/api/journal/open` | Buka posisi (ticker, entry_phase, date, price) |
| POST | `/api/journal/close` | Tutup semua posisi ticker (exit_date, sell_price, reason) |
| GET | `/api/journal/trade-detail` | Detail trade + data analytics dari eod_summary |

---

### 11.6 `routes_admin.py`

| Method | Path | Keterangan |
|---|---|---|
| GET | `/admin/scraper-status` | First/latest date per channel + total rows |
| GET | `/admin/scraper-weekly?days=N` | Trigger backfill N hari |
| GET | `/admin/rebuild-summary` | Rebuild eod_summary dari raw_messages |
| GET | `/admin/recompute-analytics` | Recompute analytics semua tanggal |
| GET | `/admin/backfill-prices` | Backfill harga dari Yahoo + recompute |
| GET | `/admin/backfill-200d` | Backfill OHLCV 210 hari ke price_history |
| GET | `/admin/trigger-backtest` | Jalankan backtest via daemon queue |
| POST | `/admin/upload-session` | Upload file session Telegram (binary) |
| GET | `/admin/users` | Daftar user |
| POST | `/admin/users/add` | Tambah user (username, password, role) |
| POST | `/admin/users/delete/<id>` | Hapus user |

---

## 12. Layer Autentikasi

```python
# core/auth.py

login(username, password)
→ SELECT dari users WHERE username = ?
→ bcrypt.checkpw(password, password_hash)
→ Set session: {"user_id": id, "username": ..., "role": ...}

register(username, password, role)
→ bcrypt.hashpw(password)
→ INSERT INTO users

is_authed()     → bool: session["user_id"] exists
get_role()      → "admin" atau "guest"
is_admin()      → role == "admin"

# Decorators
@require_auth   → redirect ke / jika belum login
@require_admin  → return 403 jika bukan admin
```

---

## 13. Price Fetching

### `data/price_fetch.py`

**Sumber:** Yahoo Finance (temporary — paid API belum ada).

**Fitur utama:**
- Fetch untuk **semua ticker di ticker_universe** (tidak terbatas Telegram-active)
- OHLCV ditulis ke price_history (digunakan BSJP + Wyckoff context)
- Price close juga copy ke eod_summary (untuk tickers dengan SM/BM)

**Fungsi utama:**

```python
enrich_daily_ohlcv(conn, date_str)
→ Fetch OHLCV untuk semua ticker di ticker_universe (is_active=TRUE)
→ Fallback: jika ticker_universe kosong, ambil dari eod_summary[date_str]
→ Write ke price_history
→ Update eod_summary.price_close HANYA untuk tickers yang ada di eod_summary[date_str]
  (Telegram-only tickers)

backfill_price_history_ohlcv(conn, date_from=None, date_to=None)
→ Fetch 210 hari OHLCV untuk semua ticker di ticker_universe
→ Fallback: jika ticker_universe kosong, ambil dari eod_summary
→ Paralel dengan semaphore max 10 concurrent
→ Write ke price_history (yang akan digunakan BSJP scanner)

sync_eod_prices_from_history(conn)
→ Copy price_history.close → eod_summary.price_close
→ Tanpa Yahoo call (gunakan data yang sudah ada)

fetch_ohlcv(ticker, tf, interval_map)
→ Fetch untuk chart (5m, 15m, 30m, 1h, 1d)
→ Return {candles: [...], meta: {...}}
```

**Arsitektur:**
- **ticker_universe** adalah master list semua saham yang ditrack
- Setiap kali SM/BM/MF+/MF- diterima, ticker auto-upsert ke ticker_universe
- Daily: enrich_daily_ohlcv() fetch untuk **semua ticker di ticker_universe**
- Karena itu BSJP bisa compute indicator untuk semua saham, tidak hanya yang punya Telegram data

**Rate limiting:**
- `asyncio.Semaphore(10)` → max 10 request bersamaan ke Yahoo
- Cache gain per ticker: 5 menit (`GAIN_CACHE_TTL`)

**Format date:** Konversi DD-MM-YYYY ↔ YYYY-MM-DD sesuai kebutuhan.

---

### 13.1 Intraday 15m Backfill (untuk BSJP Backtest)

**Fungsi tambahan:**

```python
backfill_intraday_15m(conn, date_from: str, date_to: str)
→ Fetch 15m candles dari Yahoo Finance untuk ALL tickers di ticker_universe
→ Store ke price_history_15m (datetime WIB, OHLCV)
→ Parallel max 8 concurrent workers
→ User-triggered via admin panel dengan date range inputs
```

**Use case:**
- BSJP backtest perlu tahu exact timing SL/TP hit selama session
- Daily OHLC saja tidak cukup — perlu sequence intra-day
- Example: entry signal di sore → pagi next day check first 15m candles:
  - Apakah kena SL (low < entry - atr*1.5)?
  - Atau hit TP lebih dulu?

**Constraint:**
- Yahoo Finance 15m data: max ~60 hari kebelakang
- Admin trigger kecil-kecilan (2–3 hari per run) untuk avoid bottleneck
- Accumulate history gradually

**Admin Panel:**
1. **Manual Range**: `/admin/backfill-intraday?date_from=DD-MM-YYYY&date_to=DD-MM-YYYY`
   - Fetch single date range manual
   - 4 concurrent workers, ThreadPoolExecutor
   
2. **Fetch All (Otomatis)**: `/admin/backfill-intraday-all`
   - Loop semua tanggal IDX dalam 60 hari kalender kebelakang
   - 180 detik (3 menit) delay antar tanggal untuk avoid rate limit
   - 4 concurrent workers per tanggal (reduced dari 8 untuk safety)
   - Estimasi: ~2 jam untuk 42 hari bursa
   - Progress polling: status real-time, "Hari ke-5/42 — 2026-03-25 | 3.247 rows"
   - Auto-resume jika halaman di-refresh saat job berjalan

**Rate Limit Mitigation:**
- Yahoo Finance: ~2000 req/jam limit (~1 req/sec sustained)
- Strategy:
  - Max 4 concurrent workers (vs 8) → reduce burst load
  - 180s delay between dates → let Yahoo "cool down"
  - Each date fetch ~3-4 min, delay 3 min → ~6-7 min per tanggal
  - Total untuk 42 hari: ~42 × 6-7 min = ~4-5 jam (diestimasi ~2 jam worst-case)
- Jika masih kena limit: reduce `max_workers` ke 2-3, atau extend delay ke 5 menit

---

## 14. Backtest Engine

### `algo/algo_backtest.py` — `run_backtest(conn, days=30, ...)`

**Fitur:**
- Multi-entry: bisa hold beberapa posisi terbuka pada ticker yang sama
- Dynamic action: tidak pakai kolom `action` di DB, tapi re-classify setiap hari
- ATR-based stop loss
- SELL menutup semua posisi terbuka untuk ticker tersebut

**Algorithm:**
```
1. Query eod_summary untuk range tanggal, sort ascending
2. Per hari, per ticker:
   - Re-classify action dari data hari itu (bukan dari DB)
   - Jika action == BUY → buka posisi baru
   - Setiap hari: cek stop loss (pchg < -ATR*1.5)
   - Jika action == SELL atau stop loss → close semua posisi

3. Metrics per fase (SOS, SPRING, ABSORB, ACCUM, UPTHRUST, DISTRI):
   - Win rate, Avg profit, Loss rate, Avg loss
   - Profit factor = total profit / total loss
   - Avg hold duration

4. Cache hasil ke backtest_cache
```

---

## 15. Trade Journal

### `data/journal.py`

```python
open_position(conn, ticker, entry_phase, entry_date, buy_price)
→ INSERT INTO trade_journal (status='open')

close_position(conn, ticker, exit_date, sell_price, exit_reason)
→ UPDATE semua posisi open untuk ticker
→ Hitung gain_pct = (sell - buy) / buy * 100
→ Hitung hold_days
→ SET status='closed'

check_stop_loss(conn, date_str, threshold_pct=-10.0)
→ Cari posisi open yang price_change_pct ≤ threshold
→ Return list ticker yang kena SL

get_trade_detail(conn, ticker, date_str)
→ JOIN trade_journal + eod_summary
→ Return detail posisi + kondisi market hari itu
```

---

## 16. Caching Strategy

| Cache | Lokasi | TTL | Scope |
|---|---|---|---|
| `TTLCache` (analytics_map) | `routes_flow.py` | 5 mnt (today) / 30 mnt (hist) | Per tanggal |
| Gain cache | `price_fetch.py` | 5 mnt | Per ticker+range |
| CACHE_TTL | `config.py` | 24 jam (Railway) / 5 mnt (lokal) | Server-wide |
| `backtest_cache` | PostgreSQL | Tidak expire | Per run_id |

**Thread safety:** `TTLCache` menggunakan `threading.Lock()` untuk semua operasi.

---

## 17. Startup & Inisialisasi

### `startup.py` — `run_startup(app)`

Dipanggil sekali saat Flask start:

```
1. _init_schema()
   → db_schema.ensure_schema()
   → CREATE TABLE IF NOT EXISTS semua tabel

2. _seed_admin()
   → Jika env ADMIN_INIT_PASSWORD ada dan user 'admin' belum exists
   → INSERT user admin dengan password dari env

3. _start_scraper()
   → Cek file lock: /tmp/zenith_scraper.lock
   → Jika sudah running (lock exists) → skip
   → Buat daemon thread untuk asyncio.run(scraper_main())

4. _start_backtest()
   → Thread background: run_backtest(conn, days=30)
```

### `app.py` — Flask Factory

```python
app = Flask(__name__)
app.secret_key = FLASK_SECRET
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = SESSION_DIR

# Register blueprints
app.register_blueprint(bp_main)
app.register_blueprint(bp_flow)
app.register_blueprint(bp_sector)
app.register_blueprint(bp_backtest)
app.register_blueprint(bp_journal)
app.register_blueprint(bp_admin)

run_startup(app)
```

---

## 18. Environment Variables

| Variable | Required | Default | Keterangan |
|---|---|---|---|
| `DATABASE_URL` | **Yes** | `postgresql://...localhost.../zenith` | PostgreSQL connection string |
| `FLASK_SECRET` | **Yes** | `zenith-secret-key-dev` | Session signing key |
| `TG_API_ID` | **Yes** | `0` | Telegram API ID |
| `TG_API_HASH` | **Yes** | `""` | Telegram API hash |
| `TG_SESSION_PATH` | **Yes** | `/data/session_joker_2` | Path file session Telethon |
| `ADMIN_INIT_PASSWORD` | No | — | Password admin awal (sekali pakai saat seed) |
| `SCRAPER_ENABLED` | No | `"1"` | Set `"0"` untuk disable scraper |
| `SESSION_DIR` | No | `/tmp/zenith_2_0_sessions/` | Direktori session Flask |
| `DATASECTORS_API_KEY` | No | `""` | Belum aktif — untuk integrasi DataSectors |
| `LOG_LEVEL` | No | `WARNING` (Railway) / `DEBUG` (lokal) | Level logging |
| `RAILWAY_ENVIRONMENT` | Auto | — | Diset Railway otomatis (deteksi environment) |

---

## 19. Dependency Graph

```
app.py
  ├── startup.py
  │     ├── core/db_schema.py
  │     ├── core/auth.py
  │     ├── scraper/scraper_daily.py
  │     └── algo/algo_backtest.py
  │
  ├── routes/routes_main.py
  │     ├── core/auth.py
  │     ├── core/db.py
  │     └── data/price_fetch.py
  │
  ├── routes/routes_flow.py
  │     ├── core/auth.py, db.py, cache.py, utils.py
  │     ├── data/price_fetch.py
  │     └── algo/algo_wyckoff.py
  │
  ├── routes/routes_sector.py
  │     ├── core/auth.py, db.py
  │     └── config.py (SECTORS)
  │
  ├── routes/routes_backtest.py
  │     ├── core/auth.py, db.py
  │     └── algo/algo_backtest.py
  │
  ├── routes/routes_journal.py
  │     ├── core/auth.py, db.py
  │     └── data/journal.py
  │
  └── routes/routes_admin.py
        ├── core/auth.py, db.py
        ├── algo/summary_rebuild.py
        ├── algo/analytics_daily.py
        ├── algo/analytics_bsjp.py
        ├── algo/algo_backtest.py
        └── data/price_fetch.py (enrich_daily_ohlcv, backfill_price_history_ohlcv, backfill_intraday_15m)

scraper/scraper_daily.py
  ├── scraper/scraper_parser.py   (pure — zero DB)
  ├── scraper/scraper_saver.py
  ├── scraper/scraper_weekly.py
  ├── algo/summary_rebuild.py
  ├── algo/analytics_daily.py
  ├── algo/analytics_bsjp.py
  ├── algo/algo_backtest.py
  └── data/price_fetch.py

algo/analytics_daily.py
  ├── algo/indicators.py          (pure)
  ├── algo/algo_wyckoff.py        (pure)
  └── core/db.py

algo/analytics_bsjp.py
  ├── algo/indicators.py          (pure)
  └── core/db.py

algo/algo_backtest.py
  ├── algo/algo_wyckoff.py        (pure)
  └── core/db.py
```

---

## 20. Aturan Desain (Design Rules)

> Setiap file punya aturan eksplisit di docstring-nya. Ini penting untuk menjaga konsistensi.

| Modul | Aturan |
|---|---|
| `config.py` | Tidak ada hardcode di file lain — selalu import dari sini |
| `core/db.py` | Zero business logic — koneksi dan query helper saja |
| `core/db_schema.py` | Semua CREATE TABLE hanya di sini — plus ticker_universe seeding |
| `algo/algo_wyckoff.py` | Pure functions only — zero DB, zero HTTP |
| `algo/indicators.py` | Pure functions only — oldest-first lists convention |
| `scraper/scraper_parser.py` | Pure functions only — zero DB, zero side effects |
| `routes/*.py` | Routing + input validation only — no business logic, no direct API calls |
| `algo/analytics_daily.py` | No HTTP calls. Wyckoff + flow analysis (Telegram tickers hanya). Per-ticker exception handling. |
| `algo/analytics_bsjp.py` | No HTTP calls. Pure price-based BSJP indicators (all tickers). Per-ticker exception handling. No Telegram data. |
| `algo/summary_rebuild.py` | Hanya agregasi flow — analytics fields disentuh `analytics_daily.py` atau `analytics_bsjp.py` |
| `scraper/scraper_saver.py` | Auto-register tickers ke `ticker_universe` via `_register_tickers()` |
| `data/price_fetch.py` | Fetch dari `ticker_universe` (all active), fallback ke `eod_summary` jika universe kosong. Intraday 15m via `backfill_intraday_15m()` user-triggered. |

**Pola utama:**
- Separation of concerns ketat (parsing ≠ saving ≠ computing ≠ routing)
- Caller mengontrol commit (lower-level functions tidak commit sendiri)
- Auto-reconnect pada DB loss (Railway bisa restart PostgreSQL)
- Per-row exception handling (satu ticker gagal tidak stop batch)
- Throttle analytics recompute 60s per tanggal (mencegah burst overwrite)
- **Two-tier analytics:**
  - `analytics_daily.py`: Wyckoff + flow (untuk Telegram tickers)
  - `analytics_bsjp.py`: Price-only indicators (untuk all tickers di ticker_universe)
- **ticker_universe** sebagai master list semua tickers (auto-register saat SM/BM/MF masuk)

---

## 21. Fitur Belum Aktif (Placeholder)

### DataSectors Integration (Tier 1–4)
Semua tabel dan file sudah dibuat, tapi **tidak ada API call aktif** karena `DATASECTORS_API_KEY` belum ada.

| File | Tujuan | Status |
|---|---|---|
| `data/ds_smartmoney.py` | Institutional flow signal (ACCUMULATION/DISTRIBUTION/NEUTRAL) — hanya badge, tidak mempengaruhi signal utama | **Placeholder** |
| `data/ds_fundamental.py` | Corporate events: dividen, split, rights issue — flag 30-hari ke depan | **Placeholder** |
| `data/price_datasectors.py` | Ganti Yahoo Finance sebagai price source setelah 2 minggu stabilitas | **Placeholder** |
| `ohlcv_cache` (DB) | Cache harga dari DataSectors | **Created, unused** |
| `corporate_events` (DB) | Cache event korporasi | **Created, unused** |
| `inst_flow_cache` (DB) | Cache institutional flow signal | **Created, unused** |

---

*Dokumen ini diupdate per 16 Mei 2026:*

**BSJP Refactoring (15 Mei):**
- Ditambah: `ticker_universe` table untuk master list semua saham
- Ditambah: `analytics_bsjp.py` untuk BSJP indicators (price-only, all tickers)
- Dipisah: analytics menjadi 2 tier (Wyckoff + BSJP)
- Diupdate: price_fetch untuk fetch dari ticker_universe (bukan hanya eod_summary)
- Diupdate: scraper_saver untuk auto-register tickers
- Diupdate: 19 kolom BSJP dipindah ke price_history (bukan eod_summary)

**Intraday 15m (16 Mei):**
- Ditambah: `price_history_15m` table (datetime WIB PK)
- Ditambah: `backfill_intraday_15m()` untuk fetch range spesifik (user-triggered)
- Ditambah: `backfill_intraday_all()` untuk auto-loop 60 hari kalender, 180s delay/hari
- Ditambah: `/admin/backfill-intraday` (manual range) dan `/admin/backfill-intraday-all` (fetch all)
- Ditambah: BSJP Intraday 15m card di admin UI dengan "Fetch Range" + "Fetch All" buttons
- Use case: BSJP backtest perlu exact timing SL/TP hit intra-day (daily OHLC tidak cukup)

**Rate Limit Mitigation (16 Mei revisi):**
- Yahoo block 805 tickers sekaligus dengan 8 workers (burst ~800 req/menit)
- Solusi: `max_workers` 8 → 4, delay 30s → 180s (3 menit) antar tanggal
- Estimasi: ~2 jam untuk 42 hari bursa (vs ~21 menit sebelumnya, tapi sustainable)
