# DataSectors API Reference

> Sumber: `https://api.datasectors.com/openapi.json` (public, tanpa auth)  
> Docs UI: `https://api.datasectors.com/docs` (JS-rendered, tidak bisa di-WebFetch langsung — gunakan openapi.json)  
> Base URL: `https://api.datasectors.com`  
> Auth: `Authorization: Bearer <DS_API_KEY>` (header)  
> Key di project: `config.DS_API_KEY` ← dari env var `DATASECTORS_API_KEY`

---

## Cara Akses Docs

```bash
# Fetch semua endpoint via OpenAPI spec (public, tanpa auth):
curl https://api.datasectors.com/openapi.json

# Fetch dengan WebFetch tool:
# url: https://api.datasectors.com/openapi.json
# (JANGAN pakai url /docs — itu JS-rendered, hasilnya kosong)
```

---

## Semua Endpoint (79 total)

### Documentation & Reference
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/docs/chart-v2` | Guide untuk Chart V2 endpoints |
| GET | `/api/docs/investor-activity` | Guide untuk investor activity |
| GET | `/api/docs/smartmoney` | Guide untuk smart money tracking |
| GET | `/api/docs/timezones` | List semua timezone GMT yang didukung |
| GET | `/api/docs/countries` | List semua country code yang didukung |

### Search
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/search/market` | Cari trading market dan symbol |

### Chart Data (Global)
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/chart/price` | Fetch OHLCV price data |
| GET | `/api/chart/historical` | OHLCV sebelum tanggal tertentu |
| GET | `/api/chart/range` | OHLCV antara dua tanggal |
| GET | `/api/chart/custom-type` | Data dengan custom chart type |

### Chart Saham (IDX — Saham Indonesia) ⭐
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/chart-saham/{symbol}/{timeframe}` | OHLCV candle untuk saham IDX |
| GET | `/api/chart-saham/{symbol}/{timeframe}/latest` | Candle terbaru saja (efisien) |

**Timeframe yang didukung:** `15m`, `1h`, `daily`

**Contoh request:**
```bash
curl "https://api.datasectors.com/api/chart-saham/DSSA/daily?from=2026-07-01&to=2026-07-12" \
  -H "Authorization: Bearer <DS_API_KEY>"
```

**Contoh response (field per candle — dari live test DSSA 2026-07-10):**
```json
{
  "date": "2026-07-10",
  "unixdate": 1783616400,
  "open": 790,
  "high": 795,
  "low": 775,
  "close": 785,
  "volume": 266957000,
  "value": 209914099000,
  "frequency": 14987,
  "foreignbuy": 121200060000,
  "foreignsell": 113415938000,
  "foreignflow": -1820681371268,
  "soxclose": 151220892800000,
  "shareoutstanding": 192638080000,
  "dividend": 0,
  "freq_analyzer": 79.30
}
```

**Field penting:**
- `foreignbuy` / `foreignsell` — aliran dana asing (Rp), berguna untuk konfirmasi institutional
- `foreignflow` — kumulatif net foreign flow (negatif = net jual asing)
- `freq_analyzer` — skor frekuensi (0–100), definisi belum dikonfirmasi
- `value` — nilai transaksi harian (Rp)
- `shareoutstanding` — saham beredar (untuk hitung market cap)
- `dividend` — flag dividen hari itu

### Chart V2 (Global Multi-Provider)
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/chart/v2/data-provider` | Cari instrumen + data provider tersedia |
| GET | `/api/chart/v2/timeseries` | OHLC candle untuk symbol apapun |

### Stocks ⭐
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/stocks/earnings/events` | Earnings calendar (range tanggal) |
| GET | `/api/stocks/earnings/details/:ticker` | Detail earnings per ticker |
| GET | `/api/stocks/dividends/events` | Dividends calendar (range tanggal) |
| GET | `/api/stocks/dividends/details/:ticker` | Detail dividen per ticker |
| GET | `/api/stocks/ipo/events` | IPO calendar (range tanggal) |
| GET | `/api/stocks/splits/events` | Stock splits calendar |
| GET | `/api/stocks/splits/details/:ticker` | Detail splits per ticker |
| GET | `/api/stocks/investors/list` | Mapping investor slug → CIK |
| GET | `/api/stocks/investors/portfolio` | Holdings investor tertentu |
| GET | `/api/stocks/investors/trade-activity` | Trade activity investor dalam range |
| GET | `/api/stocks/smartmoney/guru-consensus` | Saham yang dipegang 2+ guru |
| GET | `/api/stocks/smartmoney/guru-performance` | Performa top holdings guru |
| GET | `/api/stocks/smartmoney/institutional-flow` | Rasio buy vs sell institutional |

> ⚠️ `investors/*` dan `smartmoney/*` berbasis SEC filing (US market). Kemungkinan tidak relevan untuk IDX.

### Stocks V2 (Beta) ⭐
| Method | Path | Params | Deskripsi |
|---|---|---|---|
| GET | `/api/stocks/v2/search` | `symbol`, `market` | Validasi symbol + info dasar perusahaan |
| GET | `/api/stocks/v2/earnings` | `symbol`, `market` | EPS history/forecast, earnings surprise, tanggal rilis |
| GET | `/api/stocks/v2/equities` | `symbol`, `market` | Financial statements, key metrics, analyst estimates |
| GET | `/api/stocks/v2/insights` | `symbol`, `market` | Valuation, earnings growth, health metrics vs peers |
| GET | `/api/stocks/v2/key-ratios` | `symbol`, `market` | P/E, P/B, ROE, dll vs industry average + historical |

**Default `market`: `id-id` (Indonesia)**

**Contoh request:**
```bash
curl "https://api.datasectors.com/api/stocks/v2/insights?symbol=DSSA&market=id-id" \
  -H "Authorization: Bearer <DS_API_KEY>"

curl "https://api.datasectors.com/api/stocks/v2/key-ratios?symbol=DSSA&market=id-id" \
  -H "Authorization: Bearer <DS_API_KEY>"
```

> ⚠️ Response schema belum di-test live. Perlu di-explore sebelum implement scoring.

### Analysis & Indicators ⭐
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/analysis` | Technical analysis Buy/Sell/Neutral recommendation |
| GET | `/api/analysis/forex-orderbook` | Order/position book untuk forex |

**`/api/analysis`** menarik untuk Wyckoff scoring: konfirmasi independen dari DataSectors sendiri.

### Moving Average Indicators
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/indicator/ma/sma` | Simple Moving Average |
| GET | `/api/indicator/ma/ema` | Exponential Moving Average |
| GET | `/api/indicator/ma/dema` | Double EMA |
| GET | `/api/indicator/ma/tema` | Triple EMA |
| GET | `/api/indicator/ma/wma` | Weighted Moving Average |
| GET | `/api/indicator/ma/hma` | Hull Moving Average |
| GET | `/api/indicator/ma/vwma` | Volume Weighted MA |
| GET | `/api/indicator/ma/smma` | Smoothed MA |

### Finance News
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/news` | Berita terbaru semua market |
| GET | `/api/news/type` | Berita filtered by market type |
| GET | `/api/news/search` | Full-text search berita |
| GET | `/api/news/market-types` | Semua market type yang tersedia |

### Economic Calendar
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/calendar` | Economic calendar data |
| GET | `/api/calendar/:id` | Event ekonomi spesifik by ID |
| GET | `/api/calendar/history/today` | Data hari ini |
| GET | `/api/calendar/history/yesterday` | Data kemarin |
| GET | `/api/calendar/history/tomorrow` | Data besok |
| GET | `/api/calendar/history/this-week` | Data minggu ini |
| GET | `/api/calendar/history/last-week` | Data 7 hari terakhir |
| GET | `/api/calendar/history/next-week` | Data 7 hari ke depan |
| GET | `/api/calendar/history/this-month` | Data bulan ini |
| GET | `/api/calendar/history/last-month` | Data bulan lalu |
| GET | `/api/calendar/history/next-month` | Data bulan depan |

### Cryptocurrency
| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/crypto/events` | Crypto calendar events |
| GET | `/api/crypto/details/:ticker` | Detail crypto per ticker |
| GET | `/api/crypto/trending` | Top trending coins, NFTs, kategori |
| GET | `/api/crypto/global-heatmap` | Breakdown posisi per segmen |
| GET | `/api/crypto/walls` | Deteksi order wall besar (>3x avg) |
| GET | `/api/crypto/strong-trend` | Klasifikasi trend kekuatan coin |
| GET | `/api/crypto/correlation` | Korelasi Pearson antar crypto |
| GET | `/api/crypto/orderbook-imbalance` | Rasio imbalance orderbook |

---

## Coverage IDX

- `chart-saham/*` — confirmed IDX, sudah live test (DSSA berhasil)
- `stocks/v2/*` — kemungkinan IDX dengan `market=id-id`, belum dikonfirmasi semua ticker
- `stocks/dividends/details/:ticker` — live test PSAB: **not found** (mungkin coverage terbatas untuk mid-cap)
- `stocks/investors/*` dan `smartmoney/*` — US SEC-based, **tidak relevan untuk IDX**

---

## Relevansi untuk Wyckoff Scoring

Field dari `/api/chart-saham` yang sudah confirmed ada dan berguna:

```
foreignbuy   → konfirmasi institutional buying (dana asing)
foreignsell  → konfirmasi institutional selling
foreignflow  → kumulatif net asing (trend jangka menengah)
freq_analyzer → skor frekuensi (perlu dikonfirmasi definisinya)
```

Endpoint yang perlu di-test sebelum implement:
1. `/api/stocks/v2/insights` — health + valuation status
2. `/api/stocks/v2/key-ratios` — P/E, P/B vs industry
3. `/api/stocks/v2/earnings` — tanggal earnings berikutnya
4. `/api/analysis` — technical recommendation
