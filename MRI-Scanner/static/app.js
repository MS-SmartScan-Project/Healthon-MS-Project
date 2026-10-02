/* MS SmartScan — MRI Scanner (results are saved to the Patient Registry automatically) */
(() => {
  // The Scanner never reads the registry: it only submits scans. Records are viewed on the separate Patient Registry site.
  const { $, $$, LABEL, TONE, ICON, esc, fmtDate, pct, wait, toast, chrome } = window.MSS;
  window.name = 'mss-scanner';   // the Registry's "MRI Scanner" link reuses this window

  const els = {
    name: $('patient'), id: $('patientId'), fName: $('fName'), fId: $('fId'),
    nameErr: $('patientErr'), idErr: $('patientIdErr'),
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
  };

  const normId = (v) => v.replace(/\s+/g, '').toUpperCase();
  const normName = (v) => v.replace(/\s+/g, ' ').trim();

  /* ================= Model status ================= */
  async function pollStatus() {
    try {
      const s = await (await fetch('/api/status')).json();
      const chip = $('modelChip');
      state.csrf = s.csrf_token || '';
      if (s.ready) {
        chip.dataset.state = 'ready'; chip.lastElementChild.textContent = 'AI model ready'; chip.title = 'YOLO26s · lesion model loaded';
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

  let touched = false;
  function onPatientInput() {
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
      state.image = toSquare640(img, img.naturalWidth, img.naturalHeight);
      state.imageMeta = { name: file.name, info: `${img.naturalWidth} × ${img.naturalHeight} → ${MODEL_SIZE} × ${MODEL_SIZE} px` };
      URL.revokeObjectURL(img.src);
      resetResult();
      showImage(state.image);
      updateUI();
    };
    img.onerror = () => { URL.revokeObjectURL(img.src); els.imageErr.textContent = 'The image file could not be read.'; };
    img.src = URL.createObjectURL(file);
    els.fileInput.value = '';
  }

  /* Every image sent to the model is the centre square, resized to the model's 640 × 640 input.
     The live camera view shows exactly this square, so what you see is what gets analyzed. */
  const MODEL_SIZE = 640;
  function toSquare640(source, w, h) {
    const side = Math.min(w, h);
    const c = document.createElement('canvas');
    c.width = MODEL_SIZE; c.height = MODEL_SIZE;
    c.getContext('2d').drawImage(source, (w - side) / 2, (h - side) / 2, side, side, 0, 0, MODEL_SIZE, MODEL_SIZE);
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
    $('camHint').hidden = !showVideo;
    els.stageEmpty.hidden = showVideo || !els.preview.hidden;
    const name = normName(els.name.value), id = normId(els.id.value);
    els.vhPatient.innerHTML = name || id ? `<b>${esc(name || 'Unnamed')}</b>${id ? ' · #' + esc(id) : ''}` : 'No patient selected';
    $('mPatient').textContent = name || '—';
    $('mNumber').textContent = id || '—';
    $('mScan').textContent = state.image ? (state.mode === 'camera' ? 'Captured' : 'Loaded') : showVideo ? 'Live camera' : 'No image';

    let status = ['idle', 'Awaiting image'];
    if (state.busy) status = ['busy', 'Analyzing'];
    else if (r && r.error) status = r.code === 'duplicate_image' ? ['amber', 'Duplicate rejected'] : r.code === 'not_mri' ? ['amber', 'Not an MRI'] : ['red', 'Analysis failed'];
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
      image = toSquare640(els.video, els.video.videoWidth, els.video.videoHeight);
      state.image = image; state.imageMeta = { name: 'Camera capture', info: `${MODEL_SIZE} × ${MODEL_SIZE} px` };
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
      await loadStats();
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
      if (d.code === 'not_mri') tag('Not an MRI — rejected', 'amber');
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
      // The model finds white matter lesions but cannot tell MS from small vessel disease (SVD) — see README
      $('fTitle').textContent = 'Abnormal';
      $('fText').textContent = 'White matter lesions were detected. They may indicate Multiple Sclerosis (MS) or cerebral Small Vessel Disease (SVD); MRI appearance alone cannot reliably tell them apart.';
      $('fConfNote').textContent = 'Highest confidence among the lesion regions returned by the model.';
      $('nsLead').textContent = 'Further evaluation is needed to differentiate MS from SVD.';
      $('nsSub').textContent = 'Tests that help tell MS and SVD apart';
      ns.hidden = false; tag('Abnormal', 'red');
    } else if (d.result === 'Uncertain') {
      f.dataset.tone = 'amber'; $('fIcon').innerHTML = ICON.alert;
      $('fTitle').textContent = 'Abnormal (low confidence)';
      $('fText').textContent = 'The model found a possible white matter lesion with confidence below the 50% review threshold. Expert review is recommended before acting on this result.';
      $('fConfNote').textContent = 'Below the 50% threshold (marker on the bar) used to report an abnormal result.';
      $('nsLead').textContent = 'Expert radiology review of this MRI is recommended first.';
      $('nsSub').textContent = 'If a lesion is confirmed on review';
      ns.hidden = false; tag('Abnormal (low confidence)', 'amber');
    } else {
      f.dataset.tone = 'green'; $('fIcon').innerHTML = ICON.check;
      $('fTitle').textContent = 'Normal';
      $('fText').textContent = 'No white matter lesion was detected by the AI screening model.';
      $('fConfNote').textContent = 'The model returned no lesion regions, so no confidence score is reported.';
      ns.hidden = true; tag('Normal', 'green');
    }
    $('rsInfo').textContent = `${normName(els.name.value)} · #${normId(els.id.value)} · ${fmtDate(d.created_at)}`;
    els.recordSaved.hidden = false;
  }

  $('newImageBtn').addEventListener('click', () => { if (state.busy) return; clearImage(); if (state.mode === 'upload') els.fileInput.click(); });
  $('newPatientBtn').addEventListener('click', () => {
    if (state.busy) return;
    els.name.value = ''; els.id.value = ''; touched = false;
    showFieldErrors({}); [els.fName, els.fId].forEach((w) => w.classList.remove('valid'));
    clearImage(); els.name.focus();
  });

  /* ================= Hero stat (no patient data) ================= */
  async function loadStats() {
    try {
      const s = await (await fetch('/api/stats')).json();
      $('heroAvg').innerHTML = typeof s.avg_seconds === 'number' ? `${s.avg_seconds.toFixed(1)}<small>s</small>` : '—';
    } catch (e) { /* ignore — server may be restarting */ }
  }

  /* ================= Page chrome ================= */
  chrome();
  const navLinks = $$('.topnav a[data-nav]');
  const spy = new IntersectionObserver((entries) => {
    entries.forEach((en) => { if (en.isIntersecting) navLinks.forEach((a) => a.classList.toggle('active', a.dataset.nav === en.target.id)); });
  }, { rootMargin: '-45% 0px -50% 0px' });
  ['workspace', 'technology'].forEach((id) => spy.observe($(id)));

  try { if (!localStorage.getItem('mss-notice-ack')) $('notice').hidden = false; } catch (e) { $('notice').hidden = false; }
  $('noticeOk').addEventListener('click', () => { $('notice').hidden = true; try { localStorage.setItem('mss-notice-ack', '1'); } catch (e) { /* ignore */ } });

  addEventListener('beforeunload', stopCamera);
  updateUI(); pollStatus(); loadStats();
})();