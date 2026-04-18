
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlparse
from typing import Any, Callable, Dict, List, Optional, Tuple

from flask import Flask, request, render_template_string
from telebot import types
from telebot.types import WebAppInfo


# ============================================================
# Generic helpers
# ============================================================

def utc_now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def safe_json_loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def stable_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def normalize_ip(ip_address: str) -> str:
    return (ip_address or "").strip()[:128]


def normalize_user_agent(user_agent: str) -> str:
    return (user_agent or "").strip()[:500]


def is_suspicious_user_agent(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    risky = [
        "python-requests",
        "curl/",
        "wget/",
        "postman",
        "insomnia",
        "headless",
        "phantomjs",
        "selenium",
        "scrapy",
        "httpclient",
    ]
    return any(x in ua for x in risky)


def default_anticheat_settings() -> Dict[str, Any]:
    return {
        "enabled": True,
        "same_ip_soft_limit": 1,
        "same_ip_hard_limit": 2,
        "same_fp_soft_limit": 1,
        "same_fp_hard_limit": 2,
        "rate_limit_5m_per_ip": 5,
        "rate_limit_1h_per_ip": 20,
        "rate_limit_5m_per_user": 4,
        "rate_limit_1h_per_user": 10,
        "fraud_flag_threshold": 45,
        "fraud_block_threshold": 80,
        "referral_hold_minutes": 10,
        "auto_flag_on_duplicate_ip": True,
        "auto_flag_on_duplicate_fp": True,
    }


# ============================================================
# Web verification UI
# ============================================================

HTML_SUCCESS = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verification Complete</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .card {
            width: 92%;
            max-width: 460px;
            background: #1e293b;
            border-radius: 20px;
            padding: 28px;
            text-align: center;
            box-shadow: 0 12px 36px rgba(0,0,0,0.35);
            animation: fadeUp 0.6s ease;
        }
        .icon {
            font-size: 58px;
            margin-bottom: 12px;
            animation: pop 0.5s ease;
        }
        .btn {
            display: inline-block;
            margin-top: 18px;
            padding: 12px 18px;
            border-radius: 10px;
            background: #22c55e;
            color: white;
            text-decoration: none;
            font-weight: bold;
        }
        .muted {
            opacity: 0.85;
            font-size: 14px;
        }
        code {
            background: #334155;
            padding: 6px 10px;
            border-radius: 8px;
            display: inline-block;
            margin-top: 8px;
        }
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(18px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes pop {
            0%   { transform: scale(0.7); opacity: 0; }
            100% { transform: scale(1); opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">✅</div>
        <h1>Verification Complete</h1>
        <p>Your session has been verified successfully.</p>
        <code>User ID: {{ user_id }}</code>
        <p class="muted">Return to Telegram and tap <b>I Verified</b>.</p>
        <a class="btn" href="https://t.me/{{ bot_username }}">Return to Telegram</a>
    </div>
</body>
</html>
"""

HTML_ERROR = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verification Failed</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .card {
            width: 92%;
            max-width: 460px;
            background: #1e293b;
            border-radius: 20px;
            padding: 28px;
            text-align: center;
            box-shadow: 0 12px 36px rgba(0,0,0,0.35);
            animation: fadeUp 0.6s ease;
        }
        .icon {
            font-size: 58px;
            margin-bottom: 12px;
            animation: shake 0.5s ease;
        }
        .btn {
            display: inline-block;
            margin-top: 18px;
            padding: 12px 18px;
            border-radius: 10px;
            background: #3b82f6;
            color: white;
            text-decoration: none;
            font-weight: bold;
        }
        .reason {
            background: #334155;
            padding: 12px;
            border-radius: 10px;
            margin-top: 10px;
        }
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(18px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes shake {
            0%,100% { transform: translateX(0); }
            25% { transform: translateX(-5px); }
            75% { transform: translateX(5px); }
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">❌</div>
        <h1>Verification Failed</h1>
        <div class="reason">{{ message }}</div>
        <a class="btn" href="https://t.me/{{ bot_username }}">Return to Telegram</a>
    </div>
</body>
</html>
"""


# ============================================================
# Flask app factory for Railway
# ============================================================

def create_verification_app(
    DB_PATH: Optional[str] = None,
    BOT_USERNAME: Optional[str] = None,
) -> Flask:
    db_path = DB_PATH or os.environ.get("DB_PATH", "/data/bot_database.db")
    bot_username = BOT_USERNAME or os.environ.get("BOT_USERNAME", "NeturalPredictorbot")
    app = Flask(__name__)

    def get_db() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema() -> None:
        conn = get_db()
        cur = conn.cursor()

        cur.executescript("""
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
            first_verified_ip TEXT DEFAULT '',
            latest_ip TEXT DEFAULT '',
            fingerprint_hash TEXT DEFAULT '',
            fraud_score INTEGER DEFAULT 0,
            verification_status TEXT DEFAULT 'pending',
            verification_note TEXT DEFAULT '',
            flagged_for_review INTEGER DEFAULT 0,
            referral_hold_until TEXT DEFAULT '',
            last_verification_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS verification_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            ip_address TEXT DEFAULT '',
            fingerprint_hash TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            result TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            fraud_score INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS anti_settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );
        """)

        alter_statements = [
            "ALTER TABLE users ADD COLUMN first_verified_ip TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN latest_ip TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN fingerprint_hash TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN fraud_score INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN verification_status TEXT DEFAULT 'pending'",
            "ALTER TABLE users ADD COLUMN verification_note TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN flagged_for_review INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN referral_hold_until TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN last_verification_at TEXT DEFAULT ''",
        ]
        for stmt in alter_statements:
            try:
                cur.execute(stmt)
            except sqlite3.OperationalError:
                pass

        cur.execute(
            "INSERT OR IGNORE INTO anti_settings (key, value) VALUES (?, ?)",
            ("config", json.dumps(default_anticheat_settings()))
        )

        conn.commit()
        conn.close()

    def get_anti_settings() -> Dict[str, Any]:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM anti_settings WHERE key='config'")
        row = cur.fetchone()
        conn.close()
        if not row:
            return default_anticheat_settings()
        return safe_json_loads(row["value"], default_anticheat_settings())

    def get_real_ip() -> str:
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            return normalize_ip(forwarded_for.split(",")[0].strip())
        real_ip = request.headers.get("X-Real-IP", "")
        if real_ip:
            return normalize_ip(real_ip.strip())
        return normalize_ip(request.remote_addr or "")

    def build_fingerprint_hash() -> str:
        raw_fp = request.args.get("fp", "").strip()
        if raw_fp:
            return stable_hash(raw_fp)

        ua = normalize_user_agent(request.headers.get("User-Agent", ""))
        accept_lang = request.headers.get("Accept-Language", "")
        accept = request.headers.get("Accept", "")
        reduced = f"{ua}|{accept_lang}|{accept}"
        return stable_hash(reduced)

    def get_user(user_id: int) -> Optional[sqlite3.Row]:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return row

    def log_attempt(user_id: int, ip_address: str, fingerprint_hash: str, user_agent: str,
                    result: str, reason: str, fraud_score: int) -> None:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO verification_attempts
            (user_id, ip_address, fingerprint_hash, user_agent, result, reason, fraud_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, ip_address, fingerprint_hash, user_agent, result, reason, fraud_score, utc_now_str())
        )
        conn.commit()
        conn.close()

    def count_verified_accounts_by_ip(ip_address: str, exclude_user_id: int = 0) -> int:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS c FROM users WHERE first_verified_ip=? AND user_id!=?",
            (ip_address, exclude_user_id)
        )
        row = cur.fetchone()
        conn.close()
        return int(row["c"] if row else 0)

    def count_verified_accounts_by_fp(fingerprint_hash: str, exclude_user_id: int = 0) -> int:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS c FROM users WHERE fingerprint_hash=? AND user_id!=?",
            (fingerprint_hash, exclude_user_id)
        )
        row = cur.fetchone()
        conn.close()
        return int(row["c"] if row else 0)

    def count_attempts_by_ip(ip_address: str, minutes: int) -> int:
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS c FROM verification_attempts WHERE ip_address=? AND created_at>=?",
            (ip_address, cutoff)
        )
        row = cur.fetchone()
        conn.close()
        return int(row["c"] if row else 0)

    def count_attempts_by_user(user_id: int, minutes: int) -> int:
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS c FROM verification_attempts WHERE user_id=? AND created_at>=?",
            (user_id, cutoff)
        )
        row = cur.fetchone()
        conn.close()
        return int(row["c"] if row else 0)

    def compute_fraud_score(user_id: int, ip_address: str, fingerprint_hash: str, user_agent: str) -> Tuple[int, List[str]]:
        cfg = get_anti_settings()
        score = 0
        reasons: List[str] = []

        ip_uses = count_verified_accounts_by_ip(ip_address, user_id)
        fp_uses = count_verified_accounts_by_fp(fingerprint_hash, user_id)
        ip_5m = count_attempts_by_ip(ip_address, 5)
        ip_1h = count_attempts_by_ip(ip_address, 60)
        user_5m = count_attempts_by_user(user_id, 5)
        user_1h = count_attempts_by_user(user_id, 60)

        if ip_uses >= cfg["same_ip_soft_limit"]:
            score += 20 + (ip_uses * 10)
            reasons.append(f"IP reused by {ip_uses} verified account(s)")
        if ip_uses >= cfg["same_ip_hard_limit"]:
            score += 15
            reasons.append("IP crossed hard limit")

        if fp_uses >= cfg["same_fp_soft_limit"]:
            score += 25 + (fp_uses * 15)
            reasons.append(f"Fingerprint reused by {fp_uses} verified account(s)")
        if fp_uses >= cfg["same_fp_hard_limit"]:
            score += 15
            reasons.append("Fingerprint crossed hard limit")

        if ip_5m >= cfg["rate_limit_5m_per_ip"]:
            score += 20
            reasons.append("Too many attempts from same IP in 5 minutes")
        if ip_1h >= cfg["rate_limit_1h_per_ip"]:
            score += 15
            reasons.append("Too many attempts from same IP in 1 hour")

        if user_5m >= cfg["rate_limit_5m_per_user"]:
            score += 15
            reasons.append("Too many attempts for same user in 5 minutes")
        if user_1h >= cfg["rate_limit_1h_per_user"]:
            score += 10
            reasons.append("Too many attempts for same user in 1 hour")

        if is_suspicious_user_agent(user_agent):
            score += 30
            reasons.append("Suspicious user agent")

        return score, reasons

    def verify_user(user_id: int, ip_address: str, fingerprint_hash: str, user_agent: str) -> Tuple[bool, str]:
        cfg = get_anti_settings()
        user = get_user(user_id)

        if not user:
            log_attempt(user_id, ip_address, fingerprint_hash, user_agent, "failed", "User not found", 100)
            return False, "User not found in database."

        if int(user["ip_verified"] or 0) == 1:
            log_attempt(user_id, ip_address, fingerprint_hash, user_agent, "success", "Already verified", int(user["fraud_score"] or 0))
            return True, "Already verified."

        score, reasons = compute_fraud_score(user_id, ip_address, fingerprint_hash, user_agent)
        reason_text = "; ".join(reasons) if reasons else "Clean verification"

        verification_status = "verified"
        flagged_for_review = 0
        verification_note = ""

        if score >= cfg["fraud_block_threshold"]:
            verification_status = "blocked"
            flagged_for_review = 1
            verification_note = reason_text or "Blocked by fraud score"

        elif score >= cfg["fraud_flag_threshold"]:
            verification_status = "flagged"
            flagged_for_review = 1
            verification_note = reason_text or "Flagged for admin review"

        conn = get_db()
        cur = conn.cursor()

        if verification_status == "blocked":
            cur.execute(
                """
                UPDATE users
                SET latest_ip=?, fingerprint_hash=?, fraud_score=?,
                    verification_status=?, verification_note=?, flagged_for_review=?,
                    last_verification_at=?
                WHERE user_id=?
                """,
                (
                    ip_address,
                    fingerprint_hash,
                    score,
                    verification_status,
                    verification_note,
                    flagged_for_review,
                    utc_now_str(),
                    user_id,
                )
            )
            conn.commit()
            conn.close()
            log_attempt(user_id, ip_address, fingerprint_hash, user_agent, "failed", verification_note, score)
            return False, f"Verification blocked. Reason: {verification_note}"

        hold_until = (datetime.utcnow() + timedelta(minutes=int(cfg["referral_hold_minutes"]))).strftime("%Y-%m-%d %H:%M:%S")
        first_verified_ip = user["first_verified_ip"] or ip_address

        cur.execute(
            """
            UPDATE users
            SET ip_address=?, ip_verified=1, first_verified_ip=?, latest_ip=?,
                fingerprint_hash=?, fraud_score=?, verification_status=?,
                verification_note=?, flagged_for_review=?, referral_hold_until=?,
                last_verification_at=?
            WHERE user_id=?
            """,
            (
                ip_address,
                first_verified_ip,
                ip_address,
                fingerprint_hash,
                score,
                verification_status,
                verification_note,
                flagged_for_review,
                hold_until,
                utc_now_str(),
                user_id,
            )
        )
        conn.commit()
        conn.close()

        if verification_status == "flagged":
            log_attempt(user_id, ip_address, fingerprint_hash, user_agent, "flagged", verification_note, score)
            return True, "Verified, but flagged for admin review."

        log_attempt(user_id, ip_address, fingerprint_hash, user_agent, "success", reason_text, score)
        return True, "Verified successfully."

    @app.route("/")
    def home():
        return "IP verify server is running."

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/ip-verify")
    def ip_verify():
        uid = request.args.get("uid", "").strip()
        if not uid or not uid.isdigit():
            return render_template_string(
                HTML_ERROR,
                message="Invalid or missing user ID.",
                bot_username=bot_username,
            ), 400

        user_id = int(uid)
        ip_address = get_real_ip()
        user_agent = normalize_user_agent(request.headers.get("User-Agent", ""))
        fingerprint_hash = build_fingerprint_hash()

        ok, message = verify_user(user_id, ip_address, fingerprint_hash, user_agent)
        if not ok:
            return render_template_string(
                HTML_ERROR,
                message=message,
                bot_username=bot_username,
            ), 400

        return render_template_string(
            HTML_SUCCESS,
            user_id=user_id,
            bot_username=bot_username,
        )

    init_schema()
    return app


# ============================================================
# Main bot anti-cheat class
# ============================================================

class AntiCheatSystem:
    def __init__(
        self,
        bot: Any,
        db_path: str,
        db_execute: Callable[..., Any],
        get_user: Callable[[int], Any],
        update_user: Callable[..., Any],
        get_setting: Callable[[str], Any],
        set_setting: Callable[[str, Any], None],
        safe_send: Callable[..., Any],
        safe_answer: Callable[..., Any],
        is_admin: Callable[[int], bool],
        pe: Callable[[str], str],
        process_referral_bonus: Callable[[int], Any],
    ) -> None:
        self.bot = bot
        self.db_path = db_path
        self.db_execute = db_execute
        self.get_user = get_user
        self.update_user = update_user
        self.get_setting = get_setting
        self.set_setting = set_setting
        self.safe_send = safe_send
        self.safe_answer = safe_answer
        self.is_admin = is_admin
        self.pe = pe
        self.process_referral_bonus = process_referral_bonus
        self.public_base_url = normalize_public_base_url(os.environ.get("PUBLIC_BASE_URL", ""))

    # ----------------------------
    # Schema
    # ----------------------------
    def init_schema(self) -> None:
        self.db_execute("""
        CREATE TABLE IF NOT EXISTS verification_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            ip_address TEXT DEFAULT '',
            fingerprint_hash TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            result TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            fraud_score INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ''
        )
        """)

        self.db_execute("""
        CREATE TABLE IF NOT EXISTS anti_settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        )
        """)

        alter_statements = [
            "ALTER TABLE users ADD COLUMN first_verified_ip TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN latest_ip TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN fingerprint_hash TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN fraud_score INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN verification_status TEXT DEFAULT 'pending'",
            "ALTER TABLE users ADD COLUMN verification_note TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN flagged_for_review INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN referral_hold_until TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN last_verification_at TEXT DEFAULT ''",
        ]
        existing_columns = {row["name"] for row in self.db_execute("PRAGMA table_info(users)", fetch=True) or []}
        for stmt in alter_statements:
            try:
                col_name = stmt.split("ADD COLUMN", 1)[1].strip().split()[0]
                if col_name in existing_columns:
                    continue
                self.db_execute(stmt)
                existing_columns.add(col_name)
            except Exception:
                pass

        existing = self.db_execute(
            "SELECT value FROM anti_settings WHERE key='config'",
            fetchone=True
        )
        if not existing:
            self.db_execute(
                "INSERT INTO anti_settings (key, value) VALUES (?, ?)",
                ("config", json.dumps(default_anticheat_settings()))
            )

    def get_anti_settings(self) -> Dict[str, Any]:
        row = self.db_execute(
            "SELECT value FROM anti_settings WHERE key='config'",
            fetchone=True
        )
        if not row:
            return default_anticheat_settings()
        return safe_json_loads(row["value"], default_anticheat_settings())

    def save_anti_settings(self, cfg: Dict[str, Any]) -> None:
        self.db_execute(
            "INSERT OR REPLACE INTO anti_settings (key, value) VALUES (?, ?)",
            ("config", json.dumps(cfg))
        )

    # ----------------------------
    # Data queries
    # ----------------------------
    def count_verified_accounts_by_ip(self, ip_address: str, exclude_user_id: int = 0) -> int:
        row = self.db_execute(
            "SELECT COUNT(*) AS c FROM users WHERE first_verified_ip=? AND user_id!=?",
            (ip_address, exclude_user_id),
            fetchone=True
        )
        return int(row["c"] if row else 0)

    def count_verified_accounts_by_fp(self, fingerprint_hash: str, exclude_user_id: int = 0) -> int:
        row = self.db_execute(
            "SELECT COUNT(*) AS c FROM users WHERE fingerprint_hash=? AND user_id!=?",
            (fingerprint_hash, exclude_user_id),
            fetchone=True
        )
        return int(row["c"] if row else 0)

    def count_attempts_by_ip(self, ip_address: str, minutes: int) -> int:
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        row = self.db_execute(
            "SELECT COUNT(*) AS c FROM verification_attempts WHERE ip_address=? AND created_at>=?",
            (ip_address, cutoff),
            fetchone=True
        )
        return int(row["c"] if row else 0)

    def count_attempts_by_user(self, user_id: int, minutes: int) -> int:
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        row = self.db_execute(
            "SELECT COUNT(*) AS c FROM verification_attempts WHERE user_id=? AND created_at>=?",
            (user_id, cutoff),
            fetchone=True
        )
        return int(row["c"] if row else 0)

    def get_flagged_users(self) -> List[Any]:
        return self.db_execute(
            """
            SELECT * FROM users
            WHERE flagged_for_review=1
               OR verification_status IN ('flagged', 'blocked')
            ORDER BY fraud_score DESC, last_verification_at DESC
            """,
            fetch=True
        ) or []

    def get_duplicate_ips(self) -> List[Any]:
        return self.db_execute(
            """
            SELECT first_verified_ip AS ip_address, COUNT(*) AS total
            FROM users
            WHERE first_verified_ip != ''
            GROUP BY first_verified_ip
            HAVING COUNT(*) > 1
            ORDER BY total DESC
            """,
            fetch=True
        ) or []

    def get_duplicate_fingerprints(self) -> List[Any]:
        return self.db_execute(
            """
            SELECT fingerprint_hash, COUNT(*) AS total
            FROM users
            WHERE fingerprint_hash != ''
            GROUP BY fingerprint_hash
            HAVING COUNT(*) > 1
            ORDER BY total DESC
            """,
            fetch=True
        ) or []

    def get_recent_attempts(self, limit: int = 20) -> List[Any]:
        return self.db_execute(
            "SELECT * FROM verification_attempts ORDER BY created_at DESC LIMIT ?",
            (limit,),
            fetch=True
        ) or []

    # ----------------------------
    # Fraud logic
    # ----------------------------
    def can_pay_referral_bonus(self, user_id: int) -> Tuple[bool, str]:
        user = self.get_user(user_id)
        if not user:
            return False, "User not found"

        if int(user["ip_verified"] or 0) != 1:
            return False, "IP not verified"

        status = (user["verification_status"] or "pending").lower()
        if status in ("blocked", "flagged", "review"):
            return False, f"Verification status: {status}"

        if int(user["flagged_for_review"] or 0) == 1:
            return False, "Flagged for manual review"

        fraud_score = int(user["fraud_score"] or 0)
        cfg = self.get_anti_settings()
        if fraud_score >= cfg["fraud_flag_threshold"]:
            return False, f"Fraud score too high: {fraud_score}"

        hold_until = (user["referral_hold_until"] or "").strip()
        if hold_until:
            try:
                dt = datetime.strptime(hold_until, "%Y-%m-%d %H:%M:%S")
                if datetime.utcnow() < dt:
                    return False, f"Referral hold active until {hold_until}"
            except Exception:
                pass

        if int(user["referral_paid"] or 0) == 1:
            return False, "Referral already paid"

        if not int(user["referred_by"] or 0):
            return False, "No referrer found"

        return True, "Eligible"

    def send_ip_verify_message(self, chat_id: int, user_id: int) -> None:
        self.public_base_url = normalize_public_base_url(self.public_base_url)
        if not self.public_base_url:
            self.safe_send(chat_id, "❌ IP verification is not configured. Please set a valid HTTPS PUBLIC_BASE_URL.")
            return

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "🚀 Verify & Unlock Reward",
                web_app=WebAppInfo(url=f"{self.public_base_url}/ip-verify?uid={user_id}")
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                "✅ I Verified",
                callback_data="check_ip_verified"
            )
        )

        self.safe_send(
            chat_id,
            f"{self.pe('shield')} <b>Advanced Verification</b> {self.pe('verify')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{self.pe('warning')} <b>Action Required!</b>\n"
            f"{self.pe('info')} Complete verification to unlock your reward.\n\n"
            f"{self.pe('target')} <b>Checks include:</b>\n"
            f"{self.pe('arrow')} IP review\n"
            f"{self.pe('arrow')} device/session fingerprint checks\n"
            f"{self.pe('arrow')} multi-account risk scoring\n\n"
            f"{self.pe('zap')} <b>Steps:</b>\n"
            f"{self.pe('play')} Tap verify button\n"
            f"{self.pe('play')} Complete quick check\n"
            f"{self.pe('play')} Return and tap <b>I Verified</b>\n\n"
            f"{self.pe('money')} <b>Reward Status:</b> Locked 🔒\n"
            f"{self.pe('arrow')} You can still continue using the bot anytime.\n"
            f"{self.pe('play')} Just tap /start to begin again but if you direct /start Your Inviter Cant Recives The Bonus 🚀" 
            f"━━━━━━━━━━━━━━━━━━━━━━",
            reply_markup=markup
        )

    # ----------------------------
    # Admin panel
    # ----------------------------
    def build_admin_keyboard(self) -> types.InlineKeyboardMarkup:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🚨 Flagged Users", callback_data="ac_flagged"),
            types.InlineKeyboardButton("🌐 Duplicate IPs", callback_data="ac_dup_ips"),
        )
        markup.add(
            types.InlineKeyboardButton("🧬 Duplicate Fingerprints", callback_data="ac_dup_fp"),
            types.InlineKeyboardButton("📝 Recent Attempts", callback_data="ac_attempts"),
        )
        markup.add(
            types.InlineKeyboardButton("⚙️ Anti Settings", callback_data="ac_settings"),
            types.InlineKeyboardButton("📊 Anti Stats", callback_data="ac_stats"),
        )
        return markup

    def format_flagged_users(self) -> str:
        rows = self.get_flagged_users()
        if not rows:
            return "✅ <b>No flagged users right now.</b>"

        text = "🚨 <b>Flagged / Blocked Users</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for row in rows[:20]:
            text += (
                f"👤 <code>{row['user_id']}</code>\n"
                f"• status: <b>{row['verification_status'] or 'pending'}</b>\n"
                f"• fraud score: <b>{int(row['fraud_score'] or 0)}</b>\n"
                f"• ip: <code>{row['latest_ip'] or row['first_verified_ip'] or '-'}</code>\n"
                f"• note: {row['verification_note'] or '-'}\n\n"
            )
        return text

    def format_duplicate_ips(self) -> str:
        rows = self.get_duplicate_ips()
        if not rows:
            return "✅ <b>No duplicate verified IPs found.</b>"
        text = "🌐 <b>Duplicate Verified IPs</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for row in rows[:20]:
            text += f"• <code>{row['ip_address']}</code> → <b>{row['total']}</b> account(s)\n"
        return text

    def format_duplicate_fingerprints(self) -> str:
        rows = self.get_duplicate_fingerprints()
        if not rows:
            return "✅ <b>No duplicate verified fingerprints found.</b>"
        text = "🧬 <b>Duplicate Fingerprints</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for row in rows[:20]:
            short_fp = (row["fingerprint_hash"] or "")[:20]
            text += f"• <code>{short_fp}...</code> → <b>{row['total']}</b> account(s)\n"
        return text

    def format_attempts(self) -> str:
        rows = self.get_recent_attempts(20)
        if not rows:
            return "ℹ️ <b>No verification attempts logged yet.</b>"
        text = "📝 <b>Recent Verification Attempts</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for row in rows:
            text += (
                f"👤 <code>{row['user_id']}</code>\n"
                f"• result: <b>{row['result']}</b>\n"
                f"• score: <b>{row['fraud_score']}</b>\n"
                f"• reason: {row['reason'] or '-'}\n"
                f"• at: {row['created_at']}\n\n"
            )
        return text

    def format_settings(self) -> str:
        cfg = self.get_anti_settings()
        return (
            "⚙️ <b>Anti-Cheat Settings</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"• enabled: <b>{cfg['enabled']}</b>\n"
            f"• same_ip_soft_limit: <b>{cfg['same_ip_soft_limit']}</b>\n"
            f"• same_ip_hard_limit: <b>{cfg['same_ip_hard_limit']}</b>\n"
            f"• same_fp_soft_limit: <b>{cfg['same_fp_soft_limit']}</b>\n"
            f"• same_fp_hard_limit: <b>{cfg['same_fp_hard_limit']}</b>\n"
            f"• rate_limit_5m_per_ip: <b>{cfg['rate_limit_5m_per_ip']}</b>\n"
            f"• rate_limit_1h_per_ip: <b>{cfg['rate_limit_1h_per_ip']}</b>\n"
            f"• rate_limit_5m_per_user: <b>{cfg['rate_limit_5m_per_user']}</b>\n"
            f"• rate_limit_1h_per_user: <b>{cfg['rate_limit_1h_per_user']}</b>\n"
            f"• fraud_flag_threshold: <b>{cfg['fraud_flag_threshold']}</b>\n"
            f"• fraud_block_threshold: <b>{cfg['fraud_block_threshold']}</b>\n"
            f"• referral_hold_minutes: <b>{cfg['referral_hold_minutes']}</b>\n"
        )

    def format_stats(self) -> str:
        total_attempts = self.db_execute("SELECT COUNT(*) AS c FROM verification_attempts", fetchone=True)
        success = self.db_execute("SELECT COUNT(*) AS c FROM verification_attempts WHERE result='success'", fetchone=True)
        flagged = self.db_execute("SELECT COUNT(*) AS c FROM verification_attempts WHERE result='flagged'", fetchone=True)
        failed = self.db_execute("SELECT COUNT(*) AS c FROM verification_attempts WHERE result='failed'", fetchone=True)
        blocked_users = self.db_execute("SELECT COUNT(*) AS c FROM users WHERE verification_status='blocked'", fetchone=True)
        flagged_users = self.db_execute("SELECT COUNT(*) AS c FROM users WHERE flagged_for_review=1", fetchone=True)

        return (
            "📊 <b>Anti-Cheat Stats</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"• total attempts: <b>{int(total_attempts['c'] if total_attempts else 0)}</b>\n"
            f"• success attempts: <b>{int(success['c'] if success else 0)}</b>\n"
            f"• flagged attempts: <b>{int(flagged['c'] if flagged else 0)}</b>\n"
            f"• failed attempts: <b>{int(failed['c'] if failed else 0)}</b>\n"
            f"• blocked users: <b>{int(blocked_users['c'] if blocked_users else 0)}</b>\n"
            f"• users pending review: <b>{int(flagged_users['c'] if flagged_users else 0)}</b>\n"
        )

    def register_bot_handlers(self) -> None:
        # IMPORTANT: No duplicate "check_ip_verified" handler here.
        # Your main bot file should keep its own check_ip_verified() callback.
        @self.bot.message_handler(commands=["anticheat"])
        def anticheat_panel(message: Any) -> None:
            if not self.is_admin(message.from_user.id):
                self.safe_send(message.chat.id, "❌ Access denied")
                return
            self.safe_send(
                message.chat.id,
                "🛡 <b>Anti-Cheat Panel</b>\n\nChoose an option below.",
                reply_markup=self.build_admin_keyboard()
            )

        @self.bot.callback_query_handler(func=lambda call: call.data in {
            "ac_flagged", "ac_dup_ips", "ac_dup_fp", "ac_attempts", "ac_settings", "ac_stats"
        })
        def anticheat_callbacks(call: Any) -> None:
            if not self.is_admin(call.from_user.id):
                self.safe_answer(call, "Access denied", True)
                return

            self.safe_answer(call)

            mapping = {
                "ac_flagged": self.format_flagged_users,
                "ac_dup_ips": self.format_duplicate_ips,
                "ac_dup_fp": self.format_duplicate_fingerprints,
                "ac_attempts": self.format_attempts,
                "ac_settings": self.format_settings,
                "ac_stats": self.format_stats,
            }

            text = mapping[call.data]()
            self.safe_send(call.message.chat.id, text, reply_markup=self.build_admin_keyboard())

def normalize_public_base_url(raw_url: str) -> str:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        for env_key in ("PUBLIC_BASE_URL", "RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL"):
            candidate = (os.environ.get(env_key, "") or "").strip()
            if candidate:
                raw_url = candidate
                break
    if not raw_url:
        return ""

    if not re.match(r"^https?://", raw_url, re.IGNORECASE):
        raw_url = f"https://{raw_url.lstrip('/')}"

    parsed = urlparse(raw_url)
    if not parsed.netloc:
        return ""

    return f"https://{parsed.netloc}{parsed.path}".rstrip("/")


