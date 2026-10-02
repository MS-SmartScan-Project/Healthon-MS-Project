/* MS SmartScan — Patient Registry: doctor PIN sign-in, records by role, live updates from the MRI Scanner */
(() => {
  const { $, $$, LABEL, TONE, ICON, esc, fmtDate, scanConf, toast, normPin, pinError, authMessage, liveEvents, chrome } = window.MSS;
  // Separate site: the MRI Scanner has no link or access to this page or its data.
  // The server decides who is signed in and what they may see; this page only shows what the server returns.

  const IDLE_MS = 60 * 1000;   // signed out after 60 seconds without activity (the server enforces the same limit)
  const PING_MS = 5 * 1000;    // user activity is reported to the server at most every 5 seconds
  const state = { items: [], filter: 'all', query: '', csrf: '', doctor: null };
  let events = null;

  /* ================= Server calls ================= */
  async function loadStatus() {
    try {
      const s = await (await fetch('/api/status')).json();
      state.csrf = s.csrf_token || '';
      return s;
    } catch (e) { return {}; }
  }

  async function api(url, { method = 'GET', json, keepalive = false } = {}) {
    const headers = {};
    if (method !== 'GET') headers['X-CSRF-Token'] = state.csrf;
    if (json !== undefined) headers['Content-Type'] = 'application/json';
    let res;
    try {
      res = await fetch(url, { method, headers, body: json !== undefined ? JSON.stringify(json) : undefined, keepalive, cache: 'no-store' });
    } catch (e) { return { ok: false, status: 0, data: {} }; }
    let data = {};
    try { data = await res.json(); } catch (e) { /* not JSON */ }
    if (res.status === 401 && data.code === 'session_expired' && state.doctor) signOut('expired');
    return { ok: res.ok, status: res.status, data };
  }

  // One-way link to the Scanner (its address can differ if port 8000 was busy)
  async function loadScannerUrl() {
    try {
      const { scanner_url: url } = await (await fetch('/api/info')).json();
      if (url) $$('[data-scanner-link]').forEach((a) => { a.href = url; });
    } catch (e) { /* keep the default address */ }
  }

  /* ================= Sign-in ================= */
  const NOTES = {
    idle: 'You were signed out after 60 seconds of inactivity.',
    expired: 'Your session has ended. Sign in again with your PIN.',
    manual: 'You have signed out.',
    other: 'You were signed out in another window.',
  };
  let unlockTimer = null;

  function showLogin(status) {
    $('app').hidden = true; $('authScreen').hidden = false;
    let reason = null;
    try { reason = sessionStorage.getItem('mss-reg-signout'); sessionStorage.removeItem('mss-reg-signout'); } catch (e) { /* ignore */ }
    $('authNote').hidden = !NOTES[reason];
    $('authNote').textContent = NOTES[reason] || '';
    if (status && status.locked_until) showLocked(status.locked_until);
    else $('loginPin').focus();
  }

  function setLoginError(msg) {
    $('loginErr').textContent = msg;
    $('fLoginPin').classList.toggle('invalid', !!msg);
    $('loginPin').setAttribute('aria-invalid', msg ? 'true' : 'false');
  }

  function showLocked(until) {
    setLoginError(authMessage({ code: 'locked', locked_until: until }));
    $('loginPin').disabled = true; $('loginBtn').disabled = true;
    clearTimeout(unlockTimer);
    const ms = new Date(until) - Date.now();
    if (ms > 0 && ms < 2 ** 31) unlockTimer = setTimeout(() => location.reload(), ms + 1000);
  }

  $('loginPin').addEventListener('input', () => {
    const up = $('loginPin').value.toUpperCase();
    if (up !== $('loginPin').value) $('loginPin').value = up;
    if ($('loginErr').textContent) setLoginError('');
  });

  $('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const pin = normPin($('loginPin').value);
    const err = pinError(pin);
    if (err) { setLoginError(err); $('loginPin').focus(); return; }
    const btn = $('loginBtn');
    btn.disabled = true; btn.classList.add('loading');
    if (!state.csrf) await loadStatus();
    let r = await api('/api/login', { method: 'POST', json: { pin } });
    if (r.status === 403 && r.data.code === 'csrf') {   // the server was restarted: get a fresh token and try once more
      await loadStatus();
      r = await api('/api/login', { method: 'POST', json: { pin } });
    }
    $('loginPin').value = '';
    btn.disabled = false; btn.classList.remove('loading');
    if (r.ok) { enter(r.data.doctor); return; }
    if (r.data.code === 'locked') { showLocked(r.data.locked_until); return; }
    setLoginError(authMessage(r.data) || r.data.error || 'The registry server is not responding. Please restart it.');
    $('loginPin').focus();
  });

  /* ================= Signed in ================= */
  const initials = (name) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || 'DR';

  function enter(doctor) {
    state.doctor = doctor;
    const head = doctor.role === 'head';
    $('authScreen').hidden = true; $('app').hidden = false;
    $('whoName').textContent = doctor.name;
    $('whoInitials').textContent = initials(doctor.name);
    $('whoRole').textContent = head ? 'Department head' : 'Doctor';
    $('whoDept').textContent = doctor.department;
    $('docDept').textContent = doctor.department;
    $('scopeNote').textContent = head
      ? 'Department head view: every scan in the department, including records saved before doctor sign-in was added (shown as Unassigned).'
      : 'Doctor view: only your own patients and scans are shown.';
    ['whoami', 'signOutBtn', 'liveChip'].forEach((id) => { $(id).hidden = false; });
    $('doctors').hidden = !head; $('navDoctors').hidden = !head;
    startIdleWatch();
    ping();   // signing in (or reloading the page) is user activity
    startLive();
    loadScannerUrl();
    loadHistory().then(focusFromHash);
    if (head) loadDoctors();
  }

  /* Inactivity: only real user input counts — background updates never keep the session alive */
  let lastActivity = Date.now(), lastPing = 0, trailingPing = null, lastShared = 0, idleTimer = null;
  const SHARED = 'mss-reg-activity';   // shared with other Registry tabs (a time only, no patient data)

  function onActivity() {
    if (!state.doctor) return;
    lastActivity = Date.now();
    if (lastActivity - lastShared > 1000) {
      lastShared = lastActivity;
      try { localStorage.setItem(SHARED, String(lastActivity)); } catch (e) { /* ignore */ }
    }
    const since = lastActivity - lastPing;
    if (since >= PING_MS) ping();
    else if (!trailingPing) trailingPing = setTimeout(() => { trailingPing = null; ping(); }, PING_MS - since);
  }

  function ping() {
    if (!state.doctor) return;
    lastPing = Date.now();
    api('/api/activity', { method: 'POST' });   // a 401 here signs the page out
  }

  function checkIdle() {
    if (!state.doctor) return;
    let last = lastActivity;
    try { last = Math.max(last, Number(localStorage.getItem(SHARED)) || 0); } catch (e) { /* ignore */ }
    if (Date.now() - last >= IDLE_MS) signOut('idle');
  }

  function startIdleWatch() {
    lastActivity = Date.now();
    clearInterval(idleTimer);
    idleTimer = setInterval(checkIdle, 1000);
  }
  ['click', 'keydown', 'mousemove', 'pointerdown', 'wheel', 'touchstart', 'input'].forEach((ev) => addEventListener(ev, onActivity, { passive: true, capture: true }));
  addEventListener('scroll', onActivity, { passive: true, capture: true });   // also catches scrolling inside the records table
  document.addEventListener('visibilitychange', checkIdle);

  /* Sign-out clears everything: the server session is ended and the page reloads to the PIN screen */
  function signOut(reason) {
    if (!state.doctor) return;
    state.doctor = null;
    clearInterval(idleTimer); clearTimeout(trailingPing);
    if (events) { events.close(); events = null; }
    closeModal();
    state.items = []; $('recordsBody').innerHTML = ''; $('doctorsBody').innerHTML = '';
    $('app').hidden = true;
    try {
      sessionStorage.setItem('mss-reg-signout', reason);
      if (reason !== 'other') localStorage.setItem('mss-reg-signout', String(Date.now()));   // tells other Registry tabs
    } catch (e) { /* ignore */ }
    const done = () => location.replace('/');
    fetch('/api/logout', { method: 'POST', headers: { 'X-CSRF-Token': state.csrf }, keepalive: true }).finally(done);
  }
  $('signOutBtn').addEventListener('click', () => signOut('manual'));
  addEventListener('storage', (e) => { if (e.key === 'mss-reg-signout' && e.newValue) signOut('other'); });

  /* ================= Data ================= */
  async function loadHistory() {
    const r = await api('/api/history');
    if (!r.ok) return;   // signed out, or the server is restarting (the live link retries)
    const d = r.data;
    state.items = d.items || [];
    const s = d.stats;
    $('sTotal').textContent = s.total; $('sPatients').textContent = s.patients;
    $('sInf').textContent = s.infected; $('sUncertain').textContent = s.uncertain; $('sOk').textContent = s.healthy;
    $('sAvg').textContent = typeof s.avg_seconds === 'number' ? s.avg_seconds.toFixed(1) + ' s' : '—';
    $('lastSync').textContent = 'Updated ' + new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    renderChart(d.daily || []);
    renderRecords();
    if (current) { const fresh = state.items.find((x) => x.id === current.id); if (!fresh) closeModal(); }
  }

  function filtered() {
    const q = state.query.trim().toLowerCase();
    return state.items.filter((s) => (state.filter === 'all' || s.result === state.filter)
      && (!q || (s.patient || '').toLowerCase().includes(q) || (s.patient_id || '').toLowerCase().includes(q)));
  }

  const modelName = (s) => (!s.inference_version ? 'Legacy scan' : s.inference_version.startsWith('yolo26') ? 'YOLO26s' : 'YOLO11n');
  const ownerName = (s) => s.owner || 'Unassigned (before sign-in)';

  function renderRecords() {
    const rows = filtered();
    const head = state.doctor && state.doctor.role === 'head';
    $('recordsBody').innerHTML = rows.map((s) => `
      <tr data-id="${esc(s.id)}" tabindex="0">
        <td data-label="Patient"><div class="who"><span class="thumb">${s.media_available ? `<img src="${esc(s.annotated)}" alt="" loading="lazy">` : ''}</span>
          <span><b>${esc(s.patient || 'Unnamed (legacy record)')}</b><small>${esc(modelName(s))}</small>${head ? `<small class="owner${s.owner ? '' : ' unassigned'}"${s.owner ? ' data-no-i18n' : ''}>${esc(ownerName(s))}</small>` : ''}</span></div></td>
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

  /* Formatted Excel workbook built by the server, using the filter and search shown on screen (only records this doctor may see) */
  $('exportXlsx').addEventListener('click', async () => {
    const rows = filtered();
    if (!rows.length) { toast('No records to export.'); return; }
    if (!(await api('/api/me')).ok) return;   // session ended: the page returns to the PIN screen
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
    $('dDoctor').textContent = ownerName(current);
    $('dDoctor').toggleAttribute('data-no-i18n', !!current.owner);
    $('dId').textContent = current.id; $('dId').title = current.id;
    $('dModel').textContent = current.inference_version || 'Legacy';
    $('dText').textContent = current.result === 'Infected'
      ? 'White matter lesions detected that may indicate MS or Small Vessel Disease (SVD); MRI alone cannot tell them apart. Tests to differentiate: lumbar puncture (CSF OCBs, κ-FLC), contrast-enhanced MRI of the brain and spinal cord, and vascular risk assessment (blood pressure, HbA1c, lipids).'
      : current.result === 'Uncertain' ? 'Low-confidence finding below the 50% review threshold. Expert radiology review is recommended first; if a lesion is confirmed, the same tests help differentiate MS from SVD.'
        : 'No white matter lesion suggestive of MS or SVD was detected by the current AI screening model.';
    $$('#dToggle .seg-btn').forEach((x, i) => x.classList.toggle('on', i === 0));
    modal.classList.add('open');
    modal.querySelector('[data-close]').focus();
  }
  function closeModal() { modal.classList.remove('open'); $('dImg').removeAttribute('src'); current = null; }
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
    const r = await api('/api/history/' + encodeURIComponent(current.id), { method: 'DELETE' });
    if (!r.ok) { if (state.doctor) toast('The scan could not be deleted. Reload the page and try again.'); return; }
    closeModal(); toast('Scan deleted.'); await loadHistory();
  });

  /* ================= Links from the Scanner (#scan=<id>) ================= */
  async function focusFromHash() {
    const m = location.hash.match(/^#scan=([\w-]+)$/); if (!m) return;
    if (!state.items.some((s) => s.id === m[1])) await loadHistory();
    showAll(); flashRow(m[1]); openScan(m[1]);
    history.replaceState(null, '', location.pathname);
  }
  addEventListener('hashchange', () => { if (state.doctor) focusFromHash(); });

  /* ================= Live updates from the Scanner (only scans this doctor may see) ================= */
  let lastCheck = 0;
  function startLive() {
    const chip = $('liveChip');
    events = liveEvents({
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
      // the live link also drops when the session ends: check (without extending it) and return to the PIN screen if so
      else if (state.doctor && Date.now() - lastCheck > 3000) { lastCheck = Date.now(); api('/api/me'); }
    });
  }

  /* ================= Doctor accounts (department head) ================= */
  async function loadDoctors() {
    const r = await api('/api/doctors');
    if (!r.ok) return;
    $('doctorsBody').innerHTML = r.data.items.map((d) => `
      <tr data-doctor="${d.id}">
        <td><div class="who"><span class="avatar avatar-sm" data-no-i18n>${esc(initials(d.name))}</span><span><b data-no-i18n>${esc(d.name)}</b><small>${esc(d.department)}</small></span></div></td>
        <td>${d.role === 'head' ? 'Department head' : 'Doctor'}</td>
        <td><span class="badge ${d.active ? 'green' : 'red'}">${d.active ? 'Active' : 'Disabled'}</span></td>
        <td class="num-cell">${d.scans}</td>
        <td>${fmtDate(d.created_at)}</td>
        <td class="act">${d.role === 'head' ? '<span class="muted-cell">—</span>'
          : `<button type="button" class="btn btn-sm ${d.active ? 'btn-danger' : 'btn-soft'}" data-access="${d.active ? 'off' : 'on'}" data-name="${esc(d.name)}">${d.active ? 'Disable access' : 'Enable access'}</button>`}</td>
      </tr>`).join('');
  }

  $('doctorsBody').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-access]'); if (!b) return;
    const id = b.closest('tr').dataset.doctor, enable = b.dataset.access === 'on';
    if (!enable && !confirm(`Disable access for ${b.dataset.name}? They are signed out now and cannot use their PIN on either site until access is enabled again.`)) return;
    b.disabled = true;
    const r = await api(`/api/doctors/${id}/access`, { method: 'POST', json: { active: enable } });
    if (r.ok) toast(enable ? `Access enabled for ${r.data.doctor.name}.` : `Access disabled for ${r.data.doctor.name}.`);
    else if (state.doctor) toast(r.data.error || 'The change could not be saved.');
    loadDoctors();
  });

  const docFields = { name: ['fDocName', 'docNameErr', 'docName'], pin: ['fDocPin', 'docPinErr', 'docPin'], confirm: ['fDocPin2', 'docPin2Err', 'docPin2'] };
  function showDocErrors(errs) {
    let first = null;
    Object.entries(docFields).forEach(([key, [wrap, err, input]]) => {
      const msg = errs[key] || '';
      $(err).textContent = msg; $(wrap).classList.toggle('invalid', !!msg);
      $(input).setAttribute('aria-invalid', msg ? 'true' : 'false');
      if (msg && !first) first = $(input);
    });
    if (first) first.focus();
    return !first;
  }
  ['docPin', 'docPin2'].forEach((id) => $(id).addEventListener('input', () => { const up = $(id).value.toUpperCase(); if (up !== $(id).value) $(id).value = up; }));

  $('doctorForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = $('docName').value.replace(/\s+/g, ' ').trim();
    const pin = normPin($('docPin').value), confirmPin = normPin($('docPin2').value);
    const errs = {};
    if (name.length < 2) errs.name = "Enter the doctor's full name (2–80 characters).";
    const pe = pinError(pin); if (pe) errs.pin = pe === 'Doctor PIN is required.' ? 'PIN is required.' : pe;
    if (!errs.pin && confirmPin !== pin) errs.confirm = 'The two PINs do not match.';
    if (!showDocErrors(errs)) return;
    $('docSubmit').disabled = true;
    const r = await api('/api/doctors', { method: 'POST', json: { name, pin } });
    $('docSubmit').disabled = false;
    $('docPin').value = ''; $('docPin2').value = '';
    if (r.ok) {
      $('docName').value = '';
      showDocErrors({});
      $('docName').blur();
      toast(`${r.data.doctor.name} is registered and can sign in now.`);
      loadDoctors();
      return;
    }
    if (!state.doctor) return;
    if (r.data.fields) showDocErrors(r.data.fields);
    else toast(r.data.error || 'The doctor could not be registered.');
  });

  /* ================= Start ================= */
  chrome();
  (async () => {
    const status = await loadStatus();
    const me = await api('/api/me');
    if (me.ok) enter(me.data.doctor);
    else showLogin(status);
  })();
})();
