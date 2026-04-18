import os
import time
import sqlite3
import hashlib
import re
import json
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__, template_folder="templates")

DB_PATH = os.environ.get("DB_PATH", "/data/bot_database.db")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "realupilootbot")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SECRET_SALT = os.environ.get("SECRET_SALT", "change_me_in_production")

MAX_ATTEMPTS = 5
RATE_WINDOW = 3600


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            balance REAL DEFAULT 0,
            total_earned REAL DEFAULT 0,
            total_withdrawn REAL DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            upi_id TEXT DEFAULT '',
            banned INTEGER DEFAULT 0,
            joined_at TEXT DEFAULT '',
            last_daily TEXT DEFAULT '',
            is_premium INTEGER DEFAULT 0,
            referral_paid INTEGER DEFAULT 0,
            ip_address TEXT DEFAULT '',
            ip_verified INTEGER DEFAULT 0,
            verify_attempts INTEGER DEFAULT 0,
            last_attempt_at REAL DEFAULT 0,
            verified_at REAL DEFAULT 0,
            session_hash TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            device_type TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS verify_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ip TEXT,
            result TEXT,
            reason TEXT,
            user_agent TEXT,
            ts REAL,
            session_hash TEXT DEFAULT ''
        )
    """)

    extra_columns = [
        ("referral_paid", "INTEGER DEFAULT 0"),
        ("ip_address", "TEXT DEFAULT ''"),
        ("ip_verified", "INTEGER DEFAULT 0"),
        ("verify_attempts", "INTEGER DEFAULT 0"),
        ("last_attempt_at", "REAL DEFAULT 0"),
        ("verified_at", "REAL DEFAULT 0"),
        ("session_hash", "TEXT DEFAULT ''"),
        ("user_agent", "TEXT DEFAULT ''"),
        ("device_type", "TEXT DEFAULT ''"),
    ]

    for col_name, col_type in extra_columns:
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


def get_setting_value(key, default=None):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        if not row:
            return default
        raw = row["value"]
        try:
            return json.loads(raw)
        except Exception:
            return raw
    finally:
        conn.close()


def send_bot_message(user_id: int, text: str, reply_markup=None):
    if not BOT_TOKEN:
        return False
    try:
        payload = {
            "chat_id": user_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10,
        )
        return resp.ok
    except Exception:
        return False


def notify_verification_result(user_id: int, success: bool):
    if success:
        msg = (
            "<tg-emoji emoji-id='5206607081334906820'>✅</tg-emoji> <b>Verification complete!</b>\n\n"
            "<tg-emoji emoji-id='5461151367559141950'>🎉</tg-emoji> Welcome! Your account is ready to use now! "
            "<tg-emoji emoji-id='5325547803936572038'>✨</tg-emoji>"
            "<tg-emoji emoji-id='5424972470023104089'>🚀</tg-emoji>\n"
            "<tg-emoji emoji-id='5409048419211682843'>💰</tg-emoji> Your verification was successful.\n"
            "<tg-emoji emoji-id='5427168083074628963'>🎁</tg-emoji> Just click on the button below to continue and receive your welcome bonus! "
            "<tg-emoji emoji-id='5424972470023104089'>🔥</tg-emoji>\n\n"
            "<tg-emoji emoji-id='5397916757333654639'>👉</tg-emoji> If something glitched, the manual verify button is still available below."
        )
        keyboard = {
            "inline_keyboard": [[
                {"text": "✅ I Verified", "callback_data": "check_ip_verified"}
            ]]
        }
        return send_bot_message(user_id, msg, reply_markup=keyboard)
    else:
        msg = (
            "<tg-emoji emoji-id='5447644880824181073'>⚠️</tg-emoji> <b>Welcome! Unfortunately, your verification has failed, but you can still use the bot. Click the button below to continue.</b>\n\n"
            "<tg-emoji emoji-id='5251203410396458957'>🛡️</tg-emoji> You can still use the bot even though IP verification failed.\n"
            "<tg-emoji emoji-id='5210952531676504517'>❌</tg-emoji> Your referrer will not receive the referral bonus for this verification.\n"
            "<tg-emoji emoji-id='5305265301917549162'>📎</tg-emoji> If something glitched, the manual verify button is still available in the bot.\n\n"
            "<tg-emoji emoji-id='5260293700088511294'>🚫</tg-emoji> Fake and same IP referrals are not available."
        )
        keyboard = {
            "inline_keyboard": [[
                {"text": "🚀 Continue to Bot", "url": f"https://t.me/{BOT_USERNAME}?start=continue"}
            ]]
        }
        return send_bot_message(user_id, msg, reply_markup=keyboard)


def get_real_ip():
    headers_to_check = ["CF-Connecting-IP", "X-Real-IP", "X-Forwarded-For"]
    for header in headers_to_check:
        value = request.headers.get(header, "")
        if value:
            return value.split(",")[0].strip()
    return request.remote_addr or ""


def detect_device(user_agent: str) -> str:
    ua = user_agent or ""
    if re.search(r"iPad|Tablet", ua, re.IGNORECASE):
        return "Tablet"
    if re.search(r"Mobi|Android|iPhone|iPod", ua, re.IGNORECASE):
        return "Mobile"
    return "Desktop"


def make_session_hash(user_id: int, ip: str, user_agent: str) -> str:
    raw = f"{user_id}|{ip}|{user_agent}|{SECRET_SALT}|{time.time()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def ip_taken_by_other_account(ip: str, user_id: int) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id FROM users WHERE ip_address = ? AND user_id != ? LIMIT 1",
        (ip, user_id)
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def format_ts(ts_value):
    try:
        ts_value = float(ts_value or 0)
        if ts_value <= 0:
            return "—"
        return time.strftime("%d %b %Y • %I:%M %p", time.localtime(ts_value))
    except Exception:
        return "—"


def log_verification(cur, user_id, ip, result, reason, user_agent, session_hash=""):
    cur.execute("""
        INSERT INTO verify_log (user_id, ip, result, reason, user_agent, ts, session_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, ip, result, reason, user_agent, time.time(), session_hash))


def verify_user(user_id: int, ip: str, user_agent: str):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()

    if not user:
        log_verification(cur, user_id, ip, "fail", "user_not_found", user_agent)
        conn.commit()
        conn.close()
        return False, {
            "message": "User not found. Please start the bot first.",
            "code": "ERR_USER_404"
        }

    if int(user["banned"] or 0) == 1:
        log_verification(cur, user_id, ip, "fail", "account_banned", user_agent)
        conn.commit()
        conn.close()
        return False, {
            "message": "Your account is banned.",
            "code": "ERR_ACCT_BAN"
        }

    ip_verification_enabled = bool(get_setting_value("ip_verification_enabled", True))

    if not ip_verification_enabled:
        now_ts = time.time()
        session_hash = make_session_hash(user_id, ip or "no-ip", user_agent)
        device_type = detect_device(user_agent)
        cur.execute(
            "UPDATE users SET ip_verified = 1, verified_at = ?, session_hash = ?, user_agent = ?, device_type = ? WHERE user_id = ?",
            (now_ts, session_hash, user_agent, device_type, user_id)
        )
        log_verification(cur, user_id, ip, "success", "ip_verification_disabled", user_agent, session_hash)
        conn.commit()
        conn.close()
        notify_verification_result(user_id, True)
        return True, {
            "message": "IP verification is disabled by admin. Welcome message sent automatically.",
            "status": "verified",
            "user_id": user_id,
            "session_hash": session_hash,
            "verified_at": format_ts(now_ts),
            "device_type": device_type,
            "bot_username": BOT_USERNAME
        }

    now = time.time()
    attempts = int(user["verify_attempts"] or 0)
    last_attempt_at = float(user["last_attempt_at"] or 0)

    if now - last_attempt_at >= RATE_WINDOW:
        attempts = 0

    if attempts >= MAX_ATTEMPTS:
        remaining = int(max(60, RATE_WINDOW - (now - last_attempt_at)))
        mins = max(1, remaining // 60)
        log_verification(cur, user_id, ip, "fail", "rate_limited", user_agent)
        conn.commit()
        conn.close()
        return False, {
            "message": f"Too many attempts. Try again in {mins} minute(s).",
            "code": "ERR_RATE_LIMIT"
        }

    if not ip:
        log_verification(cur, user_id, ip, "fail", "ip_missing", user_agent)
        conn.commit()
        conn.close()
        return False, {
            "message": "Could not detect your IP address.",
            "code": "ERR_IP_DETECT"
        }

    if int(user["ip_verified"] or 0) == 1:
        conn.close()
        return True, {
            "message": "Already verified.",
            "status": "already_verified",
            "user_id": user_id,
            "session_hash": user["session_hash"] or "",
            "verified_at": format_ts(user["verified_at"]),
            "device_type": user["device_type"] or detect_device(user_agent),
            "bot_username": BOT_USERNAME
        }

    if ip_taken_by_other_account(ip, user_id):
        cur.execute("""
            UPDATE users
            SET verify_attempts = ?, last_attempt_at = ?
            WHERE user_id = ?
        """, (attempts + 1, now, user_id))
        log_verification(cur, user_id, ip, "fail", "ip_conflict", user_agent)
        conn.commit()
        conn.close()
        notify_verification_result(user_id, False)
        return False, {
            "message": "This IP is already linked to another account. You can still use the bot, but your referrer cannot get the referral bonus.",
            "code": "ERR_IP_CONFLICT"
        }

    device_type = detect_device(user_agent)
    session_hash = make_session_hash(user_id, ip, user_agent)

    cur.execute("""
        UPDATE users
        SET
            ip_address = ?,
            ip_verified = 1,
            verify_attempts = ?,
            last_attempt_at = ?,
            verified_at = ?,
            session_hash = ?,
            user_agent = ?,
            device_type = ?
        WHERE user_id = ?
    """, (
        ip,
        attempts + 1,
        now,
        now,
        session_hash,
        user_agent,
        device_type,
        user_id
    ))

    log_verification(cur, user_id, ip, "success", "verified", user_agent, session_hash)
    conn.commit()
    conn.close()
    notify_verification_result(user_id, True)

    return True, {
        "message": "Verification successful.",
        "status": "verified",
        "user_id": user_id,
        "session_hash": session_hash,
        "verified_at": format_ts(now),
        "device_type": device_type,
        "bot_username": BOT_USERNAME
    }


@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "service": "web_verify",
        "version": "5.0"
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "timestamp": int(time.time())
    })


@app.route("/ip-verify")
@app.route("/ip-verify/")
def ip_verify():
    uid = request.args.get("uid", "").strip()

    if not uid or not uid.isdigit():
        return render_template(
            "verify.html",
            page_state="error",
            title="Verification Failed",
            message="Invalid or missing user ID. Use the correct link from the bot.",
            error_code="ERR_INVALID_UID",
            user_id="—",
            session_hash="—",
            verified_at="—",
            device_type="—",
            bot_username=BOT_USERNAME,
            redirect_url=f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "",
        ), 400

    user_id = int(uid)
    ip = get_real_ip()
    user_agent = request.headers.get("User-Agent", "")

    ok, data = verify_user(user_id, ip, user_agent)

    if not ok:
        return render_template(
            "verify.html",
            page_state="error",
            title="Verification Failed",
            message=data["message"],
            error_code=data.get("code", "ERR_UNKNOWN"),
            user_id=user_id,
            session_hash="—",
            verified_at="—",
            device_type=detect_device(user_agent),
            bot_username=BOT_USERNAME,
            redirect_url=f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "",
        ), 400

    return render_template(
        "verify.html",
        page_state="success",
        title="Verified Successfully",
        message=data["message"],
        error_code="—",
        user_id=data["user_id"],
        session_hash=data["session_hash"],
        verified_at=data["verified_at"],
        device_type=data["device_type"],
        bot_username=data["bot_username"],
        redirect_url=f"https://t.me/{data['bot_username']}" if data.get("bot_username") else "",
    )


@app.route("/api/verify-status/<int:user_id>")
def verify_status(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT ip_verified, ip_address, verified_at, device_type, session_hash
        FROM users
        WHERE user_id = ?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({
            "verified": False,
            "error": "user_not_found"
        }), 404

    return jsonify({
        "verified": bool(int(row["ip_verified"] or 0)),
        "ip_address": row["ip_address"] or "",
        "verified_at": row["verified_at"] or 0,
        "device_type": row["device_type"] or "",
        "session_hash": row["session_hash"] or ""
    })


@app.route("/api/verify-log/<int:user_id>")
def verify_log(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT result, reason, ts, ip
        FROM verify_log
        WHERE user_id = ?
        ORDER BY ts DESC
        LIMIT 20
    """, (user_id,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    return jsonify({
        "user_id": user_id,
        "logs": rows
    })


@app.route("/api/stats")
def stats():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM users")
    total_users = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM users WHERE ip_verified = 1")
    total_verified = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM verify_log WHERE result = 'fail'")
    total_failed = cur.fetchone()["total"]

    conn.close()

    return jsonify({
        "total_users": total_users,
        "total_verified": total_verified,
        "total_failed_attempts": total_failed
    })


ensure_schema()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
