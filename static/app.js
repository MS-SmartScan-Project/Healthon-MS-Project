/* MS SmartScan — clinical workspace interactions */
(() => {
  const $ = (id) => document.getElementById(id);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const els = {
    name: $('patient'), id: $('patientId'), fName: $('fName'), fId: $('fId'),
    nameErr: $('patientErr'), idErr: $('patientIdErr'), hint: $('patientHint'),
    drop: $('dropZone'), fileInput: $('fileInput'), cameraPanel: $('cameraPanel'), camSelect: $('camSelect'),
    startCam: $('startCam'), fileChip: $('fileChip'), imageErr: $('imageErr'),
    analyze: $('analyzeBtn'), after: $('afterActions'),
    video: $('video'), preview: $('preview'), stage: $('stage'), stageInner: $('stageInner'), stageEmpty: $('stageEmpty'),
    scanline: $('scanline'), busy: $('busyOverlay'), elapsed: $('elapsed'), stageTag: $('stageTag'),
    scanStatus: $('scanStatus'), vhPatient: $('vhPatient'), finding: $('finding'),
    nextStep: $('nextStep'), recordSaved: $('recordSaved'),
  };

  const state = {
    mode: 'upload', stream: null, image: null, imageMeta: null, busy: false, modelReady: false,
    csrf: '', result: null, view: 'annotated', zoom: 1, pan: { x: 0, y: 0 },
    items: [], patients: [], filter: 'all', query: '', stats: null,
  };

  const LABEL = { Infected: 'Suspicious lesion', Uncertain: 'Low confidence', Healthy: 'No finding' };
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
  const normId = (v) => v.replace(/\s+/g, '').toUpperCase();
  const normName = (v) => v.replace(/\s+/g, ' ').trim();
  const pct = (v) => (typeof v === 'number' ? v.toFixed(1) + '%' : '—');
  // "No finding" has no lesion boxes, so no model confidence exists (legacy rows stored a placeholder 100).
  const scanConf = (s) => (s.result !== 'Healthy' && s.confidence != null ? pct(s.confidence) : null);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  function toast(msg) {
    const t = $('toast'); t.textContent = msg; t.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, 3200);
  }

  /* ================= Model status ================= */
  async function pollStatus() {
    try {
      const s = await (await fetch('/api/status')).json();
      const chip = $('modelChip');
      state.csrf = s.csrf_token || '';
      if (s.ready) {
        chip.dataset.state = 'ready'; chip.lastElementChild.textContent = 'AI model ready'; chip.title = 'YOLO11n · best.pt loaded';
        state.modelReady = true; updateUI(); return;
      }
      if (s.error) { chip.dataset.state = 'error'; chip.lastElementChild.textContent = 'Model unavailable'; chip.title = s.error; return; }
    } catch (e) { /* server still starting */ }
    setTimeout(pollStatus, 1500);
  }

  /* ================= Patient validation ================= */
  function fieldErrors() {
    const errs = {};
    const name = normName(els.name.value), id = normId(els.id.value);
    if (!name) errs.patient = 'Patient name is required.';
    if (!id) errs.patient_id = 'Medical number is required.';
    else if (!/^[A-Z0-9][A-Z0-9\-_/.]{0,29}$/.test(id)) errs.patient_id = 'Use letters, digits, - _ / . only (maximum 30 characters).';
    else if (mismatchPatient()) errs.patient_id = 'This medical number is registered to a different patient.';
    return errs;
  }

  function showFieldErrors(errs, { focus = false } = {}) {
    const pairs = [['patient', els.fName, els.nameErr, els.name], ['patient_id', els.fId, els.idErr, els.id]];
    let first = null;
    pairs.forEach(([key, wrap, errEl, input]) => {
      const msg = errs[key] || '';
      errEl.textContent = msg;
      wrap.classList.toggle('invalid', !!msg);
      wrap.classList.toggle('valid', !msg && !!input.value.trim());
      input.setAttribute('aria-invalid', msg ? 'true' : 'false');
      if (msg && !first) first = input;
    });
    if (focus && first) { first.focus({ preventScroll: true }); shake(first.closest('.field')); }
    return !first;
  }

  function shake(el) { if (!el) return; el.classList.remove('shake'); void el.offsetWidth; el.classList.add('shake'); }

  const findPatient = (id) => state.patients.find((p) => p.medical_number === id);
  function mismatchPatient() {
    const p = findPatient(normId(els.id.value)); const name = normName(els.name.value);
    return p && name && p.name.toLowerCase() !== name.toLowerCase() ? p : null;
  }

  function updatePatientHint() {
    const id = normId(els.id.value); const p = id && findPatient(id);
    const hint = els.hint;
    if (!p) { hint.hidden = true; return; }
    const name = normName(els.name.value);
    const scans = `${p.scans} previous scan${p.scans === 1 ? '' : 's'}`;
    const last = p.last_scan ? ` · last ${fmtDate(p.last_scan)}` : '';
    hint.hidden = false;
    if (name && name.toLowerCase() !== p.name.toLowerCase()) {
      hint.className = 'patient-hint warn';
      hint.innerHTML = `<span><b>Medical number already registered</b> to ${esc(p.name)} (${scans}).</span><button type="button" data-use>Use name</button>`;
    } else {
      hint.className = 'patient-hint';
      hint.innerHTML = `<span><b>Existing patient:</b> ${esc(p.name)} · ${scans}${esc(last)}</span>${name ? '' : '<button type="button" data-use>Use name</button>'}`;
    }
  }
  els.hint.addEventListener('click', (e) => {
    if (!e.target.closest('[data-use]')) return;
    const p = findPatient(normId(els.id.value)); if (!p) return;
    els.name.value = p.name; onPatientInput();
  });

  let touched = false;
  function onPatientInput() {
    updatePatientHint();
    if (touched) showFieldErrors(fieldErrors());
    else [[els.fName, els.name], [els.fId, els.id]].forEach(([w, i]) => w.classList.toggle('valid', !!i.value.trim()));
    updateUI();
  }
  [els.name, els.id].forEach((i) => {
    i.addEventListener('input', onPatientInput);
    i.addEventListener('blur', () => { if (i.value.trim()) { touched = true; showFieldErrors(fieldErrors()); } });
  });
  $('patientForm').addEventListener('submit', (e) => { e.preventDefault(); runAnalysis(); });
  els.id.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); runAnalysis(); } });

  /* ================= Image source ================= */
  $$('#sourceCard .seg-btn').forEach((b) => b.addEventListener('click', () => {
    if (state.busy || b.dataset.mode === state.mode) return;
    $$('#sourceCard .seg-btn').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-selected', x === b); });
    state.mode = b.dataset.mode;
    clearImage();
    if (state.mode === 'upload') stopCamera();
    updateUI();
  }));

  function stopCamera() {
    state.stream?.getTracks().forEach((t) => t.stop());
    state.stream = null; els.video.srcObject = null;
  }

  async function startCamera(deviceId) {
    els.imageErr.textContent = '';
    if (!navigator.mediaDevices?.getUserMedia) {
      els.imageErr.textContent = 'This browser cannot access the camera. Open the app at http://localhost.';
      return;
    }
    try {
      stopCamera();
      state.stream = await navigator.mediaDevices.getUserMedia({
        video: deviceId ? { deviceId: { exact: deviceId } } : { width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false,
      });
      els.video.srcObject = state.stream;
      await els.video.play();
      const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
      if (cams.length > 1 && !els.camSelect.options.length) cams.forEach((c, i) => els.camSelect.add(new Option(c.label || `Camera ${i + 1}`, c.deviceId)));
      els.camSelect.hidden = cams.length < 2;
      els.startCam.querySelector('span').textContent = 'Restart camera';
    } catch (e) {
      els.imageErr.textContent = 'Camera could not be started. Allow camera access in the browser, or use Upload.';
    }
    updateUI();
  }
  els.startCam.addEventListener('click', () => startCamera());
  els.camSelect.addEventListener('change', () => startCamera(els.camSelect.value));

  els.fileInput.addEventListener('change', () => els.fileInput.files[0] && loadFile(els.fileInput.files[0]));
  ['dragenter', 'dragover'].forEach((ev) => els.drop.addEventListener(ev, (e) => { e.preventDefault(); els.drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach((ev) => els.drop.addEventListener(ev, (e) => { e.preventDefault(); els.drop.classList.remove('over'); }));
  els.drop.addEventListener('drop', (e) => e.dataTransfer.files[0] && loadFile(e.dataTransfer.files[0]));

  function loadFile(file) {
    els.imageErr.textContent = ''; els.drop.classList.remove('invalid');
    const allowed = ['image/png', 'image/jpeg', 'image/webp', 'image/bmp'];
    if (!allowed.includes(file.type)) { els.imageErr.textContent = 'Unsupported file type. Use PNG, JPG, WebP, or BMP.'; return; }
    if (file.size <= 0 || file.size > 10 * 1024 * 1024) { els.imageErr.textContent = 'The image must be 10 MB or smaller.'; return; }
    const img = new Image();
    img.onload = () => {
      state.image = toDataURL(img, img.naturalWidth, img.naturalHeight);
      state.imageMeta = { name: file.name, info: `${img.naturalWidth} × ${img.naturalHeight} px · ${(file.size / 1024 / 1024).toFixed(2)} MB` };
      URL.revokeObjectURL(img.src);
      resetResult();
      showImage(state.image);
      updateUI();
    };
    img.onerror = () => { URL.revokeObjectURL(img.src); els.imageErr.textContent = 'The image file could not be read.'; };
    img.src = URL.createObjectURL(file);
    els.fileInput.value = '';
  }

  /* Downscale to max 1600px and encode as PNG (unchanged from the original pipeline) */
  function toDataURL(source, w, h) {
    const k = Math.min(1, 1600 / Math.max(w, h));
    const c = document.createElement('canvas');
    c.width = Math.round(w * k); c.height = Math.round(h * k);
    c.getContext('2d').drawImage(source, 0, 0, c.width, c.height);
    return c.toDataURL('image/png');
  }

  function clearImage() {
    state.image = null; state.imageMeta = null;
    els.preview.hidden = true; els.preview.removeAttribute('src');
    resetResult(); resetZoom(); updateUI();
  }
  $('clearImage').addEventListener('click', () => { if (!state.busy) clearImage(); });

  function showImage(src) {
    els.preview.src = src; els.preview.hidden = false; els.video.hidden = true; resetZoom();
  }

  /* ================= Viewer: layers & zoom ================= */
  $$('#viewToggle .seg-btn').forEach((b) => b.addEventListener('click', () => {
    if (!state.result || b.disabled) return;
    state.view = b.dataset.view;
    $$('#viewToggle .seg-btn').forEach((x) => x.classList.toggle('on', x === b));
    els.preview.src = state.result[state.view] + '?t=' + Date.now();
  }));

  function applyZoom() {
    els.stageInner.style.transform = `translate(${state.pan.x}px, ${state.pan.y}px) scale(${state.zoom})`;
    $('zoomLevel').textContent = Math.round(state.zoom * 100) + '%';
    els.stage.classList.toggle('zoomed', state.zoom > 1);
  }
  function setZoom(z) { state.zoom = Math.min(4, Math.max(1, z)); if (state.zoom === 1) state.pan = { x: 0, y: 0 }; applyZoom(); }
  function resetZoom() { state.zoom = 1; state.pan = { x: 0, y: 0 }; applyZoom(); }
  $('zoomIn').addEventListener('click', () => setZoom(state.zoom + 0.5));
  $('zoomOut').addEventListener('click', () => setZoom(state.zoom - 0.5));
  $('zoomFit').addEventListener('click', resetZoom);
  els.stage.addEventListener('wheel', (e) => { if (els.preview.hidden) return; e.preventDefault(); setZoom(state.zoom + (e.deltaY < 0 ? 0.25 : -0.25)); }, { passive: false });
  let drag = null;
  els.stage.addEventListener('pointerdown', (e) => {
    if (state.zoom <= 1) return;
    drag = { x: e.clientX - state.pan.x, y: e.clientY - state.pan.y };
    els.stageInner.classList.add('dragging'); els.stage.setPointerCapture(e.pointerId);
  });
  els.stage.addEventListener('pointermove', (e) => { if (!drag) return; state.pan = { x: e.clientX - drag.x, y: e.clientY - drag.y }; applyZoom(); });
  const endDrag = () => { drag = null; els.stageInner.classList.remove('dragging'); };
  els.stage.addEventListener('pointerup', endDrag); els.stage.addEventListener('pointercancel', endDrag);

  /* ================= Workflow UI ================= */
  function setStep(name, cls) { const li = $('stepper').querySelector(`[data-step="${name}"]`); li.className = cls || ''; }

  function updateUI() {
    const errs = fieldErrors();
    const patientOk = !errs.patient && !errs.patient_id;
    const hasInput = state.mode === 'camera' ? (!!state.stream || !!state.image) : !!state.image;
    const r = state.result;

    // stepper
    setStep('patient', patientOk ? 'done' : 'active');
    setStep('mri', hasInput ? 'done' : patientOk ? 'active' : '');
    if (state.busy) { setStep('analysis', 'busy'); setStep('finding', ''); setStep('record', ''); }
    else if (r && r.error) { setStep('analysis', 'fail'); setStep('finding', ''); setStep('record', ''); }
    else if (r) {
      setStep('analysis', 'done');
      setStep('finding', r.result === 'Infected' ? 'fail' : r.result === 'Uncertain' ? 'warn' : 'done');
      setStep('record', 'done');
    } else { setStep('analysis', patientOk && hasInput ? 'active' : ''); setStep('finding', ''); setStep('record', ''); }

    // input panes
    els.drop.hidden = state.mode !== 'upload' || !!state.image;
    els.cameraPanel.hidden = state.mode !== 'camera' || (!!state.image && !!r);
    els.fileChip.hidden = !state.image || state.mode !== 'upload';
    if (state.imageMeta && state.mode === 'upload') {
      $('fileThumb').src = state.image; $('fileName').textContent = state.imageMeta.name; $('fileInfo').textContent = state.imageMeta.info;
    }

    // viewer
    const showVideo = state.mode === 'camera' && !!state.stream && !state.image;
    els.video.hidden = !showVideo;
    els.stageEmpty.hidden = showVideo || !els.preview.hidden;
    const name = normName(els.name.value), id = normId(els.id.value);
    els.vhPatient.innerHTML = name || id ? `<b>${esc(name || 'Unnamed')}</b>${id ? ' · #' + esc(id) : ''}` : 'No patient selected';
    $('mPatient').textContent = name || '—';
    $('mNumber').textContent = id || '—';
    $('mScan').textContent = state.image ? (state.mode === 'camera' ? 'Captured' : 'Loaded') : showVideo ? 'Live camera' : 'No image';

    let status = ['idle', 'Awaiting image'];
    if (state.busy) status = ['busy', 'Analyzing'];
    else if (r && r.error) status = [r.code === 'duplicate_image' ? 'amber' : 'red', r.code === 'duplicate_image' ? 'Duplicate rejected' : 'Analysis failed'];
    else if (r) status = [TONE[r.result], LABEL[r.result]];
    else if (showVideo) status = ['ready', 'Live camera'];
    else if (state.image) status = ['ready', 'Ready to analyze'];
    els.scanStatus.dataset.tone = status[0]; els.scanStatus.textContent = status[1];

    const mA = $('mAnalysis'), mR = $('mResult'), mC = $('mConfidence');
    mA.textContent = state.busy ? 'In progress' : r ? (r.error ? (r.code === 'duplicate_image' ? 'Rejected' : 'Failed') : `Complete · ${r.seconds}s`) : 'Not started';
    mR.className = ''; mC.className = '';
    if (r && !r.error) {
      mR.textContent = LABEL[r.result]; mR.className = 't-' + TONE[r.result];
      mC.textContent = typeof r.confidence === 'number' ? pct(r.confidence) : 'N/A';
    } else { mR.textContent = '—'; mC.textContent = '—'; }

    $$('#viewToggle .seg-btn').forEach((b) => { b.disabled = !r || !!r.error; });

    // primary action
    els.analyze.disabled = state.busy;
    els.analyze.classList.toggle('loading', state.busy);
    els.analyze.querySelector('.btn-label').textContent = state.busy ? 'Analyzing MRI…'
      : !state.modelReady ? 'Waiting for AI model…'
        : state.mode === 'camera' && !state.image ? 'Capture & analyze' : 'Run AI analysis';
    els.analyze.hidden = !!r && !r.error;
    els.after.hidden = !r || !!r.error;
  }

  /* ================= Analysis ================= */
  function progress(active) {
    const order = ['send', 'infer', 'save'];
    $$('#progressSteps li').forEach((li) => {
      const i = order.indexOf(li.dataset.p), a = order.indexOf(active);
      li.className = active === 'all' || i < a ? 'ok' : i === a ? 'active' : '';
    });
  }

  let timer = null;
  async function runAnalysis() {
    if (state.busy) return;
    touched = true;
    const errs = fieldErrors();
    const patientOk = showFieldErrors(errs, { focus: true });

    let image = state.image;   // camera frames are captured below, after validation
    const canCapture = state.mode === 'camera' && state.stream && els.video.videoWidth;
    if (!image && !canCapture) {
      els.imageErr.textContent = state.mode === 'camera' ? 'Start the camera and capture the MRI image.' : 'An MRI image is required.';
      els.drop.classList.add('invalid'); shake($('sourceCard'));
      if (patientOk) $('sourceCard').scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else { els.imageErr.textContent = ''; els.drop.classList.remove('invalid'); }
    if (!patientOk || (!image && !canCapture)) { updateUI(); return; }
    if (!state.modelReady) { toast('The AI model is still loading. Please wait a moment.'); return; }

    if (!image) { // camera capture
      image = toDataURL(els.video, els.video.videoWidth, els.video.videoHeight);
      state.image = image; state.imageMeta = { name: 'Camera capture', info: `${els.video.videoWidth} × ${els.video.videoHeight} px` };
      showImage(image);
    }

    state.busy = true; state.result = null; state.view = 'annotated';
    $$('#viewToggle .seg-btn').forEach((x) => x.classList.toggle('on', x.dataset.view === 'annotated'));
    els.nextStep.hidden = true; els.recordSaved.hidden = true; els.stageTag.hidden = true;
    els.finding.dataset.state = 'busy'; els.finding.dataset.tone = '';
    els.scanline.hidden = false; els.busy.hidden = false;
    const t0 = performance.now();
    timer = setInterval(() => { els.elapsed.textContent = ((performance.now() - t0) / 1000).toFixed(1); }, 100);
    progress('send'); updateUI();

    let data;
    try {
      const req = fetch('/api/analyze', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf },
        body: JSON.stringify({ image, patient: normName(els.name.value), patient_id: normId(els.id.value) }),
      });
      progress('infer');
      const res = await req;
      const type = res.headers.get('content-type') || '';
      if (!type.includes('application/json')) throw new Error('Unexpected response from the server.');
      data = await res.json();
      if (!res.ok) data = { ...data, error: data.error || 'Unexpected error.', status: res.status };
    } catch (e) {
      data = { error: e instanceof TypeError ? 'The local server is not responding. Please restart it.' : e.message };
    }
    clearInterval(timer);
    if (!data.error) { progress('all'); await wait(350); }

    state.busy = false;
    els.scanline.hidden = true; els.busy.hidden = true;
    state.result = data;
    if (data.fields) { showFieldErrors(data.fields, { focus: true }); }
    if (!data.error) {
      els.preview.src = data.annotated + '?t=' + Date.now();
      await Promise.all([loadHistory(), loadPatients()]);
    }
    showResult(data);
    updateUI();
  }
  els.analyze.addEventListener('click', runAnalysis);

  function resetResult() {
    state.result = null;
    els.finding.dataset.state = 'idle'; els.finding.dataset.tone = '';
    els.nextStep.hidden = true; els.recordSaved.hidden = true; els.stageTag.hidden = true;
  }

  function tag(text, tone) { els.stageTag.textContent = text; els.stageTag.className = 'stage-tag ' + tone; els.stageTag.hidden = false; }

  function showResult(d) {
    const f = els.finding; f.dataset.state = 'done';
    const conf = $('confBlock');
    if (d.error) {
      const dup = d.code === 'duplicate_image', mismatch = d.code === 'patient_mismatch';
      f.dataset.tone = dup || mismatch ? 'amber' : 'gray';
      $('fEyebrow').textContent = dup ? 'Upload rejected' : mismatch ? 'Patient check' : 'Analysis not completed';
      $('fIcon').innerHTML = dup ? ICON.copy : ICON.info;
      $('fTitle').textContent = d.title || (mismatch ? 'Medical number conflict' : d.code === 'validation' ? 'Missing information' : 'Analysis could not run');
      $('fText').textContent = dup ? d.error + ' The original patient record has not been changed.' : d.error;
      conf.hidden = true; document.querySelector('.f-stats').hidden = true;
      if (dup) tag('Duplicate MRI — rejected', 'amber');
      return;
    }
    conf.hidden = false; document.querySelector('.f-stats').hidden = false;
    const hasConf = typeof d.confidence === 'number';
    conf.classList.toggle('na', !hasConf);
    $('fConf').textContent = hasConf ? pct(d.confidence) : 'Not applicable';
    const bar = $('fConfBar'); bar.style.width = '0';
    if (hasConf) requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.width = Math.min(100, d.confidence) + '%'; }));
    $('fRegions').textContent = d.lesions;
    $('fTime').textContent = d.seconds + ' s';
    $('fEyebrow').textContent = 'AI finding';

    const ns = els.nextStep;
    if (d.result === 'Infected') {
      f.dataset.tone = 'red'; $('fIcon').innerHTML = ICON.alert;
      $('fTitle').textContent = 'Suspicious lesion detected';
      $('fText').textContent = 'A lesion was detected in the MRI image that may be associated with Multiple Sclerosis (MS) or another demyelinating condition.';
      $('fConfNote').textContent = 'Highest confidence among the lesion regions returned by the model.';
      $('nsLead').textContent = 'Further clinical evaluation is recommended.';
      $('nsTitle').textContent = 'Consider CSF analysis';
      $('nsMarkers').hidden = false;
      $('nsNote').textContent = 'CSF analysis may provide additional evidence to support the diagnostic workup for MS.';
      ns.hidden = false; tag('Suspicious lesion', 'red');
    } else if (d.result === 'Uncertain') {
      f.dataset.tone = 'amber'; $('fIcon').innerHTML = ICON.alert;
      $('fTitle').textContent = 'Low-confidence finding';
      $('fText').textContent = 'The model returned a possible lesion below the 70% review threshold. This result is inconclusive and should not be read as normal or abnormal without expert review.';
      $('fConfNote').textContent = 'Below the 70% threshold (marker on the bar) used to report a suspicious lesion.';
      $('nsLead').textContent = 'Expert review of the MRI is recommended.';
      $('nsTitle').textContent = 'Radiologist review';
      $('nsMarkers').hidden = false;
      $('nsNote').textContent = 'If clinical suspicion of MS remains after review, CSF analysis (OCBs, κ-FLC) may provide additional evidence for the diagnostic workup.';
      ns.hidden = false; tag('Low-confidence finding', 'amber');
    } else {
      f.dataset.tone = 'green'; $('fIcon').innerHTML = ICON.check;
      $('fTitle').textContent = 'No suspicious MS-related pattern detected';
      $('fText').textContent = 'No suspicious MS-related pattern was detected by the current AI screening model.';
      $('fConfNote').textContent = 'The model returned no lesion regions, so no confidence score is reported.';
      ns.hidden = true; tag('No suspicious pattern', 'green');
    }
    $('rsInfo').textContent = `${normName(els.name.value)} · #${normId(els.id.value)} · ${fmtDate(d.created_at)}`;
    $('rsView').dataset.id = d.id;
    els.recordSaved.hidden = false;
  }

  $('rsView').addEventListener('click', (e) => {
    const id = e.currentTarget.dataset.id;
    state.filter = 'all'; state.query = ''; $('search').value = '';
    $$('#filter .seg-btn').forEach((x) => x.classList.toggle('on', x.dataset.filter === 'all'));
    renderRecords();
    setTimeout(() => { const row = $('recordsBody').querySelector(`[data-id="${CSS.escape(id)}"]`); if (row) { row.classList.remove('flash'); void row.offsetWidth; row.classList.add('flash'); } }, 500);
  });

  $('newImageBtn').addEventListener('click', () => { if (state.busy) return; clearImage(); if (state.mode === 'upload') els.fileInput.click(); });
  $('newPatientBtn').addEventListener('click', () => {
    if (state.busy) return;
    els.name.value = ''; els.id.value = ''; touched = false;
    showFieldErrors({}); [els.fName, els.fId].forEach((w) => w.classList.remove('valid'));
    els.hint.hidden = true; clearImage(); els.name.focus();
  });

  /* ================= Records ================= */
  async function loadHistory() {
    try {
      const d = await (await fetch('/api/history')).json();
      state.items = d.items || []; state.stats = d.stats;
      const s = d.stats;
      $('sTotal').textContent = s.total; $('sPatients').textContent = s.patients;
      $('sInf').textContent = s.infected; $('sUncertain').textContent = s.uncertain; $('sOk').textContent = s.healthy;
      const avg = typeof s.avg_seconds === 'number' ? s.avg_seconds.toFixed(1) + ' s' : '—';
      $('sAvg').textContent = avg;
      $('heroAvg').innerHTML = typeof s.avg_seconds === 'number' ? `${s.avg_seconds.toFixed(1)}<small>s</small>` : '—';
      renderChart(d.daily || []);
      renderRecords();
    } catch (e) { /* ignore — server may be restarting */ }
  }

  async function loadPatients() {
    try { state.patients = (await (await fetch('/api/patients')).json()).items || []; updatePatientHint(); } catch (e) { /* ignore */ }
  }

  function filtered() {
    const q = state.query.trim().toLowerCase();
    return state.items.filter((s) => (state.filter === 'all' || s.result === state.filter)
      && (!q || (s.patient || '').toLowerCase().includes(q) || (s.patient_id || '').toLowerCase().includes(q)));
  }

  function renderRecords() {
    const rows = filtered();
    const body = $('recordsBody');
    body.innerHTML = rows.map((s) => `
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
      $('emptyText').textContent = any ? 'Try a different name, medical number, or filter.' : "Completed analyses will appear here with the patient's details.";
    }
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
      if (d.scans) out += `<rect class="bar" x="${x}" y="${base - h}" width="${bw}" height="${h}" rx="3"><title>${d.key}: ${d.scans} scan(s), ${d.inf} suspicious</title></rect>`;
      if (d.inf) out += `<rect class="bar-inf" x="${x}" y="${base - hi}" width="${bw}" height="${hi}" rx="3"/>`;
      if (i % 2 === 1 || i === 13) out += `<text x="${x + bw / 2}" y="${H - 2}" text-anchor="middle">${d.label}</text>`;
    });
    svg.innerHTML = out;
  }

  $('exportCsv').addEventListener('click', () => {
    const rows = filtered();
    if (!rows.length) { toast('No records to export.'); return; }
    const cell = (v) => { const s = String(v ?? ''); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const head = ['Scan ID', 'Date', 'Patient name', 'Medical number', 'AI finding', 'AI confidence (%)', 'Regions flagged', 'Analysis time (s)', 'Model version'];
    const lines = [head, ...rows.map((s) => [s.id, s.created_at, s.patient, s.patient_id, LABEL[s.result] || s.result, s.confidence ?? '', s.lesions, s.seconds, s.inference_version || 'legacy'])];
    const blob = new Blob(['﻿' + lines.map((l) => l.map(cell).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = `ms-smartscan-records-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    toast(`Exported ${rows.length} record${rows.length === 1 ? '' : 's'}.`);
  });

  /* ================= Scan detail modal ================= */
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
      ? 'Suspicious lesion detected that may be associated with MS or another demyelinating condition. Consider CSF analysis (OCBs, κ-FLC) as part of further clinical evaluation.'
      : current.result === 'Uncertain' ? 'Low-confidence finding below the 70% review threshold. Expert radiology review is recommended.'
        : 'No suspicious MS-related pattern was detected by the current AI screening model.';
    $$('#dToggle .seg-btn').forEach((x, i) => x.classList.toggle('on', i === 0));
    modal.classList.add('open');
    modal.querySelector('[data-close]').focus();
  }
  $('recordsBody').addEventListener('click', (e) => { const tr = e.target.closest('tr[data-id]'); if (tr) openScan(tr.dataset.id); });
  $('recordsBody').addEventListener('keydown', (e) => { if (e.key === 'Enter') { const tr = e.target.closest('tr[data-id]'); if (tr) openScan(tr.dataset.id); } });
  $('dToggle').addEventListener('click', (e) => {
    const b = e.target.closest('.seg-btn'); if (!b || !current) return;
    $$('#dToggle .seg-btn').forEach((x) => x.classList.toggle('on', x === b));
    $('dImg').src = current[b.dataset.v];
  });
  const closeModal = () => modal.classList.remove('open');
  modal.addEventListener('click', (e) => { if (e.target === modal || e.target.closest('[data-close]')) closeModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  $('dDelete').addEventListener('click', async () => {
    if (!current || !confirm(`Delete this scan for ${current.patient || 'this patient'}? This cannot be undone.`)) return;
    const res = await fetch('/api/history/' + encodeURIComponent(current.id), { method: 'DELETE', headers: { 'X-CSRF-Token': state.csrf } });
    if (!res.ok) { toast('The scan could not be deleted. Reload the page and try again.'); return; }
    closeModal(); toast('Scan deleted.'); await Promise.all([loadHistory(), loadPatients()]);
  });

  /* ================= Page chrome ================= */
  const topbar = $('topbar');
  addEventListener('scroll', () => topbar.classList.toggle('scrolled', scrollY > 8), { passive: true });
  const navLinks = $$('.topnav a');
  const spy = new IntersectionObserver((entries) => {
    entries.forEach((en) => { if (en.isIntersecting) navLinks.forEach((a) => a.classList.toggle('active', a.dataset.nav === en.target.id)); });
  }, { rootMargin: '-45% 0px -50% 0px' });
  ['workspace', 'records', 'technology'].forEach((id) => spy.observe($(id)));

  try { if (!localStorage.getItem('mss-notice-ack')) $('notice').hidden = false; } catch (e) { $('notice').hidden = false; }
  $('noticeOk').addEventListener('click', () => { $('notice').hidden = true; try { localStorage.setItem('mss-notice-ack', '1'); } catch (e) { /* ignore */ } });

  addEventListener('beforeunload', stopCamera);
  updateUI(); pollStatus(); loadHistory(); loadPatients();
})();
