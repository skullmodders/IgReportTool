from __future__ import annotations

from typing import Any, Callable


class AdminHelpSystem:
    def __init__(
        self,
        bot: Any,
        is_admin: Callable[[int], bool],
        safe_send: Callable[..., Any],
        pe: Callable[[str], str],
    ) -> None:
        self.bot = bot
        self.is_admin = is_admin
        self.safe_send = safe_send
        self.pe = pe

    def build_help_text(self) -> str:
        return (
            f"{self.pe('admin')} <b>Admin Help</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"

            f"{self.pe('database')} <b>Database</b>\n"
            f"{self.pe('arrow')} /getdb — Download database\n"
            f"{self.pe('arrow')} /uploaddb — Upload & merge database\n\n"

            f"{self.pe('megaphone')} <b>Broadcast</b>\n"
            f"{self.pe('arrow')} /advbrod — Broadcast panel\n\n"

            f"{self.pe('shield')} <b>Anti-Cheat</b>\n"
            f"{self.pe('arrow')} /anticheat — Anti-cheat panel\n\n"

            f"{self.pe('calendar')} <b>Withdraw Limit</b>\n"
            f"{self.pe('arrow')} /withdrawlimit — Show limit\n"
            f"{self.pe('arrow')} /setwithdrawlimit — Set limit\n\n"

            f"{self.pe('gear')} <b>Panel</b>\n"
            f"{self.pe('arrow')} Use <b>👑 Admin Panel</b> button\n\n"

            f"{self.pe('sparkle')} Tap any command above to use it."
        )

    def register_handlers(self) -> None:
        @self.bot.message_handler(commands=["adminhelp"])
        def admin_help_command(message: Any) -> None:
            if not self.is_admin(message.from_user.id):
                self.safe_send(message.chat.id, "❌ Access denied")
                return

            self.safe_send(message.chat.id, self.build_help_text())
