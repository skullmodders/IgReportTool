"""
getoldb.py

Admin-only SQLite upload/merge system for pyTelegramBotAPI bots.

Purpose:
- /uploaddb command
- admin sends an old .db / .sqlite file to the bot
- module validates uploaded file is a SQLite database
- creates a backup of current DB
- merges old DB into current DB
- preserves current live data while importing missing/older records safely
- does NOT blindly overwrite the whole database by default

Recommended use:
- good for importing an old database you downloaded earlier with /getdb
- keeps current bot data safer than full replacement

How to use in main bot file:
----------------------------
from getoldb import DatabaseImportSystem

db_importer = DatabaseImportSystem(
    bot=bot,
    is_admin=is_admin,
    safe_send=safe_send,
    db_path=DB_PATH,
    get_db=get_db,
    db_execute=db_execute,
    log_admin_action=log_admin_action,   # optional
)

db_importer.register_handlers()

Command:
- /uploaddb
Then send the old database file as a document.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set


class DatabaseImportSystem:
    def __init__(
        self,
        bot: Any,
        is_admin: Callable[[int], bool],
        safe_send: Callable[..., Any],
        db_path: str,
        get_db: Callable[[], sqlite3.Connection],
        db_execute: Callable[..., Any],
        log_admin_action: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.bot = bot
        self.is_admin = is_admin
        self.safe_send = safe_send
        self.db_path = db_path
        self.get_db = get_db
        self.db_execute = db_execute
        self.log_admin_action = log_admin_action

        self.awaiting_upload: Set[int] = set()

    # ============================================================
    # Helper methods
    # ============================================================

    def now_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def make_backup(self) -> str:
        backup_dir = os.path.join(os.path.dirname(self.db_path) or ".", "db_backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_before_import_{stamp}.db")
        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def download_document_to_temp(self, file_id: str, filename: str) -> str:
        file_info = self.bot.get_file(file_id)
        file_bytes = self.bot.download_file(file_info.file_path)

        suffix = ".db"
        lower_name = (filename or "").lower()
        if lower_name.endswith(".sqlite"):
            suffix = ".sqlite"
        elif lower_name.endswith(".sqlite3"):
            suffix = ".sqlite3"
        elif lower_name.endswith(".db"):
            suffix = ".db"

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(file_bytes)
        tmp.flush()
        tmp.close()
        return tmp.name

    def validate_sqlite_file(self, file_path: str) -> bool:
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
            if header != b"SQLite format 3\x00":
                return False

            conn = sqlite3.connect(file_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            cur.fetchone()
            conn.close()
            return True
        except Exception:
            return False

    def table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cur.fetchone() is not None

    def get_columns(self, conn: sqlite3.Connection, table_name: str) -> List[str]:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table_name})")
        rows = cur.fetchall()
        return [r[1] for r in rows]

    def copy_missing_rows_by_pk(
        self,
        src_conn: sqlite3.Connection,
        dst_conn: sqlite3.Connection,
        table_name: str,
        pk_col: str,
    ) -> int:
        if not self.table_exists(src_conn, table_name) or not self.table_exists(dst_conn, table_name):
            return 0

        src_cols = self.get_columns(src_conn, table_name)
        dst_cols = self.get_columns(dst_conn, table_name)
        common_cols = [c for c in src_cols if c in dst_cols]

        if pk_col not in common_cols:
            return 0

        src_cur = src_conn.cursor()
        dst_cur = dst_conn.cursor()

        src_cur.execute(f"SELECT {', '.join(common_cols)} FROM {table_name}")
        rows = src_cur.fetchall()

        inserted = 0
        placeholders = ", ".join(["?"] * len(common_cols))
        insert_sql = f"INSERT OR IGNORE INTO {table_name} ({', '.join(common_cols)}) VALUES ({placeholders})"

        for row in rows:
            try:
                dst_cur.execute(insert_sql, tuple(row))
                if dst_cur.rowcount > 0:
                    inserted += 1
            except Exception:
                continue

        dst_conn.commit()
        return inserted

    def merge_users(self, src_conn: sqlite3.Connection, dst_conn: sqlite3.Connection) -> Dict[str, int]:
        result = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
        }

        if not self.table_exists(src_conn, "users") or not self.table_exists(dst_conn, "users"):
            return result

        src_cols = self.get_columns(src_conn, "users")
        dst_cols = self.get_columns(dst_conn, "users")
        common_cols = [c for c in src_cols if c in dst_cols]

        if "user_id" not in common_cols:
            return result

        src_cur = src_conn.cursor()
        dst_cur = dst_conn.cursor()

        src_cur.execute(f"SELECT {', '.join(common_cols)} FROM users")
        src_rows = src_cur.fetchall()

        src_index = {col: idx for idx, col in enumerate(common_cols)}

        numeric_prefer_max = {
            "balance",
            "total_earned",
            "total_withdrawn",
            "referral_count",
            "referral_paid",
            "ip_verified",
            "fraud_score",
            "flagged_for_review",
            "is_premium",
            "banned",
        }

        text_fill_if_empty = {
            "username",
            "first_name",
            "upi_id",
            "ip_address",
            "first_verified_ip",
            "latest_ip",
            "fingerprint_hash",
            "verification_status",
            "verification_note",
            "joined_at",
            "last_daily",
            "referral_hold_until",
            "last_verification_at",
        }

        for row in src_rows:
            row_dict = {col: row[src_index[col]] for col in common_cols}
            user_id = row_dict["user_id"]

            dst_cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            existing = dst_cur.fetchone()

            if existing is None:
                placeholders = ", ".join(["?"] * len(common_cols))
                insert_sql = f"INSERT OR IGNORE INTO users ({', '.join(common_cols)}) VALUES ({placeholders})"
                try:
                    dst_cur.execute(insert_sql, tuple(row_dict[c] for c in common_cols))
                    if dst_cur.rowcount > 0:
                        result["inserted"] += 1
                    else:
                        result["skipped"] += 1
                except Exception:
                    result["skipped"] += 1
                continue

            existing_cols = self.get_columns(dst_conn, "users")
            ex_map = {existing_cols[i]: existing[i] for i in range(len(existing_cols))}

            updates = {}
            for col in common_cols:
                if col == "user_id":
                    continue

                old_val = row_dict.get(col)
                cur_val = ex_map.get(col)

                if col in numeric_prefer_max:
                    try:
                        old_num = float(old_val or 0)
                        cur_num = float(cur_val or 0)
                        if old_num > cur_num:
                            updates[col] = old_val
                    except Exception:
                        pass

                elif col in text_fill_if_empty:
                    if (not cur_val or str(cur_val).strip() == "") and old_val not in (None, ""):
                        updates[col] = old_val

                elif col == "referred_by":
                    try:
                        cur_ref = int(cur_val or 0)
                        old_ref = int(old_val or 0)
                        if cur_ref == 0 and old_ref != 0:
                            updates[col] = old_ref
                    except Exception:
                        pass

            if updates:
                set_sql = ", ".join([f"{col}=?" for col in updates.keys()])
                params = list(updates.values()) + [user_id]
                try:
                    dst_cur.execute(f"UPDATE users SET {set_sql} WHERE user_id=?", params)
                    result["updated"] += 1
                except Exception:
                    result["skipped"] += 1
            else:
                result["skipped"] += 1

        dst_conn.commit()
        return result

    def merge_database_file(self, uploaded_db_path: str) -> Dict[str, Any]:
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Live DB not found: {self.db_path}")

        backup_path = self.make_backup()

        src_conn = sqlite3.connect(uploaded_db_path)
        src_conn.row_factory = sqlite3.Row

        dst_conn = sqlite3.connect(self.db_path)
        dst_conn.row_factory = sqlite3.Row

        summary: Dict[str, Any] = {
            "backup_path": backup_path,
            "users": {},
            "generic_tables": {},
        }

        try:
            # Merge users carefully
            summary["users"] = self.merge_users(src_conn, dst_conn)

            # Generic import for other tables using INSERT OR IGNORE
            generic_tables = [
                ("withdrawals", "id"),
                ("gift_codes", "code"),
                ("gift_claims", "id"),
                ("broadcasts", "id"),
                ("bonus_history", "id"),
                ("tasks", "id"),
                ("task_submissions", "id"),
                ("task_completions", "id"),
                ("admins", "user_id"),
                ("admin_logs", "id"),
                ("verification_attempts", "id"),
                ("anti_settings", "key"),
            ]

            for table_name, pk_col in generic_tables:
                inserted = self.copy_missing_rows_by_pk(src_conn, dst_conn, table_name, pk_col)
                summary["generic_tables"][table_name] = inserted

            dst_conn.commit()
            return summary
        finally:
            src_conn.close()
            dst_conn.close()

    def format_summary(self, summary: Dict[str, Any]) -> str:
        users = summary.get("users", {})
        generic = summary.get("generic_tables", {})

        lines = [
            "✅ <b>Database import completed</b>",
            "",
            f"🛟 <b>Backup created:</b>",
            f"<code>{summary.get('backup_path', '-')}</code>",
            "",
            "👥 <b>Users merge:</b>",
            f"• Inserted: <b>{users.get('inserted', 0)}</b>",
            f"• Updated: <b>{users.get('updated', 0)}</b>",
            f"• Skipped: <b>{users.get('skipped', 0)}</b>",
            "",
            "🗂 <b>Other tables imported:</b>",
        ]

        for table_name, count in generic.items():
            lines.append(f"• {table_name}: <b>{count}</b> row(s)")

        return "\n".join(lines)

    # ============================================================
    # Handlers
    # ============================================================

    def register_handlers(self) -> None:
        @self.bot.message_handler(commands=["uploaddb"])
        def upload_db_command(message: Any) -> None:
            user_id = message.from_user.id
            if not self.is_admin(user_id):
                self.safe_send(message.chat.id, "❌ Access denied")
                return

            self.awaiting_upload.add(user_id)
            self.safe_send(
                message.chat.id,
                "📥 <b>Upload Old Database</b>\n\n"
                "Send the old database file as a <b>document</b> now.\n\n"
                "<b>Supported:</b>\n"
                "• .db\n"
                "• .sqlite\n"
                "• .sqlite3\n\n"
                "This importer will:\n"
                "• validate the file\n"
                "• create a backup of your current DB\n"
                "• merge old data into the current DB\n"
                "• preserve current users as safely as possible"
            )

        @self.bot.message_handler(
            func=lambda m: m.from_user and self.is_admin(m.from_user.id) and (m.from_user.id in self.awaiting_upload),
            content_types=["document"]
        )
        def receive_db_document(message: Any) -> None:
            user_id = message.from_user.id

            document = getattr(message, "document", None)
            if not document:
                self.safe_send(message.chat.id, "❌ Please send the database as a document.")
                return

            filename = (document.file_name or "").lower()
            if not (filename.endswith(".db") or filename.endswith(".sqlite") or filename.endswith(".sqlite3")):
                self.safe_send(message.chat.id, "❌ Invalid file type. Send a .db / .sqlite / .sqlite3 file.")
                return

            self.safe_send(message.chat.id, "⏳ Downloading and validating database file...")

            temp_path = None
            try:
                temp_path = self.download_document_to_temp(document.file_id, document.file_name or "uploaded.db")

                if not self.validate_sqlite_file(temp_path):
                    self.safe_send(message.chat.id, "❌ Invalid SQLite database file.")
                    return

                self.safe_send(message.chat.id, "🔄 Merging old database into current live DB...")
                summary = self.merge_database_file(temp_path)

                if self.log_admin_action:
                    try:
                        self.log_admin_action(
                            user_id,
                            "uploaddb",
                            f"Imported database file: {document.file_name or 'unknown'}"
                        )
                    except Exception:
                        pass

                self.safe_send(message.chat.id, self.format_summary(summary))
                self.awaiting_upload.discard(user_id)

            except Exception as e:
                self.safe_send(
                    message.chat.id,
                    f"❌ <b>Database import failed</b>\n\n"
                    f"<code>{str(e)}</code>"
                )
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                self.awaiting_upload.discard(user_id)
