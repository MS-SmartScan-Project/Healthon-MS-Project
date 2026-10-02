"""
MS SmartScan — موقع الفحص (MRI Scanner)
التشغيل:  python server.py   ثم افتحي  http://localhost:8000

يحلل صور الرنين بالذكاء الاصطناعي ويحفظ النتيجة في قاعدة البيانات المشتركة (../data).
هذا الموقع يرسل الفحوصات فقط — لا يعرض السجل. السجل في موقع مستقل: ../Patient-Registry
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
MIN_CONFIDENCE = 50      # أقل من ذلك تُعرض النتيجة كغير حاسمة، لا كسليمة
MAX_UPLOAD_MB = 15
MAX_IMAGE_PIXELS = 25_000_000
CSRF_TOKEN = secrets.token_urlsafe(32)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_REQUESTS = 30
INFERENCE_VERSION = "yolo26s-mslesseg-photo-v6"   # v6: YOLO26s, MSLesSeg FLAIR + simulated camera photos, conf 0.25, 640 px, no CLAHE, no TTA
MEDICAL_NUMBER_RE = re.compile(r"[A-Z0-9][A-Z0-9\-_/.]{0,29}")
_request_times = defaultdict(deque)
_rate_lock = threading.Lock()
_record_lock = threading.Lock()   # يمنع تسجيل نفس الصورة لمريضين في نفس اللحظة

mimetypes.add_type("image/webp", ".webp")   # إصدارات بايثون القديمة على Raspberry Pi لا تعرفه

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
DATA = os.path.join(os.path.dirname(BASE), "data")   # قاعدة البيانات المشتركة بين الموقعين
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
        raw_result  TEXT,               -- ناتج النموذج قبل قاعدة الـ 50%
        lesions     INTEGER NOT NULL DEFAULT 0,
        boxes       TEXT,               -- JSON
        seconds     REAL
    )""")
    existing_columns = {row[1] for row in con.execute("PRAGMA table_info(scans)")}
    if "source_sha256" not in existing_columns:
        con.execute("ALTER TABLE scans ADD COLUMN source_sha256 TEXT")
    if "inference_version" not in existing_columns:
        con.execute("ALTER TABLE scans ADD COLUMN inference_version TEXT")
    if "pixel_sha256" not in existing_columns:          # بصمة البكسلات لكشف تكرار نفس صورة الرنين
        con.execute("ALTER TABLE scans ADD COLUMN pixel_sha256 TEXT")
    con.execute("CREATE INDEX IF NOT EXISTS idx_scans_source_sha256 ON scans(source_sha256)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_scans_pixel_sha256 ON scans(pixel_sha256)")
    con.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at  TEXT NOT NULL,
        action      TEXT NOT NULL,
        target_id   TEXT,
        outcome     TEXT NOT NULL
    )""")
    # المرضى: الرقم الطبي هو المعرّف الفريد للمريض
    con.execute("""CREATE TABLE IF NOT EXISTS patients (
        medical_number  TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        created_at      TEXT NOT NULL
    )""")


def normalize_medical_number(value):
    return re.sub(r"\s+", "", value).upper() if isinstance(value, str) else ""


def normalize_name(value):
    return re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else ""


def pixel_fingerprint(image):
    """SHA-256 of the decoded pixels, so re-encoded copies of the same MRI still match."""
    return hashlib.sha256(f"{image.shape}|{image.dtype}|".encode() + image.tobytes()).hexdigest()


def migrate_existing_records():
    """Fill new fields for old rows without changing or deleting any existing data."""
    with db() as con:
        # 1) سجلات المرضى من الفحوصات السابقة (الأحدث أولاً، ولا يُستبدل أي مريض موجود)
        rows = con.execute("""SELECT patient_id, patient, created_at FROM scans
                              WHERE patient_id IS NOT NULL AND patient IS NOT NULL
                              ORDER BY created_at DESC""").fetchall()
        for r in rows:
            number, name = normalize_medical_number(r["patient_id"]), normalize_name(r["patient"])
            if number and name:
                con.execute("INSERT OR IGNORE INTO patients (medical_number, name, created_at) VALUES (?, ?, ?)",
                            (number, name, r["created_at"]))
        # 2) بصمة البكسلات للفحوصات القديمة من الصورة الأصلية المحفوظة
        missing = con.execute("SELECT id FROM scans WHERE pixel_sha256 IS NULL").fetchall()
    for r in missing:
        path = os.path.join(IMAGES, r["id"] + "_original.png")
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED) if os.path.isfile(path) else None
        if image is None:
            continue
        with db() as con:
            con.execute("UPDATE scans SET pixel_sha256 = ? WHERE id = ? AND pixel_sha256 IS NULL",
                        (pixel_fingerprint(image), r["id"]))


def find_duplicate(con, source_sha256, pixel_sha256, medical_number):
    """Return an existing scan of the same image that belongs to a different patient."""
    return con.execute("""SELECT id, created_at FROM scans
        WHERE (source_sha256 = ? OR pixel_sha256 = ?)
          AND (patient_id IS NULL OR UPPER(REPLACE(patient_id, ' ', '')) <> ?)
        LIMIT 1""", (source_sha256, pixel_sha256, medical_number)).fetchone()


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
migrate_existing_records()


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

        # موقع الفحص لا يقرأ السجل أبداً — فقط متوسط زمن التحليل (بدون أي بيانات مرضى)
        if path == "/api/stats":
            with db() as con:
                avg = con.execute("SELECT AVG(seconds) FROM scans").fetchone()[0]
            return self.send_json({"avg_seconds": round(avg, 2) if avg is not None else None})
        self.send_error(404)

    # ---- POST: تحليل صورة ----
    def do_POST(self):
        if not self.request_allowed():
            return self.send_json({"error": "Request not allowed."}, 403)
        if self.rate_limited():
            return self.send_json({"error": "Too many requests. Please wait a minute and try again."}, 429)
        if not self.csrf_valid():
            return self.send_json({"error": "Request could not be verified. Please reload the page."}, 403)
        if urlparse(self.path).path != "/api/analyze":
            return self.send_error(404)
        if self.headers.get_content_type() != "application/json":
            return self.send_json({"error": "Unsupported request type."}, 415)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.send_json({"error": "Invalid request length."}, 400)
        if length <= 0 or length > MAX_UPLOAD_MB * 1024 * 1024:
            return self.send_json({"error": f"Image size is not supported (maximum {MAX_UPLOAD_MB} MB)."}, 413)
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            image_value = payload.get("image", "")
            if not isinstance(image_value, str):
                raise ValueError("image must be a string")
            m = re.fullmatch(r"data:image/(png|jpe?g|webp|bmp);base64,([A-Za-z0-9+/=\r\n]+)", image_value)
            if not m:
                return self.send_json({"error": "No valid MRI image was received."}, 422)
            raw = base64.b64decode(m.group(2), validate=True)
        except (ValueError, TypeError, json.JSONDecodeError, Base64Error):
            return self.send_json({"error": "Invalid request data."}, 400)

        # بيانات المريض إلزامية: الاسم والرقم الطبي
        patient = normalize_name(payload.get("patient"))[:80]
        patient_id = normalize_medical_number(payload.get("patient_id"))
        fields = {}
        if not patient:
            fields["patient"] = "Patient name is required."
        if not patient_id:
            fields["patient_id"] = "Medical number is required."
        elif not MEDICAL_NUMBER_RE.fullmatch(patient_id):
            fields["patient_id"] = "Use letters, digits, - _ / . only (maximum 30 characters)."
        if fields:
            return self.send_json({"error": "Required patient information is missing.",
                                   "code": "validation", "fields": fields}, 422)

        if not detector.status()["ready"]:
            return self.send_json({"error": "The AI model is still loading. Please wait a moment and try again."}, 503)

        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if image is None or image.ndim not in (2, 3):
            return self.send_json({"error": "The image file could not be read."}, 422)
        height, width = image.shape[:2]
        if width < 32 or height < 32 or width * height > MAX_IMAGE_PIXELS:
            return self.send_json({"error": "Image dimensions are not supported."}, 422)

        source_sha256 = hashlib.sha256(raw).hexdigest()
        pixel_sha256 = pixel_fingerprint(image)

        def conflict():
            """Duplicate image or medical number registered to a different name → error response, else None."""
            with db() as con:
                if find_duplicate(con, source_sha256, pixel_sha256, patient_id):
                    audit("analyze", None, "duplicate-rejected")
                    return {"error": "This MRI image has already been associated with an existing patient "
                                     "record and cannot be uploaded again.",
                            "code": "duplicate_image", "title": "Duplicate MRI detected"}
                known = con.execute("SELECT name FROM patients WHERE medical_number = ?", (patient_id,)).fetchone()
            if known and known["name"].casefold() != patient.casefold():
                audit("analyze", None, "patient-mismatch-rejected")
                return {"error": "This medical number is already registered to a different patient name. "
                                 "Check the medical number or use the registered name.",
                        "code": "patient_mismatch", "fields": {"patient_id": "Medical number belongs to another patient."}}
            return None

        # فحص التكرار قبل تشغيل النموذج (لا حاجة لتحليل صورة مرفوضة)
        rejected = conflict()
        if rejected:
            return self.send_json(rejected, 409)

        scan_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex
        original_path = os.path.join(IMAGES, scan_id + "_original.png")
        img_path = os.path.join(IMAGES, scan_id + ".png")
        ann_path = os.path.join(IMAGES, scan_id + "_boxes.png")
        if not cv2.imwrite(original_path, image):
            audit("analyze", scan_id, "image-save-failed")
            return self.send_json({"error": "The image could not be saved."}, 500)

        t0 = time.time()
        try:
            out = detector.analyze(original_path, img_path, ann_path)
        except Exception as e:
            for p in (original_path, img_path, ann_path):
                if os.path.exists(p):
                    os.remove(p)
            sys.stderr.write(f"Analysis failed for {scan_id}: {e}\n")
            audit("analyze", scan_id, "analysis-failed")
            return self.send_json({"error": "The image could not be analyzed."}, 500)
        seconds = round(time.time() - t0, 2)

        result = out["result"]
        conf = None if result == "Healthy" else out["confidence"]
        uncertain = result == "Infected" and conf is not None and conf < MIN_CONFIDENCE
        if uncertain:
            result = "Uncertain"

        rec = {
            "id": scan_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "patient": patient,
            "patient_id": patient_id,
            "result": result,
            "confidence": conf,
            # ناتج النموذج كما هو للمراجعة، مع الصناديق الكبيرة التي تم تجاهلها
            "raw_result": json.dumps({"result": out["result"], "confidence": out["confidence"],
                                      "ignored_whole_brain_boxes": out.get("ignored_boxes", [])}),
            "lesions": len(out["boxes"]),
            "boxes": json.dumps(out["boxes"]),
            "seconds": seconds,
            "source_sha256": source_sha256,
            "pixel_sha256": pixel_sha256,
            "inference_version": INFERENCE_VERSION,
        }

        def discard_files():
            for path in (original_path, img_path, ann_path):
                if os.path.exists(path):
                    os.remove(path)

        try:
            with _record_lock:
                # إعادة الفحص قبل الحفظ مباشرة: ربما سُجّلت نفس الصورة أثناء التحليل
                rejected = conflict()
                if rejected:
                    discard_files()
                    return self.send_json(rejected, 409)
                with db() as con:
                    con.execute("INSERT OR IGNORE INTO patients (medical_number, name, created_at) VALUES (?, ?, ?)",
                                (patient_id, patient, rec["created_at"]))
                    # الاسم المسجّل للمريض (نفس الاسم بحروف مختلفة الحجم يُحفظ بصيغته الأصلية)
                    rec["patient"] = con.execute("SELECT name FROM patients WHERE medical_number = ?",
                                                 (patient_id,)).fetchone()["name"]
                    con.execute("""INSERT INTO scans
                        (id, created_at, patient, patient_id, result, confidence, raw_result, lesions, boxes, seconds,
                         source_sha256, inference_version, pixel_sha256)
                        VALUES (:id,:created_at,:patient,:patient_id,:result,:confidence,:raw_result,:lesions,:boxes,
                                :seconds,:source_sha256,:inference_version,:pixel_sha256)""", rec)
        except sqlite3.Error as error:
            discard_files()
            sys.stderr.write(f"Database write failed for {scan_id}: {error}\n")
            audit("analyze", scan_id, "database-failed")
            return self.send_json({"error": "The scan result could not be saved."}, 500)
        audit("analyze", scan_id, result)
        data = row_to_dict(rec)
        data["uncertain"] = uncertain
        return self.send_json(data)

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
    try:   # يقرأه موقع السجل ليعرض رابط "MRI Scanner" الصحيح
        with open(os.path.join(DATA, "scanner_url.txt"), "w", encoding="utf-8") as f:
            f.write(url)
    except OSError:
        pass

    print("\n  MS SmartScan — MRI Scanner")
    print("  -----------------------------")
    print(f"  Website:  {url}")
    print("  Stop:     Ctrl + C\n")
    print("  Loading AI model ...")

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
