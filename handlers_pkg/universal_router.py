from core import *
from .basic_user import send_db, start_handler, balance_handler, refer_handler
from .user_withdraw_gift import withdraw_handler, gift_handler
from .user_tasks import tasks_handler
from .admin_main import (
    admin_cmd, admin_dashboard, admin_all_users, admin_withdrawals, admin_settings,
    admin_broadcast, admin_gift_manager, admin_redeem_manager
)
from .admin_management import admin_manager
from .admin_task_manager import admin_task_manager
from .db_manager import (
    admin_db_manager, handle_db_add_user, handle_db_edit_user, handle_db_add_withdrawal,
    handle_db_edit_withdrawal, handle_db_add_gift, handle_db_add_task, handle_db_raw_query,
    handle_db_search_user, handle_db_delete_user, handle_db_delete_withdrawal,
    handle_db_edit_task, handle_db_add_task_completion
)
from .admin_withdrawals import show_user_info
from .admin_task_ops import process_task_rejection

# ======================== ADMIN PANEL BUTTON ========================
@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel" and is_admin(m.from_user.id))
def open_admin_panel_btn(message):
    safe_send(
        message.chat.id,
        f"{pe('crown')} <b>Admin Panel</b> {pe('gear')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Welcome, Admin! Use the keyboard below.",
        reply_markup=get_admin_keyboard()
    )

# ======================== TEXT/PHOTO UNIVERSAL HANDLER ========================
@bot.message_handler(
    content_types=["text", "photo", "document"],
    func=lambda m: True
)
def universal_handler(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        mark_user_active(user_id)
    state = get_state(user_id)
    text = message.text.strip() if message.text else ""

    # ---- Allow commands before universal handling ----
    if message.content_type == "text" and text.startswith("/"):
        cmd = text.split()[0].split("@")[0].lower()

        if cmd in ["/admin", "/panel"]:
            admin_cmd(message)
            return
        if cmd == "/start":
            start_handler(message)
            return
        if cmd == "/getdb":
            send_db(message)
            return
        return

       # ---- Keyboard buttons ----
    if message.content_type == "text":
        if text == "💰 Balance":
            balance_handler(message)
            return
        if text == "👥 Refer":
            refer_handler(message)
            return
        if text == "🏧 Withdraw":
            withdraw_handler(message)
            return
        if text == "🎁 Gift":
            gift_handler(message)
            return
        if text == "📋 Tasks":
            tasks_handler(message)
            return
        if text == "👑 Admin Panel" and is_admin(user_id):
            open_admin_panel_btn(message)
            return
        if text == "📊 Dashboard" and is_admin(user_id):
            admin_dashboard(message)
            return
        if text == "👥 All Users" and is_admin(user_id):
            admin_all_users(message)
            return
        if text == "💳 Withdrawals" and is_admin(user_id):
            admin_withdrawals(message)
            return
        if text == "⚙️ Settings" and is_admin(user_id):
            admin_settings(message)
            return
        if text == "📢 Broadcast" and is_admin(user_id):
            admin_broadcast(message)
            return
        if text == "🎁 Gift Manager" and is_admin(user_id):
            admin_gift_manager(message)
            return
        if text == "🎟 Redeem Codes" and is_admin(user_id):
            admin_redeem_manager(message)
            return
        if text == "📋 Task Manager" and is_admin(user_id):
            admin_task_manager(message)
            return
        if text == "🗄 DB Manager" and is_admin(user_id):
            admin_db_manager(message)
            return
        if text == "👮 Admin Manager" and is_admin(user_id):
            admin_manager(message)
            return
        if text == "🔙 User Panel" and is_admin(user_id):
            back_user_panel(message)
            return
        if text.startswith("/"):
            return

    if not state:
        return

    # ---- Task proof submission ----
    if state == "task_submit_proof":
        data = get_state_data(user_id)
        task_id = data.get("task_id")
        clear_state(user_id)
        if not task_id:
            return
        task = get_task(task_id)
        if not task or task["status"] != "active":
            safe_send(message.chat.id, f"{pe('cross')} Task is no longer available!")
            return
        existing_comp = get_task_completion(task_id, user_id)
        if existing_comp:
            safe_send(message.chat.id, f"{pe('check')} Task already completed!")
            return
        existing_sub = get_task_submission(task_id, user_id)
        if existing_sub and existing_sub["status"] == "pending":
            safe_send(message.chat.id, f"{pe('pending2')} Already submitted! Wait for review.")
            return
        proof_text = text or ""
        proof_file_id = ""
        if message.content_type == "photo":
            proof_file_id = message.photo[-1].file_id
            proof_text = message.caption or "Photo proof"
        elif message.content_type == "document":
            proof_file_id = message.document.file_id
            proof_text = message.caption or "Document proof"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sub_id = db_lastrowid(
            "INSERT INTO task_submissions "
            "(task_id, user_id, status, submitted_at, proof_text, proof_file_id) "
            "VALUES (?,?,?,?,?,?)",
            (task_id, user_id, "pending", now, proof_text, proof_file_id)
        )
        user = get_user(user_id)
        safe_send(
            message.chat.id,
            f"{pe('check')} <b>Proof Submitted!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('task')} <b>Task:</b> {task['title']}\n"
            f"{pe('coins')} <b>Reward:</b> ₹{task['reward']}\n"
            f"{pe('pending2')} <b>Status:</b> Under Review ⏳\n\n"
            f"{pe('bell')} You'll be notified when reviewed!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            admin_markup = types.InlineKeyboardMarkup(row_width=2)
            admin_markup.add(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"tsub_approve|{sub_id}"),
                types.InlineKeyboardButton("❌ Reject", callback_data=f"tsub_reject|{sub_id}"),
            )
            admin_markup.add(types.InlineKeyboardButton("👤 User Info", callback_data=f"uinfo|{user_id}"))
            admin_text = (
                f"{pe('siren')} <b>New Task Submission!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{pe('task')} <b>Task:</b> {task['title']} (#{task['id']})\n"
                f"{pe('disguise')} <b>User:</b> {user['first_name'] if user else 'Unknown'} "
                f"(<code>{user_id}</code>)\n"
                f"{pe('coins')} <b>Reward:</b> ₹{task['reward']}\n"
                f"{pe('info')} <b>Proof:</b> {proof_text[:200]}\n"
                f"{pe('calendar')} <b>Time:</b> {now}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            if proof_file_id:
                try:
                    bot.send_photo(ADMIN_ID, proof_file_id, caption=admin_text, parse_mode="HTML", reply_markup=admin_markup)
                except:
                    bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML", reply_markup=admin_markup)
            else:
                bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML", reply_markup=admin_markup)
        except Exception as e:
            print(f"Admin task notify error: {e}")
        return

    if message.content_type != "text":
        return

    # --- Enter UPI ---
    if state == "enter_upi":
        if "@" not in text or len(text) < 5:
            safe_send(message.chat.id, f"{pe('cross')} <b>Invalid UPI ID!</b>\nMust contain '@'\nExample: <code>name@paytm</code>")
            return
        update_user(user_id, upi_id=text)
        clear_state(user_id)
        set_state(user_id, "enter_amount", {"upi_id": text})
        user = get_user(user_id)
        min_w = get_setting("min_withdraw")
        max_w = get_setting("max_withdraw_per_day")
        safe_send(
            message.chat.id,
            f"{pe('check')} <b>UPI Saved!</b> <code>{text}</code>\n\n"
            f"{pe('money')} Balance: ₹{user['balance']:.2f}\n"
            f"{pe('down_arrow')} Min: ₹{min_w} | Max: ₹{max_w}\n\n"
            f"{pe('pencil')} Enter withdrawal amount:"
        )
        return

    # --- Enter Amount ---
    if state == "enter_amount":
        try:
            amount = float(text)
        except ValueError:
            safe_send(message.chat.id, f"{pe('cross')} Enter a valid number!")
            return
        user = get_user(user_id)
        min_w = get_setting("min_withdraw")
        max_w = get_setting("max_withdraw_per_day")
        if amount < min_w:
            safe_send(message.chat.id, f"{pe('cross')} Minimum is ₹{min_w}")
            return
        if amount > max_w:
            safe_send(message.chat.id, f"{pe('cross')} Maximum is ₹{max_w}")
            return
        tax = get_withdrawal_tax_breakdown(user, amount)
        if tax["total_debit"] > user["balance"]:
            safe_send(message.chat.id, f"{pe('cross')} Insufficient balance! Need ₹{tax['total_debit']:.2f} including tax/GST. You have ₹{user['balance']:.2f}")
            return
        state_data = get_state_data(user_id)
        upi_id = state_data.get("upi_id", user["upi_id"])
        clear_state(user_id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Confirm", callback_data=f"cwith|{amount}|{upi_id}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")
        )
        safe_send(
            message.chat.id,
            f"{pe('warning')} <b>Confirm Withdrawal</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('fly_money')} <b>Amount:</b> ₹{amount}\n"
            f"{pe('link')} <b>UPI:</b> <code>{upi_id}</code>\n\n"
            f"{pe('info')} Tap Confirm to proceed.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━",
            reply_markup=markup
        )
        return

    # --- Gift Code Redeem ---
    if state == "enter_gift_code":
        code = text.upper()
        clear_state(user_id)
        min_refs_redeem = int(get_setting("referral_min_activity_for_redeem") or 0)
        if int(get_user(user_id)["referral_count"] or 0) < min_refs_redeem:
            safe_send(message.chat.id, f"{pe('cross')} Need at least {min_refs_redeem} referrals to claim redeem code.")
            return
        gift = db_execute("SELECT * FROM gift_codes WHERE code=? AND is_active=1", (code,), fetchone=True)
        if not gift:
            safe_send(message.chat.id, f"{pe('cross')} <b>Invalid or Expired Code!</b>\nCode: <code>{code}</code>")
            return
        existing = db_execute("SELECT * FROM gift_claims WHERE code=? AND user_id=?", (code, user_id), fetchone=True)
        if existing:
            safe_send(message.chat.id, f"{pe('cross')} <b>Already Redeemed!</b>\nYou already used code <code>{code}</code>.")
            return
        if gift["total_claims"] >= gift["max_claims"]:
            db_execute("UPDATE gift_codes SET is_active=0 WHERE code=?", (code,))
            safe_send(message.chat.id, f"{pe('cross')} <b>Code Exhausted!</b>\nThis code has reached max redemptions.")
            return
        amount = gift["amount"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = get_user(user_id)
        update_user(user_id, balance=user["balance"] + amount, total_earned=user["total_earned"] + amount)
        db_execute("UPDATE gift_codes SET total_claims=total_claims+1, claimed_by=?, claimed_at=? WHERE code=?", (user_id, now, code))
        db_execute("INSERT INTO gift_claims (code, user_id, claimed_at) VALUES (?,?,?)", (code, user_id, now))
        if gift["total_claims"] + 1 >= gift["max_claims"]:
            db_execute("UPDATE gift_codes SET is_active=0 WHERE code=?", (code,))
        safe_send(
            message.chat.id,
            f"{pe('party')} <b>Code Redeemed!</b> {pe('check')}\n\n"
            f"{pe('money')} You got <b>₹{amount}</b>!\n"
            f"{pe('fly_money')} New Balance: <b>₹{user['balance'] + amount:.2f}</b>\n\n"
            f"{pe('fire')} Keep earning!"
        )
        return

    # --- Gift Amount ---
    if state == "enter_gift_amount":
        try:
            amount = float(text)
        except ValueError:
            safe_send(message.chat.id, f"{pe('cross')} Enter a valid number!")
            return
        user = get_user(user_id)
        min_gift = get_setting("min_gift_amount")
        max_gift = get_setting("max_gift_create")
        if amount < min_gift:
            safe_send(message.chat.id, f"{pe('cross')} Minimum gift is ₹{min_gift}")
            return
        if amount > max_gift:
            safe_send(message.chat.id, f"{pe('cross')} Maximum gift is ₹{max_gift}")
            return
        if amount > user["balance"]:
            safe_send(message.chat.id, f"{pe('cross')} Insufficient balance!")
            return
        clear_state(user_id)
        code = generate_code()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_user(user_id, balance=user["balance"] - amount)
        db_execute(
            "INSERT INTO gift_codes (code, amount, created_by, created_at, gift_type, max_claims) VALUES (?,?,?,?,?,?)",
            (code, amount, user_id, now, "user", 1)
        )
        safe_send(
            message.chat.id,
            f"{pe('party')} <b>Gift Code Created!</b> {pe('sparkle')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('star')} <b>Code:</b> <code>{code}</code>\n"
            f"{pe('money')} <b>Amount:</b> ₹{amount}\n\n"
            f"{pe('arrow')} Share this with anyone!\n"
            f"{pe('info')} Redeem via Gift → Redeem Code\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        return

    # =================== ADMIN STATES ===================
    if not is_admin(user_id):
        return

    if state == "admin_broadcast":
        clear_state(user_id)
        safe_send(message.chat.id, f"{pe('megaphone')} <b>Broadcasting...</b>")
        threading.Thread(target=do_broadcast, args=(text, message.chat.id), daemon=True).start()
        return

    if state == "admin_add_balance":
        try:
            parts = text.split()
            tid = int(parts[0])
            amt = float(parts[1])
        except:
            safe_send(message.chat.id, f"{pe('cross')} Format: <code>USER_ID AMOUNT</code>")
            return
        clear_state(user_id)
        target = get_user(tid)
        if not target:
            safe_send(message.chat.id, f"{pe('cross')} User not found!")
            return
        update_user(tid, balance=target["balance"] + amt, total_earned=target["total_earned"] + abs(amt))
        log_admin_action(user_id, "add_balance", f"Added ₹{amt} to {tid}")
        safe_send(message.chat.id, f"{pe('check')} Added ₹{amt} to user <code>{tid}</code>\nNew balance: ₹{target['balance'] + amt:.2f}")
        try:
            safe_send(tid, f"{pe('party')} <b>₹{amt} Added!</b>\n{pe('fly_money')} New Balance: ₹{target['balance'] + amt:.2f}")
        except:
            pass
        return

    if state == "admin_deduct_balance":
        try:
            parts = text.split()
            tid = int(parts[0])
            amt = float(parts[1])
        except:
            safe_send(message.chat.id, f"{pe('cross')} Format: <code>USER_ID AMOUNT</code>")
            return
        clear_state(user_id)
        target = get_user(tid)
        if not target:
            safe_send(message.chat.id, f"{pe('cross')} User not found!")
            return
        new_bal = max(0.0, target["balance"] - amt)
        update_user(tid, balance=new_bal)
        log_admin_action(user_id, "deduct_balance", f"Deducted ₹{amt} from {tid}")
        safe_send(message.chat.id, f"{pe('check')} Deducted ₹{amt} from <code>{tid}</code>\nNew balance: ₹{new_bal:.2f}")
        return

    if state == "admin_ban_user":
        try:
            tid = int(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid User ID!")
            return
        clear_state(user_id)
        if not get_user(tid):
            safe_send(message.chat.id, f"{pe('cross')} User not found!")
            return
        update_user(tid, banned=1)
        log_admin_action(user_id, "ban_user", f"Banned user {tid}")
        safe_send(message.chat.id, f"{pe('check')} User <code>{tid}</code> banned!")
        return

    if state == "admin_unban_user":
        try:
            tid = int(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid User ID!")
            return
        clear_state(user_id)
        if not get_user(tid):
            safe_send(message.chat.id, f"{pe('cross')} User not found!")
            return
        update_user(tid, banned=0)
        log_admin_action(user_id, "unban_user", f"Unbanned user {tid}")
        safe_send(message.chat.id, f"{pe('check')} User <code>{tid}</code> unbanned!")
        return

    if state == "admin_user_info":
        try:
            tid = int(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid User ID!")
            return
        clear_state(user_id)
        show_user_info(message.chat.id, tid)
        return

    if state == "admin_create_gift":
        try:
            parts = text.split()
            amt = float(parts[0])
            mc = int(parts[1]) if len(parts) > 1 else 1
            gc = parts[2].upper() if len(parts) > 2 else generate_code(10)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Format: <code>AMOUNT MAX_CLAIMS [CODE]</code>")
            return
        clear_state(user_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_execute(
            "INSERT OR REPLACE INTO gift_codes (code, amount, created_by, created_at, gift_type, max_claims) VALUES (?,?,?,?,?,?)",
            (gc, amt, user_id, now, "admin", mc)
        )
        log_admin_action(user_id, "create_gift", f"Created gift code {gc} ₹{amt} x{mc}")
        safe_send(
            message.chat.id,
            f"{pe('check')} <b>Gift Code Created!</b>\n\n"
            f"{pe('star')} Code: <code>{gc}</code>\n"
            f"{pe('money')} Amount: ₹{amt}\n"
            f"{pe('thumbs_up')} Max Claims: {mc}"
        )
        return

    if state == "admin_add_redeem_code":
        try:
            parts = [p.strip() for p in text.split("|")]
            platform = parts[0]
            amount = float(parts[1])
            code = parts[2]
            note = parts[3] if len(parts) > 3 else ""
        except Exception:
            safe_send(message.chat.id, f"{pe('cross')} Format: <code>PLATFORM | AMOUNT | CODE | NOTE(optional)</code>")
            return
        if amount < get_redeem_min_withdraw() or int(amount) % get_redeem_multiple_of() != 0:
            safe_send(message.chat.id, f"{pe('cross')} Amount must be at least ₹{get_redeem_min_withdraw():.0f} and in multiples of ₹{get_redeem_multiple_of():.0f}.")
            return
        clear_state(user_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_execute(
            "INSERT INTO redeem_codes (platform, code, amount, gst_cut, is_active, created_by, created_at, note) VALUES (?,?,?,?,?,?,?,?)",
            (platform, code, amount, get_redeem_gst_cut(), 1, user_id, now, note)
        )
        log_admin_action(user_id, "add_redeem_code", f"{platform} ₹{amount} code added")
        safe_send(
            message.chat.id,
            f"{pe('check')} Redeem code added!\n"
            f"Brand: <b>{platform}</b>\n"
            f"Amount: ₹{amount:.0f}\n"
            f"Code: <code>{code}</code>"
        )
        return

    if state == "admin_edit_redeem_code":
        try:
            parts = [p.strip() for p in text.split("|", 2)]
            code_id = int(parts[0])
            field = parts[1].lower()
            value = parts[2]
        except Exception:
            safe_send(message.chat.id, f"{pe('cross')} Format: <code>ID | FIELD | VALUE</code>")
            return
        allowed = {"platform", "amount", "code", "note", "is_active", "gst_cut"}
        if field not in allowed:
            safe_send(message.chat.id, f"{pe('cross')} Allowed fields: {', '.join(sorted(allowed))}")
            return
        row = get_redeem_code_by_id(code_id)
        if not row:
            safe_send(message.chat.id, f"{pe('cross')} Redeem code ID not found!")
            return
        if field in {"amount", "gst_cut"}:
            try:
                value = float(value)
            except Exception:
                safe_send(message.chat.id, f"{pe('cross')} {field} must be numeric")
                return
        if field == "amount" and (value < get_redeem_min_withdraw() or int(value) % get_redeem_multiple_of() != 0):
            safe_send(message.chat.id, f"{pe('cross')} Amount must be at least ₹{get_redeem_min_withdraw():.0f} and in multiples of ₹{get_redeem_multiple_of():.0f}.")
            return
        if field == "is_active":
            value = 1 if str(value).strip().lower() in ["1", "true", "yes", "active"] else 0
        clear_state(user_id)
        db_execute(f"UPDATE redeem_codes SET {field}=? WHERE id=?", (value, code_id))
        log_admin_action(user_id, "edit_redeem_code", f"ID {code_id} {field}={value}")
        safe_send(message.chat.id, f"{pe('check')} Redeem code #{code_id} updated: <b>{field}</b> = <code>{value}</code>")
        return

    if state == "admin_check_redeem_code":
        query = text.strip()
        clear_state(user_id)
        row = db_execute(
            "SELECT * FROM redeem_codes WHERE id=? OR UPPER(code)=UPPER(?) ORDER BY id DESC LIMIT 1",
            (int(query) if query.isdigit() else -1, query),
            fetchone=True
        )
        if not row:
            safe_send(message.chat.id, f"{pe('cross')} Redeem code not found!")
            return
        assigned_text = f"<code>{row['assigned_to']}</code> on {row['assigned_at']}" if row['assigned_to'] else "Not used"
        status = "🟢 Active" if row['is_active'] and not row['assigned_to'] else "🔴 Used/Inactive"
        safe_send(
            message.chat.id,
            f"{pe('tag')} <b>Redeem Code Details</b>\n\n"
            f"ID: <code>{row['id']}</code>\n"
            f"Brand: <b>{row['platform']}</b>\n"
            f"Amount: ₹{row['amount']:.0f}\n"
            f"GST: ₹{row['gst_cut']:.0f}\n"
            f"Code: <code>{row['code']}</code>\n"
            f"Status: {status}\n"
            f"Used By: {assigned_text}\n"
            f"Note: {row['note'] or '-'}"
        )
        return

    if state == "admin_set_redeem_min":
        try:
            val = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        if val < 15 or int(val) % 5 != 0:
            safe_send(message.chat.id, f"{pe('cross')} Minimum must be ₹15 or more and in multiples of ₹5.")
            return
        clear_state(user_id)
        set_setting("redeem_min_withdraw", val)
        safe_send(message.chat.id, f"{pe('check')} Redeem minimum set to ₹{val:.0f}")
        return

    if state == "admin_set_redeem_gst":
        try:
            val = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        if val < 5:
            safe_send(message.chat.id, f"{pe('cross')} GST cut cannot be less than ₹5.")
            return
        clear_state(user_id)
        set_setting("redeem_gst_cut", val)
        safe_send(message.chat.id, f"{pe('check')} Redeem GST cut set to ₹{val:.0f}")
        return

    if state == "admin_delete_redeem_code":
        try:
            code_id = int(text.strip())
        except Exception:
            safe_send(message.chat.id, f"{pe('cross')} Enter a valid redeem code ID!")
            return
        row = get_redeem_code_by_id(code_id)
        clear_state(user_id)
        if not row:
            safe_send(message.chat.id, f"{pe('cross')} Redeem code not found!")
            return
        db_execute("DELETE FROM redeem_codes WHERE id=?", (code_id,))
        log_admin_action(user_id, "delete_redeem_code", f"Deleted redeem code #{code_id}")
        safe_send(message.chat.id, f"{pe('check')} Redeem code #{code_id} deleted.")
        return

    if state == "admin_set_per_refer":
        try:
            val = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        clear_state(user_id)
        set_setting("per_refer", val)
        safe_send(message.chat.id, f"{pe('check')} Per Refer = ₹{val}")
        return

    if state == "admin_set_min_withdraw":
        try:
            val = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        clear_state(user_id)
        set_setting("min_withdraw", val)
        safe_send(message.chat.id, f"{pe('check')} Min Withdraw = ₹{val}")
        return

    if state == "admin_set_welcome_bonus":
        try:
            val = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        clear_state(user_id)
        set_setting("welcome_bonus", val)
        safe_send(message.chat.id, f"{pe('check')} Welcome Bonus = ₹{val}")
        return

    if state == "admin_set_daily_bonus":
        try:
            val = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        clear_state(user_id)
        set_setting("daily_bonus", val)
        safe_send(message.chat.id, f"{pe('check')} Daily Bonus = ₹{val}")
        return


    if state == "admin_set_referral_min_bonus":
        try:
            val = int(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid integer!")
            return
        clear_state(user_id)
        set_setting("referral_min_activity_for_bonus", val)
        safe_send(message.chat.id, f"{pe('check')} Min referrals for daily bonus = {val}")
        return

    if state == "admin_set_referral_min_redeem":
        try:
            val = int(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid integer!")
            return
        clear_state(user_id)
        set_setting("referral_min_activity_for_redeem", val)
        safe_send(message.chat.id, f"{pe('check')} Min referrals for redeem code = {val}")
        return

    if state == "admin_set_inactivity_percent":
        try:
            val = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        clear_state(user_id)
        set_setting("inactivity_deduction_percent", val)
        safe_send(message.chat.id, f"{pe('check')} Inactivity deduction = {val}%")
        return

    if state == "admin_set_inactivity_days":
        try:
            val = int(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid integer!")
            return
        clear_state(user_id)
        set_setting("inactivity_period_days", val)
        safe_send(message.chat.id, f"{pe('check')} Inactivity period = {val} day(s)")
        return

    if state == "admin_set_inactivity_floor":
        try:
            val = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        clear_state(user_id)
        set_setting("inactivity_min_balance_floor", val)
        safe_send(message.chat.id, f"{pe('check')} Inactivity floor = ₹{val}")
        return

    if state == "admin_set_random_bonus_range":
        try:
            a, b = [float(x) for x in text.replace('-', ' ').split()[:2]]
        except:
            safe_send(message.chat.id, f"{pe('cross')} Format: <code>MIN MAX</code>")
            return
        if a > b:
            a, b = b, a
        clear_state(user_id)
        set_setting("random_daily_bonus_min", a)
        set_setting("random_daily_bonus_max", b)
        safe_send(message.chat.id, f"{pe('check')} Random daily bonus range = ₹{a} to ₹{b}")
        return

    if state == "admin_set_bonus_tax_percent":
        try:
            val = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        clear_state(user_id)
        set_setting("withdraw_bonus_balance_tax_percent", val)
        safe_send(message.chat.id, f"{pe('check')} Bonus balance withdrawal tax = {val}%")
        return

    if state.startswith("admin_set_ref_level_"):
        try:
            level = int(state.rsplit('_', 1)[1])
            mode, value = text.split()[:2]
            mode = mode.lower()
            value = float(value)
            if mode not in {"fixed", "percent"}:
                raise ValueError
        except:
            safe_send(message.chat.id, f"{pe('cross')} Format: <code>fixed 2</code> or <code>percent 10</code>")
            return
        clear_state(user_id)
        set_setting(f"referral_level_{level}_type", mode)
        set_setting(f"referral_level_{level}_value", value)
        safe_send(message.chat.id, f"{pe('check')} Referral level {level} set to {mode} {value}")
        return

    if state == "admin_set_max_withdraw":
        try:
            val = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        clear_state(user_id)
        set_setting("max_withdraw_per_day", val)
        safe_send(message.chat.id, f"{pe('check')} Max Withdraw/Day = ₹{val}")
        return

    if state == "admin_set_withdraw_time":
        try:
            parts = text.split("-")
            s = int(parts[0].strip())
            e = int(parts[1].strip())
            if not (0 <= s <= 23 and 0 <= e <= 23):
                raise ValueError
        except:
            safe_send(message.chat.id, f"{pe('cross')} Format: <code>START-END</code> (0-23)\nExample: <code>10-18</code>")
            return
        clear_state(user_id)
        set_setting("withdraw_time_start", s)
        set_setting("withdraw_time_end", e)
        safe_send(message.chat.id, f"{pe('check')} Withdraw Time: {s}:00 – {e}:00")
        return

    if state == "admin_set_welcome_image":
        clear_state(user_id)
        set_setting("welcome_image", text)
        safe_send(message.chat.id, f"{pe('check')} Welcome image updated!")
        return

    if state == "admin_set_withdraw_image":
        clear_state(user_id)
        set_setting("withdraw_image", text)
        safe_send(message.chat.id, f"{pe('check')} Withdraw image updated!")
        return

    if state == "admin_reset_user":
        try:
            tid = int(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid User ID!")
            return
        clear_state(user_id)
        if not get_user(tid):
            safe_send(message.chat.id, f"{pe('cross')} User not found!")
            return
        update_user(tid, balance=0.0, total_earned=0.0, total_withdrawn=0.0, referral_count=0)
        log_admin_action(user_id, "reset_user", f"Reset user {tid}")
        safe_send(message.chat.id, f"{pe('check')} User <code>{tid}</code> reset!")
        return


    if state == "admin_add_user_note":
        data = get_state_data(user_id)
        tid = int(data.get("target_id", 0) or 0)
        clear_state(user_id)
        if not tid:
            safe_send(message.chat.id, f"{pe('cross')} Target user missing.")
            return
        add_user_note(tid, user_id, text.strip())
        log_admin_action(user_id, 'user_note', f'{tid}')
        safe_send(message.chat.id, f"{pe('check')} Note added for <code>{tid}</code>.")
        return

    if state == "admin_add_user_warning":
        data = get_state_data(user_id)
        tid = int(data.get("target_id", 0) or 0)
        clear_state(user_id)
        if not tid:
            safe_send(message.chat.id, f"{pe('cross')} Target user missing.")
            return
        add_user_warning(tid, user_id, text.strip())
        log_admin_action(user_id, 'user_warning', f'{tid}')
        safe_send(message.chat.id, f"{pe('check')} Warning added for <code>{tid}</code>.")
        return

    if state == "admin_set_user_tier":
        data = get_state_data(user_id)
        tid = int(data.get("target_id", 0) or 0)
        try:
            name, level = text.rsplit(' ', 1)
            level = int(level)
        except Exception:
            safe_send(message.chat.id, f"{pe('cross')} Format: <code>Name Level</code>")
            return
        clear_state(user_id)
        set_user_tier(tid, name.strip(), level, user_id)
        log_admin_action(user_id, 'set_user_tier', f'{tid} => {name.strip()} {level}')
        safe_send(message.chat.id, f"{pe('check')} Tier updated for <code>{tid}</code>.")
        return

    if state in ["admin_notes_lookup", "admin_warnings_lookup", "admin_tiers_lookup", "admin_activity_lookup"]:
        try:
            tid = int(text.strip())
        except Exception:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid user ID.")
            return
        clear_state(user_id)
        from .admin_withdrawals import show_user_info
        show_user_info(message.chat.id, tid)
        return

    if state == "admin_user_search":
        clear_state(user_id)
        rows = search_users_admin(text.strip(), 20)
        if not rows:
            safe_send(message.chat.id, f"{pe('cross')} No users found.")
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for row in rows[:20]:
            label = f"{row['first_name'] or 'User'} • @{row['username'] or 'none'} • {row['user_id']}"
            markup.add(types.InlineKeyboardButton(label[:64], callback_data=f"uinfo|{row['user_id']}"))
        safe_send(message.chat.id, f"{pe('search')} Found <b>{len(rows)}</b> matching users. Tap below.", reply_markup=markup)
        return

    if state == "admin_announcement_edit":
        clear_state(user_id)
        if text.strip().lower() == 'off':
            set_setting('announcement_text', '')
            set_setting('announcement_enabled', False)
            safe_send(message.chat.id, f"{pe('check')} Announcement cleared.")
            return
        set_setting('announcement_text', text.strip())
        set_setting('announcement_enabled', True)
        safe_send(message.chat.id, f"{pe('check')} Announcement updated.")
        return
    if state == "admin_send_msg":
        data = get_state_data(user_id)
        tid = data.get("target_id")
        clear_state(user_id)
        if not tid:
            return
        try:
            bot.send_message(tid, text, parse_mode="HTML")
            safe_send(message.chat.id, f"{pe('check')} Message sent to <code>{tid}</code>!")
        except Exception as e:
            safe_send(message.chat.id, f"{pe('cross')} Failed: {e}")
        return

    # ======= ADMIN TASK STATES =======
    if state == "admin_task_create_title":
        data = get_state_data(user_id)
        data["title"] = text
        set_state(user_id, "admin_task_create_desc", data)
        safe_send(message.chat.id, f"{pe('pencil')} <b>Step 2/7: Description</b>\n\nEnter task description:")
        return

    if state == "admin_task_create_desc":
        data = get_state_data(user_id)
        data["description"] = text
        set_state(user_id, "admin_task_create_reward", data)
        safe_send(message.chat.id, f"{pe('pencil')} <b>Step 3/7: Reward Amount</b>\n\nEnter reward in ₹ (e.g. 5):")
        return

    if state == "admin_task_create_reward":
        try:
            reward = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        data = get_state_data(user_id)
        data["reward"] = reward
        set_state(user_id, "admin_task_create_type", data)
        markup = types.InlineKeyboardMarkup(row_width=3)
        types_list = ["channel","youtube","instagram","twitter","facebook","website","app","survey","custom","video","follow"]
        btns = [types.InlineKeyboardButton(f"{get_task_type_emoji(t)} {t.capitalize()}", callback_data=f"task_type_sel|{t}") for t in types_list]
        for i in range(0, len(btns), 3):
            markup.add(*btns[i:i+3])
        safe_send(message.chat.id, f"{pe('pencil')} <b>Step 4/7: Task Type</b>\n\nSelect task type:", reply_markup=markup)
        return

    if state == "admin_task_create_url":
        data = get_state_data(user_id)
        data["task_url"] = text if text.lower() != "skip" else ""
        set_state(user_id, "admin_task_create_channel", data)
        safe_send(
            message.chat.id,
            f"{pe('pencil')} <b>Step 6/7: Channel Username</b>\n\n"
            f"Enter channel username for auto-verify (e.g. @mychannel)\n"
            f"Or type <code>skip</code> if not applicable:"
        )
        return

    if state == "admin_task_create_channel":
        data = get_state_data(user_id)
        data["task_channel"] = text if text.lower() != "skip" else ""
        set_state(user_id, "admin_task_create_maxcomp", data)
        safe_send(
            message.chat.id,
            f"{pe('pencil')} <b>Step 7/7: Max Completions</b>\n\n"
            f"Enter max users who can complete (0 = unlimited):"
        )
        return

    if state == "admin_task_create_maxcomp":
        try:
            mc = int(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid number!")
            return
        data = get_state_data(user_id)
        data["max_completions"] = mc
        clear_state(user_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task_id = db_lastrowid(
            "INSERT INTO tasks (title, description, reward, task_type, task_url, task_channel, "
            "required_action, status, created_by, created_at, updated_at, max_completions, category) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                data.get("title",""), data.get("description",""),
                data.get("reward",0), data.get("task_type","custom"),
                data.get("task_url",""), data.get("task_channel",""),
                "complete", "active", user_id, now, now,
                mc, data.get("category","general")
            )
        )
        log_admin_action(user_id, "create_task", f"Created task #{task_id}: {data.get('title','')}")
        safe_send(
            message.chat.id,
            f"{pe('check')} <b>Task Created!</b> {pe('rocket')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('task')} <b>Title:</b> {data.get('title')}\n"
            f"{pe('coins')} <b>Reward:</b> ₹{data.get('reward')}\n"
            f"{pe('zap')} <b>Type:</b> {data.get('task_type','custom')}\n"
            f"{pe('info')} <b>Task ID:</b> #{task_id}\n"
            f"{pe('thumbs_up')} <b>Max Completions:</b> {'Unlimited' if mc == 0 else mc}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        return

    if state == "admin_task_edit_field":
        data = get_state_data(user_id)
        task_id = data.get("task_id")
        field = data.get("field")
        clear_state(user_id)
        if not task_id or not field:
            return
        val = text
        if field == "reward":
            try:
                val = float(text)
            except:
                safe_send(message.chat.id, f"{pe('cross')} Invalid number!")
                return
        if field == "max_completions":
            try:
                val = int(text)
            except:
                safe_send(message.chat.id, f"{pe('cross')} Invalid number!")
                return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_execute(f"UPDATE tasks SET {field}=?, updated_at=? WHERE id=?", (val, now, task_id))
        safe_send(message.chat.id, f"{pe('check')} Task #{task_id} <b>{field}</b> updated to: <code>{val}</code>")
        task = get_task(task_id)
        if task:
            show_admin_task_detail(message.chat.id, task)
        return

    if state == "admin_task_reject_reason":
        data = get_state_data(user_id)
        sub_id = data.get("sub_id")
        clear_state(user_id)
        if not sub_id:
            return
        process_task_rejection(message.chat.id, sub_id, text)
        return

    if state == "admin_task_bulk_reward":
        data = get_state_data(user_id)
        clear_state(user_id)
        try:
            amount = float(text)
        except:
            safe_send(message.chat.id, f"{pe('cross')} Invalid amount!")
            return
        users_list = db_execute("SELECT user_id FROM users WHERE banned=0", fetch=True) or []
        count = 0
        for u in users_list:
            uu = get_user(u["user_id"])
            if uu:
                update_user(u["user_id"], balance=uu["balance"] + amount, total_earned=uu["total_earned"] + amount)
                count += 1
        log_admin_action(user_id, "bulk_reward", f"Sent ₹{amount} to {count} users")
        safe_send(
            message.chat.id,
            f"{pe('check')} <b>Bulk Reward Sent!</b>\n\n"
            f"{pe('coins')} ₹{amount} sent to {count} users!"
        )
        return

    # ======= ADMIN MANAGER STATES =======
    if state == "admin_add_new":
        try:
            tid = int(text.strip())
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid User ID!")
            return
        clear_state(user_id)
        if int(tid) == int(ADMIN_ID):
            safe_send(message.chat.id, f"{pe('info')} This is the main admin!")
            return
        target = get_user(tid)
        fname = target["first_name"] if target else "Unknown"
        uname = target["username"] if target else ""
        add_admin(tid, uname, fname, user_id)
        log_admin_action(user_id, "add_admin", f"Added admin {tid}")
        safe_send(
            message.chat.id,
            f"{pe('check')} <b>Admin Added!</b>\n\n"
            f"{pe('disguise')} Name: {fname}\n"
            f"{pe('info')} ID: <code>{tid}</code>\n"
            f"{pe('shield')} Permissions: All"
        )
        try:
            safe_send(
                tid,
                f"{pe('crown')} <b>You are now an Admin!</b>\n\n"
                f"{pe('info')} You have been granted admin access.\n"
                f"{pe('shield')} Use /admin to access the admin panel."
            )
        except:
            pass
        return

    if state == "admin_remove_admin":
        try:
            tid = int(text.strip())
        except:
            safe_send(message.chat.id, f"{pe('cross')} Enter valid User ID!")
            return
        clear_state(user_id)
        if int(tid) == int(ADMIN_ID):
            safe_send(message.chat.id, f"{pe('cross')} Cannot remove main admin!")
            return
        remove_admin(tid)
        log_admin_action(user_id, "remove_admin", f"Removed admin {tid}")
        safe_send(message.chat.id, f"{pe('check')} Admin <code>{tid}</code> removed!")
        try:
            safe_send(tid, f"{pe('warning')} Your admin access has been revoked.")
        except:
            pass
        return

    # ======= DB MANAGER STATES =======
    if state == "db_add_user":
        clear_state(user_id)
        handle_db_add_user(message.chat.id, text)
        return

    if state == "db_edit_user":
        clear_state(user_id)
        handle_db_edit_user(message.chat.id, text)
        return

    if state == "db_add_withdrawal":
        clear_state(user_id)
        handle_db_add_withdrawal(message.chat.id, text)
        return

    if state == "db_edit_withdrawal":
        clear_state(user_id)
        handle_db_edit_withdrawal(message.chat.id, text)
        return

    if state == "db_add_gift":
        clear_state(user_id)
        handle_db_add_gift(message.chat.id, text)
        return

    if state == "db_add_task":
        clear_state(user_id)
        handle_db_add_task(message.chat.id, text)
        return

    if state == "db_raw_query":
        clear_state(user_id)
        handle_db_raw_query(message.chat.id, text)
        return

    if state == "db_search_user":
        clear_state(user_id)
        handle_db_search_user(message.chat.id, text)
        return

    if state == "db_delete_user":
        clear_state(user_id)
        handle_db_delete_user(message.chat.id, text)
        return

    if state == "db_delete_withdrawal":
        clear_state(user_id)
        handle_db_delete_withdrawal(message.chat.id, text)
        return

    if state == "db_edit_task_direct":
        data = get_state_data(user_id)
        clear_state(user_id)
        handle_db_edit_task(message.chat.id, text, data)
        return

    if state == "db_add_task_completion":
        clear_state(user_id)
        handle_db_add_task_completion(message.chat.id, text)
        return

