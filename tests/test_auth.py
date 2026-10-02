"""
MS SmartScan — اختبارات الدخول بالرمز والصلاحيات (الموقعين معاً)

التشغيل من مجلد المشروع:   python -m unittest tests.test_auth -v
يشغّل موقع السجل وموقع الفحص الحقيقيين على مجلد بيانات مؤقت (لا يلمس data/)،
ويبدأ بقاعدة بيانات بالشكل القديم (قبل إضافة الأطباء) فيها سجلات قديمة، للتأكد من الترحيل الآمن.
يحتاج مكتبات موقع الفحص (requirements.txt)، وصورة رنين حقيقية واحدة على الأقل تقبلها بوابة الرنين:
  من MSS_TEST_MRI_DIR إن وُجد، وإلا من data/images/*_original.png
يستغرق 3–5 دقائق تقريباً (اختبار انتهاء الجلسة ينتظر 60 ثانية فعلية).
"""
import base64
import glob
import hashlib
import http.client
import http.cookiejar
import io
import json
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "Patient-Registry", "server.py")
SCANNER = os.path.join(ROOT, "MRI-Scanner", "server.py")
HEAD_PIN = "HA01"
PIN_A, PIN_B, PIN_C = "QZ71", "KM42", "XW39"   # contain letters that never appear in lowercase hex digests
ALL_PINS = [HEAD_PIN, PIN_A, PIN_B, PIN_C]


def png(width, height, pattern=lambda x, y: 255):
    """Small grayscale PNG built with the standard library."""
    raw = b"".join(b"\x00" + bytes(pattern(x, y) for x in range(width)) for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def data_url(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode()


TINY = data_url(png(8, 8))   # passes the request checks, then fails the size check — no AI inference needed


class Client:
    """One browser: its own cookies, CSRF token and Origin header."""

    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""
        self.responses = []   # every response body, checked later for PINs

    def request(self, method, path, body=None, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Origin", self.base)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if method != "GET":
            req.add_header("X-CSRF-Token", self.csrf)
        try:
            with self.opener.open(req, timeout=120) as r:
                status, payload = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, payload = e.code, e.read()
        self.responses.append(payload)
        if raw:
            return status, payload
        try:
            return status, json.loads(payload or b"{}")
        except ValueError:
            return status, {"_raw": payload[:200]}

    def get(self, path, raw=False):
        return self.request("GET", path, raw=raw)

    def post(self, path, body=None):
        return self.request("POST", path, body if body is not None else {})

    def delete(self, path):
        return self.request("DELETE", path)

    def refresh_csrf(self):
        status, s = self.get("/api/status")
        assert status == 200, s
        self.csrf = s["csrf_token"]
        return s

    def login(self, pin):
        self.refresh_csrf()
        return self.post("/api/login", {"pin": pin})

    def cookie_header(self):
        return "; ".join(f"{c.name}={c.value}" for c in self.jar)


class EventReader(threading.Thread):
    """Reads the Registry's Server-Sent Events stream for one client."""

    def __init__(self, client):
        super().__init__(daemon=True)
        host, port = client.base.split("//")[1].split(":")
        self.conn = http.client.HTTPConnection(host, int(port), timeout=90)
        self.conn.request("GET", "/api/events", headers={"Cookie": client.cookie_header(), "Origin": client.base})
        self.response = self.conn.getresponse()
        self.status = self.response.status
        self.events, self.closed_at = [], None
        if self.status == 200:
            self.start()

    def run(self):
        try:
            for line in self.response:
                if line.startswith(b"data: "):
                    self.events.append(json.loads(line[6:]))
        except OSError:
            pass
        self.closed_at = time.time()

    def ids(self, kind="scan"):
        return {e["id"] for e in self.events if e["type"] == kind}


class Server:
    def __init__(self, script, port, data_dir, *extra):
        self.script, self.port, self.data_dir, self.extra = script, port, data_dir, extra
        self.log_path = os.path.join(data_dir, os.path.basename(os.path.dirname(script)) + ".log")
        self.proc, self.base = None, None

    def start(self):
        env = dict(os.environ, MSS_DATA_DIR=self.data_dir, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        self.log = open(self.log_path, "a", encoding="utf-8")
        self.proc = subprocess.Popen([sys.executable, self.script, "--port", str(self.port), *self.extra],
                                     env=env, stdout=self.log, stderr=subprocess.STDOUT, cwd=os.path.dirname(self.script))
        deadline = time.time() + 120
        while time.time() < deadline:
            with open(self.log_path, encoding="utf-8", errors="replace") as f:
                lines = [l for l in f.read().splitlines() if "Website:" in l]
            if lines:
                self.base = "http://127.0.0.1:" + lines[-1].rsplit(":", 1)[1].strip()
                try:
                    urllib.request.urlopen(self.base + "/api/status", timeout=5).read()
                    return self
                except OSError:
                    pass
            if self.proc.poll() is not None:
                raise RuntimeError(open(self.log_path, encoding="utf-8", errors="replace").read())
            time.sleep(0.3)
        raise RuntimeError("server did not start: " + self.script)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(10)
        self.log.close()

    def restart(self):
        self.stop()
        return self.start()

    def cli(self, *args):
        env = dict(os.environ, MSS_DATA_DIR=self.data_dir, PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, self.script, *args], env=env, capture_output=True, text=True,
                              encoding="utf-8", timeout=180, cwd=os.path.dirname(self.script))


def mri_images():
    folder = os.environ.get("MSS_TEST_MRI_DIR")
    paths = sorted(glob.glob(os.path.join(folder, "*.png"))) if folder else sorted(glob.glob(os.path.join(ROOT, "data", "images", "*_original.png")))
    unique, seen = [], set()
    for p in paths:
        with open(p, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        if digest not in seen:
            seen.add(digest)
            unique.append(p)
    return unique


def make_legacy_database(data_dir):
    """The database exactly as the previous version created it: no doctors, no owner columns."""
    os.makedirs(os.path.join(data_dir, "images"), exist_ok=True)
    con = sqlite3.connect(os.path.join(data_dir, "smartscan.db"))
    con.executescript("""
        CREATE TABLE scans (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, patient TEXT, patient_id TEXT,
            result TEXT NOT NULL, confidence REAL, raw_result TEXT, lesions INTEGER NOT NULL DEFAULT 0, boxes TEXT,
            seconds REAL, source_sha256 TEXT, inference_version TEXT, pixel_sha256 TEXT);
        CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, action TEXT NOT NULL,
            target_id TEXT, outcome TEXT NOT NULL);
        CREATE TABLE patients (medical_number TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
        INSERT INTO scans VALUES ('20260101-090000-legacy1', '2026-01-01T09:00:00', 'Legacy Patient', 'LEG-1', 'Infected',
            81.5, NULL, 2, '[]', 1.2, 'aa', 'yolo26s-mslesseg-photo-v6', 'bb');
        INSERT INTO scans VALUES ('20260102-090000-legacy2', '2026-01-02T09:00:00', 'Legacy Patient', 'LEG-1', 'Healthy',
            NULL, NULL, 0, '[]', 1.1, 'cc', 'yolo26s-mslesseg-photo-v6', 'dd');
        INSERT INTO patients VALUES ('LEG-1', 'Legacy Patient', '2026-01-01T09:00:00');
    """)
    con.commit()
    con.close()
    for suffix in (".png", "_boxes.png", "_original.png"):
        with open(os.path.join(data_dir, "images", "20260101-090000-legacy1" + suffix), "wb") as f:
            f.write(png(8, 8))


class PinAuthTests(unittest.TestCase):
    """Runs in order (test_01 … test_17); later steps use accounts and scans created earlier."""

    @classmethod
    def setUpClass(cls):
        cls.images = mri_images()
        if not cls.images:
            raise unittest.SkipTest("Needs a real brain MRI image (set MSS_TEST_MRI_DIR).")
        cls.tmp = tempfile.mkdtemp(prefix="mss-auth-test-")
        make_legacy_database(cls.tmp)
        cls.registry = Server(REGISTRY, 18601, cls.tmp).start()
        cls.scanner = Server(SCANNER, 18600, cls.tmp, "--no-browser").start()
        cls.clients = []
        cls.ids = {}

    @classmethod
    def tearDownClass(cls):
        for server in (getattr(cls, "scanner", None), getattr(cls, "registry", None)):
            if server:
                server.stop()
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    # ---------------- helpers ----------------
    def reg(self):
        c = Client(self.registry.base)
        self.clients.append(c)
        return c

    def scan_client(self):
        c = Client(self.scanner.base)
        self.clients.append(c)
        c.refresh_csrf()
        return c

    def db(self):
        con = sqlite3.connect(os.path.join(self.tmp, "smartscan.db"))
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def patient(call):
        """Repeat a request while the 10-per-minute sign-in rate limit is in effect (tested separately in test_12)."""
        deadline = time.time() + 75
        while True:
            status, body = call()
            if status != 429 or time.time() > deadline:
                return status, body
            time.sleep(5)

    def signed_in(self, pin):
        c = self.reg()
        status, body = self.patient(lambda: c.login(pin))
        self.assertEqual(status, 200, body)
        return c

    def analyze(self, client, pin, patient, number, image, **extra):
        payload = {"image": image, "patient": patient, "patient_id": number, "pin": pin, **extra}
        return self.patient(lambda: client.post("/api/analyze", payload))

    def wait_model(self):
        deadline = time.time() + 300
        while time.time() < deadline:
            status, s = Client(self.scanner.base).get("/api/status")
            if s.get("ready"):
                return
            if s.get("error"):
                self.fail("AI model failed to load: " + s["error"])
            time.sleep(1)
        self.fail("AI model did not load")

    def submit_real(self, client, pin, patient, number):
        """Submit real MRI images until one passes the MRI gate. Returns (status, body, raw image bytes)."""
        for path in self.images:
            with open(path, "rb") as f:
                raw = f.read()
            status, body = self.analyze(client, pin, patient, number, data_url(raw))
            if status == 422 and body.get("code") == "not_mri":
                continue
            return status, body, raw
        self.fail("No test image passed the MRI gate")

    @staticmethod
    def mirrored(raw):
        """The same MRI flipped left–right: still a brain MRI, but a different image for the duplicate check."""
        import cv2
        import numpy as np
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
        return cv2.imencode(".png", cv2.flip(image, 1))[1].tobytes()

    def failures(self, site):
        row = self.db().execute("SELECT failures, locked_until FROM auth_lockouts WHERE site = ?", (site,)).fetchone()
        return (row["failures"], row["locked_until"]) if row else (0, None)

    # ---------------- 01 migration ----------------
    def test_01_migration_keeps_legacy_records_unassigned(self):
        con = self.db()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM scans").fetchone()[0], 2)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM patients").fetchone()[0], 1)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM scans WHERE owner_doctor_id IS NOT NULL").fetchone()[0], 0)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM patients WHERE owner_doctor_id IS NOT NULL").fetchone()[0], 0)
        heads = con.execute("SELECT name, role, department, active FROM doctors").fetchall()
        self.assertEqual([tuple(r) for r in heads], [("Hailah Alhejjei", "head", "Neurology", 1)])
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "auth.key")))

    # ---------------- 02 seeded head ----------------
    def test_02_ha01_is_department_head_and_seeded_once(self):
        c = self.reg()
        status, body = c.login("ha01")   # lower case is accepted and normalized
        self.assertEqual(status, 200, body)
        self.assertEqual(body["doctor"]["role"], "head")
        self.assertEqual(body["doctor"]["name"], "Hailah Alhejjei")
        self.assertEqual(c.get("/api/me")[1]["doctor"]["role"], "head")
        type(self).head = c
        self.registry.restart()   # starting again must not create a second head
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM doctors WHERE role = 'head'").fetchone()[0], 1)
        c.refresh_csrf()
        self.assertEqual(c.get("/api/me")[0], 200)   # sessions are stored in the database: still signed in

    # ---------------- 03 registration, duplicates, formats ----------------
    def test_03_head_registers_doctors_and_bad_pins_are_rejected(self):
        h = self.head
        for name, pin, key in (("Dr Amal Test", "qz71", "A"), ("Dr Badr Test", PIN_B, "B")):
            status, body = h.post("/api/doctors", {"name": name, "pin": pin})
            self.assertEqual(status, 201, body)
            self.assertEqual((body["doctor"]["role"], body["doctor"]["department"]), ("doctor", "Neurology"))
            self.assertFalse({"pin", "pin_hash", "pin_lookup"} & set(body["doctor"]))
            self.ids[key] = body["doctor"]["id"]
        for pin in ("QZ71", "qz71", "HA01", " km42 "):
            status, body = h.post("/api/doctors", {"name": "Duplicate", "pin": pin})
            self.assertEqual((status, body.get("code")), (409, "pin_taken"), pin)
        for pin in ("AB1", "AB12C", "AB-1", "", "١٢٣٤", "ÄB12"):
            status, body = h.post("/api/doctors", {"name": "Bad Pin", "pin": pin})
            self.assertEqual(status, 422, pin)
            self.assertIn("pin", body["fields"])
        status, body = self.reg().login("ab!")
        self.assertEqual((status, body.get("code")), (422, "invalid_format"))
        self.assertEqual(self.failures("registry")[0], 0)   # a malformed PIN is not counted as an attempt
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM doctors").fetchone()[0], 3)

    # ---------------- 04 only the head manages doctors ----------------
    def test_04_regular_doctor_cannot_register_or_manage(self):
        a = self.signed_in(PIN_A)
        self.assertEqual(a.get("/api/me")[1]["doctor"]["role"], "doctor")
        self.assertEqual(a.post("/api/doctors", {"name": "Sneaky", "pin": "SN99"})[0], 403)
        self.assertEqual(a.get("/api/doctors")[0], 403)
        self.assertEqual(a.post(f"/api/doctors/{self.ids['B']}/access", {"active": False})[0], 403)
        self.assertEqual(self.db().execute("SELECT active FROM doctors WHERE id = ?", (self.ids["B"],)).fetchone()[0], 1)
        self.assertEqual(Client(self.registry.base).post("/api/doctors", {"name": "Anon", "pin": "AN11"})[0], 403)  # no CSRF/session
        type(self).doc_a = a

    # ---------------- 05 scanner: PIN on submission, owner stored ----------------
    def test_05_scanner_requires_valid_pin_and_stores_owner(self):
        self.wait_model()
        s = self.scan_client()
        status, body = self.analyze(s, "", "Patient A", "PA-1", TINY)
        self.assertEqual(status, 422)
        self.assertIn("pin", body["fields"])
        status, body = self.analyze(s, "Q7", "Patient A", "PA-1", TINY)
        self.assertEqual(status, 422)
        status, body = self.analyze(s, "ZZ99", "Patient A", "PA-1", TINY)
        self.assertEqual((status, body.get("code"), body.get("attempts_left")), (401, "wrong_pin", 2))
        self.assertEqual(self.failures("scanner")[0], 1)
        self.assertEqual(self.failures("registry")[0], 0)   # separate counter per site

        status, body, raw = self.submit_real(s, PIN_A, "Patient A", "PA-1")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["doctor"], "Dr Amal Test")
        self.assertTrue(body["annotated"].startswith("data:image/png;base64,"))
        self.ids["scanA"], self.ids["rawA"] = body["id"], raw
        self.assertEqual(self.failures("scanner")[0], 0)   # success resets the count

        status, body = self.analyze(s, PIN_B, "Patient B", "PB-1", data_url(self.mirrored(raw)))
        self.assertEqual(status, 200, body)
        self.assertEqual(body["doctor"], "Dr Badr Test")
        self.ids["scanB"] = body["id"]

        con = self.db()
        self.assertEqual(con.execute("SELECT owner_doctor_id FROM scans WHERE id = ?", (self.ids["scanA"],)).fetchone()[0], self.ids["A"])
        self.assertEqual(con.execute("SELECT owner_doctor_id FROM scans WHERE id = ?", (self.ids["scanB"],)).fetchone()[0], self.ids["B"])
        self.assertEqual(con.execute("SELECT owner_doctor_id FROM patients WHERE medical_number = 'PA-1'").fetchone()[0], self.ids["A"])
        self.assertEqual(con.execute("SELECT owner_doctor_id FROM patients WHERE medical_number = 'PB-1'").fetchone()[0], self.ids["B"])

    def test_06_owner_cannot_be_forged_from_the_browser(self):
        s = self.scan_client()
        status, body = self.analyze(s, PIN_A, "Patient A", "PA-1", TINY, owner_doctor_id=self.ids["B"], doctor_id=self.ids["B"])
        self.assertEqual(status, 422)   # PIN accepted (A), then the tiny image is rejected — nothing saved for B
        self.assertEqual(body.get("error"), "Image dimensions are not supported.")
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM scans WHERE owner_doctor_id = ?", (self.ids["B"],)).fetchone()[0], 1)
        self.assertEqual(s.get(f"/media/{self.ids['scanA']}_boxes.png", raw=True)[0], 404)   # the Scanner serves no stored MRI files

    # ---------------- 07 isolation between doctors, head sees all ----------------
    def test_07_doctors_only_see_their_own_records(self):
        # fresh sessions: earlier ones may have reached the 60-second idle limit while the AI model loaded
        a, b, h = self.signed_in(PIN_A), self.signed_in(PIN_B), self.signed_in(HEAD_PIN)
        type(self).doc_a, type(self).doc_b, type(self).head = a, b, h
        ids_a = {x["id"] for x in a.get("/api/history")[1]["items"]}
        ids_b = {x["id"] for x in b.get("/api/history")[1]["items"]}
        ids_h = {x["id"] for x in h.get("/api/history")[1]["items"]}
        self.assertEqual(ids_a, {self.ids["scanA"]})
        self.assertEqual(ids_b, {self.ids["scanB"]})
        self.assertEqual(ids_h, {self.ids["scanA"], self.ids["scanB"], "20260101-090000-legacy1", "20260102-090000-legacy2"})
        legacy = [x for x in h.get("/api/history")[1]["items"] if x["id"].endswith("legacy1")][0]
        self.assertIsNone(legacy["owner"])   # shown to the head as unassigned
        self.assertEqual(a.get("/api/history")[1]["stats"]["total"], 1)
        self.assertEqual(a.get("/api/history")[1]["stats"]["patients"], 1)
        self.assertEqual({p["medical_number"] for p in a.get("/api/patients")[1]["items"]}, {"PA-1"})
        self.assertEqual({p["medical_number"] for p in h.get("/api/patients")[1]["items"]}, {"PA-1", "PB-1", "LEG-1"})

        # direct URLs / IDs of another doctor's records
        for suffix in (".png", "_boxes.png", "_original.png"):
            self.assertEqual(a.get(f"/media/{self.ids['scanB']}{suffix}", raw=True)[0], 404)
            self.assertEqual(b.get(f"/media/{self.ids['scanA']}{suffix}", raw=True)[0], 404)
            self.assertEqual(a.get(f"/media/20260101-090000-legacy1{suffix}", raw=True)[0], 404)
        self.assertEqual(a.get(f"/media/{self.ids['scanA']}_boxes.png", raw=True)[0], 200)
        self.assertEqual(h.get(f"/media/{self.ids['scanB']}_boxes.png", raw=True)[0], 200)
        self.assertEqual(h.get("/media/20260101-090000-legacy1_boxes.png", raw=True)[0], 200)
        self.assertEqual(a.get(f"/media/..%2f{self.ids['scanB']}.png", raw=True)[0], 404)
        self.assertEqual(a.delete(f"/api/history/{self.ids['scanB']}")[0], 404)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM scans WHERE id = ?", (self.ids["scanB"],)).fetchone()[0], 1)

        # export only contains the doctor's own rows
        status, xlsx = a.get("/api/export.xlsx?result=all&q=", raw=True)
        self.assertEqual(status, 200)
        sheet = zipfile.ZipFile(io.BytesIO(xlsx)).read("xl/worksheets/sheet1.xml").decode()
        self.assertIn("PA-1", sheet)
        self.assertNotIn("PB-1", sheet)
        self.assertNotIn("LEG-1", sheet)
        self.assertIn("Dr Amal Test", sheet)
        status, xlsx = h.get("/api/export.xlsx?result=all&q=", raw=True)
        sheet = zipfile.ZipFile(io.BytesIO(xlsx)).read("xl/worksheets/sheet1.xml").decode()
        for number in ("PA-1", "PB-1", "LEG-1"):
            self.assertIn(number, sheet)
        self.assertIn("Unassigned (before sign-in)", sheet)

    # ---------------- 08 live updates are filtered per doctor ----------------
    def test_08_live_updates_only_reach_allowed_doctors(self):
        ra, rb, rh = EventReader(self.doc_a), EventReader(self.doc_b), EventReader(self.head)
        self.assertEqual((ra.status, rb.status, rh.status), (200, 200, 200))
        self.assertEqual(EventReader(Client(self.registry.base)).status, 401)
        time.sleep(1)
        con = self.db()
        for sid, owner in (("20260301-100000-livea", self.ids["A"]), ("20260301-100001-liveb", self.ids["B"])):
            con.execute("INSERT INTO scans (id, created_at, patient, patient_id, result, lesions, boxes, owner_doctor_id) "
                        "VALUES (?, '2026-03-01T10:00:00', 'Live Patient', 'LIVE-1', 'Healthy', 0, '[]', ?)", (sid, owner))
        con.commit()
        time.sleep(3)
        self.assertEqual(ra.ids(), {"20260301-100000-livea"})
        self.assertEqual(rb.ids(), {"20260301-100001-liveb"})
        self.assertEqual(rh.ids(), {"20260301-100000-livea", "20260301-100001-liveb"})
        self.assertNotIn("owner", json.dumps(ra.events))
        for r in (ra, rb, rh):
            r.conn.close()
        con.execute("DELETE FROM scans WHERE id LIKE '20260301-1000%'")
        con.commit()

    # ---------------- 09 new doctor works on both sites; disable / enable ----------------
    def test_09_new_doctor_signs_in_to_both_sites_and_access_can_be_revoked(self):
        h = self.head
        status, body = h.post("/api/doctors", {"name": "Dr Ciel New", "pin": PIN_C})
        self.assertEqual(status, 201, body)
        cid = body["doctor"]["id"]
        c = self.signed_in(PIN_C)                                   # registry, immediately
        s = self.scan_client()
        status, body = self.analyze(s, PIN_C, "Patient A", "PA-1", TINY)   # scanner: PIN accepted, tiny image rejected
        self.assertEqual(body.get("error"), "Image dimensions are not supported.")
        names = {d["name"]: d for d in h.get("/api/doctors")[1]["items"]}
        self.assertTrue(names["Dr Ciel New"]["active"])
        self.assertFalse(any(k.startswith("pin") for d in names.values() for k in d))

        self.assertEqual(h.post(f"/api/doctors/{cid}/access", {"active": False})[0], 200)
        self.assertEqual(c.get("/api/me")[0], 401)                  # signed out at once
        status, body = self.reg().login(PIN_C)
        self.assertEqual((status, body.get("code")), (403, "account_disabled"))
        status, body = self.analyze(s, PIN_C, "Patient A", "PA-1", TINY)
        self.assertEqual((status, body.get("code")), (403, "account_disabled"))
        self.assertEqual(h.post("/api/doctors", {"name": "Reuse", "pin": PIN_C})[0], 409)   # unique across disabled accounts too
        head_id = self.db().execute("SELECT id FROM doctors WHERE role = 'head'").fetchone()[0]
        self.assertEqual(h.post(f"/api/doctors/{head_id}/access", {"active": False})[0], 404)   # the head cannot be disabled
        self.assertEqual(h.post(f"/api/doctors/{cid}/access", {"active": True})[0], 200)
        self.signed_in(PIN_C)

    # ---------------- 10 idle timeout, activity, background requests ----------------
    def test_10_sessions_expire_after_60_seconds_idle_and_activity_keeps_them(self):
        idle, active = self.signed_in(PIN_A), self.signed_in(HEAD_PIN)
        stream = EventReader(idle)   # an open live-update stream must not keep the session alive
        self.assertEqual(stream.status, 200)
        start = time.time()
        while time.time() - start < 50:
            self.assertEqual(idle.get("/api/history")[0], 200)   # background polling: allowed, but does not extend
            if int(time.time() - start) % 20 < 10:
                active.post("/api/activity")
            time.sleep(10)
        while time.time() - start < 66:
            active.post("/api/activity")
            time.sleep(5)
        self.assertEqual(idle.get("/api/history")[0], 401)
        self.assertEqual(idle.get("/api/me")[0], 401)
        self.assertEqual(idle.get(f"/media/{self.ids['scanA']}_boxes.png", raw=True)[0], 401)
        self.assertEqual(idle.get("/api/export.xlsx", raw=True)[0], 401)
        self.assertEqual(idle.post("/api/activity")[0], 401)       # activity cannot revive an expired session
        self.assertEqual(EventReader(idle).status, 401)
        stream.join(10)
        self.assertIsNotNone(stream.closed_at, "the live stream should close when the session expires")
        self.assertEqual(active.get("/api/history")[0], 200)
        self.assertGreater(time.time() - start, 60)
        self.assertEqual(idle.delete(f"/api/history/{self.ids['scanA']}")[0], 401)

    # ---------------- 11 registry lockout ----------------
    def test_11_registry_locks_for_24_hours_after_3_wrong_pins(self):
        c = self.reg()
        self.assertEqual(c.login("WR01")[1]["attempts_left"], 2)
        self.assertEqual(c.login("WR02")[1]["attempts_left"], 1)
        self.assertEqual(c.login(HEAD_PIN)[0], 200)                 # success resets the count
        self.assertEqual(self.failures("registry")[0], 0)
        status, body = c.login("WR03")
        self.assertEqual((status, body["attempts_left"]), (401, 2))
        status, body = c.login("WR04")
        self.assertEqual((status, body["attempts_left"]), (401, 1))
        status, body = c.login("WR05")
        self.assertEqual((status, body["code"]), (423, "locked"))
        _, until = self.failures("registry")
        self.assertAlmostEqual(until - time.time(), 24 * 3600, delta=120)
        status, body = c.login(HEAD_PIN)                            # the correct PIN is rejected while locked
        self.assertEqual((status, body["code"]), (423, "locked"))
        self.assertEqual(self.reg().get("/api/status")[1]["locked_until"] is not None, True)

    def test_12_lockout_survives_refresh_new_tabs_and_restart(self):
        status, body = self.reg().login(HEAD_PIN)                   # a new browser / tab / refresh
        self.assertEqual(status, 423)
        self.registry.restart()
        status, body = self.reg().login(HEAD_PIN)
        self.assertEqual((status, body["code"]), (423, "locked"))
        # the separate login rate limit also applies (10 per minute)
        c = self.reg()
        c.refresh_csrf()
        codes = [c.post("/api/login", {"pin": HEAD_PIN})[0] for _ in range(11)]
        self.assertIn(429, codes)
        # the Scanner keeps its own counter and still works
        s = self.scan_client()
        self.assertEqual(self.analyze(s, PIN_A, "Patient A", "PA-1", TINY)[1].get("error"), "Image dimensions are not supported.")

    def test_13_admin_reset_from_the_server_terminal(self):
        out = self.registry.cli("--reset-lockout")
        self.assertIn("lockout cleared", out.stdout)
        self.registry.restart()
        self.signed_in(HEAD_PIN)

    # ---------------- 14 scanner lockout ----------------
    def test_14_scanner_locks_after_3_wrong_pins(self):
        s = self.scan_client()
        self.assertEqual(self.analyze(s, "WR11", "Patient A", "PA-1", TINY)[1]["attempts_left"], 2)
        self.assertEqual(self.analyze(s, "WR12", "Patient A", "PA-1", TINY)[1]["attempts_left"], 1)
        status, body = self.analyze(s, "WR13", "Patient A", "PA-1", TINY)
        self.assertEqual((status, body["code"]), (423, "locked"))
        status, body = self.analyze(s, PIN_A, "Patient A", "PA-1", TINY)
        self.assertEqual((status, body["code"]), (423, "locked"))
        self.signed_in(HEAD_PIN)                                    # the Registry is not affected
        self.assertIn("lockout cleared", self.scanner.cli("--reset-lockout").stdout)
        self.assertEqual(self.analyze(s, PIN_A, "Patient A", "PA-1", TINY)[1].get("error"), "Image dimensions are not supported.")

    # ---------------- 15 existing features ----------------
    def test_15_existing_features_still_work(self):
        s = self.scan_client()
        status, body = self.analyze(s, PIN_B, "Someone Else", "PZ-9", data_url(self.ids["rawA"]))
        self.assertEqual((status, body.get("code")), (409, "duplicate_image"))
        status, body = self.analyze(s, PIN_B, "Wrong Name", "PA-1", TINY)
        self.assertEqual(status, 422)   # tiny image rejected before the patient checks
        status, body = self.analyze(s, PIN_B, "Wrong Name", "PA-1", data_url(png(64, 64, lambda x, y: (x * 4) % 256)))
        self.assertEqual((status, body.get("code")), (409, "patient_mismatch"))
        status, body = self.analyze(s, PIN_B, "Checker Board", "CB-1", data_url(png(320, 320, lambda x, y: 255 * ((x // 40 + y // 40) % 2))))
        self.assertEqual((status, body.get("code")), (422, "not_mri"))
        self.assertEqual(s.get("/api/stats")[0], 200)

        b = self.signed_in(PIN_B)
        self.assertEqual(b.delete(f"/api/history/{self.ids['scanB']}")[0], 200)   # a doctor can delete their own scan
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "images", self.ids["scanB"] + ".png")))
        self.assertEqual(b.get("/api/history")[1]["stats"]["total"], 0)
        status, page = self.reg().get("/", raw=True)
        self.assertEqual(status, 200)
        self.assertNotIn(b"Patient A", page)   # the page itself holds no patient data

    # ---------------- 16 no PINs in plain text anywhere ----------------
    def test_16_pins_never_stored_logged_or_returned_in_plain_text(self):
        blobs = {}
        for name in os.listdir(self.tmp):
            path = os.path.join(self.tmp, name)
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    blobs[name] = f.read()
        for c in self.clients:
            for i, body in enumerate(c.responses):
                # embedded images are random-looking base64 that could contain any 4 letters by chance
                blobs[f"response {i} from {c.base}"] = re.sub(rb"data:image/png;base64,[A-Za-z0-9+/=]+", b"", body)
        for pin in ALL_PINS:
            for name, blob in blobs.items():
                self.assertNotIn(pin.encode(), blob, f"{pin} found in {name}")
                self.assertNotIn(pin.lower().encode(), blob, f"{pin.lower()} found in {name}")
        for name, blob in blobs.items():
            if name.startswith("response"):
                self.assertNotIn(b"pin_hash", blob)
                self.assertNotIn(b"pin_lookup", blob)
        hashes = [r[0] for r in self.db().execute("SELECT pin_hash FROM doctors")]
        self.assertTrue(all(h.startswith("pbkdf2_sha256$300000$") for h in hashes))
        self.assertEqual(len(set(hashes)), len(hashes))

    # ---------------- 17 shared files are identical in both sites ----------------
    def test_17_shared_files_are_identical(self):
        for rel in ("auth.py", "static/common.js", "static/i18n.js"):
            with open(os.path.join(ROOT, "MRI-Scanner", rel), "rb") as f:
                a = f.read()
            with open(os.path.join(ROOT, "Patient-Registry", rel), "rb") as f:
                b = f.read()
            self.assertEqual(a, b, rel + " differs between the two folders")


if __name__ == "__main__":
    unittest.main(verbosity=2)
