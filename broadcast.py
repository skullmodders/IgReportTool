from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional

from telebot import types


class BroadcastSystem:
    def __init__(
        self,
        bot: Any,
        is_admin: Callable[[int], bool],
        get_all_users: Callable[[], List[Any]],
        safe_send: Callable[..., Any],
        log_admin_action: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.bot = bot
        self.is_admin = is_admin
        self.get_all_users = get_all_users
        self.safe_send = safe_send
        self.log_admin_action = log_admin_action
        self.states: Dict[int, Dict[str, Any]] = {}

    # ============================================================
    # State helpers
    # ============================================================

    def set_state(
        self,
        user_id: int,
        step: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.states[int(user_id)] = {
            "step": step,
            "data": data if data is not None else {},
        }

    def get_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.states.get(int(user_id))

    def clear_state(self, user_id: int) -> None:
        self.states.pop(int(user_id), None)

    # ============================================================
    # Safe wrappers
    # ============================================================

    def _send(
        self,
        chat_id: int,
        text: str,
        reply_markup: Any = None,
        parse_mode: str = "HTML",
    ) -> Any:
        """Unified safe send wrapper."""
        try:
            return self.bot.send_message(
                chat_id,
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            print(f"[BroadcastSystem] send error to {chat_id}: {exc}")
            return None

    def _answer(self, call: Any, text: str = "", show_alert: bool = False) -> None:
        """Safe answer to a callback query."""
        try:
            self.bot.answer_callback_query(
                call.id,
                text=text,
                show_alert=show_alert,
            )
        except Exception as exc:
            print(f"[BroadcastSystem] answer_callback error: {exc}")

    # ============================================================
    # UI helpers
    # ============================================================

    def main_menu(self) -> types.InlineKeyboardMarkup:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(
                "📝 Text Broadcast", callback_data="advbrod_type_text"
            ),
            types.InlineKeyboardButton(
                "🖼 Photo Broadcast", callback_data="advbrod_type_photo"
            ),
        )
        markup.add(
            types.InlineKeyboardButton(
                "🎬 Video Broadcast", callback_data="advbrod_type_video"
            ),
            types.InlineKeyboardButton(
                "📄 Document Broadcast", callback_data="advbrod_type_document"
            ),
        )
        markup.add(
            types.InlineKeyboardButton(
                "🎞 Animation Broadcast", callback_data="advbrod_type_animation"
            ),
            types.InlineKeyboardButton(
                "🎵 Audio Broadcast", callback_data="advbrod_type_audio"
            ),
        )
        markup.add(
            types.InlineKeyboardButton(
                "🎤 Voice Broadcast", callback_data="advbrod_type_voice"
            ),
            types.InlineKeyboardButton(
                "🙂 Sticker Broadcast", callback_data="advbrod_type_sticker"
            ),
        )
        markup.add(
            types.InlineKeyboardButton(
                "📤 Forward / Copy Existing", callback_data="advbrod_type_copy"
            )
        )
        markup.add(
            types.InlineKeyboardButton("❌ Cancel", callback_data="advbrod_cancel")
        )
        return markup

    def buttons_menu(self) -> types.InlineKeyboardMarkup:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(
                "➕ Add Buttons", callback_data="advbrod_buttons_yes"
            ),
            types.InlineKeyboardButton(
                "⏭ Skip Buttons", callback_data="advbrod_buttons_no"
            ),
        )
        markup.add(
            types.InlineKeyboardButton("❌ Cancel", callback_data="advbrod_cancel")
        )
        return markup

    def preview_menu(self) -> types.InlineKeyboardMarkup:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(
                "✅ Send Broadcast", callback_data="advbrod_send"
            ),
            types.InlineKeyboardButton(
                "✏️ Edit Buttons", callback_data="advbrod_edit_buttons"
            ),
        )
        markup.add(
            types.InlineKeyboardButton("🔁 Restart", callback_data="advbrod_restart"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="advbrod_cancel"),
        )
        return markup

    # ============================================================
    # Button parsing
    # ============================================================

    def parse_buttons(
        self, raw_text: str
    ) -> Optional[types.InlineKeyboardMarkup]:
        """
        Parse a JSON array of button rows.

        Format:
            [
              [{"text": "Label", "url": "https://..."}],
              [{"text": "CB",    "callback_data": "some_data"}]
            ]

        Returns None when raw_text is empty or "[]".
        Raises ValueError / json.JSONDecodeError on bad input.
        """
        raw_text = (raw_text or "").strip()
        if not raw_text or raw_text == "[]":
            return None

        parsed = json.loads(raw_text)  # raises json.JSONDecodeError on bad JSON

        if not isinstance(parsed, list):
            raise ValueError("Buttons JSON must be a list of rows.")

        markup = types.InlineKeyboardMarkup()
        for row in parsed:
            if not isinstance(row, list):
                raise ValueError("Each row must be a list of button objects.")
            btn_row: List[types.InlineKeyboardButton] = []
            for item in row:
                if not isinstance(item, dict):
                    raise ValueError("Each button must be a JSON object.")
                text = item.get("text", "").strip()
                url = item.get("url")
                callback_data = item.get("callback_data")
                if not text:
                    raise ValueError("Every button must have a 'text' field.")
                if url:
                    btn_row.append(
                        types.InlineKeyboardButton(text, url=url)
                    )
                elif callback_data:
                    btn_row.append(
                        types.InlineKeyboardButton(
                            text, callback_data=callback_data
                        )
                    )
                else:
                    raise ValueError(
                        "Every button must have either 'url' or 'callback_data'."
                    )
            if btn_row:
                markup.row(*btn_row)

        return markup

    # ============================================================
    # User collection
    # ============================================================

    def collect_target_users(self) -> List[int]:
        users = self.get_all_users() or []
        user_ids: List[int] = []
        for u in users:
            try:
                uid = int(u["user_id"] if isinstance(u, dict) else u["user_id"])
                user_ids.append(uid)
            except Exception:
                continue
        return user_ids

    # ============================================================
    # Preview helpers
    # ============================================================

    def build_preview_text(
        self, data: Dict[str, Any], total_users: int
    ) -> str:
        btype = data.get("broadcast_type", "unknown")
        body = data.get("text") or data.get("caption") or "(no text)"
        if len(body) > 800:
            body = body[:800] + "\n\n...truncated in preview..."

        has_buttons = bool((data.get("buttons_json") or "").strip())
        return (
            f"🚀 <b>Advanced Broadcast Preview</b>\n\n"
            f"<b>Type:</b> {btype}\n"
            f"<b>Total users:</b> {total_users}\n"
            f"<b>Buttons:</b> {'Yes' if has_buttons else 'No'}\n\n"
            f"<b>Preview text/caption:</b>\n{body}"
        )

    def send_preview(self, chat_id: int, data: Dict[str, Any]) -> None:
        total_users = len(self.collect_target_users())

        # Try to build buttons markup for the preview sample
        markup: Optional[types.InlineKeyboardMarkup] = None
        try:
            markup = self.parse_buttons(data.get("buttons_json", ""))
        except Exception:
            markup = None

        preview_text = self.build_preview_text(data, total_users)
        btype = data.get("broadcast_type")

        # Always send the preview info card first
        self._send(chat_id, preview_text, reply_markup=self.preview_menu())

        try:
            if btype == "text":
                self._send(chat_id, data.get("text", "(empty)"), reply_markup=markup)

            elif btype == "photo":
                self.bot.send_photo(
                    chat_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "video":
                self.bot.send_video(
                    chat_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "document":
                self.bot.send_document(
                    chat_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "animation":
                self.bot.send_animation(
                    chat_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "audio":
                self.bot.send_audio(
                    chat_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "voice":
                self.bot.send_voice(
                    chat_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "sticker":
                self.bot.send_sticker(chat_id, data["file_id"])

            elif btype == "copy":
                self.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=data["source_chat_id"],
                    message_id=data["source_message_id"],
                    reply_markup=markup,
                )

        except Exception as exc:
            self._send(
                chat_id,
                f"⚠️ Preview sample could not be shown:\n<code>{exc}</code>",
            )

    # ============================================================
    # Broadcast engine
    # ============================================================

    def send_to_one(self, user_id: int, data: Dict[str, Any]) -> bool:
        markup: Optional[types.InlineKeyboardMarkup] = None
        try:
            markup = self.parse_buttons(data.get("buttons_json", ""))
        except Exception:
            markup = None

        btype = data.get("broadcast_type")

        try:
            if btype == "text":
                self.bot.send_message(
                    user_id,
                    data.get("text", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                    disable_web_page_preview=False,
                )

            elif btype == "photo":
                self.bot.send_photo(
                    user_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "video":
                self.bot.send_video(
                    user_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "document":
                self.bot.send_document(
                    user_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "animation":
                self.bot.send_animation(
                    user_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "audio":
                self.bot.send_audio(
                    user_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "voice":
                self.bot.send_voice(
                    user_id,
                    data["file_id"],
                    caption=data.get("caption", ""),
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            elif btype == "sticker":
                self.bot.send_sticker(user_id, data["file_id"])

            elif btype == "copy":
                self.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=data["source_chat_id"],
                    message_id=data["source_message_id"],
                    reply_markup=markup,
                )

            else:
                return False

            return True

        except Exception as exc:
            print(f"[BroadcastSystem] failed to send to {user_id}: {exc}")
            return False

    def execute_broadcast(
        self, admin_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        user_ids = self.collect_target_users()
        sent = 0
        failed = 0
        start_time = time.time()

        for uid in user_ids:
            if self.send_to_one(uid, data):
                sent += 1
            else:
                failed += 1
            time.sleep(0.03)

        duration = round(time.time() - start_time, 2)

        if self.log_admin_action:
            try:
                self.log_admin_action(
                    admin_id,
                    "advanced_broadcast",
                    (
                        f"type={data.get('broadcast_type')} "
                        f"sent={sent} failed={failed} duration={duration}s"
                    ),
                )
            except Exception:
                pass

        return {
            "total": len(user_ids),
            "sent": sent,
            "failed": failed,
            "duration": duration,
        }

    # ============================================================
    # Handler registration
    # ============================================================

    def register_handlers(self) -> None:

        # ── /advbrod command ──────────────────────────────────────
        @self.bot.message_handler(commands=["advbrod"])
        def open_advanced_broadcast(message: Any) -> None:
            user_id = message.from_user.id
            if not self.is_admin(user_id):
                self._send(message.chat.id, "❌ Access denied.")
                return

            self.clear_state(user_id)
            self._send(
                message.chat.id,
                (
                    "🚀 <b>Advanced Broadcast Panel</b>\n\n"
                    "Choose the broadcast type.\n\n"
                    "<b>Supported:</b>\n"
                    "• text\n• photo\n• video\n• document\n"
                    "• animation\n• audio\n• voice\n• sticker\n"
                    "• forward / copy existing message\n\n"
                    "HTML formatting and inline buttons are supported."
                ),
                reply_markup=self.main_menu(),
            )

        # ── All advbrod_ callback queries ─────────────────────────
        @self.bot.callback_query_handler(
            func=lambda call: isinstance(call.data, str)
            and call.data.startswith("advbrod_")
        )
        def advbrod_callbacks(call: Any) -> None:
            user_id = call.from_user.id

            if not self.is_admin(user_id):
                self._answer(call, "Access denied.", show_alert=True)
                return

            self._answer(call)  # acknowledge – no spinner left on button

            cdata = call.data
            chat_id = call.message.chat.id

            # ── Cancel ───────────────────────────────────────────
            if cdata == "advbrod_cancel":
                self.clear_state(user_id)
                self._send(chat_id, "❌ Broadcast cancelled.")
                return

            # ── Restart ──────────────────────────────────────────
            if cdata == "advbrod_restart":
                self.clear_state(user_id)
                self._send(
                    chat_id,
                    "🔁 Restarted. Choose the broadcast type again.",
                    reply_markup=self.main_menu(),
                )
                return

            # ── Choose broadcast type ────────────────────────────
            if cdata.startswith("advbrod_type_"):
                btype = cdata[len("advbrod_type_"):]
                self.set_state(
                    user_id,
                    "await_primary_content",
                    {"broadcast_type": btype},
                )

                prompts: Dict[str, str] = {
                    "text": (
                        "📝 <b>Send the broadcast text now.</b>\n\n"
                        "HTML formatting is supported.\n\n"
                        "Example:\n<code>&lt;b&gt;Big Update!&lt;/b&gt;</code>"
                    ),
                    "photo": "🖼 <b>Send the photo now.</b>\n\nCaption is optional.",
                    "video": "🎬 <b>Send the video now.</b>\n\nCaption is optional.",
                    "document": "📄 <b>Send the document now.</b>\n\nCaption is optional.",
                    "animation": "🎞 <b>Send the GIF / animation now.</b>\n\nCaption is optional.",
                    "audio": "🎵 <b>Send the audio file now.</b>\n\nCaption is optional.",
                    "voice": "🎤 <b>Send the voice message now.</b>\n\nCaption is optional.",
                    "sticker": "🙂 <b>Send the sticker now.</b>",
                    "copy": (
                        "📤 <b>Forward the source message to me now.</b>\n\n"
                        "I will copy it to all users exactly as-is."
                    ),
                }
                self._send(chat_id, prompts.get(btype, "Send content now."))
                return

            # ── Add buttons ──────────────────────────────────────
            if cdata == "advbrod_buttons_yes":
                state = self.get_state(user_id)
                if not state:
                    self._send(chat_id, "❌ No active broadcast. Use /advbrod.")
                    return
                # Update step in place and persist
                state["step"] = "await_buttons_json"
                self.states[user_id] = state
                self._send(
                    chat_id,
                    (
                        "➕ <b>Send buttons JSON now.</b>\n\n"
                        "Example:\n"
                        "<code>[\n"
                        '  [{"text":"Join","url":"https://t.me/example"}],\n'
                        '  [{"text":"Bot","url":"https://t.me/yourbot"}]\n'
                        "]</code>"
                    ),
                )
                return

            # ── Skip buttons ─────────────────────────────────────
            if cdata == "advbrod_buttons_no":
                state = self.get_state(user_id)
                if not state:
                    self._send(chat_id, "❌ No active broadcast. Use /advbrod.")
                    return
                state["data"]["buttons_json"] = ""
                state["step"] = "ready_preview"
                self.states[user_id] = state
                self.send_preview(chat_id, state["data"])
                return

            # ── Edit buttons ─────────────────────────────────────
            if cdata == "advbrod_edit_buttons":
                state = self.get_state(user_id)
                if not state:
                    self._send(chat_id, "❌ No active broadcast. Use /advbrod.")
                    return
                state["step"] = "await_buttons_json"
                self.states[user_id] = state
                self._send(
                    chat_id,
                    (
                        "✏️ <b>Send new buttons JSON.</b>\n\n"
                        "Send <code>[]</code> to remove all buttons."
                    ),
                )
                return

            # ── Confirm send ─────────────────────────────────────
            if cdata == "advbrod_send":
                state = self.get_state(user_id)
                if not state:
                    self._send(chat_id, "❌ No active broadcast. Use /advbrod.")
                    return

                self._send(chat_id, "🚀 Sending broadcast… please wait.")
                result = self.execute_broadcast(user_id, state["data"])
                self.clear_state(user_id)

                self._send(
                    chat_id,
                    (
                        f"✅ <b>Broadcast Finished</b>\n\n"
                        f"• Total users: <b>{result['total']}</b>\n"
                        f"• Sent:        <b>{result['sent']}</b>\n"
                        f"• Failed:      <b>{result['failed']}</b>\n"
                        f"• Duration:    <b>{result['duration']}s</b>"
                    ),
                )
                return

        # ── Incoming content while a state is active ──────────────
        @self.bot.message_handler(
            func=lambda m: (
                m.from_user is not None
                and self.is_admin(m.from_user.id)
                and self.get_state(m.from_user.id) is not None
            ),
            content_types=[
                "text", "photo", "video", "document",
                "animation", "audio", "voice", "sticker",
            ],
        )
        def advbrod_state_handler(message: Any) -> None:
            user_id = message.from_user.id
            state = self.get_state(user_id)
            if not state:
                return

            step = state["step"]
            data = state["data"]
            chat_id = message.chat.id
            btype = data.get("broadcast_type")

            # ── Waiting for primary media / text ──────────────────
            if step == "await_primary_content":
                self._handle_primary_content(
                    user_id, chat_id, message, btype, data
                )
                return

            # ── Waiting for buttons JSON ──────────────────────────
            if step == "await_buttons_json":
                if message.content_type != "text":
                    self._send(chat_id, "❌ Please send the buttons as text JSON.")
                    return

                raw = (message.text or "").strip()
                try:
                    self.parse_buttons(raw)          # validate only
                    data["buttons_json"] = "" if raw == "[]" else raw
                    state["step"] = "ready_preview"
                    self.states[user_id] = state
                    self._send(chat_id, "✅ Buttons saved.")
                    self.send_preview(chat_id, data)
                except Exception as exc:
                    self._send(
                        chat_id,
                        (
                            f"❌ Invalid buttons JSON.\n\n"
                            f"<b>Error:</b> <code>{exc}</code>\n\n"
                            "Please try again."
                        ),
                    )
                return

    # ============================================================
    # Primary-content dispatcher (keeps register_handlers clean)
    # ============================================================

    def _handle_primary_content(
        self,
        user_id: int,
        chat_id: int,
        message: Any,
        btype: Optional[str],
        data: Dict[str, Any],
    ) -> None:
        """Validate & store the primary media, then ask about buttons."""

        ct = message.content_type

        # ── text ─────────────────────────────────────────────────
        if btype == "text":
            if ct != "text":
                self._send(chat_id, "❌ Please send plain text.")
                return
            data["text"] = message.text or ""

        # ── photo ────────────────────────────────────────────────
        elif btype == "photo":
            if ct != "photo":
                self._send(chat_id, "❌ Please send a photo.")
                return
            data["file_id"] = message.photo[-1].file_id
            data["caption"] = message.caption or ""

        # ── video ────────────────────────────────────────────────
        elif btype == "video":
            if ct != "video":
                self._send(chat_id, "❌ Please send a video.")
                return
            data["file_id"] = message.video.file_id
            data["caption"] = message.caption or ""

        # ── document ─────────────────────────────────────────────
        elif btype == "document":
            if ct != "document":
                self._send(chat_id, "❌ Please send a document.")
                return
            data["file_id"] = message.document.file_id
            data["caption"] = message.caption or ""

        # ── animation ────────────────────────────────────────────
        elif btype == "animation":
            if ct != "animation":
                self._send(chat_id, "❌ Please send a GIF / animation.")
                return
            data["file_id"] = message.animation.file_id
            data["caption"] = message.caption or ""

        # ── audio ────────────────────────────────────────────────
        elif btype == "audio":
            if ct != "audio":
                self._send(chat_id, "❌ Please send an audio file.")
                return
            data["file_id"] = message.audio.file_id
            data["caption"] = message.caption or ""

        # ── voice ────────────────────────────────────────────────
        elif btype == "voice":
            if ct != "voice":
                self._send(chat_id, "❌ Please send a voice message.")
                return
            data["file_id"] = message.voice.file_id
            data["caption"] = message.caption or ""

        # ── sticker ──────────────────────────────────────────────
        elif btype == "sticker":
            if ct != "sticker":
                self._send(chat_id, "❌ Please send a sticker.")
                return
            data["file_id"] = message.sticker.file_id

        # ── copy / forward ────────────────────────────────────────
        elif btype == "copy":
            data["source_chat_id"] = message.chat.id
            data["source_message_id"] = message.message_id

        else:
            self._send(chat_id, "❌ Unknown broadcast type. Use /advbrod to restart.")
            self.clear_state(user_id)
            return

        # Persist updated data and advance step
        self.set_state(user_id, "await_buttons_choice", data)
        label = btype.capitalize()
        self._send(
            chat_id,
            f"✅ {label} saved.\n\nDo you want to add inline buttons?",
            reply_markup=self.buttons_menu(),
        )
