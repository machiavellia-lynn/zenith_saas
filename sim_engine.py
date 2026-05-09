#!/usr/bin/env python
"""
sim_engine.py — Local Wyckoff + Multi-Algo Simulation Engine
Test trading algo logic safely offline before production.
"""
import argparse
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("sim")
log.setLevel(logging.INFO)
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] SIM %(levelname)s — %(message)s", "%H:%M:%S"))
    log.addHandler(h)

# ── Database Connection ────────────────────────────────────────────────────────
def get_db():
    """Connect to local simulation DB."""
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/wyckoff_sim")
    return psycopg2.connect(db_url)

def fetchall(conn, query, params=None):
    """Helper to fetch all rows as dicts."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query, params or [])
    return cur.fetchall()

# ── Algo Framework ────────────────────────────────────────────────────────────

class BaseAlgo:
    """Base class for algo implementations."""
    name = "BaseAlgo"

    def signal(self, ticker: str, eod_row: dict) -> str | None:
        """
        Evaluate EOD data and return action: 'BUY', 'SELL', or None.
        eod_row keys: date, ticker, sm_val, bm_val, mf_plus, mf_minus,
                      price_close, atr_pct, action, phase, etc.
        """
        raise NotImplementedError


class WyckoffAlgo(BaseAlgo):
    """Wyckoff method implementation."""
    name = "Wyckoff"

    def __init__(self):
        self.lookback = 20  # bars for phase detection

    def signal(self, ticker: str, eod_row: dict) -> str | None:
        """
        Wyckoff rules:
        - Accumulation phase: BM val drops, MF+ rising
        - Distribution phase: SM val peaks, MF- rising
        """
        bm = eod_row.get("bm_val") or 0
        mf_plus = eod_row.get("mf_plus") or 0
        mf_minus = eod_row.get("mf_minus") or 0

        # Rough Wyckoff logic (customize as needed)
        if bm > 0 and mf_plus > 0:
            return "BUY"
        elif mf_minus > mf_plus and eod_row.get("sm_val", 0) > 0:
            return "SELL"
        return None


class SimpleSmartMoneyAlgo(BaseAlgo):
    """Test algo: just follow smart money flow."""
    name = "SmartMoney"

    def signal(self, ticker: str, eod_row: dict) -> str | None:
        sm = eod_row.get("sm_val") or 0
        if sm > 5:
            return "BUY"
        elif sm < -5:
            return "SELL"
        return None


# ── Backtester ────────────────────────────────────────────────────────────────

class Backtester:
    """Run backtest for any algo."""

    def __init__(self, conn, algo: BaseAlgo, days: int = 90):
        self.conn = conn
        self.algo = algo
        self.days = days
        self.trades = []

    def run(self) -> dict:
        """Execute backtest and return stats."""
        log.info(f"Running {self.algo.name} backtest ({self.days} days)...")

        # Fetch date range
        distinct = fetchall(self.conn, """
            SELECT date FROM (SELECT DISTINCT date FROM eod_summary) t
            ORDER BY TO_DATE(date, 'DD-MM-YYYY') ASC
        """)
        all_dates = [r["date"] for r in distinct]

        if len(all_dates) < self.days:
            cutoff_idx = 0
        else:
            cutoff_idx = len(all_dates) - self.days

        cutoff_date = all_dates[cutoff_idx]
        log.info(f"Testing from {cutoff_date} ({len(all_dates) - cutoff_idx} days)")

        # Fetch all rows in range
        all_rows = fetchall(self.conn, """
            SELECT ticker, date, price_close, action, phase, atr_pct,
                   sm_val, bm_val, mf_plus, mf_minus
            FROM eod_summary
            WHERE TO_DATE(date, 'DD-MM-YYYY') >= TO_DATE(%s, 'DD-MM-YYYY')
            ORDER BY ticker, date
        """, [cutoff_date])

        log.info(f"Loaded {len(all_rows)} EOD rows")

        # Index by date and ticker
        days_index = defaultdict(dict)
        for row in all_rows:
            days_index[row["date"]][row["ticker"]] = row

        sorted_dates = sorted(days_index.keys(), key=lambda d: datetime.strptime(d, "%d-%m-%Y"))

        # Multi-entry trading
        open_positions = defaultdict(list)  # {ticker: [{entry_date, entry_price, entry_phase}, ...]}
        trades = []

        for date_str in sorted_dates:
            day_tickers = days_index[date_str]

            # Check ATR SL daily
            for ticker, positions in list(open_positions.items()):
                if not positions or ticker not in day_tickers:
                    continue
                price = day_tickers[ticker].get("price_close")
                if not price:
                    continue

                surviving = []
                for pos in positions:
                    loss_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100
                    sl_threshold = -min(max((pos.get("atr_pct") or 2.5) * 2.0, 5.0), 12.0)
                    if loss_pct <= sl_threshold:
                        trades.append({
                            "ticker": ticker,
                            "entry_date": pos["entry_date"],
                            "exit_date": date_str,
                            "entry_price": pos["entry_price"],
                            "exit_price": price,
                            "profit": round(loss_pct, 2),
                            "exit_phase": "SL",
                        })
                    else:
                        surviving.append(pos)
                open_positions[ticker] = surviving

            # Process signals
            for ticker, eod_row in day_tickers.items():
                signal = self.algo.signal(ticker, eod_row)
                price = eod_row.get("price_close")
                if not signal or not price:
                    continue

                if signal == "BUY":
                    open_positions[ticker].append({
                        "entry_date": date_str,
                        "entry_price": price,
                        "entry_phase": eod_row.get("phase"),
                        "atr_pct": eod_row.get("atr_pct"),
                    })

                elif signal == "SELL" and open_positions[ticker]:
                    for pos in open_positions[ticker]:
                        profit = round((price - pos["entry_price"]) / pos["entry_price"] * 100, 2)
                        trades.append({
                            "ticker": ticker,
                            "entry_date": pos["entry_date"],
                            "exit_date": date_str,
                            "entry_price": pos["entry_price"],
                            "exit_price": price,
                            "profit": profit,
                            "exit_phase": eod_row.get("phase"),
                        })
                    open_positions[ticker] = []

        # Filter extreme losses (delisting/rights)
        valid_trades = [t for t in trades if t.get("profit", 0) >= -50]

        wins = [t for t in valid_trades if t["profit"] > 0]
        losses = [t for t in valid_trades if t["profit"] <= 0]

        gross_p = sum(t["profit"] for t in wins)
        gross_l = abs(sum(t["profit"] for t in losses))

        stats = {
            "algo": self.algo.name,
            "total_trades": len(valid_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(valid_trades) * 100, 1) if valid_trades else 0,
            "avg_profit": round(sum(t["profit"] for t in valid_trades) / len(valid_trades), 2) if valid_trades else 0,
            "profit_factor": round(gross_p / gross_l, 2) if gross_l > 0 else (99.0 if gross_p > 0 else 0),
            "gross_profit": round(gross_p, 2),
            "gross_loss": round(gross_l, 2),
            "trades": valid_trades[:20],  # Top 20 for inspection
        }

        return stats


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Local Wyckoff Simulation Engine")
    parser.add_argument("--algo", choices=["wyckoff", "smartmoney"], default="wyckoff", help="Algo to test")
    parser.add_argument("--days", type=int, default=90, help="Backtest days")
    parser.add_argument("--compare", action="store_true", help="Compare all algos")
    args = parser.parse_args()

    algos_map = {
        "wyckoff": WyckoffAlgo(),
        "smartmoney": SimpleSmartMoneyAlgo(),
    }

    conn = get_db()

    if args.compare:
        log.info("Comparing all algos...")
        results = []
        for name, algo in algos_map.items():
            bt = Backtester(conn, algo, days=args.days)
            result = bt.run()
            results.append(result)
            print_result(result)
            print()

        # Compare table
        print("\n📊 COMPARISON")
        print("─" * 80)
        for r in results:
            pf_str = f"{r['profit_factor']:.2f}×" if r["profit_factor"] != 99.0 else "N/A"
            print(f"{r['algo']:15} | Trades: {r['total_trades']:4} | WR: {r['win_rate']:5.1f}% | "
                  f"Avg: {r['avg_profit']:+6.2f}% | PF: {pf_str}")
    else:
        algo = algos_map.get(args.algo)
        if not algo:
            log.error(f"Unknown algo: {args.algo}")
            return

        bt = Backtester(conn, algo, days=args.days)
        result = bt.run()
        print_result(result)

    conn.close()


def print_result(result: dict):
    """Pretty print backtest result."""
    print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║ {result['algo'].upper():^65} ║
╚═══════════════════════════════════════════════════════════════════╝

  Trades:        {result['total_trades']}
  Wins / Losses: {result['wins']} / {result['losses']}
  Win Rate:      {result['win_rate']:.1f}%
  Avg Profit:    {result['avg_profit']:+.2f}%
  Profit Factor: {result['profit_factor']:.2f}×
  Gross P/L:     +{result['gross_profit']:.2f}% / -{result['gross_loss']:.2f}%

  Sample Trades (first 5):
  """)
    for i, t in enumerate(result["trades"][:5]):
        print(f"    {i+1}. {t['ticker']:6} | "
              f"{t['entry_date']} → {t['exit_date']} | "
              f"{t['entry_price']:.0f} → {t['exit_price']:.0f} | "
              f"{t['profit']:+.2f}%")


if __name__ == "__main__":
    main()
