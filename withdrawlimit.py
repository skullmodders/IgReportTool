from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, Dict, Tuple


class WithdrawLimitSystem:
    def __init__(
        self,
        db_execute: Callable[..., Any],
        get_setting: Callable[[str], Any],
        set_setting: Callable[[str, Any], None],
        safe_send: Callable[..., Any],
        pe: Callable[[str], str],
        count_statuses: tuple[str, ...] = ("pending", "approved"),
    ) -> None:
        self.db_execute = db_execute
        self.get_setting = get_setting
        self.set_setting = set_setting
        self.safe_send = safe_send
        self.pe = pe
        self.count_statuses = count_statuses

    def ensure_settings(self) -> None:
        existing = self.get_setting("daily_withdraw_limit")
        if existing is None:
            self.set_setting("daily_withdraw_limit", 2)

    def get_daily_limit(self) -> int:
        raw = self.get_setting("daily_withdraw_limit")
        try:
            value = int(raw)
            if value < 1:
                return 2
            return value
        except Exception:
            return 2

    def set_daily_limit(self, value: int) -> int:
        if value < 1:
            value = 1
        self.set_setting("daily_withdraw_limit", value)
        return value

    def get_today_withdraw_count(self, user_id: int) -> int:
        today = datetime.now().strftime("%Y-%m-%d")

        placeholders = ",".join(["?"] * len(self.count_statuses))
        query = (
            f"SELECT COUNT(*) as cnt "
            f"FROM withdrawals "
            f"WHERE user_id=? AND date(created_at)=? AND status IN ({placeholders})"
        )
        params = (user_id, today, *self.count_statuses)

        row = self.db_execute(query, params, fetchone=True)
        return int(row["cnt"] if row else 0)

    def get_today_summary(self, user_id: int) -> Dict[str, int]:
        used_today = self.get_today_withdraw_count(user_id)
        daily_limit = self.get_daily_limit()
        remaining = max(0, daily_limit - used_today)

        return {
            "used_today": used_today,
            "daily_limit": daily_limit,
            "remaining": remaining,
        }

    def can_user_withdraw(self, user_id: int) -> Tuple[bool, str]:
        summary = self.get_today_summary(user_id)
        used_today = summary["used_today"]
        daily_limit = summary["daily_limit"]

        if used_today >= daily_limit:
            return (
                False,
                f"{self.pe('warning')} <b>Daily Withdrawal Limit Reached!</b>\n\n"
                f"{self.pe('info')} You can only make <b>{daily_limit} withdrawals per day</b>.\n"
                f"{self.pe('calendar')} Today's Withdrawals: <b>{used_today}/{daily_limit}</b>\n\n"
                f"{self.pe('hourglass')} Please try again tomorrow."
            )

        return True, ""

    def check_and_send_limit_message(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        summary = self.get_today_summary(user_id)
        used_today = summary["used_today"]
        daily_limit = summary["daily_limit"]

        if used_today >= daily_limit:
            self.safe_send(
                chat_id,
                f"{self.pe('warning')} <b>Daily Withdrawal Limit Reached!</b>\n\n"
                f"{self.pe('info')} You can only make <b>{daily_limit} withdrawals per day</b>.\n"
                f"{self.pe('calendar')} Today's Withdrawals: <b>{used_today}/{daily_limit}</b>\n\n"
                f"{self.pe('hourglass')} Please try again tomorrow."
            )
            return {
                "allowed": False,
                "used_today": used_today,
                "daily_limit": daily_limit,
                "remaining": 0,
            }

        return {
            "allowed": True,
            "used_today": used_today,
            "daily_limit": daily_limit,
            "remaining": max(0, daily_limit - used_today),
        }

    def build_withdraw_limit_line(self, user_id: int) -> str:
        summary = self.get_today_summary(user_id)
        return (
            f"{self.pe('calendar')} <b>Daily Limit:</b> {summary['daily_limit']} withdrawals per day\n"
            f"{self.pe('calendar')} <b>Today's Withdrawals:</b> {summary['used_today']}/{summary['daily_limit']}\n"
        )

    def build_limit_status_block(self, user_id: int) -> str:
        summary = self.get_today_summary(user_id)
        return (
            f"{self.pe('calendar')} <b>Withdrawal Limit Status</b>\n\n"
            f"{self.pe('info')} Daily Limit: <b>{summary['daily_limit']}</b>\n"
            f"{self.pe('arrow')} Used Today: <b>{summary['used_today']}</b>\n"
            f"{self.pe('check')} Remaining Today: <b>{summary['remaining']}</b>"
        )

    def handle_show_limit_command(self, message: Any, is_admin_func: Callable[[int], bool]) -> bool:
        if not is_admin_func(message.from_user.id):
            return False

        limit = self.get_daily_limit()
        self.safe_send(
            message.chat.id,
            f"{self.pe('calendar')} <b>Current Daily Withdrawal Limit</b>\n\n"
            f"{self.pe('info')} Users can withdraw <b>{limit} times per day</b>."
        )
        return True

    def handle_set_limit_command(self, message: Any, is_admin_func: Callable[[int], bool]) -> bool:
        if not is_admin_func(message.from_user.id):
            return False

        parts = (message.text or "").split()
        if len(parts) != 2 or not parts[1].isdigit():
            self.safe_send(
                message.chat.id,
                f"{self.pe('warning')} <b>Invalid Usage</b>\n\n"
                f"{self.pe('info')} Use: <code>/setwithdrawlimit 2</code>"
            )
            return True

        new_limit = int(parts[1])
        saved = self.set_daily_limit(new_limit)

        self.safe_send(
            message.chat.id,
            f"{self.pe('check')} <b>Daily Withdrawal Limit Updated</b>\n\n"
            f"{self.pe('calendar')} New Limit: <b>{saved} withdrawals per day</b>"
        )
        return True
