/* MS SmartScan — helpers shared by the MRI Scanner and the Patient Registry */
window.MSS = (() => {
  const $ = (id) => document.getElementById(id);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const LABEL = { Infected: 'Suspected MS/SVD', Uncertain: 'Low confidence', Healthy: 'Clear' };
  const TONE = { Infected: 'red', Uncertain: 'amber', Healthy: 'green' };
  const ICON = {
    alert: '<svg viewBox="0 0 24 24"><path d="M12 3 2 20h20Z"/><path d="M12 10v4M12 17.5v.01"/></svg>',
    check: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>',
    info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>',
    copy: '<svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V6a2 2 0 0 1 2-2h10"/></svg>',
    eye: '<svg class="ic" viewBox="0 0 24 24"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>',
  };

  const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtDate = (iso) => { const d = new Date(iso); return isNaN(d) ? '—' : d.toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }); };
  const pct = (v) => (typeof v === 'number' ? v.toFixed(1) + '%' : '—');
  // "Clear" has no lesion boxes, so no model confidence exists (legacy rows stored a placeholder 100).
  const scanConf = (s) => (s.result !== 'Healthy' && s.confidence != null ? pct(s.confidence) : null);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  function toast(msg) {
    const t = $('toast'); t.textContent = msg; t.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, 3600);
  }

  /* Live link between the two sites: the server pushes an event whenever a scan is saved or deleted */
  function liveEvents(handlers, onState = () => {}) {
    if (!window.EventSource) { onState('off'); return; }
    const es = new EventSource('/api/events');
    es.onopen = () => onState('live');
    es.onerror = () => onState('reconnecting');   // the browser reconnects automatically
    Object.entries(handlers).forEach(([type, fn]) => es.addEventListener(type, (e) => {
      try { fn(JSON.parse(e.data)); } catch (err) { /* ignore malformed event */ }
    }));
    addEventListener('beforeunload', () => es.close());
  }

  function chrome() {
    const topbar = $('topbar');
    addEventListener('scroll', () => topbar.classList.toggle('scrolled', scrollY > 8), { passive: true });
  }

  return { $, $$, LABEL, TONE, ICON, esc, fmtDate, pct, scanConf, wait, toast, liveEvents, chrome };
})();
