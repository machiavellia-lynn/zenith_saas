# Zenith External Data API (`/api/v1/*`)

Read-only REST API for pulling data out of the Zenith 2.0 database from any external
tool (script, spreadsheet, another app), gated by a single API key.

web = https://zenithsaas-production.up.railway.app/

## Auth

Set an environment variable on the server:

```
ZENITH_API_KEY=<a long random string you choose>
```

Then every request must include it, either as a header (preferred) or a query param:

```bash
curl -H "X-API-Key: $ZENITH_API_KEY" "https://<your-zenith-host>/api/v1/eod-summary?ticker=BBCA&limit=5"

# or

curl "https://<your-zenith-host>/api/v1/eod-summary?ticker=BBCA&limit=5&api_key=$ZENITH_API_KEY"
```

Missing/wrong key → `401 {"error": "unauthorized"}`.
If `ZENITH_API_KEY` isn't set on the server at all, every request is rejected (fail closed).

## Response shape

Every endpoint (except `/tables`) returns:

```json
{
  "count": 5,
  "limit": 500,
  "offset": 0,
  "data": [ { ... row ... }, ... ]
}
```

- `limit` — max rows to return, default 500, capped at 5000.
- `offset` — rows to skip, for pagination (`offset=500&limit=500` for the next page).
- Dates are `DD-MM-YYYY` strings (matches how Zenith stores them internally) unless noted otherwise.

## Discovery

```
GET /api/v1/tables
```

Returns this same endpoint list as JSON — useful for scripting against the API without
re-reading this file.

## Endpoints

| Endpoint | Table | Filters |
|---|---|---|
| `GET /api/v1/eod-summary` | `eod_summary` — daily per-ticker analytics (SM/BM value, money flow, price, Wyckoff phase/action, MAs, RSI, Bollinger Bands, BSJP indicators) | `ticker`, `date_from`, `date_to`, `limit`, `offset` |
| `GET /api/v1/price-history` | `price_history` — daily OHLCV + indicators | `ticker`, `date_from`, `date_to`, `limit`, `offset` |
| `GET /api/v1/price-history-15m` | `price_history_15m` — 15-min intraday OHLCV (WIB) | `ticker`, `date` (`YYYY-MM-DD`), `limit`, `offset` |
| `GET /api/v1/raw-messages` | `raw_messages` — raw Telegram Smart Money / Bad Money tape | `ticker`, `channel` (`smart`\|`bad`), `date_from`, `date_to`, `limit`, `offset` |
| `GET /api/v1/raw-mf-messages` | `raw_mf_messages` — raw Telegram Money Flow tape | `ticker`, `channel` (`mf_plus`\|`mf_minus`), `date_from`, `date_to`, `limit`, `offset` |
| `GET /api/v1/tickers` | `ticker_universe` — tracked IDX tickers | `is_active` (`true`/`false`), `limit`, `offset` |
| `GET /api/v1/trade-journal` | `trade_journal` — Wyckoff algo live trade log | `ticker`, `status` (`open`\|`closed`), `date_from`/`date_to` (on `entry_date`), `limit`, `offset` |
| `GET /api/v1/bsjp-signals` | `bsjp_signals` — BSJP day-trade signals | `ticker`, `date_from`, `date_to`, `limit`, `offset` |
| `GET /api/v1/bsjp-results` | `bsjp_results` — BSJP trade outcomes | `ticker`, `date_from`, `date_to`, `limit`, `offset` |
| `GET /api/v1/backtest-cache` | `backtest_cache` — cached backtest runs (`result` returned as parsed JSON) | `run_id`, `limit`, `offset` |
| `GET /api/v1/ohlcv-cache` | `ohlcv_cache` — DataSectors OHLCV cache (Tier 1, currently inactive) | `ticker`, `limit`, `offset` |
| `GET /api/v1/corporate-events` | `corporate_events` — DataSectors corporate events (Tier 2, currently inactive) | `ticker`, `event_type`, `limit`, `offset` |
| `GET /api/v1/inst-flow-cache` | `inst_flow_cache` — DataSectors institutional flow (Tier 3, currently inactive) | `ticker`, `limit`, `offset` |

Not exposed: `users` (login table — contains password hashes, intentionally excluded).

## Examples

```bash
# Last 30 days of BBCA analytics
curl -H "X-API-Key: $KEY" \
  "https://zenith.example.com/api/v1/eod-summary?ticker=BBCA&date_from=01-06-2026&date_to=30-06-2026"

# Today's BSJP signals, ranked
curl -H "X-API-Key: $KEY" \
  "https://zenith.example.com/api/v1/bsjp-signals?date_from=17-07-2026&date_to=17-07-2026"

# All open Wyckoff positions
curl -H "X-API-Key: $KEY" \
  "https://zenith.example.com/api/v1/trade-journal?status=open"

# Page 2 of raw SM tape for a ticker
curl -H "X-API-Key: $KEY" \
  "https://zenith.example.com/api/v1/raw-messages?ticker=BBRI&channel=smart&limit=500&offset=500"
```
