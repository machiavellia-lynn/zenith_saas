# Simulation Engine — Usage & Customization

## Quick Start

```bash
# 1. Export prod data (5 min)
bash export_db.sh

# 2. Start Docker DB (30s)
docker run --name wyckoff-db -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=wyckoff_sim -p 5432:5432 -d postgres:15
sleep 5

# 3. Restore (5-10 min depending on data size)
pg_restore -U postgres -h localhost -d wyckoff_sim -Fc zenith_full_backup.dump

# 4. Setup Python
python -m venv venv_sim
source venv_sim/bin/activate
pip install psycopg2-binary python-dotenv

# 5. Test Wyckoff algo
python sim_engine.py --algo wyckoff --days 90
```

## Run Algos

```bash
# Test individual algo
python sim_engine.py --algo wyckoff --days 90
python sim_engine.py --algo smartmoney --days 90

# Compare all algos side-by-side
python sim_engine.py --compare --days 90

# Change lookback period
python sim_engine.py --algo wyckoff --days 180
```

## Customize Wyckoff Algo

Edit `WyckoffAlgo.signal()` in `sim_engine.py`:

```python
class WyckoffAlgo(BaseAlgo):
    def signal(self, ticker: str, eod_row: dict) -> str | None:
        """
        Available fields in eod_row:
        - date: "DD-MM-YYYY"
        - ticker: "MORA", "BBCA", etc
        - price_close: float
        - sm_val, bm_val: smart/bad money value
        - mf_plus, mf_minus: money flow in/out
        - atr_pct: volatility
        - phase: current phase tag
        - action: existing signal (ignore if custom)
        - tx_count, tx_sm, tx_bm: transaction counts
        - sri, mes, rpr: other indicators
        """
        bm = eod_row.get("bm_val") or 0
        mf_plus = eod_row.get("mf_plus") or 0

        # Your Wyckoff logic here
        if bm > 0 and mf_plus > 0:
            return "BUY"
        elif eod_row.get("mf_minus", 0) > mf_plus:
            return "SELL"
        return None
```

## Add New Algo

```python
class MyCustomAlgo(BaseAlgo):
    name = "CustomAlgo"

    def signal(self, ticker: str, eod_row: dict) -> str | None:
        price = eod_row.get("price_close") or 0
        mf = (eod_row.get("mf_plus") or 0) - (eod_row.get("mf_minus") or 0)

        # Your logic
        if mf > 10:
            return "BUY"
        return None

# Register in algos_map
algos_map = {
    "wyckoff": WyckoffAlgo(),
    "smartmoney": SimpleSmartMoneyAlgo(),
    "custom": MyCustomAlgo(),  # Add here
}
```

Then test:
```bash
python sim_engine.py --algo custom --days 90
```

## Inspect Data

Check what data is available:

```bash
# List all columns in eod_summary
psql -U postgres -h localhost -d wyckoff_sim -c "\d eod_summary"

# Sample EOD data for a ticker
psql -U postgres -h localhost -d wyckoff_sim -c \
  "SELECT * FROM eod_summary WHERE ticker='MORA' LIMIT 5"

# Money flow data
psql -U postgres -h localhost -d wyckoff_sim -c \
  "SELECT date, ticker, mf_plus, mf_minus FROM raw_mf_messages LIMIT 10"

# Smart/bad money flow
psql -U postgres -h localhost -d wyckoff_sim -c \
  "SELECT date, ticker, channel, value_numeric FROM raw_messages LIMIT 10"
```

## Debug Single Ticker

```python
# Add to sim_engine.py for quick debug
if __name__ == "__main__":
    conn = get_db()
    rows = fetchall(conn, """
        SELECT * FROM eod_summary 
        WHERE ticker='MORA' 
        ORDER BY TO_DATE(date, 'DD-MM-YYYY') DESC
        LIMIT 10
    """)
    for r in rows:
        algo = WyckoffAlgo()
        signal = algo.signal(r["ticker"], r)
        print(f"{r['date']} {r['ticker']} | "
              f"BM: {r['bm_val']:.0f} | MF+: {r['mf_plus']:.0f} | "
              f"Signal: {signal}")
```

## Performance Tips

- **Reduce days** for faster iteration: `--days 30`
- **Filter tickers**: Edit fetch query to WHERE ticker IN ('MORA', 'BBCA', ...)
- **Cache results**: Pickle trades after first run, reload for algo tweaks

## Next: Deploy to Production

Once algo is validated locally:

1. Copy `WyckoffAlgo.signal()` logic to `algo/algo_backtest.py:run_backtest()`
2. Test in `/backtest` page against full prod dataset
3. Deploy via PR → main
4. Monitor first week with smaller position sizes

---

**Questions?** Check `eod_summary` schema or add `print()` statements in `signal()` to debug!
