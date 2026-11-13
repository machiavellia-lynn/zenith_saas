# Zenith SaaS – IDX Smart Money Platform

## 1. Project Summary
**Zenith SaaS** is a Flask‑based web service that aggregates Indonesian stock‑market data, parses Telegram alerts, computes technical indicators, and serves analytics via a REST API.  It is designed for low‑latency, high‑throughput use‑cases such as portfolio monitoring, back‑testing, and automated trading signal generation.

---

## 2. Architecture Overview
```
client   →  Flask (HTTP)  →  core (db, utils)  →  PostgreSQL
               │                │
               │                └─► price cache thread (price_cache.py)
               │
               └─► scraper daemon (scraper_daily.py) – parses Telegram messages → raw tables
```
Key services:
- **Flask API** (`routes/`) – request handling, auth (`api_auth.py`).
- **Telegram Scraper** (`scraper/`) – runs as a background thread, stores parsed SM/BM/MF rows.
- **Analytics Engine** (`algo/analytics_*.py`) – reads `eod_summary`, computes indicators (MA, RSI, BSJP, etc.) and writes back.
- **Price Cache** (`data/price_cache.py`) – live 30‑second refresh of IHSG index and ~800 IDX tickers.
- **Back‑fill Jobs** – weekly DataSectors corrections, intraday 15‑min candles, historical back‑fills.

---

## 3. Directory Structure
```
zenith_saas/
├─ app.py                 # Flask entry point
├─ config.py              # Environment variables & constants
├─ Procfile               # Railway / Heroku process definition
├─ requirements.txt       # Python dependencies
│
├─ core/                  # Low‑level utilities
│   ├─ db.py              # Connection pool, transaction helpers
│   ├─ cache.py           # In‑memory TTL cache implementation
│   ├─ utils.py           # Pure helper functions (date parsing, formatting)
│   └─ api_auth.py        # API key validation middleware
│
├─ algo/                  # Business logic / analytics
│   ├─ indicators.py      # Technical indicator pure functions
│   ├─ analytics_daily.py # Orchestrates daily analytics
│   ├─ analytics_bsjp.py # BSJP indicator computation
│   ├─ analytics_*.py    # Additional algorithm modules
│   └─ summary_rebuild.py# Aggregates raw telegram data → eod_summary
│
├─ scraper/               # Telegram scraper daemon
│   ├─ scraper_daily.py   # Scheduler & daily back‑fill workflow
│   ├─ scraper_parser.py  # Pure regex parsers for SM/BM/MF messages
│   └─ scraper_saver.py   # DB insertion layer for parsed rows
│
├─ data/                  # External data‑fetching modules
│   ├─ price_fetch.py      # Yahoo Finance wrapper (gains, OHLCV, etc.)
│   └─ price_cache.py      # Live price‑cache background thread
│
├─ routes/                # Flask Blueprints (API, admin, back‑test, etc.)
│   ├─ routes_api.py
│   ├─ routes_admin.py
│   ├─ routes_backtest.py
│   └─ routes_*.py
│
├─ scripts/               # Operational scripts (setup, migrations)
│   └─ init_db.sql        # Schema creation script
│
└─ docs/ (optional)       # Architecture diagrams, design docs
```

---

## 4. Core Database Schema (high‑level)
| Table | Primary Purpose |
|-------|-----------------|
| `users` | Auth & role management |
| `ticker_universe` | Master list of IDX tickers (active flag) |
| `raw_messages` | Parsed SM/BM telegram alerts |
| `raw_mf_messages` | Parsed MF+ / MF‑ telegram alerts |
| `eod_summary` | Daily aggregated flow + analytics fields (SM/BM volumes, indicators, phase, action) |
| `price_history` | Daily OHLCV per ticker (used for indicators) |
| `price_history_15m` | Intraday 15‑min candles |
| `api_keys` | Multi‑key API authentication |
| `backtest_cache`, `ohlcv_cache`, … | Misc caches for performance |

All tables use `date` in `DD‑MM‑YYYY` format for user‑facing fields and `YYYY‑MM‑DD` for internal storage where appropriate.

---

## 5. Configuration & Environment
`config.py` loads values from environment variables (or `.env`).  Required keys:
```text
DATABASE_URL               # PostgreSQL connection string
WIB                        # tzinfo for Jakarta
YF_HEADERS                 # HTTP headers for Yahoo Finance
DS_API_KEY, DS_BASE_URL    # DataSectors API (optional weekly correction)
GAIN_CACHE_TTL             # Seconds for gains cache (default 300)
```
Sensitive values must never be committed; they are stored in the server’s secret store.

---

## 6. Dependency Management
- Python **3.12**
- Frameworks: `Flask`, `psycopg2‑binary`, `requests`
- Concurrency: `threading`, `concurrent.futures`
- Utilities: `python‑dateutil`, `pytz`
- Testing: `pytest`, `pytest‑cov`
- Linting/Formatting: `ruff`, `black`
All dependencies are pinned in `requirements.txt` and installed via:
```bash
pip install -r requirements.txt
```
The project follows the **PEP 518** build system (no compiled extensions).

---

## 7. Local Development Setup
1. **Clone** the repo and `cd` into `D:\zenith_saas`.
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Git‑bash on Windows
   ```
3. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
4. Spin up a local PostgreSQL instance (Docker is recommended):
   ```bash
   docker run -d --name pg -e POSTGRES_PASSWORD=secret -p 5432:5432 postgres:15
   ```
5. Initialise the schema:
   ```bash
   psql postgresql://postgres:secret@localhost:5432/postgres -f scripts/init_db.sql
   ```
6. Populate minimal config (copy from `.env.example`):
   ```bash
   export DATABASE_URL=postgresql://postgres:secret@localhost:5432/postgres
   export YF_HEADERS='User-Agent: Mozilla/5.0'
   # add other env vars as needed
   ```
7. Run the price‑cache thread (optional but required for live data):
   ```bash
   python -m data.price_cache &
   ```
8. Start the Flask app:
   ```bash
   FLASK_APP=app.py FLASK_ENV=development flask run
   ```
9. Verify endpoints:
   ```bash
   curl http://127.0.0.1:5000/api/v1/ping
   ```

---

## 8. Development Workflow
| Step | Command |
|------|---------|
| **Lint** | `ruff .` |
| **Format** | `black .` |
| **Run Tests** | `pytest -v --cov=./` |
| **Generate Docs** | `mkdocs build` (if docs folder exists) |
| **Commit** | Follow Conventional Commits (type, scope, description). |
| **CI** | GitHub Actions run lint, test, and build on each PR. |

All database migrations are handled manually via SQL scripts in `scripts/`.

---

## 9. Testing Strategy
- **Unit tests** for pure functions in `algo/indicators.py`, `scraper_parser.py`, and utilities.
- **Integration tests** spin up a temporary PostgreSQL container, load fixture data, and exercise API routes (`routes_api.py`).
- **End‑to‑end** can be executed via a Docker‑Compose stack (`docker-compose.yml` – not versioned yet) that includes the Flask app, PostgreSQL, and a mock Telegram bot.

Tests are located under `tests/` (not checked in this snapshot) and executed in CI.

---

## 10. Deployment & Ops
- **Railway** (as defined in `Procfile`) runs `gunicorn --workers 1 app:app` with the environment variables from the platform.
- **Process model**: one gunicorn worker, one price‑cache thread (started via `startup.py`), and the scraper daemon launched by a `cron` job inside the container.
- **Metrics**: logged via Python’s `logging` (JSON format preferred) and exported to CloudWatch / Grafana using side‑car.
- **Health‑check** endpoint: `GET /api/v1/health` returns 200 if DB connection is alive and cache thread is running.
- **Scaling**: Horizontal scaling is limited because the price‑cache thread is single‑instance; for larger load, run a dedicated cache service (Redis) and refactor `price_cache.py`.

---

## 11. Maintenance & Known Issues
- **Yahoo back‑adjusted closes** can corrupt historical `price_history`. The weekly DataSectors correction job (`fetch_daily_datasectors`) mitigates this.
- **Ticker universe drift** – `ticker_universe` must be refreshed quarterly from IDX official list.
- **Scraper reliability** – Telegram disconnections require manual restart; consider adding exponential‑backoff and watchdog.
- **Database growth** – `price_history_15m` can exceed 10 GB after 2 years; implement a retention policy (e.g., keep 90 days).

---

## 12. Roadmap / Future Work
- Migrate price‑cache to **Redis** for faster reads and multi‑instance scaling.
- Add **WebSocket** endpoint for live ticker pushes to frontend clients.
- Replace raw SQL with an ORM (SQLAlchemy) for safer schema migrations.
- Containerise the scraper daemon using a lightweight **Alpine** image.
- Implement **OpenAPI** spec generation for API documentation.

---

*Document generated on `$(date '+%Y-%m-%d %H:%M:%S')` by Hermes Agent.*