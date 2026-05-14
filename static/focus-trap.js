/* focus-trap.js — Shared modal accessibility utility for Zenith.
   ZenithModal.open(backdropId, triggerEl)  — opens modal, traps Tab, closes on ESC, focuses first element.
   ZenithModal.close(backdropId)            — closes modal, returns focus to trigger. */
(function(w) {
  var FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
  var _trigger = null, _trapH = null, _escH = null, _bdId = null;

  function open(backdropId, triggerEl) {
    var bd = document.getElementById(backdropId);
    if (!bd) return;
    _bdId    = backdropId;
    _trigger = triggerEl || null;
    if (_trigger) _trigger.setAttribute('aria-expanded', 'true');
    bd.classList.add('open');
    document.body.style.overflow = 'hidden';
    var els = bd.querySelectorAll(FOCUSABLE);
    if (els.length) setTimeout(function() { els[0].focus(); }, 50);
    _trapH = function(e) {
      if (e.key !== 'Tab') return;
      var focusable = Array.from(bd.querySelectorAll(FOCUSABLE));
      if (!focusable.length) return;
      var first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey) { if (document.activeElement === first) { e.preventDefault(); last.focus(); } }
      else            { if (document.activeElement === last)  { e.preventDefault(); first.focus(); } }
    };
    _escH = function(e) { if (e.key === 'Escape') close(backdropId); };
    bd.addEventListener('keydown', _trapH);
    document.addEventListener('keydown', _escH);
  }

  function close(backdropId) {
    var bd = document.getElementById(backdropId || _bdId);
    if (!bd) return;
    bd.classList.remove('open');
    document.body.style.overflow = '';
    if (_trapH) { bd.removeEventListener('keydown', _trapH); _trapH = null; }
    if (_escH)  { document.removeEventListener('keydown', _escH); _escH = null; }
    if (_trigger) { _trigger.setAttribute('aria-expanded', 'false'); _trigger.focus(); }
    _trigger = null; _bdId = null;
  }

  w.ZenithModal = { open: open, close: close };
})(window);
