"""
MS SmartScan — سيرفر الموقع
التشغيل:  python server.py   ثم افتحي  http://localhost:8000

لا يحتاج PHP ولا XAMPP ولا MySQL — مكتبات بايثون القياسية فقط + ultralytics و opencv.
السجل يُحفظ في ملف SQLite داخل مجلد data (يُنشأ تلقائياً).
"""
import base64
import hashlib
import json
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import sys
import threading
import time
import uuid
import webbrowser
from binascii import Error as Base64Error
from collections import defaultdict, deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

try:
    import cv2
    import numpy as np
    import detector
except ImportError as error:
    sys.exit(f"Missing dependency: {error.name}. Run: python -m pip install -r requirements.txt")

# ---------------- الإعدادات ----------------
PORT = 8000
MIN_CONFIDENCE = 70      # أقل من ذلك تُعرض النتيجة كغير حاسمة، لا كسليمة
MAX_UPLOAD_MB = 15
MAX_IMAGE_PIXELS = 25_000_000
CSRF_TOKEN = secrets.token_urlsafe(32)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_REQUESTS = 30
INFERENCE_VERSION = "yolo11n-clahe-tta-v2"
_request_times = defaultdict(deque)
_rate_lock = threading.Lock()

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
DATA = os.path.join(BASE, "data")
IMAGES = os.path.join(DATA, "images")
BACKUPS = os.path.join(DATA, "backups")
DB_PATH = os.path.join(DATA, "smartscan.db")
os.makedirs(IMAGES, exist_ok=True)
os.makedirs(BACKUPS, exist_ok=True)


# ---------------- قاعدة البيانات (SQLite) ----------------
def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=10000")
    return con


with db() as con:
    con.execute("""CREATE TABLE IF NOT EXISTS scans (
        id          TEXT PRIMARY KEY,
        created_at  TEXT NOT NULL,
        patient     TEXT,
        patient_id  TEXT,
        result      TEXT NOT NULL,      -- Infected / Healthy / Uncertain
        confidence  REAL,
        raw_result  TEXT,               -- ناتج النموذج قبل قاعدة الـ 70%
        lesions     INTEGER NOT NULL DEFAULT 0,
        boxes       TEXT,               -- JSON
        seconds     REAL
    )""")
    existing_columns = {row[1] for row in con.execute("PRAGMA table_info(scans)")}
    if "source_sha256" not in existing_columns:
        con.execute("ALTER TABLE scans ADD COLUMN source_sha256 TEXT")
    if "inference_version" not in existing_columns:
        con.execute("ALTER TABLE scans ADD COLUMN inference_version TEXT")
    con.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at  TEXT NOT NULL,
        action      TEXT NOT NULL,
        target_id   TEXT,
        outcome     TEXT NOT NULL
    )""")


def backup_database():
    """Create a consistent local backup and keep the newest seven copies."""
    if not os.path.isfile(DB_PATH):
        return
    backup_path = os.path.join(BACKUPS, datetime.now().strftime("smartscan-%Y%m%d-%H%M%S.db"))
    source = sqlite3.connect(DB_PATH, timeout=10)
    destination = sqlite3.connect(backup_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    backups = sorted(
        (path for path in os.listdir(BACKUPS) if re.fullmatch(r"smartscan-\d{8}-\d{6}\.db", path)),
        reverse=True,
    )
    for old_name in backups[7:]:
        os.remove(os.path.join(BACKUPS, old_name))


def audit(action, target_id=None, outcome="ok"):
    try:
        with db() as con:
            con.execute(
                "INSERT INTO audit_log (created_at, action, target_id, outcome) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"), action, target_id, outcome),
            )
    except sqlite3.Error as error:
        sys.stderr.write(f"Audit write failed: {error}\n")


backup_database()


def row_to_dict(r):
    d = dict(r)
    try:
        d["boxes"] = json.loads(d["boxes"] or "[]")
    except (TypeError, json.JSONDecodeError):
        d["boxes"] = []
    d["image"] = f"/media/{d['id']}.png"
    d["annotated"] = f"/media/{d['id']}_boxes.png"
    original_path = os.path.join(IMAGES, d["id"] + "_original.png")
    d["original"] = f"/media/{d['id']}_original.png" if os.path.isfile(original_path) else d["image"]
    d["media_available"] = os.path.isfile(os.path.join(IMAGES, d["id"] + ".png"))
    return d


# ---------------- الطلبات ----------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SmartScan"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, fmt, *args):   # سجل مختصر في الطرفية
        if "/api/" in self.path:
            sys.stdout.write("  %s  %s\n" % (datetime.now().strftime("%H:%M:%S"), self.requestline))

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data: blob:; media-src 'self' blob:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        super().end_headers()

    def client_allowed(self):
        return self.client_address[0] in ("127.0.0.1", "::1")

    def host_allowed(self):
        host = self.headers.get("Host", "")
        parsed = urlparse("//" + host)
        return parsed.hostname in ("localhost", "127.0.0.1", "::1") and parsed.port == self.server.server_port

    def origin_allowed(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        return (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
                and parsed.port == self.server.server_port)

    def request_allowed(self):
        return self.client_allowed() and self.host_allowed() and self.origin_allowed()

    def rate_limited(self):
        now = time.monotonic()
        key = self.client_address[0]
        with _rate_lock:
            times = _request_times[key]
            while times and now - times[0] > RATE_LIMIT_WINDOW:
                times.popleft()
            if len(times) >= RATE_LIMIT_REQUESTS:
                return True
            times.append(now)
            return False

    def csrf_valid(self):
        return secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), CSRF_TOKEN)

    # ---- أدوات ----
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
        is_private_media = os.path.commonpath((os.path.realpath(path), os.path.realpath(IMAGES))) == os.path.realpath(IMAGES)
        self.send_header("Cache-Control", "no-store" if is_private_media else "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ---- GET ----
    def do_GET(self):
        if not self.request_allowed():
            return self.send_error(403)
        path = urlparse(self.path).path
        if path == "/":
            return self.send_file(os.path.join(STATIC, "index.html"))
        if path.startswith("/static/"):
            return self.send_file(safe_join(STATIC, path[len("/static/"):]))
        if path.startswith("/media/"):
            return self.send_file(safe_join(IMAGES, path[len("/media/"):]))
        if path == "/api/status":
            return self.send_json({**detector.status(), "min_confidence": MIN_CONFIDENCE,
                                   "csrf_token": CSRF_TOKEN})
        if path == "/api/history":
            with db() as con:
                rows = con.execute("SELECT * FROM scans ORDER BY created_at DESC LIMIT 60").fetchall()
                stats = con.execute("""SELECT COUNT(*) total,
                    SUM(result='Infected') infected,
                    SUM(result='Healthy') healthy,
                    SUM(result='Uncertain') uncertain FROM scans""").fetchone()
            return self.send_json({"items": [row_to_dict(r) for r in rows],
                                   "stats": {k: stats[k] or 0 for k in ("total", "infected", "healthy", "uncertain")}})
        self.send_error(404)

    # ---- POST: تحليل صورة ----
    def do_POST(self):
        if not self.request_allowed():
            return self.send_json({"error": "غير مسموح"}, 403)
        if self.rate_limited():
            return self.send_json({"error": "طلبات كثيرة؛ حاولي بعد دقيقة"}, 429)
        if not self.csrf_valid():
            return self.send_json({"error": "تعذر التحقق من الطلب"}, 403)
        if urlparse(self.path).path != "/api/analyze":
            return self.send_error(404)
        if self.headers.get_content_type() != "application/json":
            return self.send_json({"error": "نوع الطلب غير مدعوم"}, 415)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.send_json({"error": "طول الطلب غير صالح"}, 400)
        if length <= 0 or length > MAX_UPLOAD_MB * 1024 * 1024:
            return self.send_json({"error": "حجم الصورة غير مناسب"}, 413)
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            image_value = payload.get("image", "")
            if not isinstance(image_value, str):
                raise ValueError("image must be a string")
            m = re.fullmatch(r"data:image/(png|jpe?g|webp|bmp);base64,([A-Za-z0-9+/=\r\n]+)", image_value)
            if not m:
                return self.send_json({"error": "لم تصل صورة صالحة"}, 422)
            raw = base64.b64decode(m.group(2), validate=True)
        except (ValueError, TypeError, json.JSONDecodeError, Base64Error):
            return self.send_json({"error": "بيانات غير صالحة"}, 400)

        if not detector.status()["ready"]:
            return self.send_json({"error": "النموذج لسه يتحمّل أو فيه مكتبة ناقصة — راجعي الطرفية"}, 503)

        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if image is None or image.ndim not in (2, 3):
            return self.send_json({"error": "ملف الصورة غير صالح"}, 422)
        height, width = image.shape[:2]
        if width < 32 or height < 32 or width * height > MAX_IMAGE_PIXELS:
            return self.send_json({"error": "أبعاد الصورة غير مسموحة"}, 422)

        scan_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex
        original_path = os.path.join(IMAGES, scan_id + "_original.png")
        img_path = os.path.join(IMAGES, scan_id + ".png")
        ann_path = os.path.join(IMAGES, scan_id + "_boxes.png")
        if not cv2.imwrite(original_path, image):
            audit("analyze", scan_id, "image-save-failed")
            return self.send_json({"error": "تعذر حفظ الصورة"}, 500)

        t0 = time.time()
        try:
            out = detector.analyze(original_path, img_path, ann_path)
        except Exception as e:
            for p in (original_path, img_path, ann_path):
                if os.path.exists(p):
                    os.remove(p)
            sys.stderr.write(f"Analysis failed for {scan_id}: {e}\n")
            audit("analyze", scan_id, "analysis-failed")
            return self.send_json({"error": "تعذّر تحليل الصورة"}, 500)
        seconds = round(time.time() - t0, 2)

        result = out["result"]
        conf = None if result == "Healthy" else out["confidence"]
        uncertain = result == "Infected" and conf is not None and conf < MIN_CONFIDENCE
        if uncertain:
            result = "Uncertain"

        patient = payload.get("patient")
        patient_id = payload.get("patient_id")
        patient = patient.strip()[:80] or None if isinstance(patient, str) else None
        patient_id = patient_id.strip()[:30] or None if isinstance(patient_id, str) else None

        rec = {
            "id": scan_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "patient": patient,
            "patient_id": patient_id,
            "result": result,
            "confidence": conf,
            "raw_result": f'{out["result"]},{out["confidence"]}',
            "lesions": len(out["boxes"]),
            "boxes": json.dumps(out["boxes"]),
            "seconds": seconds,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "inference_version": INFERENCE_VERSION,
        }
        try:
            with db() as con:
                con.execute("""INSERT INTO scans
                    (id, created_at, patient, patient_id, result, confidence, raw_result, lesions, boxes, seconds,
                     source_sha256, inference_version)
                    VALUES (:id,:created_at,:patient,:patient_id,:result,:confidence,:raw_result,:lesions,:boxes,:seconds,
                            :source_sha256,:inference_version)""", rec)
        except sqlite3.Error as error:
            for path in (original_path, img_path, ann_path):
                if os.path.exists(path):
                    os.remove(path)
            sys.stderr.write(f"Database write failed for {scan_id}: {error}\n")
            audit("analyze", scan_id, "database-failed")
            return self.send_json({"error": "تعذر حفظ نتيجة الفحص"}, 500)
        audit("analyze", scan_id, result)
        data = row_to_dict(rec)
        data["uncertain"] = uncertain
        return self.send_json(data)

    # ---- DELETE: حذف فحص ----
    def do_DELETE(self):
        if not self.request_allowed():
            return self.send_json({"error": "غير مسموح"}, 403)
        if self.rate_limited():
            return self.send_json({"error": "طلبات كثيرة؛ حاولي بعد دقيقة"}, 429)
        if not self.csrf_valid():
            return self.send_json({"error": "تعذر التحقق من الطلب"}, 403)
        m = re.match(r"^/api/history/([\w-]+)$", urlparse(self.path).path)
        if not m:
            return self.send_error(404)
        sid = m.group(1)
        with db() as con:
            cursor = con.execute("DELETE FROM scans WHERE id = ?", (sid,))
        if cursor.rowcount == 0:
            return self.send_json({"error": "الفحص غير موجود"}, 404)
        for suffix in (".png", "_boxes.png", "_original.png"):
            p = os.path.join(IMAGES, sid + suffix)
            if os.path.exists(p):
                os.remove(p)
        audit("delete", sid, "ok")
        return self.send_json({"ok": True})


def safe_join(root, rel):
    p = os.path.realpath(os.path.join(root, rel))
    return p if p.startswith(os.path.realpath(root) + os.sep) else os.path.join(root, "__none__")


def main():
    port = PORT
    server = None
    for p in range(PORT, PORT + 10):   # لو المنفذ مشغول نجرب اللي بعده
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            server.daemon_threads = True
            port = p
            break
        except OSError:
            continue
    if server is None:
        sys.exit("No free port found")

    url = f"http://localhost:{port}"
    print("\n  MS SmartScan")
    print("  -----------------------------")
    print(f"  Website:  {url}")
    print("  Stop:     Ctrl + C\n")
    print("  Loading AI model (best.pt) ...")

    def boot():
        ok = detector.load_model()
        print("  [OK] Model ready - you can start scanning\n" if ok else f"  [X] Model failed to load: {detector.status()['error']}\n"
              "      Check the internet connection, close this window and start again.\n")
    threading.Thread(target=boot, daemon=True).start()

    if "--no-browser" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
