/* MS SmartScan — Patient Registry (updates live when the MRI Scanner saves a scan) */
(() => {
  const { $, $$, LABEL, TONE, ICON, esc, fmtDate, scanConf, toast, liveEvents, chrome } = window.MSS;
  // Separate site: the MRI Scanner has no link or access to this page or its data.

  const state = { items: [], filter: 'all', query: '', csrf: '' };

  async function loadCsrf() {
    try { state.csrf = (await (await fetch('/api/status')).json()).csrf_token || ''; } catch (e) { setTimeout(loadCsrf, 1500); }
  }

  // One-way link to the Scanner (its address can differ if port 8000 was busy)
  async function loadScannerUrl() {
    try {
      const { scanner_url: url } = await (await fetch('/api/info')).json();
      if (url) $$('[data-scanner-link]').forEach((a) => { a.href = url; });
    } catch (e) { /* keep the default address */ }
  }

  /* ================= Data ================= */
  async function loadHistory() {
    try {
      const d = await (await fetch('/api/history')).json();
      state.items = d.items || [];
      const s = d.stats;
      $('sTotal').textContent = s.total; $('sPatients').textContent = s.patients;
      $('sInf').textContent = s.infected; $('sUncertain').textContent = s.uncertain; $('sOk').textContent = s.healthy;
      $('sAvg').textContent = typeof s.avg_seconds === 'number' ? s.avg_seconds.toFixed(1) + ' s' : '—';
      $('lastSync').textContent = 'Updated ' + new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      renderChart(d.daily || []);
      renderRecords();
      if (current) { const fresh = state.items.find((x) => x.id === current.id); if (!fresh) closeModal(); }
    } catch (e) { /* server may be restarting; the live link retries */ }
  }

  function filtered() {
    const q = state.query.trim().toLowerCase();
    return state.items.filter((s) => (state.filter === 'all' || s.result === state.filter)
      && (!q || (s.patient || '').toLowerCase().includes(q) || (s.patient_id || '').toLowerCase().includes(q)));
  }

  function renderRecords() {
    const rows = filtered();
    $('recordsBody').innerHTML = rows.map((s) => `
      <tr data-id="${esc(s.id)}" tabindex="0">
        <td data-label="Patient"><div class="who"><span class="thumb">${s.media_available ? `<img src="${esc(s.annotated)}" alt="" loading="lazy">` : ''}</span>
          <span><b>${esc(s.patient || 'Unnamed (legacy record)')}</b><small>${esc(s.inference_version ? 'YOLO11n' : 'Legacy scan')}</small></span></div></td>
        <td data-label="Medical no.">${s.patient_id ? `<span class="mrn">${esc(s.patient_id)}</span>` : '—'}</td>
        <td data-label="Date & time">${fmtDate(s.created_at)}</td>
        <td data-label="AI finding"><span class="badge ${TONE[s.result] || 'green'}">${LABEL[s.result] || esc(s.result)}</span></td>
        <td data-label="Confidence" class="num-cell">${scanConf(s) || '—'}</td>
        <td data-label="Regions" class="num-cell">${s.lesions ?? '—'}</td>
        <td class="act"><button type="button" class="view-btn">${ICON.eye} View</button></td>
      </tr>`).join('');
    const empty = rows.length === 0;
    $('recordsEmpty').hidden = !empty;
    if (empty) {
      const any = state.items.length > 0;
      $('emptyTitle').textContent = any ? 'No matching records' : 'No scans recorded yet';
      $('emptyText').textContent = any ? 'Try a different name, medical number, or filter.' : 'Scans completed in the MRI Scanner appear here automatically.';
    }
  }

  function flashRow(id) {
    const row = $('recordsBody').querySelector(`[data-id="${CSS.escape(id)}"]`);
    if (!row) return;
    row.classList.remove('flash'); void row.offsetWidth; row.classList.add('flash');
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function showAll() {
    state.filter = 'all'; state.query = ''; $('search').value = '';
    $$('#filter .seg-btn').forEach((x) => x.classList.toggle('on', x.dataset.filter === 'all'));
    renderRecords();
  }

  $('search').addEventListener('input', (e) => { state.query = e.target.value; renderRecords(); });
  $$('#filter .seg-btn').forEach((b) => b.addEventListener('click', () => {
    state.filter = b.dataset.filter;
    $$('#filter .seg-btn').forEach((x) => x.classList.toggle('on', x === b));
    renderRecords();
  }));

  function renderChart(daily) {
    const svg = $('activityChart'), days = [];
    const byDay = Object.fromEntries(daily.map((d) => [d.day, d]));
    for (let i = 13; i >= 0; i--) {
      const dt = new Date(); dt.setDate(dt.getDate() - i);
      const key = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
      days.push({ key, label: dt.getDate(), scans: byDay[key]?.scans || 0, inf: byDay[key]?.infected || 0 });
    }
    const max = Math.max(1, ...days.map((d) => d.scans));
    const W = 280, H = 90, top = 6, base = 76, bw = 12, gap = (W - bw * 14) / 13;
    let out = `<line class="base" x1="0" x2="${W}" y1="${base}" y2="${base}"/>`;
    days.forEach((d, i) => {
      const x = i * (bw + gap), h = (d.scans / max) * (base - top), hi = (d.inf / max) * (base - top);
      if (d.scans) out += `<rect class="bar" x="${x}" y="${base - h}" width="${bw}" height="${h}" rx="3"><title>${d.key}: ${d.scans} scan(s), ${d.inf} suspected MS/SVD</title></rect>`;
      if (d.inf) out += `<rect class="bar-inf" x="${x}" y="${base - hi}" width="${bw}" height="${hi}" rx="3"/>`;
      if (i % 2 === 1 || i === 13) out += `<text x="${x + bw / 2}" y="${H - 2}" text-anchor="middle">${d.label}</text>`;
    });
    svg.innerHTML = out;
  }

  /* Formatted Excel workbook built by the server, using the filter and search shown on screen */
  $('exportXlsx').addEventListener('click', () => {
    const rows = filtered();
    if (!rows.length) { toast('No records to export.'); return; }
    const params = new URLSearchParams({ result: state.filter, q: state.query.trim() });
    const a = document.createElement('a');
    a.href = '/api/export.xlsx?' + params; a.download = '';
    document.body.appendChild(a); a.click(); a.remove();
    toast(`Exporting ${rows.length} record${rows.length === 1 ? '' : 's'} to Excel…`);
  });

  /* ================= Scan detail ================= */
  const modal = $('modal'); let current = null;
  function openScan(id) {
    current = state.items.find((s) => s.id === id); if (!current) return;
    const tone = TONE[current.result] || 'green';
    $('dImg').src = current.annotated;
    $('dBadge').className = 'badge ' + tone; $('dBadge').textContent = LABEL[current.result] || current.result;
    $('dName').textContent = current.patient || 'Unnamed (legacy record)';
    $('dNumber').textContent = current.patient_id ? 'Medical no. ' + current.patient_id : 'No medical number';
    $('dConf').textContent = scanConf(current) || 'Not applicable';
    $('dRegions').textContent = current.lesions;
    $('dDate').textContent = fmtDate(current.created_at);
    $('dTime').textContent = current.seconds != null ? current.seconds + ' s' : '—';
    $('dId').textContent = current.id; $('dId').title = current.id;
    $('dModel').textContent = current.inference_version || 'Legacy';
    $('dText').textContent = current.result === 'Infected'
      ? 'White matter lesions detected that may indicate MS or Small Vessel Disease (SVD); MRI alone cannot tell them apart. Tests to differentiate: lumbar puncture (CSF OCBs, κ-FLC), contrast-enhanced MRI of the brain and spinal cord, and vascular risk assessment (blood pressure, HbA1c, lipids).'
      : current.result === 'Uncertain' ? 'Low-confidence finding below the 70% review threshold. Expert radiology review is recommended first; if a lesion is confirmed, the same tests help differentiate MS from SVD.'
        : 'No white matter lesion suggestive of MS or SVD was detected by the current AI screening model.';
    $$('#dToggle .seg-btn').forEach((x, i) => x.classList.toggle('on', i === 0));
    modal.classList.add('open');
    modal.querySelector('[data-close]').focus();
  }
  const closeModal = () => { modal.classList.remove('open'); current = null; };
  $('recordsBody').addEventListener('click', (e) => { const tr = e.target.closest('tr[data-id]'); if (tr) openScan(tr.dataset.id); });
  $('recordsBody').addEventListener('keydown', (e) => { if (e.key === 'Enter') { const tr = e.target.closest('tr[data-id]'); if (tr) openScan(tr.dataset.id); } });
  $('dToggle').addEventListener('click', (e) => {
    const b = e.target.closest('.seg-btn'); if (!b || !current) return;
    $$('#dToggle .seg-btn').forEach((x) => x.classList.toggle('on', x === b));
    $('dImg').src = current[b.dataset.v];
  });
  modal.addEventListener('click', (e) => { if (e.target === modal || e.target.closest('[data-close]')) closeModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  $('dDelete').addEventListener('click', async () => {
    if (!current || !confirm(`Delete this scan for ${current.patient || 'this patient'}? This cannot be undone.`)) return;
    const res = await fetch('/api/history/' + encodeURIComponent(current.id), { method: 'DELETE', headers: { 'X-CSRF-Token': state.csrf } });
    if (!res.ok) { toast('The scan could not be deleted. Reload the page and try again.'); return; }
    closeModal(); toast('Scan deleted.'); await loadHistory();
  });

  /* ================= Links from the Scanner (#scan=<id>) ================= */
  async function focusFromHash() {
    const m = location.hash.match(/^#scan=([\w-]+)$/); if (!m) return;
    if (!state.items.some((s) => s.id === m[1])) await loadHistory();
    showAll(); flashRow(m[1]); openScan(m[1]);
    history.replaceState(null, '', location.pathname);
  }
  addEventListener('hashchange', focusFromHash);

  /* ================= Live updates from the Scanner ================= */
  const chip = $('liveChip');
  liveEvents({
    scan: async (ev) => {
      await loadHistory();
      const visible = filtered().some((s) => s.id === ev.id);
      if (!visible) showAll();
      flashRow(ev.id);
      toast(`New scan received: ${ev.patient || 'Patient'} · ${LABEL[ev.result] || ev.result}`);
    },
    delete: () => loadHistory(),
  }, (st) => {
    chip.dataset.state = st;
    chip.lastElementChild.textContent = st === 'live' ? 'Live · connected to Scanner' : st === 'off' ? 'Live updates unavailable' : 'Reconnecting…';
    if (st === 'live') loadHistory();   // catch up on anything missed while disconnected
  });

  chrome();
  loadCsrf();
  loadScannerUrl();
  loadHistory().then(focusFromHash);
})();
