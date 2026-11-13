# BSJP Live Signal — Implementation Guide for Zenith 2.0

> **Tujuan dokumen ini**: Panduan lengkap implementasi fitur BSJP live signal di Zenith 2.0 (Railway).
> Claude Code bisa langsung implement tanpa bertanya apapun.

---

## 1. Gambaran Umum

BSJP = **Beli Sore Jual Pagi** — overnight swing strategy. Entry EOD via HAKA (pre-close auction 15:50–16:00 IDX), exit hari berikutnya berdasarkan TP/SL.

**Flow signal (single pass):**
```
~15:48 WIB → Scan semua ticker (kondisi setup dicek pakai candle 15:45 & 09:00,
              entry = eod_summary.price_close) → simpan top-15 by score
```

Tidak ada status ESTIMASI/CONFIRMED/INVALID dan tidak ada pass finalize kedua di 16:30 — itu desain lama yang sudah dibuang. `bsjp_signals` sekarang satu baris final per ticker per hari, langsung dari satu kali scan.

---

## 2. Hasil Backtest (Validated — 90 Hari, 492 Trades)

> Data: 15-09-2025 s/d 13-05-2026 (159 hari trading). Backtest pakai 90 hari terakhir.
> Exit determination menggunakan data intraday 15m (price_history_15m) — wajib ada, jika tidak ada data 15m trade di-skip.

### 2.1 Overall Performance

| Metric | Nilai |
|--------|-------|
| Total trades | 492 |
| Winrate | **67.3%** |
| Expectancy | **+1.08% per trade** |
| Avg Win | +2.70% |
| Avg Loss | -2.26% |
| Max sinyal per hari | **15** (top-15 by composite score) |

### 2.2 Per Setup

| # | Setup | Trades | WR | Expectancy | AvgWin | AvgLoss |
|---|-------|--------|----|------------|--------|---------|
| 1 | POWER_BREAK (V2.1 & V2.2) | 40 | 60.0% | **+2.17%** | +5.83% | -3.32% |
| 2 | BB_PULLBACK (BB_MID) | 17 | 70.6% | **+1.39%** | +2.21% | -0.60% |
| 3 | SMA5_BREAKOUT_V13 (V1.3) | 230 | 78.3% | **+1.20%** | +2.51% | -3.50% |
| 4 | SMA5_BREAKOUT_V11 (V1.1) | 169 | 55.6% | +0.72% | +2.53% | -1.54% |
| 5 | SMA5_PULLBACK_V12 (V1.2) | 36 | 58.3% | +0.57% | +1.82% | -1.17% |

> **Setup BB_REVERSAL telah dihapus** dari algo karena WR 33.3% dan expectancy negatif (-0.31%).
> **Min score filter tidak dipakai** — backtest confirmed tidak membaik (score 0.50-0.60 justru menurunkan expectancy).

### 2.3 Proyeksi Profit (Fixed Capital Strategy)

Strategi terpilih: **Fixed 10M per sinyal, 15 sinyal/hari = 150M modal/hari, recycled daily**

| Kondisi | Return/hari | Gain 47 hari | Modal akhir |
|---------|-------------|--------------|-------------|
| Gross (tanpa fee) | +1.07% | +97.4M (+64.91%) | 247M |
| **Net (fee 0.15% beli + 0.25% jual)** | **+0.67%** | **+55.3M (+36.87%)** | **205M** |

> Fee total per round-trip: 0.40%. Net return = 1.07% - 0.40% = **0.67%/hari**.

---

## 3. Algo Rules

### 3.1 SM Gate (Wajib lolos semua)

| Filter | Threshold |
|--------|-----------|
| Phase | Bukan UPTHRUST atau DISTRI |
| SRI | >= 1.2 |
| RPR | <= 0.55 |
| MF Ratio | >= 50% |
| RSM | >= 60% (SM dominance) |

### 3.2 Setup Conditions (6 Setup Aktif)

| Setup | Kondisi Utama |
|-------|---------------|
| POWER_BREAK_V21 | change >= 10%, close > MA5, prev_close_below_ma5, value >= 5M |
| POWER_BREAK_V22 | change >= 10%, close > MA5, is_sideways, value >= 5M |
| SMA5_BREAKOUT_V13 | ma5_streak >= 3, prev_high_break, change > 0, close > MA5 |
| SMA5_BREAKOUT_V11 | prev_close_below_ma5, change > 0, close > MA5, ma5_streak == 1 |
| BB_PULLBACK | change < 0, close >= BB_MID, close <= BB_MID × 1.03, first touch |
| SMA5_PULLBACK_V12 | change < 0, close >= MA5, ma5_streak >= 1 |

### 3.3 SL per Setup

| Setup | SL Type | SL |
|-------|---------|----|
| POWER_BREAK_V21 | FIXED_2PCT | entry × 0.98 |
| POWER_BREAK_V22 | FIXED_2PCT | entry × 0.98 |
| SMA5_BREAKOUT_V13 | MA5 | nilai MA5 |
| SMA5_BREAKOUT_V11 | MA5 | nilai MA5 |
| BB_PULLBACK | BB_MID | nilai BB midline |
| SMA5_PULLBACK_V12 | MA5 | nilai MA5 |

### 3.4 TP

- TP1 = entry × 1.01 (+1%)
- TP2 = entry × 1.02 (+2%)

### 3.5 Blacklist Ticker

Ticker berikut tidak akan pernah muncul di sinyal BSJP:
```
HATM, JAST, CYBR, AYLS, VAST, VTNY
```

---

## 4. Composite Score & Ranking

Setiap hari, semua ticker yang lolos SM Gate + setup di-rank berdasarkan composite score. **Hanya top-15 yang ditampilkan sebagai sinyal.**

```
Score = (RSM_n    × 0.30)   # SM dominance
      + (SRI_n    × 0.25)   # SM intensity vs rata-rata 10 hari
      + (Setup_WR × 0.25)   # Historical winrate setup
      + (close_pos × 0.10)  # Close position dalam range hari ini (0–1)
      + (MF_n     × 0.10)   # Mutual fund participation
```

**Normalisasi:**
- `RSM_n` = (RSM - 60) / 40, clamp 0–1
- `SRI_n` = (SRI - 1.2) / 3.8, clamp 0–1
- `MF_n` = (MF_ratio - 50) / 50, clamp 0–1

**Historical WR per setup (dari backtest — update berkala):**

| Setup | WR | Bobot Setup_WR |
|-------|----|----------------|
| SMA5_BREAKOUT_V13 | 78.4% | 0.784 |
| SMA5_PULLBACK_V12 | 63.8% | 0.638 |
| BB_PULLBACK | 59.6% | 0.596 |
| SMA5_BREAKOUT_V11 | 55.0% | 0.550 |
| POWER_BREAK_V21 | 52.0% | 0.520 |
| POWER_BREAK_V22 | 52.0% | 0.520 |

**Catatan validasi**: Filter min_score tidak digunakan. Backtest menunjukkan filter 0.50–0.60 justru menurunkan expectancy. Top-15 ranking sudah cukup sebagai filter kualitas.

---

## 5. Position Sizing (Rekomendasi)

Tampilkan rekomendasi lot di web saat generate sinyal.

**Formula terpilih: Fixed Capital 10M per sinyal**
```
Lot = 10.000.000 / entry_price
```

> Dari backtest perbandingan 3 strategi (Risk-Based, Score-Weighted, Fixed Capital):
> - Risk-Based: return +0.94% (lebih rendah, karena SL sempit → lot terlalu besar)
> - Score-Weighted: return +1.07%
> - Fixed Capital: return +1.07%
> Score-Weighted sedikit lebih capital-efficient, tapi Fixed Capital lebih simpel dan hasilnya identik.

---

## 6. Market Filter (Risk Management)

**Jika IHSG pada hari entry turun > 1.5%**: tampilkan warning di web, tidak perlu blokir sinyal tapi beri label "Pasar Melemah — pertimbangkan skip".

Latar belakang: dari data backtest, ada cluster SL[gap] besar di satu hari (01-04-2026) ketika market selloff — 7+ sinyal kena SL[gap] di hari yang sama. BSJP sangat sensitif terhadap sentimen market overnight.

---

## 7. Exit Logic — 15m Intraday

Exit ditentukan **chronologically** menggunakan candle 15m hari N+1:

```
Candle pertama (09:00):
  → Jika open <= SL: exit di open (SL gap)
  → Jika open >= TP2: exit di open (TP2 gap)
  → Jika TP1 <= open < TP2: exit di open (TP1 gap), cek TP2 dari high
  → Jika open normal: lanjut ke intraday

Candle berikutnya:
  → SL dan TP keduanya dalam satu candle: tiebreak by open vs midpoint(SL, TP1)
  → SL hit duluan: exit SL
  → TP2 hit: exit TP2
  → TP1 hit: exit TP1

Akhir hari (tidak ada target tercapai):
  → Exit di last close (NO_TARGET)
```

---

## 8. File Baru yang Harus Dibuat

### 8.1 `algo/algo_bsjp.py` — BSJP Algorithm

```python
"""
algo/algo_bsjp.py — BSJP Overnight Swing Algorithm (6 setups)

Pure functions only — zero DB, zero HTTP.
Entry EOD, exit N+1 berdasarkan TP/SL.

Setup priority (urutan cek):
1. POWER_BREAK_V21
2. POWER_BREAK_V22
3. SMA5_BREAKOUT_V13
4. SMA5_BREAKOUT_V11
5. BB_PULLBACK
6. SMA5_PULLBACK_V12
"""


def _f(val, default=None):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _b(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val) if val is not None else False


def _i(val, default=0):
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


class BSJPAlgo:
    """BSJP overnight swing: 6 setups, TP/SL exit."""

    name = "BSJP"

    # SM Gate thresholds
    MIN_SRI      = 1.2
    MAX_RPR      = 0.55
    MIN_MF_RATIO = 50.0
    MIN_RSM      = 60.0

    # Setup-specific
    POWER_BREAK_MIN_VALUE = 5_000_000_000  # 5 Miliar IDR

    SL_MAP = {
        "POWER_BREAK_V21":   "FIXED_2PCT",
        "POWER_BREAK_V22":   "FIXED_2PCT",
        "SMA5_BREAKOUT_V13": "MA5",
        "SMA5_BREAKOUT_V11": "MA5",
        "BB_PULLBACK":       "BB_MID",
        "SMA5_PULLBACK_V12": "MA5",
    }

    def signal(self, ticker: str, row: dict) -> str | None:
        return "BUY" if self.signal_detail(ticker, row) else None

    def signal_detail(self, ticker: str, row: dict) -> dict | None:
        """
        Return detail signal atau None.
        {
            "action": "BUY",
            "setup":  str,
            "entry":  int,
            "tp1":    int,
            "tp2":    int,
            "sl":     int,
            "sl_type": str,
        }
        """
        price_close = _f(row.get("price_close"))
        if price_close is None or price_close <= 0:
            return None

        if not self._sm_gate(row):
            return None

        setups = [
            ("POWER_BREAK_V21",   self._setup_power_break_v21),
            ("POWER_BREAK_V22",   self._setup_power_break_v22),
            ("SMA5_BREAKOUT_V13", self._setup_sma5_breakout_v13),
            ("SMA5_BREAKOUT_V11", self._setup_sma5_breakout_v11),
            ("BB_PULLBACK",       self._setup_bb_pullback),
            ("SMA5_PULLBACK_V12", self._setup_sma5_pullback_v12),
        ]

        for name, fn in setups:
            if fn(row):
                entry   = round(price_close)
                sl_type = self.SL_MAP[name]
                sl      = self._compute_sl(row, entry, sl_type)
                return {
                    "action":  "BUY",
                    "setup":   name,
                    "entry":   entry,
                    "tp1":     round(price_close * 1.01),
                    "tp2":     round(price_close * 1.02),
                    "sl":      sl,
                    "sl_type": sl_type,
                }

        return None

    def _compute_sl(self, row: dict, entry: int, sl_type: str) -> int:
        if sl_type == "MA5":
            ma5 = _f(row.get("ma5"), 0)
            return round(ma5) if ma5 > 0 else round(entry * 0.98)
        elif sl_type == "BB_MID":
            bb_mid = _f(row.get("bb_mid"), 0)
            return round(bb_mid) if bb_mid > 0 else round(entry * 0.98)
        return round(entry * 0.98)

    def _sm_gate(self, row: dict) -> bool:
        phase = row.get("phase", "")
        if phase in {"UPTHRUST", "DISTRI"}:
            return False
        if _f(row.get("sri"), 0) < self.MIN_SRI:
            return False
        if _f(row.get("rpr"), 1) > self.MAX_RPR:
            return False
        if _f(row.get("mf_ratio"), 0) < self.MIN_MF_RATIO:
            return False
        sm  = _f(row.get("sm_val"), 0)
        bm  = abs(_f(row.get("bm_val"), 0))
        rsm = sm / (sm + bm) * 100 if (sm + bm) > 0 else 0
        if rsm < self.MIN_RSM:
            return False
        return True

    def _setup_power_break_v21(self, row: dict) -> bool:
        return (
            _f(row.get("price_change_pct"), 0) >= 10.0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
            and _b(row.get("prev_close_below_ma5"))
            and _f(row.get("daily_value"), 0) >= self.POWER_BREAK_MIN_VALUE
        )

    def _setup_power_break_v22(self, row: dict) -> bool:
        return (
            _f(row.get("price_change_pct"), 0) >= 10.0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
            and _b(row.get("is_sideways"))
            and _f(row.get("daily_value"), 0) >= self.POWER_BREAK_MIN_VALUE
        )

    def _setup_sma5_breakout_v13(self, row: dict) -> bool:
        return (
            _i(row.get("ma5_price_streak"), 0) >= 3
            and _b(row.get("prev_high_break"))
            and _f(row.get("price_change_pct"), 0) > 0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
        )

    def _setup_sma5_breakout_v11(self, row: dict) -> bool:
        return (
            _b(row.get("prev_close_below_ma5"))
            and _f(row.get("price_change_pct"), 0) > 0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
            and _i(row.get("ma5_price_streak"), 0) == 1
        )

    def _setup_bb_pullback(self, row: dict) -> bool:
        bb_mid = _f(row.get("bb_mid"), None)
        if bb_mid is None:
            return False
        price_close = _f(row.get("price_close"), 0)
        days_since  = row.get("days_since_near_bb_mid")
        first_touch = (days_since is None or _i(days_since, -1) >= 10)
        return (
            _f(row.get("price_change_pct"), 0) < 0
            and price_close >= bb_mid
            and price_close <= bb_mid * 1.03
            and first_touch
        )

    def _setup_sma5_pullback_v12(self, row: dict) -> bool:
        return (
            _f(row.get("price_change_pct"), 0) < 0
            and _f(row.get("price_close"), 0) >= _f(row.get("ma5"), 0)
            and _i(row.get("ma5_price_streak"), 0) >= 1
        )
```

---

### 8.2 `routes/routes_bsjp.py` — Blueprint BSJP

```python
"""
routes/routes_bsjp.py — BSJP Signal endpoints

GET /bsjp              → halaman BSJP signals (HTML)
GET /api/bsjp/signals  → list signal hari ini (JSON)
GET /api/bsjp/history  → history signal N hari lalu (JSON)
"""
from flask import Blueprint, jsonify, request, render_template
from core.db  import get_conn
from core.auth import require_auth
from datetime import datetime, timezone, timedelta

bp_bsjp = Blueprint("bsjp", __name__)
WIB     = timezone(timedelta(hours=7))


@bp_bsjp.route("/bsjp")
@require_auth
def page_bsjp():
    return render_template("bsjp.html")


@bp_bsjp.route("/api/bsjp/signals")
@require_auth
def api_bsjp_signals():
    """
    Return list signal BSJP hari ini, sorted by score DESC.
    Query params:
      date — DD-MM-YYYY (default: hari ini)
    """
    conn = get_conn()
    try:
        date_str = request.args.get("date") or _today_dmy()

        sql    = "SELECT * FROM bsjp_signals WHERE date = %s ORDER BY score DESC NULLS LAST"
        params = [date_str]

        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        return jsonify({"success": True, "date": date_str, "count": len(rows), "signals": rows})
    finally:
        conn.close()


@bp_bsjp.route("/api/bsjp/history")
@require_auth
def api_bsjp_history():
    """
    Query params:
      ticker — filter by ticker (opsional)
      days   — lookback (default 30)
    """
    conn = get_conn()
    try:
        ticker = request.args.get("ticker", "").upper() or None
        days   = int(request.args.get("days", 30))

        sql    = "SELECT * FROM bsjp_signals WHERE 1=1"
        params = []
        if ticker:
            sql    += " AND ticker = %s"
            params.append(ticker)
        sql += " ORDER BY date DESC LIMIT %s"
        params.append(days * 50)

        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        return jsonify({"success": True, "count": len(rows), "signals": rows})
    finally:
        conn.close()


def _today_dmy() -> str:
    return datetime.now(WIB).strftime("%d-%m-%Y")
```

---

## 9. File yang Harus Dimodifikasi

### 9.1 `core/db_schema.py` — Tambah tabel `bsjp_signals`

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS bsjp_signals (
        id              SERIAL PRIMARY KEY,
        date            TEXT NOT NULL,          -- DD-MM-YYYY
        ticker          TEXT NOT NULL,
        setup           TEXT NOT NULL,
        entry           REAL,                   -- eod_summary.price_close, tick-rounded
        tp1             REAL,
        tp2             REAL,
        sl              REAL,
        sl_type         TEXT,                   -- FIXED_2PCT | MA5 | BB_MID
        score           REAL,                   -- composite score 0-1
        day_rank        INTEGER,                -- rank di antara semua sinyal hari itu (1-15)
        lot_size        INTEGER,                -- rekomendasi lot (10M / entry)
        computed_at     TEXT,
        UNIQUE(date, ticker)
    )
""")
conn.execute("CREATE INDEX IF NOT EXISTS idx_bsjp_date   ON bsjp_signals(date)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_bsjp_ticker ON bsjp_signals(ticker)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_bsjp_status ON bsjp_signals(status)")
```

### 9.2 `scraper/scraper_daily.py` — Tambah pass 15:48

#### Konstanta:
```python
BSJP_HOUR   = 15
BSJP_MINUTE = 48
TOP_N_BSJP  = 10   # max sinyal per hari (scraper_daily.py:99)
```
> Backtest engine punya konstanta terpisah `TOP_N = 10` di `algo_backtest.py:324` — dua angka ini harus sama, kalau beda hasil backtest tidak lagi mewakili sinyal live.
Blacklist ticker dipisah ke `algo.corporate_actions.excluded_tickers(conn)` — gabungan blacklist statis kualitas manual + ticker corporate action confirmed, bukan konstanta lokal di scraper.

#### Fungsi `_compute_bsjp_score()`:

```python
def _compute_bsjp_score(row: dict, sig: dict) -> float:
    SETUP_WR = {
        "SMA5_BREAKOUT_V13": 0.784,
        "SMA5_PULLBACK_V12": 0.638,
        "BB_PULLBACK":       0.596,
        "SMA5_BREAKOUT_V11": 0.550,
        "POWER_BREAK_V21":   0.520,
        "POWER_BREAK_V22":   0.520,
    }

    def _f(v, d=0.0):
        try: return float(v) if v is not None else d
        except: return d

    sm  = _f(row.get("sm_val"))
    bm  = abs(_f(row.get("bm_val")))
    rsm = sm / (sm + bm) * 100 if (sm + bm) > 0 else 0
    rsm_n = max(0.0, min(1.0, (rsm - 60) / 40))

    sri   = _f(row.get("sri"), 1.2)
    sri_n = max(0.0, min(1.0, (sri - 1.2) / 3.8))

    setup_wr  = SETUP_WR.get(sig["setup"], 0.5)
    close_pos = max(0.0, min(1.0, _f(row.get("close_pos"), 0.5)))

    mf   = _f(row.get("mf_ratio"), 50)
    mf_n = max(0.0, min(1.0, (mf - 50) / 50))

    return round(rsm_n*0.30 + sri_n*0.25 + setup_wr*0.25 + close_pos*0.10 + mf_n*0.10, 4)
```

#### Fungsi `run_bsjp_scan()` (satu pass, implementasi aktual di `scraper/scraper_daily.py`):

Tidak ada lagi pass "estimasi" jam 15:48 diikuti "finalize" jam 16:30 dengan status ESTIMASI/CONFIRMED/INVALID —
desain itu sudah dibuang karena salah kaprah (entry BSJP memang selalu final: `eod_summary.price_close`,
bukan harga live yang perlu dikonfirmasi ulang). Sekarang cuma satu fungsi, satu kali jalan per hari:

```python
def run_bsjp_scan(conn, date_dmy: str | None = None):
    """Generate BSJP signals — single pass, top-15 by score."""
    from algo.algo_bsjp import BSJPAlgo, _is_ara, _compute_score, _to_tick
    from algo.corporate_actions import excluded_tickers

    algo = BSJPAlgo()
    excluded = excluded_tickers(conn)   # blacklist statis + corporate action confirmed

    # eod_summary (hari ini) + candle 15:45 & 09:00 (price_history_15m) wajib ada
    # keduanya — dipakai HANYA untuk cek kondisi setup (arah gerak intraday),
    # bukan sebagai entry. Entry selalu eod_summary.price_close (tick-rounded).
    scored = []
    for row in eod_rows:
        if row["ticker"] in excluded:
            continue
        row_scan = dict(row)
        row_scan["price_close"]      = close_1545   # dari price_history_15m
        row_scan["price_change_pct"] = (close_1545 - open_0900) / open_0900 * 100
        if _is_ara(row_scan):
            continue
        sig = algo.signal_detail(row["ticker"], row_scan)
        if not sig:
            continue
        sig["entry"] = _to_tick(row["price_close"])           # entry final, bukan estimasi
        sig["tp1"]   = _to_tick(row["price_close"] * 1.01)
        sig["tp2"]   = _to_tick(row["price_close"] * 1.02)
        score = _compute_score(row_scan, sig["setup"])
        scored.append((score, row["ticker"], sig, row_scan))

    scored.sort(key=lambda x: -x[0])
    top = scored[:TOP_N_BSJP]

    # DELETE + INSERT ulang bsjp_signals untuk tanggal ini, tanpa kolom status
```

Karena entry sudah final sejak awal, tidak ada lagi konsep "sinyal batal setelah recompute" — sinyal yang tidak lolos gate/setup memang tidak pernah masuk tabel, bukan disimpan lalu ditandai invalid.

### 9.3 `app.py` — Register blueprint

```python
from routes.routes_bsjp import bp_bsjp
app.register_blueprint(bp_bsjp)
```

---

## 10. Data Flow

```
eod_summary (hari ini) + price_history_15m (candle 15:45 & 09:00, cek kondisi setup saja)
→ exclude blacklist + corporate action (algo.corporate_actions.excluded_tickers)
→ SM Gate + 6 setup + per-setup RPR filter
→ compute score → sort → top-15
→ DELETE + INSERT bsjp_signals untuk tanggal ini (satu baris final per ticker)
```

Tidak ada pass kedua, tidak ada recompute, tidak ada status. Kalau sebuah ticker tidak lolos gate/setup, dia
tidak pernah muncul di `bsjp_signals` — bukan muncul dulu lalu ditandai gagal.

---

## 11. Frontend — Template `bsjp.html`

```
Sinyal BSJP — [tanggal hari ini]

[⚠️ Warning jika IHSG hari ini turun > 1.5%: "Pasar Melemah — pertimbangkan skip"]

Tabel (sorted by score DESC, max 15 rows):
  Rank | Ticker | Setup | Entry | TP1 | TP2 | SL | Score | Lot
```

Hasil eksekusi trade (kena TP/SL/NO_TARGET keesokan harinya) dicatat terpisah di `bsjp_results`
(kolom `status`: `Berhasil`/`Gagal`, `reason`: `TP1`/`TP2`/`SL`/`SL[gap]`/`NO_TARGET`, dst — lihat
`eval_exit_15m()` di `algo/algo_bsjp.py`). Itu status *hasil exit*, bukan status *validitas sinyal*.

---

## 12. API Response Format

### `GET /api/bsjp/signals`

```json
{
  "success": true,
  "date": "16-05-2026",
  "count": 12,
  "signals": [
    {
      "day_rank": 1,
      "ticker": "BBRI",
      "setup": "SMA5_BREAKOUT_V13",
      "entry": 4185,
      "tp1": 4227,
      "tp2": 4269,
      "sl": 4100,
      "sl_type": "MA5",
      "score": 0.8234,
      "lot_size": 2390
    }
  ]
}
```

---

## 13. Checklist Implementasi

- [x] Buat `algo/algo_bsjp.py` (6 setup — BB_REVERSAL tidak ada)
- [x] Tambah tabel `bsjp_signals` di `core/db_schema.py` (include `day_rank`, `lot_size`, tanpa kolom status)
- [x] Tambah `_compute_score()` di `algo/algo_bsjp.py`
- [x] Tambah `run_bsjp_scan()` — satu pass — di `scraper/scraper_daily.py`
- [x] Tambah konstanta `BSJP_HOUR=15`, `BSJP_MINUTE=48`, `TOP_N_BSJP=10`
- [x] Blacklist + corporate action exclusion via `algo/corporate_actions.py`
- [x] Buat `routes/routes_bsjp.py`
- [x] Register blueprint di `app.py`
- [x] Buat `templates/bsjp.html` (include market warning IHSG < -1.5%)

---

*Dokumen ini diperbarui: desain dua-pass ESTIMASI/CONFIRMED/INVALID dibuang — implementasi aktual satu pass.*
*WR historis perlu diupdate secara berkala seiring data backtest bertambah (target: update tiap 90 hari).*
*WR historis perlu diupdate secara berkala seiring data backtest bertambah (target: update tiap 90 hari).*
