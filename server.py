"""
MS SmartScan — سيرفر الموقع
التشغيل:  python server.py   ثم افتحي  http://localhost:8000

لا يحتاج PHP ولا XAMPP ولا MySQL — مكتبات بايثون القياسية فقط + ultralytics و opencv.
السجل يُحفظ في ملف SQLite داخل مجلد data (يُنشأ تلقائياً).
"""
import base64
import json
import mimetypes
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import importlib.util
import subprocess


def ensure_libraries():
    """أول تشغيل: يثبّت ultralytics و opencv تلقائياً إذا كانت ناقصة."""
    missing = [pkg for mod, pkg in (("ultralytics", "ultralytics"), ("cv2", "opencv-python"))
               if importlib.util.find_spec(mod) is None]
    if not missing:
        return
    print("\n  First run: installing " + ", ".join(missing) + " ... (a few minutes, please wait)\n")
    cmd = [sys.executable, "-m", "pip", "install", *missing]
    if sys.platform.startswith("linux"):          # Raspberry Pi OS يحتاج هذا الخيار
        cmd.append("--break-system-packages")
    if subprocess.call(cmd) != 0 and sys.platform.startswith("linux"):
        subprocess.call(cmd[:-1])                  # أنظمة لينكس القديمة لا تعرف الخيار
    importlib.invalidate_caches()


ensure_libraries()
import detector  # noqa: E402

# ---------------- الإعدادات ----------------
PORT = 8000
MIN_CONFIDENCE = 70      # نفس قاعدة النظام الأصلي: Infected بثقة أقل من 70% تُعرض سليمة
MAX_UPLOAD_MB = 15

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
DATA = os.path.join(BASE, "data")
IMAGES = os.path.join(DATA, "images")
DB_PATH = os.path.join(DATA, "smartscan.db")
os.makedirs(IMAGES, exist_ok=True)


# ---------------- قاعدة البيانات (SQLite) ----------------
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


with db() as con:
    con.execute("""CREATE TABLE IF NOT EXISTS scans (
        id          TEXT PRIMARY KEY,
        created_at  TEXT NOT NULL,
        patient     TEXT,
        patient_id  TEXT,
        result      TEXT NOT NULL,      -- Infected / Healthy
        confidence  REAL,
        raw_result  TEXT,               -- ناتج النموذج قبل قاعدة الـ 70%
        lesions     INTEGER NOT NULL DEFAULT 0,
        boxes       TEXT,               -- JSON
        seconds     REAL
    )""")


def row_to_dict(r):
    d = dict(r)
    d["boxes"] = json.loads(d["boxes"] or "[]")
    d["image"] = f"/media/{d['id']}.png"
    d["annotated"] = f"/media/{d['id']}_boxes.png"
    return d


# ---------------- الطلبات ----------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SmartScan"

    def log_message(self, fmt, *args):   # سجل مختصر في الطرفية
        if "/api/" in self.path:
            sys.stdout.write("  %s  %s\n" % (datetime.now().strftime("%H:%M:%S"), self.requestline))

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
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ---- GET ----
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self.send_file(os.path.join(STATIC, "index.html"))
        if path.startswith("/static/"):
            return self.send_file(safe_join(STATIC, path[len("/static/"):]))
        if path.startswith("/media/"):
            return self.send_file(safe_join(IMAGES, path[len("/media/"):]))
        if path == "/api/status":
            return self.send_json({**detector.status(), "min_confidence": MIN_CONFIDENCE})
        if path == "/api/history":
            with db() as con:
                rows = con.execute("SELECT * FROM scans ORDER BY created_at DESC LIMIT 60").fetchall()
                stats = con.execute("SELECT COUNT(*) total, SUM(result='Infected') infected, SUM(result='Healthy') healthy FROM scans").fetchone()
            return self.send_json({"items": [row_to_dict(r) for r in rows],
                                   "stats": {k: stats[k] or 0 for k in ("total", "infected", "healthy")}})
        self.send_error(404)

    # ---- POST: تحليل صورة ----
    def do_POST(self):
        if urlparse(self.path).path != "/api/analyze":
            return self.send_error(404)
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_UPLOAD_MB * 1024 * 1024:
            return self.send_json({"error": "حجم الصورة غير مناسب"}, 413)
        try:
            payload = json.loads(self.rfile.read(length))
            m = re.match(r"^data:image/(png|jpe?g|webp|bmp);base64,(.+)$", payload.get("image", ""), re.S)
            if not m:
                return self.send_json({"error": "لم تصل صورة صالحة"}, 422)
            raw = base64.b64decode(m.group(2))
        except Exception:
            return self.send_json({"error": "بيانات غير صالحة"}, 400)

        if not detector.status()["ready"]:
            return self.send_json({"error": "النموذج لسه يتحمّل أو فيه مكتبة ناقصة — راجعي الطرفية"}, 503)

        scan_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:5]
        img_path = os.path.join(IMAGES, scan_id + ".png")
        ann_path = os.path.join(IMAGES, scan_id + "_boxes.png")
        with open(img_path, "wb") as f:
            f.write(raw)

        t0 = time.time()
        try:
            out = detector.analyze(img_path, ann_path)
        except Exception as e:
            for p in (img_path, ann_path):
                if os.path.exists(p):
                    os.remove(p)
            return self.send_json({"error": f"تعذّر التحليل: {e}"}, 500)
        seconds = round(time.time() - t0, 2)

        result, conf, filtered = out["result"], out["confidence"], False
        if result == "Infected" and conf < MIN_CONFIDENCE:
            result, filtered = "Healthy", True

        rec = {
            "id": scan_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "patient": (payload.get("patient") or "").strip()[:80] or None,
            "patient_id": (payload.get("patient_id") or "").strip()[:30] or None,
            "result": result,
            "confidence": None if filtered else conf,
            "raw_result": f'{out["result"]},{out["confidence"]}',
            "lesions": 0 if filtered else len(out["boxes"]),
            "boxes": json.dumps(out["boxes"]),
            "seconds": seconds,
        }
        with db() as con:
            con.execute("INSERT INTO scans VALUES (:id,:created_at,:patient,:patient_id,:result,:confidence,:raw_result,:lesions,:boxes,:seconds)", rec)
        data = row_to_dict(rec)
        data["filtered"] = filtered
        return self.send_json(data)

    # ---- DELETE: حذف فحص ----
    def do_DELETE(self):
        m = re.match(r"^/api/history/([\w-]+)$", urlparse(self.path).path)
        if not m:
            return self.send_error(404)
        sid = m.group(1)
        with db() as con:
            con.execute("DELETE FROM scans WHERE id = ?", (sid,))
        for suffix in (".png", "_boxes.png"):
            p = os.path.join(IMAGES, sid + suffix)
            if os.path.exists(p):
                os.remove(p)
        return self.send_json({"ok": True})


def safe_join(root, rel):
    p = os.path.realpath(os.path.join(root, rel))
    return p if p.startswith(os.path.realpath(root) + os.sep) else os.path.join(root, "__none__")


def main():
    port = PORT
    server = None
    for p in range(PORT, PORT + 10):   # لو المنفذ مشغول نجرب اللي بعده
        try:
            server = ThreadingHTTPServer(("0.0.0.0", p), Handler)
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
