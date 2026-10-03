"""
MS SmartScan — موقع السجل (Patient Registry)
التشغيل:  python server.py   ثم افتحي  http://localhost:8001

موقع مستقل لعرض سجل المرضى والفحوصات وإدارته وتصديره إلى Excel.
يقرأ قاعدة البيانات المشتركة (../data) التي يكتب فيها موقع الفحص (../MRI-Scanner)،
ويراقبها ليُحدّث الصفحة فوراً عند إضافة أو حذف أي فحص.
الدخول برمز الطبيب (PIN): الطبيب يرى مرضاه وفحوصاته فقط، ورئيسة القسم ترى كل سجلات القسم وتدير حسابات الأطباء.
مكتبات بايثون القياسية فقط — لا يحتاج مكتبات الذكاء الاصطناعي.

فك القفل بعد 3 رموز خاطئة (من طرفية هذا الجهاز فقط):  python server.py --reset-lockout
"""
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import webbrowser
from collections import defaultdict, deque
from datetime import datetime
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import auth
import export_xlsx

# ---------------- الإعدادات ----------------
PORT = 8001
CSRF_TOKEN = secrets.token_urlsafe(32)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_REQUESTS = 30
AUTH_RATE_LIMIT = 10          # محاولات دخول في الدقيقة (إضافة إلى القفل بعد 3 رموز خاطئة)
ACTIVITY_RATE_LIMIT = 40      # إشعارات النشاط من الصفحة (مرة كل 5 ثوانٍ كحد أقصى)
WATCH_INTERVAL = 0.7          # ثوانٍ بين كل فحص لتغييرات قاعدة البيانات
SITE = "registry"
COOKIE = "mss_registry_session"
_request_times = defaultdict(deque)
_rate_lock = threading.Lock()

mimetypes.add_type("font/woff2", ".woff2")   # bundled fonts (works offline)
mimetypes.add_type("image/webp", ".webp")   # إصدارات بايثون القديمة على Raspberry Pi لا تعرفه

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
DATA = os.environ.get("MSS_DATA_DIR") or os.path.join(os.path.dirname(BASE), "data")   # قاعدة البيانات المشتركة بين الموقعين
IMAGES = os.path.join(DATA, "images")
DB_PATH = os.path.join(DATA, "smartscan.db")
os.makedirs(IMAGES, exist_ok=True)

AUTH = auth.AuthStore(DB_PATH, DATA)
AUTH.migrate()   # جداول الأطباء والجلسات والقفل + عمود صاحب السجل، وإنشاء رئيسة القسم مرة واحدة


# ---------------- قاعدة البيانات ----------------
def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=10000")
    return con


def table_names(con):
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def tables_ready(con):
    """الجداول يُنشئها موقع الفحص عند أول تشغيل؛ قبل ذلك يكون السجل فارغاً."""
    if not {"scans", "patients"} <= table_names(con):
        return False
    if "owner_doctor_id" not in {r[1] for r in con.execute("PRAGMA table_info(scans)")}:
        AUTH.migrate()   # موقع الفحص أنشأ الجداول بعد تشغيل السجل
    return True


def audit(action, target_id=None, outcome="ok"):
    try:
        with db() as con:
            if "audit_log" in table_names(con):
                con.execute("INSERT INTO audit_log (created_at, action, target_id, outcome) VALUES (?, ?, ?, ?)",
                            (datetime.now().isoformat(timespec="seconds"), action, target_id, outcome))
    except sqlite3.Error as error:
        sys.stderr.write(f"Audit write failed: {error}\n")


def row_to_dict(r):
    d = dict(r)
    for internal in ("owner_doctor_id", "source_sha256", "pixel_sha256"):
        d.pop(internal, None)
    try:
        d["boxes"] = json.loads(d.get("boxes") or "[]")
    except (TypeError, json.JSONDecodeError):
        d["boxes"] = []
    d["image"] = f"/media/{d['id']}.png"
    d["annotated"] = f"/media/{d['id']}_boxes.png"
    original_path = os.path.join(IMAGES, d["id"] + "_original.png")
    d["original"] = f"/media/{d['id']}_original.png" if os.path.isfile(original_path) else d["image"]
    d["media_available"] = os.path.isfile(os.path.join(IMAGES, d["id"] + ".png"))
    return d


def scanner_url():
    """عنوان موقع الفحص كما كتبه عند التشغيل (قد يتغيّر المنفذ إذا كان 8000 مشغولاً)."""
    try:
        with open(os.path.join(DATA, "scanner_url.txt"), encoding="utf-8") as f:
            return f.read().strip() or "http://localhost:8000"
    except OSError:
        return "http://localhost:8000"


# ---------------- الصلاحيات ----------------
# الطبيب: فحوصاته ومرضاه فقط. رئيسة القسم: كل فحوصات أطباء القسم + السجلات القديمة التي ليس لها صاحب.
def scan_scope(doctor, alias="s"):
    if doctor["role"] == "head":
        return (f"({alias}.owner_doctor_id IS NULL OR {alias}.owner_doctor_id IN "
                f"(SELECT id FROM doctors WHERE department = ?))", [doctor["department"]])
    return f"{alias}.owner_doctor_id = ?", [doctor["id"]]


def patient_scope(doctor):
    """Patients the doctor registered, or has scanned (their own scan already shows that patient's name)."""
    own, own_args = scan_scope(doctor, "p")
    scans, scan_args = scan_scope(doctor, "s")
    return (f"({own} OR EXISTS (SELECT 1 FROM scans s WHERE {scans} "
            f"AND UPPER(REPLACE(s.patient_id, ' ', '')) = p.medical_number))", own_args + scan_args)


def owner_visible(doctor, owner_id):
    if doctor["role"] != "head":
        return owner_id is not None and owner_id == doctor["id"]
    if owner_id is None:
        return True
    owner = AUTH.doctor(owner_id)
    return owner is not None and owner["department"] == doctor["department"]


def iso_time(epoch):
    return datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")


def lock_payload(locked_until):
    return {"error": "Too many incorrect PINs. Sign-in is locked for 24 hours.", "code": "locked",
            "locked_until": iso_time(locked_until)}


# ---------------- التحديث المباشر ----------------
# يراقب قاعدة البيانات: أي فحص جديد يحفظه موقع الفحص، أو أي حذف، يُبث فوراً لنوافذ السجل المسموح لها برؤيته.
_events = deque(maxlen=200)          # (رقم تسلسلي، الحدث)
_events_seq = 0
_events_cond = threading.Condition()


def publish(kind, **payload):
    global _events_seq
    with _events_cond:
        _events_seq += 1
        _events.append((_events_seq, {"type": kind, **payload}))
        _events_cond.notify_all()


def watch_database():
    known, last_version, con = None, None, None
    while True:
        try:
            if con is None:
                con = sqlite3.connect(DB_PATH, timeout=10)
            version = con.execute("PRAGMA data_version").fetchone()[0]   # يتغيّر عند كل حفظ من اتصال آخر
            if version != last_version:
                last_version = version
                if "scans" in table_names(con):
                    owner = "owner_doctor_id" if "owner_doctor_id" in {
                        r[1] for r in con.execute("PRAGMA table_info(scans)")} else "NULL"
                    rows = {r[0]: r for r in con.execute(f"SELECT id, patient, patient_id, result, {owner} FROM scans")}
                    if known is not None:
                        for sid in sorted(rows.keys() - known.keys()):
                            _, patient, patient_id, result, owner_id = rows[sid]
                            publish("scan", id=sid, patient=patient, patient_id=patient_id, result=result, owner=owner_id)
                        for sid in known.keys() - rows.keys():
                            publish("delete", id=sid, owner=known[sid][4])
                    known = rows
        except sqlite3.Error:
            if con is not None:
                con.close()
            con = None   # نعيد المحاولة في الدورة التالية
        time.sleep(WATCH_INTERVAL)


# ---------------- الطلبات ----------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SmartScan-Registry"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, fmt, *args):   # سجل مختصر في الطرفية (المسار فقط — الرموز في جسم الطلب ولا تُطبع)
        path = getattr(self, "path", "")   # absent when the connection timed out before sending a request
        if "/api/" in path and "/api/events" not in path and "/api/activity" not in path:
            sys.stdout.write("  %s  %s\n" % (datetime.now().strftime("%H:%M:%S"), self.requestline))

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; img-src 'self' data: blob:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        super().end_headers()

    # الوصول من نفس الجهاز فقط، وبعنوان هذا الموقع فقط
    def request_allowed(self):
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            return False
        host = urlparse("//" + self.headers.get("Host", ""))
        if host.hostname not in ("localhost", "127.0.0.1", "::1") or host.port != self.server.server_port:
            return False
        origin = self.headers.get("Origin")
        if origin:
            o = urlparse(origin)
            return o.scheme == "http" and o.hostname in ("localhost", "127.0.0.1", "::1") and o.port == self.server.server_port
        return True

    def rate_limited(self, bucket="api", limit=RATE_LIMIT_REQUESTS):
        now = time.monotonic()
        with _rate_lock:
            times = _request_times[(bucket, self.client_address[0])]
            while times and now - times[0] > RATE_LIMIT_WINDOW:
                times.popleft()
            if len(times) >= limit:
                return True
            times.append(now)
            return False

    def csrf_valid(self):
        return secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), CSRF_TOKEN)

    def send_json(self, data, code=200, headers=()):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        if not os.path.isfile(path):
            return self.send_error(404)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        private = os.path.realpath(path).startswith(os.path.realpath(IMAGES) + os.sep)
        self.send_header("Cache-Control", "no-store" if private else "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self, max_bytes=4096):
        """Small JSON object from the request body, or None."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if not 0 < length <= max_bytes:
            return None
        body = self.rfile.read(length)
        if self.headers.get_content_type() != "application/json":
            return None
        try:
            data = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    # ---- الجلسة: كوكي HttpOnly، والسيرفر وحده يحدد هوية الطبيب ----
    def session_token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        morsel = cookie.get(COOKIE)
        return morsel.value if morsel else None

    def require_doctor(self, touch=False, head=False):
        """Signed-in doctor, or None after sending 401/403. Only explicit user actions pass touch=True,
        so background requests (live updates, reloads after an event) never keep a session alive."""
        doctor = AUTH.session(SITE, self.session_token(), touch)
        if doctor is None:
            self.send_json({"error": "Your session has ended. Sign in again with your PIN.", "code": "session_expired"}, 401)
            return None
        if head and doctor["role"] != "head":
            self.send_json({"error": "Only the department head can do this.", "code": "forbidden"}, 403)
            return None
        return doctor

    def scan_visible(self, doctor, scan_id):
        where, args = scan_scope(doctor)
        with db() as con:
            if not tables_ready(con):
                return False
            return con.execute(f"SELECT 1 FROM scans s WHERE s.id = ? AND {where}", [scan_id] + args).fetchone() is not None

    def stream_events(self, doctor):
        """Server-Sent Events: pushes each new or deleted scan this doctor may see to the Registry page.
        The stream never extends the session and closes as soon as the session ends."""
        token = self.session_token()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        with _events_cond:
            seen = _events_seq
        try:
            self.wfile.write(b"retry: 3000\n\n")
            self.wfile.flush()
            last_write = time.monotonic()
            while True:
                with _events_cond:
                    _events_cond.wait_for(lambda: _events_seq != seen, timeout=5)
                    pending = [e for n, e in _events if n > seen]
                    seen = _events_seq
                if AUTH.session(SITE, token) is None:
                    return   # انتهت الجلسة (خمول، خروج، أو إيقاف الحساب)
                sent = False
                for event in pending:
                    if not owner_visible(doctor, event.get("owner")):
                        continue
                    data = json.dumps({k: v for k, v in event.items() if k != "owner"}, ensure_ascii=False)
                    self.wfile.write(f"event: {event['type']}\ndata: {data}\n\n".encode("utf-8"))
                    sent = True
                if not sent and time.monotonic() - last_write >= 15:
                    self.wfile.write(b": keep-alive\n\n")   # يمنع انقطاع الاتصال الخامل
                    sent = True
                if sent:
                    self.wfile.flush()
                    last_write = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return   # the browser closed the page

    # ---- GET ----
    def do_GET(self):
        if not self.request_allowed():
            return self.send_error(403)
        path = urlparse(self.path).path
        if path == "/":
            return self.send_file(os.path.join(STATIC, "records.html"))   # الصفحة تعرض شاشة الرمز أولاً؛ لا بيانات فيها
        if path.startswith("/static/"):
            return self.send_file(safe_join(STATIC, path[len("/static/"):]))
        if path == "/api/status":
            locked = AUTH.locked_until(SITE)
            return self.send_json({"csrf_token": CSRF_TOKEN, "locked_until": iso_time(locked) if locked else None,
                                   "idle_seconds": auth.IDLE_SECONDS})
        if path == "/api/info":
            return self.send_json({"scanner_url": scanner_url()})

        # كل ما بعد هذا يحتاج جلسة صالحة
        if path.startswith("/media/"):
            doctor = AUTH.session(SITE, self.session_token())
            if doctor is None:
                return self.send_error(401)
            m = re.fullmatch(r"/media/([0-9A-Za-z-]+)(_boxes|_original)?\.png", path)
            if not m or not self.scan_visible(doctor, m.group(1)):
                return self.send_error(404)
            return self.send_file(safe_join(IMAGES, path[len("/media/"):]))
        if path not in ("/api/me", "/api/events", "/api/history", "/api/patients", "/api/export.xlsx", "/api/doctors"):
            return self.send_error(404)
        doctor = self.require_doctor(head=path == "/api/doctors")
        if doctor is None:
            return None
        if path == "/api/me":
            return self.send_json({"doctor": doctor, "idle_seconds": auth.IDLE_SECONDS})
        if path == "/api/events":
            return self.stream_events(doctor)
        if path == "/api/history":
            return self.send_history(doctor)
        if path == "/api/patients":
            return self.send_patients(doctor)
        if path == "/api/export.xlsx":
            return self.send_export(doctor)
        return self.send_json({"items": AUTH.list_doctors(doctor["department"])})

    def send_history(self, doctor):
        empty = {"total": 0, "infected": 0, "healthy": 0, "uncertain": 0, "patients": 0, "avg_seconds": None}
        with db() as con:
            if not tables_ready(con):
                return self.send_json({"items": [], "stats": empty, "daily": []})
            where, args = scan_scope(doctor)
            pwhere, pargs = patient_scope(doctor)
            rows = con.execute(f"""SELECT s.*, d.name AS owner FROM scans s LEFT JOIN doctors d ON d.id = s.owner_doctor_id
                                   WHERE {where} ORDER BY s.created_at DESC LIMIT 200""", args).fetchall()
            stats = con.execute(f"""SELECT COUNT(*) total,
                SUM(s.result='Infected') infected,
                SUM(s.result='Healthy') healthy,
                SUM(s.result='Uncertain') uncertain,
                AVG(s.seconds) avg_seconds FROM scans s WHERE {where}""", args).fetchone()
            patients = con.execute(f"SELECT COUNT(*) FROM patients p WHERE {pwhere}", pargs).fetchone()[0]
            daily = con.execute(f"""SELECT substr(s.created_at, 1, 10) day, COUNT(*) scans,
                SUM(s.result='Infected') infected FROM scans s
                WHERE {where} AND s.created_at >= date('now', 'localtime', '-13 days')
                GROUP BY day ORDER BY day""", args).fetchall()
        summary = {k: stats[k] or 0 for k in ("total", "infected", "healthy", "uncertain")}
        summary["patients"] = patients
        summary["avg_seconds"] = round(stats["avg_seconds"], 2) if stats["avg_seconds"] is not None else None
        return self.send_json({"items": [row_to_dict(r) for r in rows], "stats": summary,
                               "daily": [dict(d) for d in daily]})

    def send_patients(self, doctor):
        with db() as con:
            if not tables_ready(con):
                return self.send_json({"items": []})
            pwhere, pargs = patient_scope(doctor)
            where, args = scan_scope(doctor)
            rows = con.execute(f"""SELECT p.medical_number, p.name, p.created_at,
                COUNT(s.id) scans, MAX(s.created_at) last_scan
                FROM patients p LEFT JOIN scans s ON UPPER(REPLACE(s.patient_id, ' ', '')) = p.medical_number AND {where}
                WHERE {pwhere}
                GROUP BY p.medical_number ORDER BY last_scan DESC""", args + pargs).fetchall()
        return self.send_json({"items": [dict(r) for r in rows]})

    def send_export(self, doctor):
        # نفس الفلتر والبحث المعروضين في الصفحة، وضمن صلاحيات الطبيب فقط
        params = parse_qs(urlparse(self.path).query)
        result = (params.get("result") or ["all"])[0]
        query = (params.get("q") or [""])[0].strip()[:80]
        rows = []
        with db() as con:
            if tables_ready(con):
                where, args = scan_scope(doctor)
                sql = f"SELECT s.*, d.name AS owner FROM scans s LEFT JOIN doctors d ON d.id = s.owner_doctor_id WHERE {where}"
                if result in export_xlsx.FINDING:
                    sql += " AND s.result = ?"
                    args.append(result)
                if query:
                    sql += " AND (LOWER(COALESCE(s.patient, '')) LIKE ? OR LOWER(COALESCE(s.patient_id, '')) LIKE ?)"
                    args += [f"%{query.lower()}%"] * 2
                rows = [dict(r) for r in con.execute(sql + " ORDER BY s.created_at DESC", args).fetchall()]
        scope = f"All {doctor['department']} records" if doctor["role"] == "head" else f"Records of {doctor['name']}"
        body = export_xlsx.build(rows, export_xlsx.FINDING.get(result, "All results"), query,
                                 exported_by=doctor["name"], scope=scope)
        audit("export", str(doctor["id"]), f"{len(rows)} rows")
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Disposition", f'attachment; filename="ms-smartscan-records-{datetime.now():%Y-%m-%d}.xlsx"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ---- POST: الدخول والخروج والنشاط وإدارة الأطباء ----
    def do_POST(self):
        if not self.request_allowed():
            return self.send_json({"error": "Request not allowed."}, 403)
        path = urlparse(self.path).path
        if path == "/api/activity":
            limited = self.rate_limited("activity", ACTIVITY_RATE_LIMIT)
        elif path == "/api/login":
            limited = self.rate_limited("auth", AUTH_RATE_LIMIT)
        else:
            limited = self.rate_limited()
        if limited:
            return self.send_json({"error": "Too many requests. Please wait a minute and try again.", "code": "rate_limited"}, 429)
        if not self.csrf_valid():
            return self.send_json({"error": "Request could not be verified. Please reload the page.", "code": "csrf"}, 403)
        if path == "/api/login":
            return self.login()
        if path == "/api/logout":
            token = self.session_token()
            doctor = AUTH.session(SITE, token)
            AUTH.end_session(token)
            if doctor:
                audit("logout", str(doctor["id"]), "ok")
            return self.send_json({"ok": True}, headers=[("Set-Cookie", self.cookie("", expire=True))])
        if path == "/api/activity":
            doctor = self.require_doctor(touch=True)
            return self.send_json({"ok": True, "idle_seconds": auth.IDLE_SECONDS}) if doctor else None
        if path == "/api/doctors":
            return self.register_doctor()
        m = re.fullmatch(r"/api/doctors/(\d+)/access", path)
        if m:
            return self.set_doctor_access(int(m.group(1)))
        return self.send_error(404)

    def cookie(self, token, expire=False):
        value = f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict"
        return value + "; Max-Age=0" if expire else value

    def login(self):
        body = self.read_json()
        locked = AUTH.locked_until(SITE)
        if locked:
            return self.send_json(lock_payload(locked), 423, headers=[("Retry-After", str(int(locked - time.time()) + 1))])
        if body is None:
            return self.send_json({"error": "Invalid request data."}, 400)
        pin = auth.normalize_pin(body.get("pin"))
        if not auth.valid_pin(pin):   # صيغة خاطئة: تُرفض ولا تُحتسب محاولة
            return self.send_json({"error": "PIN must be exactly 4 letters or digits (A–Z, 0–9).",
                                   "code": "invalid_format"}, 422)
        result = AUTH.sign_in(SITE, pin)
        status = result["status"]
        if status == "locked":
            audit("login", None, "locked")
            return self.send_json(lock_payload(result["locked_until"]), 423)
        if status == "wrong":
            audit("login", None, "wrong-pin")
            return self.send_json({"error": "Incorrect PIN.", "code": "wrong_pin",
                                   "attempts_left": result["attempts_left"]}, 401)
        doctor = result["doctor"]
        if status == "disabled":
            audit("login", str(doctor["id"]), "disabled")
            return self.send_json({"error": "This doctor account is disabled. Contact the department head.",
                                   "code": "account_disabled"}, 403)
        token = AUTH.create_session(SITE, doctor["id"])
        audit("login", str(doctor["id"]), "ok")
        doctor.pop("created_at", None)
        return self.send_json({"doctor": doctor, "idle_seconds": auth.IDLE_SECONDS},
                              headers=[("Set-Cookie", self.cookie(token))])

    def register_doctor(self):
        head = self.require_doctor(touch=True, head=True)
        if head is None:
            return None
        body = self.read_json()
        if body is None:
            return self.send_json({"error": "Invalid request data."}, 400)
        name = auth.normalize_name(body.get("name"))
        pin = auth.normalize_pin(body.get("pin"))
        fields = {}
        if not auth.valid_name(name):
            fields["name"] = "Enter the doctor's full name (2–80 characters)."
        if not pin:
            fields["pin"] = "PIN is required."
        elif not auth.valid_pin(pin):
            fields["pin"] = "PIN must be exactly 4 letters or digits (A–Z, 0–9)."
        if fields:
            return self.send_json({"error": "Check the highlighted fields.", "code": "validation", "fields": fields}, 422)
        try:
            doctor = AUTH.register_doctor(name, pin, head["department"], head["id"])
        except auth.DuplicatePin:
            audit("doctor-register", None, "duplicate-pin")
            return self.send_json({"error": "This PIN is already in use. Choose a different PIN.", "code": "pin_taken",
                                   "fields": {"pin": "This PIN is already in use. Choose a different PIN."}}, 409)
        audit("doctor-register", str(doctor["id"]), "ok")
        return self.send_json({"doctor": doctor}, 201)

    def set_doctor_access(self, doctor_id):
        head = self.require_doctor(touch=True, head=True)
        if head is None:
            return None
        body = self.read_json()
        if body is None or not isinstance(body.get("active"), bool):
            return self.send_json({"error": "Invalid request data."}, 400)
        doctor = AUTH.set_active(doctor_id, body["active"], head["department"])
        if doctor is None:
            return self.send_json({"error": "Doctor not found."}, 404)
        audit("doctor-access", str(doctor_id), "enabled" if body["active"] else "disabled")
        return self.send_json({"doctor": doctor})

    # ---- DELETE: حذف فحص (ضمن صلاحيات الطبيب فقط) ----
    def do_DELETE(self):
        if not self.request_allowed():
            return self.send_json({"error": "Request not allowed."}, 403)
        if self.rate_limited():
            return self.send_json({"error": "Too many requests. Please wait a minute and try again."}, 429)
        if not self.csrf_valid():
            return self.send_json({"error": "Request could not be verified. Please reload the page.", "code": "csrf"}, 403)
        m = re.match(r"^/api/history/([\w-]+)$", urlparse(self.path).path)
        if not m:
            return self.send_error(404)
        doctor = self.require_doctor(touch=True)
        if doctor is None:
            return None
        sid = m.group(1)
        cursor = None
        with db() as con:
            if tables_ready(con):
                where, args = scan_scope(doctor)
                cursor = con.execute(f"DELETE FROM scans WHERE id = ? AND id IN (SELECT s.id FROM scans s WHERE {where})",
                                     [sid] + args)
        if cursor is None or cursor.rowcount == 0:
            return self.send_json({"error": "Scan not found."}, 404)   # غير موجود أو ليس من صلاحيات هذا الطبيب
        for suffix in (".png", "_boxes.png", "_original.png"):
            p = os.path.join(IMAGES, sid + suffix)
            if os.path.exists(p):
                os.remove(p)
        audit("delete", sid, f"ok by {doctor['id']}")
        return self.send_json({"ok": True})   # مراقب قاعدة البيانات يبث الحذف للنوافذ المسموح لها


def safe_join(root, rel):
    p = os.path.realpath(os.path.join(root, rel))
    return p if p.startswith(os.path.realpath(root) + os.sep) else os.path.join(root, "__none__")


def main():
    global PORT
    if "--reset-lockout" in sys.argv:   # استرجاع إداري: يحتاج الوصول لطرفية الجهاز نفسه
        AUTH.reset_lockout(SITE)
        audit("lockout-reset", SITE, "ok")
        print("  Patient Registry sign-in lockout cleared.")
        return
    if "--port" in sys.argv:
        PORT = int(sys.argv[sys.argv.index("--port") + 1])
    server = None
    for p in range(PORT, PORT + 10):   # لو المنفذ مشغول نجرب اللي بعده
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            server.daemon_threads = True
            break
        except OSError:
            continue
    if server is None:
        sys.exit("No free port found")
    url = f"http://localhost:{p}"
    threading.Thread(target=watch_database, daemon=True).start()

    print("\n  MS SmartScan — Patient Registry")
    print("  -----------------------------")
    print(f"  Website:  {url}")
    print("  Stop:     Ctrl + C\n", flush=True)

    if "--open" in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
