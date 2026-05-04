# ZENITH — Trade Detail Narrative Catalog
**Versi:** v3.1 | **Format:** Market Structure × Zenith Phase  
**Struktur:** 7 Market Structure × 7 Phase = 49 kombinasi + 3 Gate Override  
**Tone:** Hybrid (deskripsi kondisi + implikasi + saran singkat)  
**Bahasa:** Indonesia + istilah teknikal Inggris

---

## PANDUAN BACA

```
[STRUKTUR] + [PHASE] → Narasi + Example Case
Gate Override menganulir narasi standar jika aktif.
```

**7 Market Structure:**
1. Strong Uptrend
2. Transitional Uptrend
3. Transitional Correction
4. Strong Downtrend
5. Cluster on Macro Uptrend
6. Cluster on Macro Downtrend
7. Bullish Messy
8. Bearish Messy

**7 Zenith Phase:**
SOS · SPRING · ABSORB · ACCUM · UPTHRUST · DISTRI · NEUTRAL

---

## 1. STRONG UPTREND
> MA5 > MA13 > MA34, Price > MA200. Semua MA aligned bullish, tren besar konfirmasi.

---

### 1.1 Strong Uptrend + SOS
**Narasi:**
Strongest Momentum — Smart Money sangat agresif di tengah tren yang sudah kuat. Konfluensi sempurna antara struktur MA bullish dan aksi SM, ini adalah setup dengan probabilitas tertinggi. Hati-hati FOMO di entry terlambat; pastikan tidak trigger Gate C.

**Example Case:**
```
Ticker: BBRI | Date: 15-04-2026
Price: 5,200 | MA5: 5,100 | MA13: 5,000 | MA34: 4,850 | MA200: 4,600
Gap MA: ((5,100-4,850)/4,850)*100 = 5.15% ≥ 3% → Cek urutan
Urutan: MA5>MA13>MA34 & Price>MA200 → Strong Uptrend ✓
RSM: 72% | SRI: 3.8x | pchg: +3.2% | ATR: 2.1%
Phase: SOS | Action: BUY
Narasi: Strongest Momentum
```

---

### 1.2 Strong Uptrend + SPRING
**Narasi:**
Pullback Sehat — Harga koreksi sementara di tengah tren bullish yang kuat, dan SM justru akumulasi di zona ini. Ini adalah "buy the dip" klasik dalam strong uptrend; setup sangat menarik jika RSM dan SRI confirm. Entry di zona SPRING dengan struktur MA intact adalah opportunity premium.

**Example Case:**
```
Ticker: UNTR | Date: 10-04-2026
Price: 14,800 | MA5: 14,900 | MA13: 14,700 | MA34: 14,400 | MA200: 13,500
Gap MA: ((14,900-14,400)/14,400)*100 = 3.47% ≥ 3% → Strong Uptrend
pchg: -2.8% | ATR: 2.0% | RSM: 67% | SRI: 2.2x
Phase: SPRING | Action: BUY
Narasi: Pullback Sehat
```

---

### 1.3 Strong Uptrend + ABSORB
**Narasi:**
Silent Accumulation in Trend — SM mengakumulasi diam-diam tanpa banyak gerak harga, sementara struktur MA masih fully bullish. Kombinasi ini sering mendahului breakout berikutnya. Volume rendah tapi SM aktif = distribusi tersembunyi yang positif.

**Example Case:**
```
Ticker: ACES | Date: 08-04-2026
Price: 830 | MA5: 828 | MA13: 820 | MA34: 808 | MA200: 750
Gap MA: ((828-808)/808)*100 = 2.47% < 3% → ... tunggu
Hmm, recalculate: MA5 828, MA13 820, MA34 808
((828-808)/808)*100 = 2.47% < 3% → Sideways/Cluster
→ Seharusnya masuk Cluster on Macro Uptrend (lihat section 5)

[KOREKSI CASE - yang benar untuk Strong Uptrend + ABSORB:]
Price: 830 | MA5: 828 | MA13: 812 | MA34: 795 | MA200: 730
Gap MA: ((828-795)/795)*100 = 4.15% ≥ 3% → Strong Uptrend
pchg: +0.3% | ATR: 1.8% | RSM: 68% | SRI: 2.5x
Phase: ABSORB | Action: BUY
Narasi: Silent Accumulation in Trend
```

---

### 1.4 Strong Uptrend + ACCUM
**Narasi:**
Steady Climb — SM mengakumulasi secara bertahap dengan tren yang fully aligned. Tidak ada urgency tinggi, tapi ini adalah posisi yang nyaman untuk hold atau tambah posisi secara gradual. Risiko rendah karena struktur makro mendukung penuh.

**Example Case:**
```
Ticker: TLKM | Date: 12-04-2026
Price: 3,800 | MA5: 3,770 | MA13: 3,720 | MA34: 3,650 | MA200: 3,400
Gap MA: ((3,770-3,650)/3,650)*100 = 3.29% ≥ 3% → Strong Uptrend
RSM: 63% | SRI: 1.4x | pchg: +0.8%
Phase: ACCUM | Action: BUY
Narasi: Steady Climb
```

---

### 1.5 Strong Uptrend + UPTHRUST
**Narasi:**
Trap di Puncak Tren — Harga naik tinggi tapi BM dominan dan RPR lemah, sinyal jebakan distribusi meski struktur MA masih bullish. Ini warning penting: MA bisa lag terhadap perubahan arah. Waspadai potensi reversal jangka pendek meski tren besar masih intact.

**Example Case:**
```
Ticker: ASII | Date: 17-04-2026
Price: 6,200 | MA5: 6,100 | MA13: 5,980 | MA34: 5,800 | MA200: 5,500
Gap MA: ((6,100-5,800)/5,800)*100 = 5.17% → Strong Uptrend
RSM: 32% | pchg: +3.5% | RPR: 0.75 | SRI: 0.8x
Phase: UPTHRUST | Action: SELL
Narasi: Trap di Puncak Tren
```

---

### 1.6 Strong Uptrend + DISTRI
**Narasi:**
Distribusi Tersembunyi — BM mulai aktif mendistribusi meski MA masih bullish aligned. Ini adalah early warning sign sebelum tren berbalik; MA biasanya lag beberapa hari. Hold posisi lama dengan trailing stop, hindari entry baru sampai ada konfirmasi.

**Example Case:**
```
Ticker: BMRI | Date: 20-04-2026
Price: 7,100 | MA5: 7,050 | MA13: 6,900 | MA34: 6,700 | MA200: 6,200
Gap MA: ((7,050-6,700)/6,700)*100 = 5.22% → Strong Uptrend
RSM: 34% | pchg: -1.8% | RPR: 0.62 | bm_gate: active
Phase: DISTRI | Action: SELL
Narasi: Distribusi Tersembunyi
```

---

### 1.7 Strong Uptrend + NEUTRAL
**Narasi:**
Konsolidasi dalam Tren Kuat — Tidak ada aksi SM atau BM yang dominan hari ini, pasar istirahat sejenak. Struktur MA masih bullish penuh; ini bukan sinyal untuk keluar. Hold posisi, tunggu fase berikutnya yang kemungkinan besar masih bullish.

**Example Case:**
```
Ticker: PGAS | Date: 14-04-2026
Price: 1,650 | MA5: 1,630 | MA13: 1,600 | MA34: 1,565 | MA200: 1,450
Gap MA: 4.1% → Strong Uptrend
RSM: 52% | SRI: 0.8x | pchg: +0.4%
Phase: NEUTRAL | Action: HOLD
Narasi: Konsolidasi dalam Tren Kuat
```

---

## 2. TRANSITIONAL UPTREND
> MA5 > MA13 > MA34, Price < MA200. Momentum pendek-menengah bullish, tapi belum tembus filter makro.

---

### 2.1 Transitional Uptrend + SOS
**Narasi:**
Recovery Agresif — SM masuk besar-besaran dalam fase pemulihan awal, tapi MA200 masih di atas sebagai resistance besar. Sinyal kuat untuk jangka pendek-menengah, tapi harga masih harus membuktikan diri dengan break MA200. Entry menarik dengan awareness bahwa ada resistance signifikan di depan.

**Example Case:**
```
Ticker: ADRO | Date: 05-04-2026
Price: 2,450 | MA5: 2,420 | MA13: 2,380 | MA34: 2,310 | MA200: 2,600
Gap MA: ((2,420-2,310)/2,310)*100 = 4.76% → Cek urutan
MA5>MA13>MA34 ✓ | Price 2,450 < MA200 2,600 → Transitional Uptrend
RSM: 71% | SRI: 3.5x | pchg: +4.1%
Phase: SOS | Action: BUY
Narasi: Recovery Agresif
```

---

### 2.2 Transitional Uptrend + SPRING
**Narasi:**
Dip dalam Recovery — Harga koreksi sementara di tengah fase pemulihan yang belum selesai, SM tetap akumulasi. Double-layered risk: belum break MA200 dan harga turun. Namun jika SRI dan RSM kuat, ini bisa jadi entry second chance yang bagus dalam recovery play.

**Example Case:**
```
Ticker: INCO | Date: 07-04-2026
Price: 3,800 | MA5: 3,850 | MA13: 3,780 | MA34: 3,680 | MA200: 4,100
Gap MA: ((3,850-3,680)/3,680)*100 = 4.62% → Transitional Uptrend
RSM: 65% | SRI: 1.9x | pchg: -2.3%
Phase: SPRING | Action: BUY
Narasi: Dip dalam Recovery
```

---

### 2.3 Transitional Uptrend + ABSORB
**Narasi:**
Akumulasi Diam-diam Sebelum Break — SM mengakumulasi dengan tenang sementara harga flat, membangun energi untuk potensi break MA200. Patience diperlukan; ini adalah setup jangka menengah yang menjanjikan tapi belum ada katalis langsung.

**Example Case:**
```
Ticker: ANTM | Date: 09-04-2026
Price: 1,580 | MA5: 1,575 | MA13: 1,555 | MA34: 1,520 | MA200: 1,680
Gap MA: 3.62% → Transitional Uptrend
RSM: 67% | SRI: 2.3x | pchg: +0.2%
Phase: ABSORB | Action: BUY
Narasi: Akumulasi Diam-diam Sebelum Break
```

---

### 2.4 Transitional Uptrend + ACCUM
**Narasi:**
Pemulihan Bertahap — Momentum bullish jangka pendek terbentuk perlahan, SM mulai masuk secara gradual meski MA200 masih jadi ceiling. Cocok untuk akumulasi bertahap dengan position sizing konservatif; avoid all-in karena resistance makro masih ada.

**Example Case:**
```
Ticker: PTBA | Date: 11-04-2026
Price: 2,700 | MA5: 2,680 | MA13: 2,640 | MA34: 2,580 | MA200: 2,900
Gap MA: 3.88% → Transitional Uptrend
RSM: 62% | SRI: 1.2x | pchg: +0.6%
Phase: ACCUM | Action: BUY
Narasi: Pemulihan Bertahap
```

---

### 2.5 Transitional Uptrend + UPTHRUST
**Narasi:**
Fake Recovery — Harga naik tapi BM mendominasi transaksi, membuat rally dalam recovery terlihat seperti jebakan distribusi. Dengan MA200 masih di atas sebagai overhead resistance, ini adalah sinyal sangat berbahaya. Hindari entry, pertimbangkan exit jika sudah punya posisi.

**Example Case:**
```
Ticker: MEDC | Date: 13-04-2026
Price: 1,050 | MA5: 1,030 | MA13: 1,010 | MA34: 985 | MA200: 1,150
Gap MA: 4.57% → Transitional Uptrend
RSM: 30% | pchg: +2.8% | RPR: 0.78
Phase: UPTHRUST | Action: SELL
Narasi: Fake Recovery
```

---

### 2.6 Transitional Uptrend + DISTRI
**Narasi:**
Recovery Terancam — Momentum pemulihan terganggu oleh distribusi aktif BM. Dengan MA200 masih di atas, ini bisa menjadi awal dari kegagalan recovery dan kelanjutan downtrend. Sinyal untuk reduce exposure; tunggu konfirmasi sebelum re-entry.

**Example Case:**
```
Ticker: HRUM | Date: 15-04-2026
Price: 1,320 | MA5: 1,300 | MA13: 1,270 | MA34: 1,230 | MA200: 1,450
Gap MA: 5.69% → Transitional Uptrend
RSM: 36% | pchg: -2.1% | RPR: 0.58 | bm_gate: active
Phase: DISTRI | Action: SELL
Narasi: Recovery Terancam
```

---

### 2.7 Transitional Uptrend + NEUTRAL
**Narasi:**
Jeda dalam Recovery — Pasar pause, tidak ada dominasi SM atau BM hari ini. Tren pemulihan masih intact tapi belum ada dorongan baru. Hold, dan tunggu konfirmasi arah berikutnya; MA200 masih jadi target resistance yang perlu diperhatikan.

**Example Case:**
```
Ticker: ELSA | Date: 16-04-2026
Price: 425 | MA5: 422 | MA13: 415 | MA34: 405 | MA200: 460
Gap MA: 4.2% → Transitional Uptrend
RSM: 54% | SRI: 0.9x | pchg: +0.3%
Phase: NEUTRAL | Action: HOLD
Narasi: Jeda dalam Recovery
```

---

## 3. TRANSITIONAL CORRECTION
> MA5 < MA13 < MA34, Price > MA200. Tekanan jual jangka pendek, tapi makro masih bullish.

---

### 3.1 Transitional Correction + SOS
**Narasi:**
Counter-Rally Kuat — SM masuk agresif di tengah tekanan jual jangka pendek, dengan MA200 masih sebagai support besar di bawah. Ini sinyal reversal jangka pendek yang menarik; potensi bounce dari zona koreksi. Entry kalkulatif dengan target kembali ke area MA34 atau lebih tinggi.

**Example Case:**
```
Ticker: BBCA | Date: 18-04-2026
Price: 9,500 | MA5: 9,480 | MA13: 9,550 | MA34: 9,650 | MA200: 9,000
Gap MA: ((9,650-9,480)/9,480)*100 = 1.79% < 3% → Cluster
→ [Koreksi: adjust angka]

Price: 9,500 | MA5: 9,400 | MA13: 9,600 | MA34: 9,820 | MA200: 9,000
Gap MA: ((9,820-9,400)/9,400)*100 = 4.47% → Cek urutan
MA5 < MA13 < MA34 ✓ | Price 9,500 > MA200 9,000 → Transitional Correction
RSM: 70% | SRI: 3.2x | pchg: +3.8%
Phase: SOS | Action: BUY
Narasi: Counter-Rally Kuat
```

---

### 3.2 Transitional Correction + SPRING
**Narasi:**
Bounce dari Support Makro — Harga turun lebih dalam tapi SM aktif akumulasi, dengan MA200 di bawah sebagai safety net. Setup SPRING dalam konteks koreksi makro bullish adalah salah satu setup terbaik untuk swing entry; risiko relatif terbatas karena floor makro jelas.

**Example Case:**
```
Ticker: BBNI | Date: 19-04-2026
Price: 4,200 | MA5: 4,150 | MA13: 4,280 | MA34: 4,420 | MA200: 3,900
Gap MA: ((4,420-4,150)/4,150)*100 = 6.5% → Transitional Correction
RSM: 66% | SRI: 2.0x | pchg: -3.1%
Phase: SPRING | Action: BUY
Narasi: Bounce dari Support Makro
```

---

### 3.3 Transitional Correction + ABSORB
**Narasi:**
Akumulasi di Koreksi — SM diam-diam membeli saat harga flat dalam periode koreksi, sinyal bahwa big players tidak panik meski MA jangka pendek bearish. Dengan MA200 masih sebagai safety net, ini setup yang menjanjikan untuk entry gradual.

**Example Case:**
```
Ticker: SMGR | Date: 21-04-2026
Price: 5,600 | MA5: 5,550 | MA13: 5,680 | MA34: 5,800 | MA200: 5,200
Gap MA: ((5,800-5,550)/5,550)*100 = 4.5% → Transitional Correction
RSM: 68% | SRI: 2.4x | pchg: -0.2% | abs(pchg): 0.2% < th_flat
Phase: ABSORB | Action: BUY
Narasi: Akumulasi di Koreksi
```

---

### 3.4 Transitional Correction + ACCUM
**Narasi:**
Akumulasi Defensif — SM mulai masuk secara perlahan di zona koreksi, meski belum dengan intensitas tinggi. Posisi makro masih mendukung (Price > MA200); ini fase persiapan sebelum potensi reversal. Cocok untuk gradual entry dengan stop di bawah MA200.

**Example Case:**
```
Ticker: JPFA | Date: 22-04-2026
Price: 1,450 | MA5: 1,430 | MA13: 1,470 | MA34: 1,520 | MA200: 1,350
Gap MA: ((1,520-1,430)/1,430)*100 = 6.3% → Transitional Correction
RSM: 61% | SRI: 1.1x | pchg: -0.5%
Phase: ACCUM | Action: BUY
Narasi: Akumulasi Defensif
```

---

### 3.5 Transitional Correction + UPTHRUST
**Narasi:**
Dead Cat Bounce — Harga sempat naik tapi BM yang dominan; bounce ini tidak genuine. Dalam konteks koreksi jangka pendek yang sudah berjalan, UPTHRUST menandakan tekanan jual belum selesai. Exit atau hold cash; bukan waktu untuk beli.

**Example Case:**
```
Ticker: SIDO | Date: 23-04-2026
Price: 680 | MA5: 672 | MA13: 690 | MA34: 715 | MA200: 620
Gap MA: ((715-672)/672)*100 = 6.4% → Transitional Correction
RSM: 29% | pchg: +2.2% | RPR: 0.81
Phase: UPTHRUST | Action: SELL
Narasi: Dead Cat Bounce
```

---

### 3.6 Transitional Correction + DISTRI
**Narasi:**
Koreksi Diperdalam — BM aktif mendistribusi di tengah koreksi yang sudah berjalan; tekanan jual bertambah. Meskipun MA200 masih di bawah sebagai support, momentum bearish jangka pendek bisa mendorong harga lebih turun sebelum bounce. Reduce exposure.

**Example Case:**
```
Ticker: ICBP | Date: 24-04-2026
Price: 9,800 | MA5: 9,700 | MA13: 9,920 | MA34: 10,150 | MA200: 9,200
Gap MA: ((10,150-9,700)/9,700)*100 = 4.64% → Transitional Correction
RSM: 33% | pchg: -2.5% | RPR: 0.66 | bm_gate: active
Phase: DISTRI | Action: SELL
Narasi: Koreksi Diperdalam
```

---

### 3.7 Transitional Correction + NEUTRAL
**Narasi:**
Koreksi Tanpa Arah Jelas — Tidak ada dominasi SM atau BM, pasar bergerak sideways dalam zona koreksi. MA200 masih di bawah sebagai safety net. Situasi wait-and-see; pantau apakah SM mulai masuk (SPRING/ACCUM) atau BM semakin dominan (DISTRI).

**Example Case:**
```
Ticker: MYOR | Date: 25-04-2026
Price: 2,050 | MA5: 2,030 | MA13: 2,080 | MA34: 2,130 | MA200: 1,900
Gap MA: 4.9% → Transitional Correction
RSM: 51% | SRI: 0.7x | pchg: -0.4%
Phase: NEUTRAL | Action: HOLD
Narasi: Koreksi Tanpa Arah Jelas
```

---

## 4. STRONG DOWNTREND
> MA5 < MA13 < MA34, Price < MA200. Semua MA aligned bearish, tren besar konfirmasi turun.

---

### 4.1 Strong Downtrend + SOS
**Narasi:**
Counter-Rally dalam Downtrend — SM masuk agresif tapi melawan arus tren besar yang sepenuhnya bearish. Ini bisa jadi bounce signifikan tapi bukan reversal; MA200 dan MA34 di atas sebagai resistance berlapis. Trading jangka sangat pendek dengan risk management ketat; jangan hold lama.

**Example Case:**
```
Ticker: KRAS | Date: 05-05-2026
Price: 1,100 | MA5: 1,120 | MA13: 1,180 | MA34: 1,250 | MA200: 1,400
Gap MA: ((1,250-1,120)/1,120)*100 = 11.6% → Strong Downtrend
RSM: 72% | SRI: 3.6x | pchg: +4.2%
Phase: SOS | Action: BUY
⚠️ Note: Konfluensi bertentangan — high risk counter-trend
Narasi: Counter-Rally dalam Downtrend
```

---

### 4.2 Strong Downtrend + SPRING
**Narasi:**
Potensi Capitulation Bottom — Harga turun tajam dengan SM akumulasi di zona yang sangat tertekan. Dalam strong downtrend, SPRING bisa menjadi tanda capitulation (akhir dari tekanan jual besar). Setup sangat high-risk, high-reward; perlu konfirmasi kuat (SRI > 2.5, RSM > 65%) sebelum pertimbangkan entry.

**Example Case:**
```
Ticker: WIKA | Date: 06-05-2026
Price: 520 | MA5: 535 | MA13: 580 | MA34: 640 | MA200: 800
Gap MA: ((640-535)/535)*100 = 19.6% → Strong Downtrend
RSM: 66% | SRI: 2.1x | pchg: -4.5%
Phase: SPRING | Action: BUY (high risk)
Narasi: Potensi Capitulation Bottom
```

---

### 4.3 Strong Downtrend + ABSORB
**Narasi:**
Akumulasi Melawan Arus — SM diam-diam membeli di tengah downtrend yang masih kuat. Bisa jadi early signal reversal jangka panjang, tapi premature untuk entry; tren besar masih bearish dan semua MA di atas sebagai resistance. Watch tapi tidak act dulu.

**Example Case:**
```
Ticker: BUMI | Date: 07-05-2026
Price: 68 | MA5: 72 | MA13: 80 | MA34: 92 | MA200: 120
Gap MA: ((92-72)/72)*100 = 27.8% → Strong Downtrend
RSM: 68% | SRI: 2.6x | pchg: +0.1%
Phase: ABSORB | Action: BUY (low conviction)
Narasi: Akumulasi Melawan Arus
```

---

### 4.4 Strong Downtrend + ACCUM
**Narasi:**
Akumulasi Awal di Downtrend Dalam — SM mulai masuk perlahan meski tren besar masih turun. Sinyal terlalu dini untuk action; perlu konfirmasi beberapa hari sebelum struktur MA berubah. Pantau apakah akumulasi ini berkembang menjadi ABSORB atau SOS.

**Example Case:**
```
Ticker: SIMP | Date: 08-05-2026
Price: 340 | MA5: 352 | MA13: 375 | MA34: 405 | MA200: 480
Gap MA: ((405-352)/352)*100 = 15.1% → Strong Downtrend
RSM: 62% | SRI: 1.3x | pchg: -0.6%
Phase: ACCUM | Action: HOLD
Narasi: Akumulasi Awal di Downtrend Dalam
```

---

### 4.5 Strong Downtrend + UPTHRUST
**Narasi:**
Jebakan Bull dalam Downtrend — Harga sempat naik tapi BM dominan; ini adalah relief rally palsu yang sangat berbahaya. Dalam strong downtrend, UPTHRUST adalah konfirmasi bahwa tekanan jual masih kuat dan banyak yang terjebak di harga tinggi. Sinyal SELL paling meyakinkan.

**Example Case:**
```
Ticker: KIJA | Date: 09-05-2026
Price: 142 | MA5: 148 | MA13: 162 | MA34: 178 | MA200: 220
Gap MA: ((178-148)/148)*100 = 20.3% → Strong Downtrend
RSM: 28% | pchg: +3.1% | RPR: 0.82
Phase: UPTHRUST | Action: SELL
Narasi: Jebakan Bull dalam Downtrend
```

---

### 4.6 Strong Downtrend + DISTRI
**Narasi:**
Downtrend Diperkuat — BM aktif mendistribusi dengan semua MA masih bearish; ini adalah konfirmasi downtrend paling kuat. Tidak ada alasan untuk hold, apalagi beli. Jika belum exit, ini momentum terakhir sebelum harga turun lebih dalam.

**Example Case:**
```
Ticker: ROTI | Date: 10-05-2026
Price: 860 | MA5: 880 | MA13: 935 | MA34: 1,010 | MA200: 1,180
Gap MA: ((1,010-880)/880)*100 = 14.8% → Strong Downtrend
RSM: 31% | pchg: -3.2% | RPR: 0.71 | bm_gate: active
Phase: DISTRI | Action: SELL
Narasi: Downtrend Diperkuat
```

---

### 4.7 Strong Downtrend + NEUTRAL
**Narasi:**
Downtrend Tanpa Katalis Baru — Tidak ada aksi dominan hari ini, tapi semua MA masih bearish aligned. Ini bukan tanda reversal; hanya jeda sementara. Jangan terjebak dengan quiet market dalam downtrend; stay out atau pertahankan short position.

**Example Case:**
```
Ticker: AIMS | Date: 11-05-2026
Price: 195 | MA5: 200 | MA13: 215 | MA34: 232 | MA200: 280
Gap MA: 16% → Strong Downtrend
RSM: 49% | SRI: 0.6x | pchg: -0.3%
Phase: NEUTRAL | Action: HOLD (no new entry)
Narasi: Downtrend Tanpa Katalis Baru
```

---

## 5. CLUSTER ON MACRO UPTREND
> Gap MA5/13/34 < 3%, Price > MA200. Konsolidasi ketat di atas MA200.

---

### 5.1 Cluster on Macro Uptrend + SOS
**Narasi:**
Breakout dari Sideways — SM masuk besar di tengah konsolidasi yang sudah lama, dengan floor makro yang aman (Price > MA200). Setup pre-breakout klasik; jika SRI dan RSM kuat, ini sangat menarik. Harga kemungkinan besar akan keluar dari cluster dengan momentum bullish.

**Example Case:**
```
Ticker: JPFA | Date: 15-04-2026
Price: 1,420 | MA5: 1,415 | MA13: 1,408 | MA34: 1,398 | MA200: 1,250
Gap MA: ((1,415-1,398)/1,398)*100 = 1.22% < 3% → Cluster
Price 1,420 > MA200 1,250 → Cluster on Macro Uptrend
RSM: 73% | SRI: 3.8x | pchg: +3.5%
Phase: SOS | Action: BUY
Narasi: Breakout dari Sideways
```

---

### 5.2 Cluster on Macro Uptrend + SPRING
**Narasi:**
Shakeout dalam Konsolidasi — Harga turun sementara keluar dari cluster tapi SM aktif akumulasi; ini classic shakeout sebelum breakout naik. Dengan MA200 aman di bawah, ini adalah zona entry yang ideal jika RSM dan SRI mendukung. Risiko rendah, reward tinggi jika breakout terjadi.

**Example Case:**
```
Ticker: SMCB | Date: 16-04-2026
Price: 960 | MA5: 970 | MA13: 975 | MA34: 968 | MA200: 850
Gap MA: ((975-968)/968)*100 = 0.72% < 3% → Cluster on Macro Uptrend
pchg: -2.8% | RSM: 67% | SRI: 2.0x
Phase: SPRING | Action: BUY
Narasi: Shakeout dalam Konsolidasi
```

---

### 5.3 Cluster on Macro Uptrend + ABSORB
**Narasi:**
Akumulasi Diam-diam dalam Konsolidasi — SM mengumpulkan posisi dengan sabar di tengah sideways yang ketat. Ini adalah fasa sebelum breakout; pasar belum notice tapi big players sudah positioning. Hold atau tambah posisi gradual; tunggu harga keluar dari cluster.

**Example Case:**
```
Ticker: CPIN | Date: 17-04-2026
Price: 5,200 | MA5: 5,185 | MA13: 5,175 | MA34: 5,162 | MA200: 4,800
Gap MA: ((5,185-5,162)/5,162)*100 = 0.45% < 3% → Cluster on Macro Uptrend
RSM: 69% | SRI: 2.8x | pchg: +0.1%
Phase: ABSORB | Action: BUY
Narasi: Akumulasi Diam-diam dalam Konsolidasi
```

---

### 5.4 Cluster on Macro Uptrend + ACCUM
**Narasi:**
Fase Akumulasi Cluster — SM masuk perlahan dalam sideways yang didukung makro bullish. Tidak ada urgency breakout segera tapi probabilitas naik lebih tinggi dari turun mengingat MA200 di bawah. Entry gradual dengan sabar; jangan chase jika harga tiba-tiba spike.

**Example Case:**
```
Ticker: WOOD | Date: 18-04-2026
Price: 275 | MA5: 273 | MA13: 272 | MA34: 270 | MA200: 240
Gap MA: ((273-270)/270)*100 = 1.11% → Cluster on Macro Uptrend
RSM: 63% | SRI: 1.2x | pchg: +0.4%
Phase: ACCUM | Action: BUY
Narasi: Fase Akumulasi Cluster
```

---

### 5.5 Cluster on Macro Uptrend + UPTHRUST
**Narasi:**
Fake Breakout di Atas Cluster — Harga sempat keluar cluster ke atas tapi BM dominan; ini false breakout klasik. Berbahaya karena banyak trader retail akan tergoda masuk saat harga tembus sideways. Hindari entry; tunggu retest dan konfirmasi SM sebelum percaya breakout ini.

**Example Case:**
```
Ticker: TINS | Date: 19-04-2026
Price: 1,560 | MA5: 1,548 | MA13: 1,542 | MA34: 1,535 | MA200: 1,400
Gap MA: 0.85% → Cluster on Macro Uptrend
RSM: 30% | pchg: +2.9% | RPR: 0.79
Phase: UPTHRUST | Action: SELL
Narasi: Fake Breakout di Atas Cluster
```

---

### 5.6 Cluster on Macro Uptrend + DISTRI
**Narasi:**
Distribusi dalam Konsolidasi — BM aktif mendistribusi meski harga masih di atas MA200; ini warning bahwa cluster ini bukan akumulasi tapi distribusi terselubung. Jika berlanjut, harga berpotensi breakdown dari cluster ke arah bawah. Reduce position; jangan tambah di sini.

**Example Case:**
```
Ticker: AISA | Date: 20-04-2026
Price: 480 | MA5: 482 | MA13: 479 | MA34: 475 | MA200: 430
Gap MA: 1.47% → Cluster on Macro Uptrend
RSM: 35% | pchg: -1.6% | RPR: 0.55 | bm_gate: active
Phase: DISTRI | Action: SELL
Narasi: Distribusi dalam Konsolidasi
```

---

### 5.7 Cluster on Macro Uptrend + NEUTRAL
**Narasi:**
Sideways Murni — Tidak ada aksi dominan, harga bergerak datar dalam cluster di atas MA200. Ini adalah fase patience; pasar sedang menentukan arah. Pantau RSM dan SRI hari-hari berikutnya; breakout dari sini biasanya cukup signifikan.

**Example Case:**
```
Ticker: DMAS | Date: 21-04-2026
Price: 218 | MA5: 217 | MA13: 216 | MA34: 215 | MA200: 195
Gap MA: 0.93% → Cluster on Macro Uptrend
RSM: 52% | SRI: 0.7x | pchg: +0.1%
Phase: NEUTRAL | Action: HOLD
Narasi: Sideways Murni
```

---

## 6. CLUSTER ON MACRO DOWNTREND
> Gap MA5/13/34 < 3%, Price < MA200. Konsolidasi ketat di bawah MA200.

---

### 6.1 Cluster on Macro Downtrend + SOS
**Narasi:**
Rally Terbatas di Bawah MA200 — SM masuk agresif dalam sideways yang tertekan secara makro. Menarik sebagai bounce play jangka pendek tapi MA200 di atas sebagai resistance berat. Jangan ekspektasi trending move; target realistis adalah tepi atas cluster atau MA200 sebagai resistance.

**Example Case:**
```
Ticker: CTRA | Date: 10-05-2026
Price: 780 | MA5: 782 | MA13: 779 | MA34: 776 | MA200: 950
Gap MA: 0.77% → Cluster on Macro Downtrend
RSM: 71% | SRI: 3.3x | pchg: +3.4%
Phase: SOS | Action: BUY (jangka pendek)
Narasi: Rally Terbatas di Bawah MA200
```

---

### 6.2 Cluster on Macro Downtrend + SPRING
**Narasi:**
Shakeout Berbahaya — Harga turun lebih dalam dari cluster yang sudah di bawah MA200; SM mencoba akumulasi di zona yang sangat tertekan. Double-risk: makro bearish dan harga jatuh dari sideways. Hanya untuk trader dengan risk tolerance tinggi dengan ukuran posisi sangat kecil.

**Example Case:**
```
Ticker: BSDE | Date: 11-05-2026
Price: 820 | MA5: 830 | MA13: 828 | MA34: 824 | MA200: 1,050
Gap MA: 0.73% → Cluster on Macro Downtrend
RSM: 64% | SRI: 1.8x | pchg: -3.5%
Phase: SPRING | Action: BUY (extreme caution)
Narasi: Shakeout Berbahaya
```

---

### 6.3 Cluster on Macro Downtrend + ABSORB
**Narasi:**
Akumulasi di Zona Berbahaya — SM diam-diam membeli di cluster yang berada di bawah MA200. Sinyal awal bottom fishing oleh big players, tapi masih terlalu dini. Pantau beberapa hari; jika RSM dan SRI terus naik, bisa jadi awal reversal jangka panjang.

**Example Case:**
```
Ticker: PWON | Date: 12-05-2026
Price: 440 | MA5: 442 | MA13: 441 | MA34: 439 | MA200: 580
Gap MA: 0.68% → Cluster on Macro Downtrend
RSM: 67% | SRI: 2.2x | pchg: +0.2%
Phase: ABSORB | Action: HOLD (observe)
Narasi: Akumulasi di Zona Berbahaya
```

---

### 6.4 Cluster on Macro Downtrend + ACCUM
**Narasi:**
Akumulasi Sabar di Bawah Makro Bearish — SM mulai masuk perlahan meski kondisi makro tidak mendukung. Ini bisa jadi akumulasi jangka panjang (months), bukan sinyal entry segera. Tidak direkomendasikan untuk swing trader; mungkin relevan untuk investor jangka panjang saja.

**Example Case:**
```
Ticker: BEST | Date: 13-05-2026
Price: 152 | MA5: 153 | MA13: 152 | MA34: 151 | MA200: 200
Gap MA: 1.32% → Cluster on Macro Downtrend
RSM: 62% | SRI: 1.1x | pchg: +0.3%
Phase: ACCUM | Action: HOLD
Narasi: Akumulasi Sabar di Bawah Makro Bearish
```

---

### 6.5 Cluster on Macro Downtrend + UPTHRUST
**Narasi:**
Jebakan di Zona Merah — False breakout di atas cluster yang sudah tertekan makro; BM mendominasi dan MA200 jauh di atas sebagai ceiling. Salah satu setup paling berbahaya — buyer retail terjebak sementara BM distribusi aktif. SELL atau stay out.

**Example Case:**
```
Ticker: SSIA | Date: 14-05-2026
Price: 385 | MA5: 383 | MA13: 381 | MA34: 379 | MA200: 520
Gap MA: 1.05% → Cluster on Macro Downtrend
RSM: 27% | pchg: +2.7% | RPR: 0.84
Phase: UPTHRUST | Action: SELL
Narasi: Jebakan di Zona Merah
```

---

### 6.6 Cluster on Macro Downtrend + DISTRI
**Narasi:**
Silent Exit — BM mendistribusi secara tenang dalam sideways yang sudah di bawah MA200; ini adalah tanda bahwa big players sedang keluar secara halus sebelum breakdown. Konfirmasi bearish paling kuat dalam konteks ini. Segera reduce atau exit posisi.

**Example Case:**
```
Ticker: KBLI | Date: 15-05-2026
Price: 285 | MA5: 287 | MA13: 286 | MA34: 284 | MA200: 380
Gap MA: 1.06% → Cluster on Macro Downtrend
RSM: 33% | pchg: -1.8% | RPR: 0.60 | bm_gate: active
Phase: DISTRI | Action: SELL
Narasi: Silent Exit
```

---

### 6.7 Cluster on Macro Downtrend + NEUTRAL
**Narasi:**
Dead Zone — Tidak ada aksi apapun dalam cluster yang sudah di bawah MA200. Ini bukan konsolidasi sehat; ini kekosongan minat. Likuiditas rendah, volatilitas rendah, tanpa katalis jelas. Stay away; banyak saham lain yang lebih layak diperhatikan.

**Example Case:**
```
Ticker: BAJA | Date: 16-05-2026
Price: 88 | MA5: 89 | MA13: 88 | MA34: 87 | MA200: 120
Gap MA: 2.3% → Cluster on Macro Downtrend
RSM: 50% | SRI: 0.4x | pchg: 0%
Phase: NEUTRAL | Action: HOLD
Narasi: Dead Zone
```

---

## 7. BULLISH MESSY
> Gap MA5/13/34 ≥ 3%, urutan MA bersilangan (bukan aligned), Price > MA200.

---

### 7.1 Bullish Messy + SOS
**Narasi:**
Momentum Kuat di Struktur Berantakan — SM sangat agresif tapi MA dalam kondisi chaotic. Sinyal SM valid dan menarik, tapi ketidakjelasan struktur MA menciptakan risiko false signal. Entry dengan sizing lebih kecil dari biasa; konfirmasi dengan apakah MA mulai realign dalam 2-3 hari ke depan.

**Example Case:**
```
Ticker: INDF | Date: 22-04-2026
Price: 7,200 | MA5: 7,350 | MA13: 7,100 | MA34: 7,250 | MA200: 6,800
Gap MA: ((7,350-7,100)/7,100)*100 = 3.52% ≥ 3%
Urutan: MA5 > MA34 > MA13 → Bersilangan → Bullish Messy (Price > MA200)
RSM: 72% | SRI: 3.4x | pchg: +3.7%
Phase: SOS | Action: BUY (reduced size)
Narasi: Momentum Kuat di Struktur Berantakan
```

---

### 7.2 Bullish Messy + SPRING
**Narasi:**
Akumulasi dalam Volatilitas Tinggi — SM masuk di penurunan tajam sementara MA sedang chaotic; tanda big players memanfaatkan ketidakpastian. Setup ini unpredictable tapi sering terjadi sebelum tren yang lebih jelas terbentuk. Entry kecil dengan konfirmasi ketat.

**Example Case:**
```
Ticker: INTP | Date: 23-04-2026
Price: 8,400 | MA5: 8,600 | MA13: 8,200 | MA34: 8,450 | MA200: 7,900
Gap MA: ((8,600-8,200)/8,200)*100 = 4.88% → Bullish Messy
RSM: 65% | SRI: 1.9x | pchg: -2.7%
Phase: SPRING | Action: BUY (cautious)
Narasi: Akumulasi dalam Volatilitas Tinggi
```

---

### 7.3 Bullish Messy + ABSORB
**Narasi:**
SM Tenang di Tengah Kekacauan MA — SM mengakumulasi dengan sabar meski struktur MA belum teratur. Ini menarik karena SM tidak terpengaruh oleh noise teknikal. Posisi makro aman (Price > MA200); tunggu MA mulai realign sebelum sizing up.

**Example Case:**
```
Ticker: KLBF | Date: 24-04-2026
Price: 1,680 | MA5: 1,720 | MA13: 1,640 | MA34: 1,700 | MA200: 1,550
Gap MA: ((1,720-1,640)/1,640)*100 = 4.88% → Bullish Messy
RSM: 67% | SRI: 2.5x | pchg: +0.2%
Phase: ABSORB | Action: BUY
Narasi: SM Tenang di Tengah Kekacauan MA
```

---

### 7.4 Bullish Messy + ACCUM
**Narasi:**
Akumulasi Gradual dalam Volatilitas — SM masuk perlahan di struktur MA yang belum teratur tapi makro masih bullish. Setup ini memerlukan patience ekstra; jangan ekspektasi immediate move. Tunggu MA mulai align sebelum sizing up lebih besar.

**Example Case:**
```
Ticker: MIKA | Date: 25-04-2026
Price: 3,200 | MA5: 3,280 | MA13: 3,150 | MA34: 3,220 | MA200: 3,000
Gap MA: 4.13% → Bullish Messy
RSM: 62% | SRI: 1.3x | pchg: +0.5%
Phase: ACCUM | Action: BUY (small)
Narasi: Akumulasi Gradual dalam Volatilitas
```

---

### 7.5 Bullish Messy + UPTHRUST
**Narasi:**
Chaos Trap — Harga naik dengan BM dominan dalam struktur MA yang sudah berantakan; sinyal paling tidak reliable karena ketidakjelasan tren. Bisa jadi reversal awal atau hanya noise volatilitas. Default ke SELL; jangan coba menerka arah di kondisi messy + UPTHRUST.

**Example Case:**
```
Ticker: ITMG | Date: 26-04-2026
Price: 22,000 | MA5: 22,500 | MA13: 21,500 | MA34: 22,200 | MA200: 20,000
Gap MA: ((22,500-21,500)/21,500)*100 = 4.65% → Bullish Messy
RSM: 29% | pchg: +3.2% | RPR: 0.77
Phase: UPTHRUST | Action: SELL
Narasi: Chaos Trap
```

---

### 7.6 Bullish Messy + DISTRI
**Narasi:**
Distribusi di Tengah Volatilitas — BM aktif mendistribusi dalam kondisi MA yang sudah chaotic; ini sinyal bahwa volatilitas ini dimanfaatkan big players untuk keluar. Meskipun Price > MA200, tekanan jual bisa cukup kuat untuk menarik harga ke bawah. Exit atau reduce.

**Example Case:**
```
Ticker: TPIA | Date: 27-04-2026
Price: 4,800 | MA5: 4,950 | MA13: 4,700 | MA34: 4,820 | MA200: 4,500
Gap MA: 5.32% → Bullish Messy
RSM: 34% | pchg: -2.4% | RPR: 0.63 | bm_gate: active
Phase: DISTRI | Action: SELL
Narasi: Distribusi di Tengah Volatilitas
```

---

### 7.7 Bullish Messy + NEUTRAL
**Narasi:**
Volatilitas Tanpa Arah — MA berantakan dan tidak ada aksi SM atau BM yang dominan; pasar sangat bingung. Dengan Price masih di atas MA200, belum ada alarm besar. Tapi hindari entry baru sampai MA mulai teratur dan ada sinyal phase yang jelas.

**Example Case:**
```
Ticker: EKAD | Date: 28-04-2026
Price: 580 | MA5: 596 | MA13: 568 | MA34: 582 | MA200: 540
Gap MA: 4.93% → Bullish Messy
RSM: 51% | SRI: 0.8x | pchg: +0.2%
Phase: NEUTRAL | Action: HOLD
Narasi: Volatilitas Tanpa Arah
```

---

## 8. BEARISH MESSY
> Gap MA5/13/34 ≥ 3%, urutan MA bersilangan (bukan aligned), Price < MA200.

---

### 8.1 Bearish Messy + SOS
**Narasi:**
Sinyal Kontroversial — SM agresif tapi MA chaotic dan Price di bawah MA200; konfluensi sangat buruk. Bisa jadi dead cat bounce atau awal reversal yang sangat dini. Risk sangat tinggi; jika entry, sizing minimal dan stop loss ketat di bawah low hari ini.

**Example Case:**
```
Ticker: ISAT | Date: 05-05-2026
Price: 2,400 | MA5: 2,450 | MA13: 2,320 | MA34: 2,400 | MA200: 2,800
Gap MA: ((2,450-2,320)/2,320)*100 = 5.6% → Bearish Messy
RSM: 70% | SRI: 3.1x | pchg: +3.6%
Phase: SOS | Action: BUY (extreme caution)
Narasi: Sinyal Kontroversial
```

---

### 8.2 Bearish Messy + SPRING
**Narasi:**
Bottom Fishing Ekstrem — Harga jatuh dalam kondisi MA chaotic dan di bawah MA200; SM mencoba akumulasi di zona yang sangat tertekan. Setup paling high-risk dalam katalog ini. Hanya relevan jika SRI > 3.0 dan RSM > 68% sebagai konfirmasi minimum. Ukuran posisi sangat kecil.

**Example Case:**
```
Ticker: TELE | Date: 06-05-2026
Price: 620 | MA5: 650 | MA13: 610 | MA34: 638 | MA200: 780
Gap MA: ((650-610)/610)*100 = 6.56% → Bearish Messy
RSM: 67% | SRI: 2.3x | pchg: -4.8%
Phase: SPRING | Action: BUY (minimal size only)
Narasi: Bottom Fishing Ekstrem
```

---

### 8.3 Bearish Messy + ABSORB
**Narasi:**
Akumulasi Tersembunyi di Zona Bearish — SM diam-diam membeli di tengah kekacauan MA dan kondisi makro yang bearish. Sinyal yang contradictory dan tidak mudah dibaca. Pantau selama beberapa hari; jika konsisten, bisa jadi awal reversal besar. Belum waktunya entry.

**Example Case:**
```
Ticker: FREN | Date: 07-05-2026
Price: 48 | MA5: 50 | MA13: 47 | MA34: 49 | MA200: 65
Gap MA: 6.38% → Bearish Messy
RSM: 68% | SRI: 2.4x | pchg: 0%
Phase: ABSORB | Action: HOLD (observe only)
Narasi: Akumulasi Tersembunyi di Zona Bearish
```

---

### 8.4 Bearish Messy + ACCUM
**Narasi:**
Sinyal Sangat Prematur — SM mulai masuk tipis-tipis tapi semua kondisi teknikal bertentangan (MA messy, Price < MA200). Terlalu early untuk act; kemungkinan SM sedang testing water. Skip sampai ada konfirmasi lebih kuat; risiko jauh lebih besar dari potensi keuntungan saat ini.

**Example Case:**
```
Ticker: DYAN | Date: 08-05-2026
Price: 178 | MA5: 185 | MA13: 174 | MA34: 180 | MA200: 230
Gap MA: 6.32% → Bearish Messy
RSM: 61% | SRI: 1.1x | pchg: -0.4%
Phase: ACCUM | Action: HOLD
Narasi: Sinyal Sangat Prematur
```

---

### 8.5 Bearish Messy + UPTHRUST
**Narasi:**
Maximum Danger — BM dominan, MA chaotic, Price di bawah MA200; ini adalah triple confirmation bearish. Tidak ada alasan apapun untuk beli. Jika masih punya posisi, ini adalah sinyal exit paling tegas. Prioritas pertama: capital preservation.

**Example Case:**
```
Ticker: MNCN | Date: 09-05-2026
Price: 480 | MA5: 500 | MA13: 462 | MA34: 488 | MA200: 620
Gap MA: 8.23% → Bearish Messy
RSM: 26% | pchg: +3.0% | RPR: 0.85
Phase: UPTHRUST | Action: SELL
Narasi: Maximum Danger
```

---

### 8.6 Bearish Messy + DISTRI
**Narasi:**
Distribusi Aktif dalam Kekacauan — BM mendistribusi agresif di tengah MA yang chaotic dan di bawah MA200; big players sedang keluar sekencang-kencangnya. Harga berpotensi turun drastis dalam waktu dekat. EXIT IMMEDIATELY jika masih punya posisi.

**Example Case:**
```
Ticker: MAPI | Date: 10-05-2026
Price: 1,100 | MA5: 1,150 | MA13: 1,060 | MA34: 1,120 | MA200: 1,380
Gap MA: ((1,150-1,060)/1,060)*100 = 8.49% → Bearish Messy
RSM: 30% | pchg: -3.5% | RPR: 0.72 | bm_gate: active
Phase: DISTRI | Action: SELL
Narasi: Distribusi Aktif dalam Kekacauan
```

---

### 8.7 Bearish Messy + NEUTRAL
**Narasi:**
Limbo Bearish — Tidak ada aksi apapun dalam kondisi MA chaotic dan di bawah MA200. Pasar tidak tahu arah tapi semua indikator struktural bearish. Jangan masuk; ini bukan opportunity. Alihkan perhatian ke saham dengan struktur lebih jelas.

**Example Case:**
```
Ticker: PNBN | Date: 11-05-2026
Price: 780 | MA5: 800 | MA13: 762 | MA34: 785 | MA200: 950
Gap MA: 5.0% → Bearish Messy
RSM: 50% | SRI: 0.5x | pchg: -0.1%
Phase: NEUTRAL | Action: HOLD (avoid)
Narasi: Limbo Bearish
```

---

## ⚡ GATE OVERRIDE NARRATIVES

> Gate override **menganulir semua narasi phase standar di atas** jika aktif.

---

### Gate A: Supply Gate (BM Abnormal)
**Trigger:** `bm_val > bm_sma10 * 3.0`

**Narasi:**
Abnormal Supply — Terdeteksi tekanan jual masif dari Bad Money (BM hari ini 3x+ rata-rata 10 hari), meskipun fase Smart Money menunjukkan akumulasi. Ada "tembok penjual" yang dapat mematikan momentum SM secara tiba-tiba. Tahan entry baru sampai supply abnormal ini mereda; risiko false signal sangat tinggi saat kondisi ini aktif.

**Example Case:**
```
Ticker: MDLN | Date: 20-04-2026
Phase: ACCUM (harusnya BUY)
BM hari ini: 450M | BM SMA10: 140M
Ratio: 450/140 = 3.21x → Gate A AKTIF → Narasi diganti ke "Abnormal Supply"
Action: HOLD (override dari BUY)
```

---

### Gate B: ARB Spring (Extreme Panic)
**Trigger:** `watch_flag == "ARB_SPRING"` (Phase = SPRING, pchg < -(ATR × 1.5))

**Narasi:**
Extreme Panic / Risiko ARB — Terdeteksi fase SPRING namun penurunan harga melampaui 1.5× volatilitas normal (ATR), mendekati zona Auto Rejection Bawah. SM mungkin benar dalam akumulasi jangka panjang, tapi momentum turun masih sangat kuat hari ini. Tunggu konfirmasi bounce di hari berikutnya sebelum entry; "tangkap pisau jatuh" adalah risiko utama di kondisi ini.

**Example Case:**
```
Ticker: BRIS | Date: 22-04-2026
Phase: SPRING | pchg: -6.2% | ATR: 3.5%
ARB threshold: -(3.5 * 1.5) = -5.25%
pchg -6.2% < -5.25% → watch_flag = "ARB_SPRING" → Gate B AKTIF
Action: HOLD (override dari BUY)
Frontend: tampil ⚠️ WATCH
```

---

### Gate C: Anti-Pucuk (Overextended)
**Trigger:** `pchg >= th_sos_h` (th_sos_h = MAX(ATR × 2.0, 5.0%))

**Narasi:**
Profit Taking Zone — Signal BUY valid dari sisi fase SM, namun harga hari ini sudah naik melampaui batas toleransi volatilitas (≥2× ATR atau ≥5%). Entry di harga ini berarti beli di puncak harian; probabilitas pullback lebih tinggi dari probabilitas kelanjutan. Tunggu koreksi atau entry di hari berikutnya jika struktur masih intact.

**Example Case:**
```
Ticker: EXCL | Date: 24-04-2026
Phase: SOS | pchg: +7.2% | ATR: 3.0%
th_sos_h: MAX(3.0*2.0, 5.0) = MAX(6.0, 5.0) = 6.0%
pchg 7.2% >= 6.0% → Gate C AKTIF
Action: HOLD (override dari BUY)
Narasi: Profit Taking Zone
```

---

## 📋 QUICK REFERENCE MATRIX

| Struktur \ Phase | SOS | SPRING | ABSORB | ACCUM | UPTHRUST | DISTRI | NEUTRAL |
|-----------------|-----|--------|--------|-------|----------|--------|---------|
| **Strong Uptrend** | Strongest Momentum | Pullback Sehat | Silent Accum in Trend | Steady Climb | Trap di Puncak | Distribusi Tersembunyi | Konsolidasi Kuat |
| **Transitional Uptrend** | Recovery Agresif | Dip dalam Recovery | Akumulasi Sebelum Break | Pemulihan Bertahap | Fake Recovery | Recovery Terancam | Jeda dalam Recovery |
| **Transitional Correction** | Counter-Rally Kuat | Bounce dari Support Makro | Akumulasi di Koreksi | Akumulasi Defensif | Dead Cat Bounce | Koreksi Diperdalam | Koreksi Tanpa Arah |
| **Strong Downtrend** | Counter-Rally Downtrend | Potensi Capitulation | Akumulasi Melawan Arus | Akumulasi Awal | Jebakan Bull | Downtrend Diperkuat | Jeda Downtrend |
| **Cluster Macro Up** | Breakout dari Sideways | Shakeout dalam Cluster | Akumulasi Diam Cluster | Fase Akumulasi | Fake Breakout | Distribusi dalam Cluster | Sideways Murni |
| **Cluster Macro Down** | Rally Terbatas | Shakeout Berbahaya | Akumulasi Zona Berbahaya | Akumulasi Sabar | Jebakan Zona Merah | Silent Exit | Dead Zone |
| **Bullish Messy** | Momentum Kuat Berantakan | Akumulasi Volatilitas | SM Tenang Kekacauan | Akumulasi Gradual | Chaos Trap | Distribusi Volatilitas | Volatilitas Tanpa Arah |
| **Bearish Messy** | Sinyal Kontroversial | Bottom Fishing Ekstrem | Akumulasi Zona Bearish | Sinyal Prematur | Maximum Danger | EXIT IMMEDIATELY | Limbo Bearish |

---

## ⚠️ ANTI-HALLUCINATION RULES (Rule 4 Implementation)

Sistem hanya boleh menggunakan narasi yang ada di katalog ini. Jika kombinasi:
- Tidak ada di katalog ini → output `[NARASI TIDAK DITEMUKAN - HARAP LAMPIRKAN DATABASE TRADE DETAIL]`
- Gate aktif → WAJIB gunakan narasi Gate, abaikan narasi phase standar
- Gate C aktif bersamaan Gate A → Gate A yang diprioritaskan (supply risk lebih urgent)

---

*Katalog ini adalah dokumen referensi resmi Zenith v3.1 — jangan modifikasi narasi tanpa review algorithm.*
