  zenith_saas/
  ├── app.py          ← entry point
  ├── config.py       ← global constants
  ├── startup.py      ← startup orchestrator
  │
  ├── core/           ← foundation
  │   ├── db.py
  │   ├── db_schema.py
  │   ├── auth.py
  │   └── utils.py
  │
  ├── scraper/        ← data ingestion
  │   ├── scraper_parser.py
  │   ├── scraper_saver.py
  │   ├── scraper_daily.py
  │   └── scraper_weekly.py
  │
  ├── algo/           ← pure logic
  │   ├── algo_wyckoff.py
  │   ├── algo_backtest.py
  │   ├── analytics_daily.py
  │   └── summary_rebuild.py
  │
  ├── data/           ← data access
  │   ├── price_fetch.py
  │   ├── price_datasectors.py
  │   ├── journal.py
  │   ├── ds_fundamental.py
  │   └── ds_smartmoney.py
  │
  └── routes/         ← HTTP layer
      ├── routes_main.py
      ├── routes_flow.py
      ├── routes_sector.py
      ├── routes_backtest.py
      ├── routes_journal.py
      └── routes_admin.py