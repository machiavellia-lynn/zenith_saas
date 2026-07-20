/* ═══════════════════════════════════════════════════════════════════
   ZENITH 2.0 — Shared Utilities & Components
   ═══════════════════════════════════════════════════════════════════ */

/* ── Money / Price formatters ──────────────────────────────────────── */
window.fmtMoney = function(v) {
  if (v == null) return '—';
  const a = Math.abs(v), s = v < 0 ? '-' : '';
  if (a >= 1000) return s + (a / 1000).toFixed(2) + 'B';
  if (a >= 1)    return s + a.toFixed(1) + 'M';
  return s + (a * 1000).toFixed(0) + 'K';
};
window.fmtPrice = function(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('id-ID');
};
window.fmtPct = function(v) {
  if (v == null) return '—';
  return (v >= 0 ? '+' : '') + Number(v).toFixed(2) + '%';
};
window.fmtMoneySign = function(v) {
  if (v == null) return '—';
  return (v >= 0 ? '+' : '') + window.fmtMoney(v);
};
window.fmtNum = function(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('id-ID');
};

/* ── IHSG Live Badge ───────────────────────────────────────────────── */
window.loadIHSGBadge = function(priceEl, gainEl) {
  fetch('/api/ihsg').then(r => r.json()).then(d => {
    if (d.price)    { if(priceEl) priceEl.textContent = Number(d.price).toLocaleString('id-ID', {minimumFractionDigits:2,maximumFractionDigits:2}); }
    if (d.gain_pct != null) {
      if(gainEl) {
        gainEl.textContent = (d.gain_pct >= 0 ? '+' : '') + d.gain_pct.toFixed(2) + '%';
        gainEl.className = gainEl.className.replace(/\bup\b|\bdown\b/g,'').trim()
          + ' ' + (d.gain_pct >= 0 ? 'up' : 'down');
      }
    }
  }).catch(()=>{});
};

/* ── Phase helpers ─────────────────────────────────────────────────── */
window.phaseClass = function(phase) {
  const map = {
    'Spring': 'phase-spring', 'SOS': 'phase-sos', 'Absorb': 'phase-absorb',
    'Accum': 'phase-accum', 'ACCUM': 'phase-accum',
    'Neutral': 'phase-neutral', 'NEUTRAL': 'phase-neutral',
    'Upthrust': 'phase-upthrust', 'Distribution': 'phase-distribution',
    'DISTRIBUTION': 'phase-distribution',
  };
  return map[phase] || 'phase-neutral';
};
window.phaseColor = function(phase) {
  const map = {
    'Spring':'#3a6b58','SOS':'#2a7a5a','Absorb':'#4a7fdb',
    'Accum':'#3a6b58','ACCUM':'#3a6b58',
    'Neutral':'#a3a097','NEUTRAL':'#a3a097',
    'Upthrust':'#c87d3a','Distribution':'#c8633a','DISTRIBUTION':'#c8633a',
  };
  return map[phase] || '#a3a097';
};
window.actionClass = function(action) {
  const map = {
    'BUY':'action-buy','HOLD':'action-hold','SELL':'action-sell',
    'WATCH':'action-watch','ACCUM':'action-accum',
  };
  return map[(action||'').toUpperCase()] || 'action-hold';
};

/* ── Ticker avatar ─────────────────────────────────────────────────── */
window.tickerAvHTML = function(ticker) {
  return `<div class="ticker-av">${(ticker||'??').slice(0,2)}</div>`;
};

/* ── CM Bar HTML ───────────────────────────────────────────────────── */
window.cmBarHTML = function(value, maxVal) {
  if (value == null) return '<span class="num dim">—</span>';
  const max = maxVal || 1;
  const pct = Math.min(100, Math.abs(value) / max * 100);
  const up  = value >= 0;
  const barInner = up
    ? `<div class="cm-bar-fill-up" style="width:${pct}%"></div>`
    : `<div class="cm-bar-fill-dn" style="width:${pct}%"></div>`;
  return `<div class="cm-bar-wrap">
    <div class="cm-bar-track">${barInner}</div>
    <span class="cm-val ${up?'up':'down'}">${up?'+':''}${window.fmtMoney(value)}</span>
  </div>`;
};

/* ── Phase badge HTML ──────────────────────────────────────────────── */
window.phaseBadgeHTML = function(phase) {
  if (!phase) return '';
  const cls = window.phaseClass(phase);
  const col = window.phaseColor(phase);
  return `<div class="phase-badge ${cls}"><div class="badge-dot" style="background:${col}"></div>${phase}</div>`;
};

/* ── Action badge HTML ─────────────────────────────────────────────── */
window.actionBadgeHTML = function(action) {
  if (!action) return '';
  const cls = window.actionClass(action);
  return `<div class="action-badge ${cls}">${action}</div>`;
};

/* ── BSJP Setup badge HTML ─────────────────────────────────────────── */
window.BSJP_STYLE = {
  'POWER_BREAK_V21':   { col:'#22C55E', bg:'rgba(34,197,94,.11)'  },
  'POWER_BREAK_V22':   { col:'#22C55E', bg:'rgba(34,197,94,.11)'  },
  'SMA5_BREAKOUT_V13': { col:'#F97316', bg:'rgba(249,115,22,.11)' },
  'SMA5_BREAKOUT_V11': { col:'#F97316', bg:'rgba(249,115,22,.11)' },
  'BB_PULLBACK':       { col:'#A855F7', bg:'rgba(168,85,247,.11)' },
  'SMA5_PULLBACK_V12': { col:'#3B82F6', bg:'rgba(59,130,246,.11)' },
};
window.setupBadgeHTML = function(setup) {
  if (!setup) return '';
  const sc = window.BSJP_STYLE[setup] || { col:'#a3a097', bg:'var(--surface2)' };
  return `<div class="setup-badge" style="background:${sc.bg};border:1px solid ${sc.col}22">
    <div class="badge-dot" style="background:${sc.col}"></div>
    <span class="setup-badge-label" style="color:${sc.col}">${setup}</span>
  </div>`;
};

/* ── BSJP TP/SL calc ───────────────────────────────────────────────── */
window.bsjpTPSL = function(price, rsm) {
  if (!price || !rsm) return { tp: null, sl: null };
  const atr = price * ((100 - rsm) / 100 * 0.055 + 0.018);
  return { tp: Math.round(price + atr * 1.6), sl: Math.round(price - atr * 0.95) };
};
window.bsjpSetup = function(ticker) {
  const SETUPS = ['POWER_BREAK_V21','POWER_BREAK_V22','SMA5_BREAKOUT_V13','SMA5_BREAKOUT_V11','BB_PULLBACK','SMA5_PULLBACK_V12'];
  const h = ticker.split('').reduce((a,c) => (a * 31 + c.charCodeAt(0)) | 0, 0);
  return SETUPS[Math.abs(h) % SETUPS.length];
};

/* ── WR Bar HTML ───────────────────────────────────────────────────── */
window.wrBarHTML = function(wr) {
  const col = wr >= 60 ? 'var(--up)' : wr >= 48 ? '#c87d3a' : 'var(--down)';
  return `<div class="wr-bar">
    <div class="wr-bar-track"><div class="wr-bar-fill" style="width:${wr}%;background:linear-gradient(90deg,${col}88,${col})"></div></div>
    <span class="wr-bar-val" style="color:${col}">${wr}%</span>
  </div>`;
};

/* ── Today's date in YYYY-MM-DD ────────────────────────────────────── */
window.todayISO = function() {
  return new Date().toISOString().slice(0,10);
};
window.todayLocal = function() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,'0');
  const dd = String(d.getDate()).padStart(2,'0');
  return `${y}-${m}-${dd}`;
};
window.isoToDD_MM_YYYY = function(iso) {
  if (!iso) return '';
  const [y,m,d] = iso.split('-');
  return `${d}-${m}-${y}`;
};
window.DD_MM_YYYYtoISO = function(s) {
  if (!s) return '';
  const [d,m,y] = s.split('-');
  return `${y}-${m}-${d}`;
};

/* ══════════════════════════════════════════════════════════════════════
   STOCKBIT DATE PICKER — Vanilla JS
   Usage:
     const sdp = new StockbitDatePicker('my-container-id', {
       from: '2026-05-20',
       onChange: (from, to) => { ... }
     });
   ══════════════════════════════════════════════════════════════════════ */
window.StockbitDatePicker = class StockbitDatePicker {
  constructor(containerId, opts) {
    this.el       = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
    this.from     = opts.from || window.todayLocal();
    this.to       = opts.to   || this.from;
    this.onChange  = opts.onChange || function(){};
    this.alignRight = opts.alignRight || false;

    this._defaultFrom = opts.defaultFrom || null;
    this._defaultTo   = opts.defaultTo   || null;

    this._open = false;
    this._step = 'from'; // 'from' | 'to'
    this._viewYear  = new Date().getFullYear();
    this._viewMonth = new Date().getMonth(); // 0-indexed

    this._MON   = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    this._WDAYS = ['Su','Mo','Tu','We','Th','Fr','Sa'];

    this._popup = null;
    this._strip = null;
    this._textEl = null;

    if (this.el) this._render();
  }

  _fmt(s) {
    if (!s) return '—';
    const d = new Date(s + 'T00:00:00');
    return `${d.getDate()} ${this._MON[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`;
  }

  _keyFromDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }

  _addDay(n) {
    const fromD = new Date((this.from || window.todayLocal()) + 'T00:00:00');
    fromD.setDate(fromD.getDate() + n);
    const newFrom = this._keyFromDate(fromD);
    if (this.to && this.from !== this.to) {
      const toD = new Date(this.to + 'T00:00:00');
      toD.setDate(toD.getDate() + n);
      this.from = newFrom;
      this.to = this._keyFromDate(toD);
    } else {
      this.from = newFrom;
      this.to = newFrom;
    }
    this._updateStrip();
    this.onChange(this.from, this.to);
  }

  _updateStrip() {
    if (!this._textEl) return;
    const isRange = this.from && this.to && this.from !== this.to;
    this._textEl.textContent = isRange
      ? `${this._fmt(this.from)} – ${this._fmt(this.to)}`
      : this._fmt(this.from);
    if (this._strip) {
      const lbl = this._strip.querySelector('.sdp-label');
      if (lbl) lbl.style.minWidth = isRange ? '190px' : '96px';
    }
  }

  _openCal() {
    if (this.from) {
      const d = new Date(this.from + 'T00:00:00');
      this._viewYear  = d.getFullYear();
      this._viewMonth = d.getMonth();
    }
    this._step = 'from';
    this._renderPopup();
    if (this._strip && this._popup) {
      const r  = this._strip.getBoundingClientRect();
      const PW = 280;
      const PH = 330;
      let left = this.alignRight ? r.right - PW : r.left;
      if (left + PW > window.innerWidth - 8) left = window.innerWidth - PW - 8;
      if (left < 8) left = 8;
      const top = (r.bottom + 6 + PH > window.innerHeight - 8)
        ? Math.max(8, r.top - PH - 6)
        : r.bottom + 6;
      this._popup.style.top  = top + 'px';
      this._popup.style.left = left + 'px';
    }
    this._popup.classList.add('open');
    this._open = true;
  }

  _closeCal() {
    if (this._popup) this._popup.classList.remove('open');
    this._open = false;
  }

  _dim(y, m) { return new Date(y, m + 1, 0).getDate(); }
  _first(y, m){ return new Date(y, m, 1).getDay(); }
  _toKey(y, m, d) {
    return `${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
  }

  _inRangeWith(k, from, to) {
    if (!from || !to || from === to) return false;
    const [lo, hi] = from <= to ? [from, to] : [to, from];
    return k > lo && k < hi;
  }

  /* Update day cell CSS classes for hover preview — no HTML rebuild */
  _applyDayClasses(hoverKey) {
    if (!this._popup) return;
    const end = (this._step === 'to' && hoverKey) ? hoverKey : this.to;
    this._popup.querySelectorAll('.sdp-cal-day[data-key]').forEach(el => {
      const k = el.dataset.key;
      const isSt = k === this.from;
      const isEn = k === end && k !== this.from;
      const inRng = this._inRangeWith(k, this.from, end);
      const isSingle = isSt && (!end || end === this.from);
      let cls = 'sdp-cal-day';
      if (isSt || isEn) cls += ' selected' + (isSingle ? '' : (isSt ? ' range-start' : ' range-end'));
      if (inRng) cls += ' in-range';
      el.className = cls;
    });
  }

  _renderPopup() {
    if (!this._popup) return;
    const { _viewYear: y, _viewMonth: m } = this;
    const dim   = this._dim(y, m);
    const first = this._first(y, m);

    let days = '';
    for (let i = 0; i < first; i++) days += '<div></div>';
    for (let d = 1; d <= dim; d++) {
      const k      = this._toKey(y, m, d);
      const isSt   = k === this.from;
      const isEn   = k === this.to && k !== this.from;
      const inRng  = this._inRangeWith(k, this.from, this.to);
      const isSingle = isSt && (!this.to || this.to === this.from);
      let cls = 'sdp-cal-day';
      if (isSt || isEn) cls += ' selected' + (isSingle ? '' : (isSt ? ' range-start' : ' range-end'));
      if (inRng) cls += ' in-range';
      days += `<div class="${cls}" data-key="${k}">${d}</div>`;
    }

    const hintText = this._step === 'from'
      ? '↓ Click start date'
      : '↓ Click end · click same for single';

    const footLabel = this.from
      ? (this.from !== this.to ? `${this._fmt(this.from)} → ${this._fmt(this.to)}` : this._fmt(this.from))
      : '—';

    this._popup.innerHTML = `
      <div class="sdp-cal-hint">${hintText}</div>
      <div class="sdp-cal-nav">
        <button class="sdp-cal-nav-btn sdp-nav-prev">‹</button>
        <div class="sdp-cal-month">${this._MON[m]} ${y}</div>
        <button class="sdp-cal-nav-btn sdp-nav-next">›</button>
      </div>
      <div class="sdp-cal-wdays">${this._WDAYS.map(w=>`<div class="sdp-cal-wday">${w}</div>`).join('')}</div>
      <div class="sdp-cal-grid">${days}</div>
      <div class="sdp-cal-foot">
        <span class="sdp-cal-foot-label">${footLabel}</span>
        <button class="sdp-cal-reset">Reset</button>
      </div>`;

    /* Month navigation — stable elements, never replaced by hover */
    this._popup.querySelector('.sdp-nav-prev').addEventListener('click', () => {
      if (this._viewMonth === 0) { this._viewMonth = 11; this._viewYear--; }
      else this._viewMonth--;
      this._renderPopup();
    });
    this._popup.querySelector('.sdp-nav-next').addEventListener('click', () => {
      if (this._viewMonth === 11) { this._viewMonth = 0; this._viewYear++; }
      else this._viewMonth++;
      this._renderPopup();
    });

    /* Day clicks */
    this._popup.querySelectorAll('.sdp-cal-day[data-key]').forEach(el => {
      el.addEventListener('click', () => {
        const k = el.dataset.key;
        if (this._step === 'from' || !this.from) {
          this.from = k; this.to = k; this._step = 'to';
        } else {
          if (k === this.from) { this._closeCal(); this._step = 'from'; }
          else {
            const [lo, hi] = this.from <= k ? [this.from, k] : [k, this.from];
            this.from = lo; this.to = hi;
            this._closeCal(); this._step = 'from';
          }
        }
        this._updateStrip();
        this.onChange(this.from, this.to);
        if (this._open) this._renderPopup();
      });
    });

    /* Hover preview — grid-level delegation, no innerHTML replacement */
    const grid = this._popup.querySelector('.sdp-cal-grid');
    if (grid) {
      grid.addEventListener('mouseover', (e) => {
        if (this._step !== 'to' || !this.from) return;
        const cell = e.target.closest('.sdp-cal-day[data-key]');
        if (cell) this._applyDayClasses(cell.dataset.key);
      });
      grid.addEventListener('mouseleave', () => {
        if (this._step === 'to') this._applyDayClasses(null);
      });
    }

    /* Reset — goes to defaultFrom/To if set, else today */
    const resetBtn = this._popup.querySelector('.sdp-cal-reset');
    if (resetBtn) resetBtn.addEventListener('click', () => {
      const defFrom = this._defaultFrom || window.todayLocal();
      const defTo   = this._defaultTo   || defFrom;
      this.from = defFrom; this.to = defTo;
      this._step = 'from';
      this._closeCal();
      this._updateStrip();
      this.onChange(this.from, this.to);
    });
  }

  _render() {
    this.el.innerHTML = `
      <div class="sdp-strip">
        <button type="button" class="sdp-arrow sdp-arrow-left" title="Hari sebelumnya">‹</button>
        <div class="sdp-label" style="min-width:96px">
          <span class="sdp-text"></span>
          <button type="button" class="sdp-cal-btn" title="Pilih tanggal">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <rect x="1" y="2" width="12" height="11" rx="1.5"/>
              <path d="M1 6h12M4 1v2M10 1v2"/>
            </svg>
          </button>
        </div>
        <button type="button" class="sdp-arrow sdp-arrow-right" title="Hari berikutnya">›</button>
      </div>`;

    this._strip  = this.el.querySelector('.sdp-strip');
    this._textEl = this.el.querySelector('.sdp-text');

    this._popup = document.createElement('div');
    this._popup.className = 'sdp-cal-popup';
    document.body.appendChild(this._popup);

    this.el.querySelector('.sdp-arrow-left').addEventListener('click',  () => this._addDay(-1));
    this.el.querySelector('.sdp-arrow-right').addEventListener('click', () => this._addDay(1));
    this.el.querySelector('.sdp-cal-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this._open ? this._closeCal() : this._openCal();
    });

    document.addEventListener('mousedown', (e) => {
      if (this._open && this._popup && !this._popup.contains(e.target) && !this.el.contains(e.target)) {
        this._closeCal();
      }
    });

    this._updateStrip();
  }

  setDates(from, to) {
    this.from = from || this.from;
    this.to   = to   || this.to;
    this._updateStrip();
  }

  setDefault(from, to) {
    this._defaultFrom = from || null;
    this._defaultTo   = to   || null;
  }
};
