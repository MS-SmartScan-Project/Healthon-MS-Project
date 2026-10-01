"""
MS SmartScan — موقع السجل (Patient Registry)
التشغيل:  python server.py   ثم افتحي  http://localhost:8001

موقع مستقل لعرض سجل المرضى والفحوصات وإدارته وتصديره إلى Excel.
يقرأ قاعدة البيانات المشتركة (../data) التي يكتب فيها موقع الفحص (../MRI-Scanner)،
ويراقبها ليُحدّث الصفحة فوراً عند إضافة أو حذف أي فحص.
مكتبات بايثون القياسية فقط — لا يحتاج مكتبات الذكاء الاصطناعي.
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import export_xlsx

# ---------------- الإعدادات ----------------
PORT = 8001
CSRF_TOKEN = secrets.token_urlsafe(32)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_REQUESTS = 30
WATCH_INTERVAL = 0.7          # ثوانٍ بين كل فحص لتغييرات قاعدة البيانات
_request_times = defaultdict(deque)
_rate_lock = threading.Lock()

mimetypes.add_type("image/webp", ".webp")   # إصدارات بايثون القديمة على Raspberry Pi لا تعرفه

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
DATA = os.path.join(os.path.dirname(BASE), "data")   # قاعدة البيانات المشتركة بين الموقعين
IMAGES = os.path.join(DATA, "images")
DB_PATH = os.path.join(DATA, "smartscan.db")
os.makedirs(IMAGES, exist_ok=True)


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
    return {"scans", "patients"} <= table_names(con)


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


# ---------------- التحديث المباشر ----------------
# يراقب قاعدة البيانات: أي فحص جديد يحفظه موقع الفحص، أو أي حذف، يُبث فوراً لكل نافذة سجل مفتوحة.
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
                    rows = {r[0]: r for r in con.execute("SELECT id, patient, patient_id, result FROM scans")}
                    if known is not None:
                        for sid in sorted(rows.keys() - known.keys()):
                            _, patient, patient_id, result = rows[sid]
                            publish("scan", id=sid, patient=patient, patient_id=patient_id, result=result)
                        for sid in known.keys() - rows.keys():
                            publish("delete", id=sid)
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

    def log_message(self, fmt, *args):   # سجل مختصر في الطرفية
        if "/api/" in self.path and "/api/events" not in self.path:
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
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data: blob:; "
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

    def rate_limited(self):
        now = time.monotonic()
        with _rate_lock:
            times = _request_times[self.client_address[0]]
            while times and now - times[0] > RATE_LIMIT_WINDOW:
                times.popleft()
            if len(times) >= RATE_LIMIT_REQUESTS:
                return True
            times.append(now)
            return False

    def csrf_valid(self):
        return secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), CSRF_TOKEN)

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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
        private = os.path.commonpath((os.path.realpath(path), os.path.realpath(IMAGES))) == os.path.realpath(IMAGES)
        self.send_header("Cache-Control", "no-store" if private else "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def stream_events(self):
        """Server-Sent Events: pushes each new or deleted scan to this Registry page."""
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
            while True:
                with _events_cond:
                    _events_cond.wait_for(lambda: _events_seq != seen, timeout=15)
                    pending = [e for n, e in _events if n > seen]
                    seen = _events_seq
                if pending:
                    for event in pending:
                        data = json.dumps(event, ensure_ascii=False)
                        self.wfile.write(f"event: {event['type']}\ndata: {data}\n\n".encode("utf-8"))
                else:
                    self.wfile.write(b": keep-alive\n\n")   # يمنع انقطاع الاتصال الخامل
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return   # the browser closed the page

    # ---- GET ----
    def do_GET(self):
        if not self.request_allowed():
            return self.send_error(403)
        path = urlparse(self.path).path
        if path == "/":
            return self.send_file(os.path.join(STATIC, "records.html"))
        if path.startswith("/static/"):
            return self.send_file(safe_join(STATIC, path[len("/static/"):]))
        if path.startswith("/media/"):
            return self.send_file(safe_join(IMAGES, path[len("/media/"):]))
        if path == "/api/status":
            return self.send_json({"csrf_token": CSRF_TOKEN})
        if path == "/api/info":
            return self.send_json({"scanner_url": scanner_url()})
        if path == "/api/events":
            return self.stream_events()
        if path == "/api/history":
            return self.send_history()
        if path == "/api/patients":
            with db() as con:
                if not tables_ready(con):
                    return self.send_json({"items": []})
                rows = con.execute("""SELECT p.medical_number, p.name, p.created_at,
                    COUNT(s.id) scans, MAX(s.created_at) last_scan
                    FROM patients p LEFT JOIN scans s ON UPPER(REPLACE(s.patient_id, ' ', '')) = p.medical_number
                    GROUP BY p.medical_number ORDER BY last_scan DESC""").fetchall()
            return self.send_json({"items": [dict(r) for r in rows]})
        if path == "/api/export.xlsx":
            return self.send_export()
        self.send_error(404)

    def send_history(self):
        empty = {"total": 0, "infected": 0, "healthy": 0, "uncertain": 0, "patients": 0, "avg_seconds": None}
        with db() as con:
            if not tables_ready(con):
                return self.send_json({"items": [], "stats": empty, "daily": []})
            rows = con.execute("SELECT * FROM scans ORDER BY created_at DESC LIMIT 200").fetchall()
            stats = con.execute("""SELECT COUNT(*) total,
                SUM(result='Infected') infected,
                SUM(result='Healthy') healthy,
                SUM(result='Uncertain') uncertain,
                AVG(seconds) avg_seconds FROM scans""").fetchone()
            patients = con.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
            daily = con.execute("""SELECT substr(created_at, 1, 10) day, COUNT(*) scans,
                SUM(result='Infected') infected FROM scans
                WHERE created_at >= date('now', 'localtime', '-13 days')
                GROUP BY day ORDER BY day""").fetchall()
        summary = {k: stats[k] or 0 for k in ("total", "infected", "healthy", "uncertain")}
        summary["patients"] = patients
        summary["avg_seconds"] = round(stats["avg_seconds"], 2) if stats["avg_seconds"] is not None else None
        return self.send_json({"items": [row_to_dict(r) for r in rows], "stats": summary,
                               "daily": [dict(d) for d in daily]})

    def send_export(self):
        # نفس الفلتر والبحث المعروضين في الصفحة
        params = parse_qs(urlparse(self.path).query)
        result = (params.get("result") or ["all"])[0]
        query = (params.get("q") or [""])[0].strip()[:80]
        rows = []
        with db() as con:
            if tables_ready(con):
                sql, args = "SELECT * FROM scans WHERE 1=1", []
                if result in export_xlsx.FINDING:
                    sql += " AND result = ?"
                    args.append(result)
                if query:
                    sql += " AND (LOWER(COALESCE(patient, '')) LIKE ? OR LOWER(COALESCE(patient_id, '')) LIKE ?)"
                    args += [f"%{query.lower()}%"] * 2
                rows = [dict(r) for r in con.execute(sql + " ORDER BY created_at DESC", args).fetchall()]
        body = export_xlsx.build(rows, export_xlsx.FINDING.get(result, "All results"), query)
        audit("export", None, f"{len(rows)} rows")
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Disposition", f'attachment; filename="ms-smartscan-records-{datetime.now():%Y-%m-%d}.xlsx"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ---- POST: لا يوجد — هذا الموقع لا يستقبل فحوصات ----
    def do_POST(self):
        self.send_error(404)

    # ---- DELETE: حذف فحص ----
    def do_DELETE(self):
        if not self.request_allowed():
            return self.send_json({"error": "Request not allowed."}, 403)
        if self.rate_limited():
            return self.send_json({"error": "Too many requests. Please wait a minute and try again."}, 429)
        if not self.csrf_valid():
            return self.send_json({"error": "Request could not be verified. Please reload the page."}, 403)
        m = re.match(r"^/api/history/([\w-]+)$", urlparse(self.path).path)
        if not m:
            return self.send_error(404)
        sid = m.group(1)
        with db() as con:
            cursor = con.execute("DELETE FROM scans WHERE id = ?", (sid,)) if tables_ready(con) else None
        if cursor is None or cursor.rowcount == 0:
            return self.send_json({"error": "Scan not found."}, 404)
        for suffix in (".png", "_boxes.png", "_original.png"):
            p = os.path.join(IMAGES, sid + suffix)
            if os.path.exists(p):
                os.remove(p)
        audit("delete", sid, "ok")
        return self.send_json({"ok": True})   # مراقب قاعدة البيانات يبث الحذف لكل النوافذ


def safe_join(root, rel):
    p = os.path.realpath(os.path.join(root, rel))
    return p if p.startswith(os.path.realpath(root) + os.sep) else os.path.join(root, "__none__")


def main():
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
    print("  Stop:     Ctrl + C\n")

    if "--open" in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
