# Wyckoff Local Simulation Engine — Project Context

## TL;DR
Building a **local algo testing engine** for Wyckoff (and other trading strategies). Test logic safely offline before pushing to production Zenith 2.0 trading bot.

## Why Local?
- ✅ Test algos without affecting production
- ✅ Fast iteration (30s backtest vs 2min prod server)
- ✅ Full data history available locally
- ✅ Easy customization & debugging

## Project Structure

```
~/wyckoff_sim/                    (YOUR LOCAL FOLDER)
├── sim_engine.py                 (Main backtester + algo framework)
├── export_db.sh                  (Export prod PostgreSQL)
├── .env                          (LOCAL DB: postgres:password@localhost:5432)
├── LOCAL_SIM_SETUP.md            (Docker + DB restore guide)
├── SIM_ENGINE_GUIDE.md           (How to customize algos)
├── venv_sim/                     (Python venv)
├── zenith_full_backup.dump       (Prod data backup, ~100MB)
└── backtest_results/             (Your test outputs)
```

## What's in sim_engine.py

**Framework with 2 example algos:**
1. `WyckoffAlgo` — your main development target
2. `SimpleSmartMoneyAlgo` — reference implementation
3. `BaseAlgo` — inherit this for custom algos

**Backtester class:**
- Multi-entry positions (like prod)
- ATR stop loss daily check
- Trade tracking: entry/exit date, price, profit%, phase
- Stats: win rate, profit factor, avg profit

**CLI:**
```bash
python sim_engine.py --algo wyckoff --days 90
python sim_engine.py --algo smartmoney --days 90
python sim_engine.py --compare --days 90
```

## Key Data Available (eod_summary table)

```python
eod_row = {
    "date": "DD-MM-YYYY",
    "ticker": "MORA",
    "price_close": 2850.0,
    "sm_val": 45.2,        # Smart money flow value
    "bm_val": -12.5,       # Bad money flow value
    "mf_plus": 120.5,      # Money flow in
    "mf_minus": 45.2,      # Money flow out
    "atr_pct": 2.5,        # Volatility (stop loss base)
    "phase": "ACCUMULATION",
    "tx_count": 1250,
    # ... more fields available
}
```

## Development Workflow

```
1. Modify WyckoffAlgo.signal() in sim_engine.py
2. Run: python sim_engine.py --algo wyckoff --days 90
3. Check results: win rate, profit factor, sample trades
4. Iterate: tweak logic → test again
5. Once validated: copy signal() logic → algo_backtest.py in main repo
6. Push to main & test in /backtest page
```

## Quick Commands (after setup)

```bash
cd ~/wyckoff_sim

# Activate venv
source venv_sim/bin/activate  # Linux/Mac
# venv_sim\Scripts\activate   # Windows

# Run backtest
python sim_engine.py --algo wyckoff --days 90

# Compare all algos
python sim_engine.py --compare --days 180

# Debug single ticker (add to sim_engine.py)
psql -U postgres -h localhost -d wyckoff_sim -c \
  "SELECT * FROM eod_summary WHERE ticker='MORA' LIMIT 5"
```

## When You're Done

1. **Algo validated** → copy to `algo_backtest.py:run_backtest()`
2. **Push to main** → test in `/backtest` against prod data
3. **Monitor** → watch /flow page first week
4. **Done!** → Wyckoff live on production Zenith 2.0

## Files on GitHub (zenith_saas main branch)

- `sim_engine.py` — backtester + framework
- `export_db.sh` — export script
- `LOCAL_SIM_SETUP.md` — full Docker + DB setup
- `SIM_ENGINE_GUIDE.md` — customization guide

## FAQ

**Q: Where do I edit the Wyckoff algo?**
A: `WyckoffAlgo.signal()` method in sim_engine.py

**Q: How do I add a new algo?**
A: Inherit `BaseAlgo`, implement `signal()`, register in algos_map

**Q: Why test locally?**
A: Prod backtest takes 2min, local takes 30s. Plus isolated dev.

**Q: Can I use SQLite instead of PostgreSQL?**
A: Yes, but need to export + convert. PostgreSQL Docker is simpler.

**Q: How do I compare my algo vs production algo?**
A: Run `--compare`, then check `/backtest` page with same date range

---

**Next Step:** Follow `LOCAL_SIM_SETUP.md` to get Docker + DB running, then start hacking `WyckoffAlgo.signal()`! 🚀
