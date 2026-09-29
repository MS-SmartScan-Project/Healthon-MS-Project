/* MS SmartScan — تفاعل الواجهة */
(() => {
  const $ = (id) => document.getElementById(id);
  const video = $('video'), preview = $('preview'), sweep = $('sweep');
  const analyzeBtn = $('analyzeBtn'), resetBtn = $('resetBtn'), camSelect = $('camSelect');
  const result = $('result');
  let mode = 'camera', stream = null, uploaded = null, busy = false, modelReady = false;

  /* ---------------- حالة النموذج ---------------- */
  async function pollStatus() {
    try {
      const s = await (await fetch('/api/status')).json();
      const chip = $('modelChip');
      if (s.ready) { chip.dataset.state = 'ready'; chip.lastElementChild.textContent = 'النموذج جاهز'; modelReady = true; refreshButton(); return; }
      if (s.error) { chip.dataset.state = 'error'; chip.lastElementChild.textContent = 'النموذج غير محمّل'; chip.title = s.error; return; }
    } catch (e) { /* السيرفر لسه يشتغل */ }
    setTimeout(pollStatus, 1500);
  }

  /* ---------------- التبويبات ---------------- */
  document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => {
    if (busy) return;
    document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('on', x === t));
    mode = t.dataset.mode;
    reset();
  }));

  function reset() {
    preview.hidden = true; preview.removeAttribute('src'); uploaded = null;
    resetBtn.hidden = true; sweep.hidden = true;
    setResult('idle');
    if (mode === 'camera') {
      $('dropZone').hidden = true; camSelect.hidden = camSelect.options.length < 2;
      video.hidden = false; $('camGate').hidden = !!stream;
      analyzeBtn.querySelector('span').textContent = 'التقاط وتحليل';
    } else {
      video.hidden = true; $('camGate').hidden = true; camSelect.hidden = true;
      $('dropZone').hidden = false;
      analyzeBtn.querySelector('span').textContent = 'تحليل الصورة';
    }
    refreshButton();
  }

  function refreshButton() {
    const hasInput = mode === 'camera' ? !!stream : !!uploaded;
    analyzeBtn.disabled = busy || !hasInput || !modelReady || !preview.hidden && mode === 'camera';
  }

  /* ---------------- الكاميرا ---------------- */
  async function startCamera(deviceId) {
    $('camErr').textContent = '';
    if (!navigator.mediaDevices?.getUserMedia) {
      $('camErr').textContent = 'المتصفح لا يدعم الكاميرا — افتحي الموقع عبر http://localhost';
      return;
    }
    try {
      stream?.getTracks().forEach((t) => t.stop());
      stream = await navigator.mediaDevices.getUserMedia({
        video: deviceId ? { deviceId: { exact: deviceId } } : { width: { ideal: 1280 }, height: { ideal: 960 } },
        audio: false,
      });
      video.srcObject = stream;
      $('camGate').hidden = true;
      const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
      if (cams.length > 1 && !camSelect.options.length) {
        cams.forEach((c, i) => camSelect.add(new Option(c.label || `كاميرا ${i + 1}`, c.deviceId)));
      }
      camSelect.hidden = cams.length < 2 || mode !== 'camera';
      refreshButton();
    } catch (e) {
      $('camErr').textContent = 'ما قدرنا نشغّل الكاميرا — اسمحي للمتصفح باستخدامها أو جرّبي «رفع صورة».';
    }
  }
  $('startCam').addEventListener('click', () => startCamera());
  camSelect.addEventListener('change', () => startCamera(camSelect.value));

  /* ---------------- رفع صورة ---------------- */
  const drop = $('dropZone'), fileInput = $('fileInput');
  fileInput.addEventListener('change', () => fileInput.files[0] && loadFile(fileInput.files[0]));
  ['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', (e) => e.dataTransfer.files[0] && loadFile(e.dataTransfer.files[0]));

  function loadFile(file) {
    if (!file.type.startsWith('image/')) return;
    const img = new Image();
    img.onload = () => {
      uploaded = toDataURL(img, img.naturalWidth, img.naturalHeight);
      preview.src = uploaded; preview.hidden = false;
      drop.hidden = true; resetBtn.hidden = false;
      setResult('idle'); refreshButton();
      URL.revokeObjectURL(img.src);
    };
    img.src = URL.createObjectURL(file);
    fileInput.value = '';
  }

  /* يصغّر الصورة لحد أقصى 1600px ويحولها PNG */
  function toDataURL(source, w, h) {
    const k = Math.min(1, 1600 / Math.max(w, h));
    const c = document.createElement('canvas');
    c.width = Math.round(w * k); c.height = Math.round(h * k);
    c.getContext('2d').drawImage(source, 0, 0, c.width, c.height);
    return c.toDataURL('image/png');
  }

  /* ---------------- التحليل ---------------- */
  analyzeBtn.addEventListener('click', async () => {
    if (busy) return;
    let image;
    if (mode === 'camera') {
      if (!video.videoWidth) return;
      image = toDataURL(video, video.videoWidth, video.videoHeight);
      preview.src = image; preview.hidden = false;
    } else image = uploaded;
    if (!image) return;

    busy = true; refreshButton(); resetBtn.hidden = true;
    const label = analyzeBtn.innerHTML;
    analyzeBtn.innerHTML = '<span class="spin"></span> جاري التحليل…';
    sweep.hidden = false;
    setResult('busy'); step(0);
    const t1 = setTimeout(() => step(1), 600), t2 = setTimeout(() => step(2), 1300);

    let data;
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image, patient: $('patient').value, patient_id: $('patientId').value }),
      });
      data = await res.json();
      if (!res.ok) throw new Error(data.error || 'خطأ غير متوقع');
    } catch (e) {
      data = { error: e.message.includes('fetch') ? 'السيرفر متوقف — شغّليه من جديد' : e.message };
    }
    clearTimeout(t1); clearTimeout(t2);
    step(3); await wait(400); step(4);

    sweep.hidden = true; busy = false;
    analyzeBtn.innerHTML = label;
    resetBtn.hidden = false;
    if (!data.error) preview.src = data.annotated + '?t=' + Date.now();
    showResult(data);
    refreshButton();
    loadHistory();
  });

  resetBtn.addEventListener('click', () => { if (!busy) reset(); });

  function step(n) {
    [...$('steps').children].forEach((li, i) => { li.className = i < n ? 'ok' : i === n ? 'active' : ''; });
  }
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  const ICONS = {
    bad: '<svg viewBox="0 0 24 24"><path d="M12 3 2 20h20Z"/><path d="M12 10v4M12 17.5v.01"/></svg>',
    good: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>',
    err: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>',
  };

  function setResult(state, cls = '') { result.className = `panel result ${state} ${cls}`.trim(); }

  function showResult(d) {
    if (d.error) {
      setResult('done', 'err');
      $('rIcon').innerHTML = ICONS.err; $('rTitle').textContent = 'تعذّر التحليل';
      $('gauge').hidden = true; $('rNote').textContent = d.error;
      $('rLesions').textContent = '—'; $('rTime').textContent = '—';
      return;
    }
    const bad = d.result === 'Infected';
    setResult('done', bad ? 'bad' : 'good');
    $('rIcon').innerHTML = bad ? ICONS.bad : ICONS.good;
    $('rTitle').textContent = bad ? 'تم اكتشاف مؤشرات إصابة' : 'لم تُكتشف بؤر';
    $('rLesions').textContent = d.lesions;
    $('rTime').textContent = d.seconds;
    const hasConf = typeof d.confidence === 'number';
    $('gauge').hidden = !hasConf;
    if (hasConf) {
      $('rConf').textContent = d.confidence.toFixed(1) + '%';
      const g = $('gFg'); g.style.strokeDashoffset = 157;
      requestAnimationFrame(() => requestAnimationFrame(() => (g.style.strokeDashoffset = 157 - 157 * d.confidence / 100)));
    }
    $('rNote').textContent = bad
      ? 'البؤر محددة بالمربعات على الصورة. يُنصح بمراجعة طبيب الأعصاب لتأكيد النتيجة.'
      : d.filtered ? 'رُصدت مؤشرات ضعيفة بثقة أقل من 70% فاعتُبرت سليمة.' : 'لم يكتشف النموذج أي بؤر في هذه الصورة.';
  }

  /* ---------------- السجل ---------------- */
  let items = [];
  async function loadHistory() {
    try {
      const d = await (await fetch('/api/history')).json();
      items = d.items;
      $('sTotal').textContent = d.stats.total; $('sInf').textContent = d.stats.infected; $('sOk').textContent = d.stats.healthy;
      $('historyEmpty').hidden = items.length > 0;
      $('historyGrid').innerHTML = items.map((s, i) => `
        <button class="item" data-i="${i}">
          <div class="thumb"><img src="${s.annotated}" alt="" loading="lazy"></div>
          <div class="body">
            <div class="top"><span class="tag ${s.result === 'Infected' ? 'bad' : 'good'}">${s.result === 'Infected' ? 'مؤشرات إصابة' : 'سليم'}</span>
              <span class="conf">${s.confidence != null ? s.confidence + '%' : '—'}</span></div>
            <span class="who">${esc(s.patient || 'بدون اسم')}${s.patient_id ? ' · #' + esc(s.patient_id) : ''}</span>
            <small>${fmt(s.created_at)}</small>
          </div>
        </button>`).join('');
    } catch (e) { /* تجاهل */ }
  }
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (iso) => new Date(iso).toLocaleString('ar-SA-u-ca-gregory-nu-latn', { dateStyle: 'medium', timeStyle: 'short' });

  /* ---------------- نافذة العرض ---------------- */
  const modal = $('modal');
  let current = null;
  $('historyGrid').addEventListener('click', (e) => {
    const b = e.target.closest('.item'); if (!b) return;
    current = items[+b.dataset.i];
    const bad = current.result === 'Infected';
    $('mImg').src = current.annotated;
    $('mTag').className = 'tag ' + (bad ? 'bad' : 'good'); $('mTag').textContent = bad ? 'مؤشرات إصابة' : 'سليم';
    $('mName').textContent = (current.patient || 'بدون اسم') + (current.patient_id ? ' · #' + current.patient_id : '');
    $('mConf').textContent = current.confidence != null ? current.confidence + '%' : '—';
    $('mLes').textContent = current.lesions;
    $('mDate').textContent = fmt(current.created_at);
    $('mTime').textContent = current.seconds + ' ثانية';
    modal.querySelectorAll('.m-toggle button').forEach((x, i) => x.classList.toggle('on', i === 0));
    modal.classList.add('open');
  });
  modal.querySelector('.m-toggle').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b || !current) return;
    modal.querySelectorAll('.m-toggle button').forEach((x) => x.classList.toggle('on', x === b));
    $('mImg').src = current[b.dataset.v];
  });
  modal.addEventListener('click', (e) => { if (e.target === modal || e.target.closest('[data-close]')) modal.classList.remove('open'); });
  document.addEventListener('keydown', (e) => e.key === 'Escape' && modal.classList.remove('open'));
  $('mDelete').addEventListener('click', async () => {
    if (!current || !confirm('حذف هذا الفحص؟')) return;
    await fetch('/api/history/' + current.id, { method: 'DELETE' });
    modal.classList.remove('open'); loadHistory();
  });

  /* ---------------- عام ---------------- */
  const nav = $('nav');
  addEventListener('scroll', () => nav.classList.toggle('scrolled', scrollY > 8), { passive: true });

  reset(); pollStatus(); loadHistory();
})();
