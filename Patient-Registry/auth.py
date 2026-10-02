"""
MS SmartScan — حسابات الأطباء، الدخول بالرمز (PIN)، الجلسات، والقفل بعد المحاولات الخاطئة.

نفس الملف موجود في MRI-Scanner/ و Patient-Registry/ (كل موقع برنامج مستقل).
إذا عدّلتيه انسخيه للمجلد الآخر — الاختبار tests/test_auth.py يتأكد إنهم متطابقين.

- الرمز: 4 خانات بالضبط A–Z / 0–9 (تُحوَّل للأحرف الكبيرة). لا يُحفظ أبداً كنص:
  يُحفظ PBKDF2 مملّح لكل حساب + بصمة HMAC بمفتاح سري (data/auth.key) تجعل الرمز فريداً وسريع البحث.
- القفل: 3 رموز خاطئة متتالية تقفل الدخول على ذلك الموقع 24 ساعة (محفوظ في قاعدة البيانات).
- الجلسة (موقع السجل): رمز عشوائي في كوكي HttpOnly، ويُحفظ هاشه فقط؛ تنتهي بعد 60 ثانية بدون نشاط.
"""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime

PIN_RE = re.compile(r"[A-Z0-9]{4}")
PBKDF2_ITERATIONS = 300_000
MAX_FAILURES = 3                      # رموز خاطئة متتالية قبل القفل
LOCKOUT_SECONDS = 24 * 60 * 60        # مدة القفل
IDLE_SECONDS = 60                     # الجلسة تنتهي بعد دقيقة بدون نشاط
SESSION_MAX_SECONDS = 12 * 60 * 60    # وحد أقصى لعمر الجلسة حتى مع النشاط
DEPARTMENT = "Neurology"

# رئيسة القسم — تُنشأ مرة واحدة عند أول تشغيل. يُحفظ هنا هاش الرمز المتفق عليه فقط، لا الرمز نفسه.
HEAD_NAME = "Hailah Alhejjei"
HEAD_PIN_HASH = "pbkdf2_sha256$300000$00b2b2d59503f571923b9c33f99372a2$367621a8fc4654fadf192af7e5dcd1a7704fb62bec72a9d59f37779a07dfea16"

_lock = threading.Lock()


class DuplicatePin(Exception):
    pass


def normalize_pin(value):
    return re.sub(r"\s+", "", value).upper() if isinstance(value, str) else ""


def valid_pin(pin):
    return isinstance(pin, str) and PIN_RE.fullmatch(pin) is not None


def normalize_name(value):
    return re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else ""


def valid_name(name):
    return 2 <= len(name) <= 80 and any(c.isalpha() for c in name) and all(c.isprintable() for c in name)


def hash_pin(pin):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_pin(pin, stored):
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        test = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(test.hex(), digest)
    except (AttributeError, ValueError):
        return False


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _load_key(path):
    """Secret key for PIN lookup digests, created once in the data folder (shared by both sites)."""
    for _ in range(50):
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            with open(path, encoding="ascii") as f:
                text = f.read().strip()
            if re.fullmatch(r"[0-9a-f]{64}", text):
                return bytes.fromhex(text)
            time.sleep(0.1)   # the other site may still be writing it
            continue
        key = secrets.token_bytes(32)
        with os.fdopen(fd, "w", encoding="ascii") as f:
            f.write(key.hex())
        return key
    raise SystemExit(f"{path} is damaged. Delete it and start again (doctors keep their PINs).")


def public_doctor(row):
    """Account details that may be sent to the browser — never the PIN, its hash, or its lookup digest."""
    d = {"id": row["id"], "name": row["name"], "role": row["role"], "department": row["department"]}
    keys = row.keys()
    if "active" in keys:
        d["active"] = bool(row["active"])
    if "created_at" in keys:
        d["created_at"] = row["created_at"]
    if "scans" in keys:
        d["scans"] = row["scans"]
    return d


class AuthStore:
    def __init__(self, db_path, data_dir):
        self.db_path = db_path
        self.key = _load_key(os.path.join(data_dir, "auth.key"))
        self.key_id = hashlib.sha256(self.key).hexdigest()[:16]

    def connect(self):
        con = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)   # autocommit; transactions are explicit
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=10000")
        return con

    def _lookup(self, pin):
        return hmac.new(self.key, pin.encode(), hashlib.sha256).hexdigest()

    def _write(self, fn):
        """Run fn(con) in one write transaction, serialised across threads and both sites."""
        with _lock, closing(self.connect()) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                result = fn(con)
                con.execute("COMMIT")
                return result
            except BaseException:
                con.execute("ROLLBACK")
                raise

    # ---------------- ترحيل قاعدة البيانات (آمن، لا يحذف شيئاً) ----------------
    def migrate(self):
        def run(con):
            con.execute("""CREATE TABLE IF NOT EXISTS doctors (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                role            TEXT NOT NULL CHECK (role IN ('head', 'doctor')),
                department      TEXT NOT NULL,
                pin_hash        TEXT NOT NULL,      -- PBKDF2-SHA256 مملّح
                pin_lookup      TEXT,               -- HMAC بمفتاح data/auth.key (للتفرّد والبحث)
                pin_lookup_key  TEXT,               -- بصمة المفتاح الذي حُسبت به
                active          INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT NOT NULL,
                created_by      INTEGER REFERENCES doctors(id)
            )""")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_doctors_pin_lookup ON doctors(pin_lookup)")
            con.execute("""CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash      TEXT PRIMARY KEY,
                site            TEXT NOT NULL,
                doctor_id       INTEGER NOT NULL REFERENCES doctors(id),
                created_at      REAL NOT NULL,
                last_activity   REAL NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS auth_lockouts (
                site            TEXT PRIMARY KEY,
                failures        INTEGER NOT NULL DEFAULT 0,
                locked_until    REAL,
                updated_at      REAL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL,
                action      TEXT NOT NULL,
                target_id   TEXT,
                outcome     TEXT NOT NULL
            )""")
            # صاحب السجل: الفحوصات والمرضى القديمة تبقى بدون صاحب (NULL) ولا تُنسب لأي طبيب تلقائياً
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ("scans", "patients"):
                if table not in tables:
                    continue
                if "owner_doctor_id" not in {r[1] for r in con.execute(f"PRAGMA table_info({table})")}:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN owner_doctor_id INTEGER REFERENCES doctors(id)")
                con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_owner ON {table}(owner_doctor_id)")
            if not con.execute("SELECT 1 FROM doctors WHERE role = 'head'").fetchone():
                con.execute("INSERT INTO doctors (name, role, department, pin_hash, active, created_at) "
                            "VALUES (?, 'head', ?, ?, 1, ?)", (HEAD_NAME, DEPARTMENT, HEAD_PIN_HASH, _now_iso()))
        self._write(run)

    # ---------------- الرموز ----------------
    def _find(self, con, pin):
        """The account with this PIN (active or not), or None. Must run inside a write transaction."""
        row = con.execute("SELECT * FROM doctors WHERE pin_lookup = ? AND pin_lookup_key = ?",
                          (self._lookup(pin), self.key_id)).fetchone()
        if row is not None:
            return row if verify_pin(pin, row["pin_hash"]) else None
        # حسابات بدون بصمة بالمفتاح الحالي (رئيسة القسم قبل أول دخول، أو بعد فقدان auth.key): نتحقق من الهاش ونحدّث البصمة
        stale = con.execute("SELECT * FROM doctors WHERE pin_lookup_key IS NULL OR pin_lookup_key <> ?",
                            (self.key_id,)).fetchall()
        for row in stale:
            if verify_pin(pin, row["pin_hash"]):
                con.execute("UPDATE doctors SET pin_lookup = ?, pin_lookup_key = ? WHERE id = ?",
                            (self._lookup(pin), self.key_id, row["id"]))
                return con.execute("SELECT * FROM doctors WHERE id = ?", (row["id"],)).fetchone()
        return None

    def locked_until(self, site):
        """Epoch seconds until which sign-in on this site is locked, or None."""
        with closing(self.connect()) as con:
            row = con.execute("SELECT locked_until FROM auth_lockouts WHERE site = ?", (site,)).fetchone()
        return row["locked_until"] if row and row["locked_until"] and row["locked_until"] > time.time() else None

    def sign_in(self, site, pin):
        """Check a well-formed PIN for a site, counting wrong PINs towards the lockout.
        Returns {"status": "ok" | "wrong" | "locked" | "disabled", "doctor", "attempts_left", "locked_until"}."""
        def run(con):
            now = time.time()
            row = con.execute("SELECT failures, locked_until FROM auth_lockouts WHERE site = ?", (site,)).fetchone()
            failures = row["failures"] if row else 0
            locked = row["locked_until"] if row else None
            if locked and locked > now:   # الرمز الصحيح أيضاً مرفوض أثناء القفل
                return {"status": "locked", "locked_until": locked}
            if locked:                    # انتهى القفل: محاولات جديدة
                failures, locked = 0, None
            doctor = self._find(con, pin)
            if doctor is not None and doctor["active"]:
                status, failures = "ok", 0
            elif doctor is not None:
                status = "disabled"       # رمز صحيح لحساب موقوف: لا يُحتسب خطأ
            else:
                failures += 1
                status = "wrong"
                if failures >= MAX_FAILURES:
                    status, failures, locked = "locked", 0, now + LOCKOUT_SECONDS
            con.execute("""INSERT INTO auth_lockouts (site, failures, locked_until, updated_at) VALUES (?, ?, ?, ?)
                           ON CONFLICT(site) DO UPDATE SET failures = excluded.failures,
                           locked_until = excluded.locked_until, updated_at = excluded.updated_at""",
                        (site, failures, locked, now))
            result = {"status": status, "locked_until": locked}
            if status == "wrong":
                result["attempts_left"] = MAX_FAILURES - failures
            if doctor is not None:
                result["doctor"] = public_doctor(doctor)
            return result
        return self._write(run)

    def reset_lockout(self, site):
        """Administrator recovery from the server's own terminal (python server.py --reset-lockout)."""
        with closing(self.connect()) as con:
            con.execute("DELETE FROM auth_lockouts WHERE site = ?", (site,))

    # ---------------- الجلسات ----------------
    def create_session(self, site, doctor_id):
        token = secrets.token_urlsafe(32)
        now = time.time()
        with closing(self.connect()) as con:
            con.execute("DELETE FROM auth_sessions WHERE last_activity < ? OR created_at < ?",
                        (now - IDLE_SECONDS, now - SESSION_MAX_SECONDS))
            con.execute("INSERT INTO auth_sessions (token_hash, site, doctor_id, created_at, last_activity) "
                        "VALUES (?, ?, ?, ?, ?)", (_token_hash(token), site, doctor_id, now, now))
        return token

    def session(self, site, token, touch=False):
        """The signed-in doctor for this session token, or None if missing, expired or disabled.
        Only touch=True (explicit user activity) extends the 60-second idle window."""
        if not token or len(token) > 128:
            return None
        now = time.time()
        with closing(self.connect()) as con:
            row = con.execute("""SELECT s.token_hash, s.created_at AS started, s.last_activity,
                                        d.id, d.name, d.role, d.department, d.active
                                 FROM auth_sessions s JOIN doctors d ON d.id = s.doctor_id
                                 WHERE s.token_hash = ? AND s.site = ?""", (_token_hash(token), site)).fetchone()
            if row is None:
                return None
            if (not row["active"] or now - row["last_activity"] > IDLE_SECONDS
                    or now - row["started"] > SESSION_MAX_SECONDS):
                con.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (row["token_hash"],))
                return None
            if touch:
                con.execute("UPDATE auth_sessions SET last_activity = ? WHERE token_hash = ?", (now, row["token_hash"]))
        return public_doctor(row)

    def end_session(self, token):
        if token:
            with closing(self.connect()) as con:
                con.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_token_hash(token),))

    # ---------------- إدارة الأطباء (رئيسة القسم فقط — يتحقق منها السيرفر) ----------------
    def doctor(self, doctor_id):
        with closing(self.connect()) as con:
            return con.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()

    def list_doctors(self, department):
        with closing(self.connect()) as con:
            has_scans = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='scans'").fetchone()
            scans = "(SELECT COUNT(*) FROM scans s WHERE s.owner_doctor_id = d.id)" if has_scans else "0"
            rows = con.execute(f"""SELECT d.id, d.name, d.role, d.department, d.active, d.created_at, {scans} AS scans
                                   FROM doctors d WHERE d.department = ?
                                   ORDER BY d.role = 'head' DESC, d.created_at, d.id""", (department,)).fetchall()
        return [public_doctor(r) for r in rows]

    def register_doctor(self, name, pin, department, created_by):
        """New regular doctor. Raises DuplicatePin if any account (active or disabled) already has this PIN."""
        def run(con):
            if self._find(con, pin) is not None:
                raise DuplicatePin()
            cursor = con.execute("""INSERT INTO doctors (name, role, department, pin_hash, pin_lookup, pin_lookup_key,
                                    active, created_at, created_by) VALUES (?, 'doctor', ?, ?, ?, ?, 1, ?, ?)""",
                                 (name, department, hash_pin(pin), self._lookup(pin), self.key_id, _now_iso(), created_by))
            return con.execute("SELECT * FROM doctors WHERE id = ?", (cursor.lastrowid,)).fetchone()
        try:
            return public_doctor(self._write(run))
        except sqlite3.IntegrityError:   # same PIN registered at the same moment
            raise DuplicatePin() from None

    def set_active(self, doctor_id, active, department):
        """Enable or disable a regular doctor in this department. Disabling ends their sessions at once."""
        def run(con):
            row = con.execute("SELECT * FROM doctors WHERE id = ? AND role = 'doctor' AND department = ?",
                              (doctor_id, department)).fetchone()
            if row is None:
                return None
            con.execute("UPDATE doctors SET active = ? WHERE id = ?", (1 if active else 0, doctor_id))
            if not active:
                con.execute("DELETE FROM auth_sessions WHERE doctor_id = ?", (doctor_id,))
            return con.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
        row = self._write(run)
        return public_doctor(row) if row is not None else None
