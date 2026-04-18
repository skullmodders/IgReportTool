from core import *

# ======================== CONFIRM WITHDRAW CALLBACK ========================
@bot.callback_query_handler(func=lambda call: call.data.startswith("cwith|"))
def confirm_withdraw_cb(call):
    user_id = call.from_user.id
    try:
        _, amount_str, upi_id = call.data.split("|", 2)
        amount = float(amount_str)
    except:
        safe_answer(call, "Invalid data!", True)
        return

    user = get_user(user_id)
    if not user:
        safe_answer(call, "User not found!", True)
        return

    tax = get_withdrawal_tax_breakdown(user, amount)
    if tax["total_debit"] > user["balance"]:
        safe_answer(call, f"❌ Need ₹{tax['total_debit']:.2f} including tax/GST.", True)
        return

    # ✅ DAILY LIMIT FINAL CHECK YAHAN
    allowed, reason = withdraw_limit.can_user_withdraw(user_id)
    if not allowed:
        safe_answer(call, "❌ Daily limit reached!", True)
        safe_send(call.message.chat.id, reason)
        return

    new_bonus_balance = max(0.0, float(user["bonus_balance"] or 0) - tax["taxable_bonus_amount"])
    update_user(user_id, balance=user["balance"] - tax["total_debit"], bonus_balance=new_bonus_balance)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    w_id = db_lastrowid(
        "INSERT INTO withdrawals (user_id, amount, upi_id, status, created_at, gst_amount, net_amount, method) VALUES (?,?,?,?,?,?,?,?)",
        (user_id, amount, upi_id, "pending", now, tax["total_tax"], amount, "upi")
    )

    safe_answer(call, "✅ Withdrawal request submitted!")
    safe_edit(
        call.message.chat.id, call.message.message_id,
        f"{pe('check')} <b>Withdrawal Submitted!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('fly_money')} <b>Amount:</b> ₹{amount}\n"
        f"{pe('link')} <b>UPI:</b> <code>{upi_id}</code>\n"
        f"{pe('hourglass')} <b>Status:</b> Pending ⏳\n\n"
        f"📋 <i>{tax['total_tax']:.2f} tax/GST deducted for UPI Processing & Management</i>\n"
        f"{pe('info')} Will be processed soon!\n"
        f"{pe('bell')} You'll be notified.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        admin_markup = types.InlineKeyboardMarkup(row_width=2)
        admin_markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"apprv|{w_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rejct|{w_id}")
        )
        admin_markup.add(types.InlineKeyboardButton("👤 User Info", callback_data=f"uinfo|{user_id}"))
        bot.send_message(
            ADMIN_ID,
            f"{pe('siren')} <b>New Withdrawal!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('info')} <b>ID:</b> #{w_id}\n"
            f"{pe('disguise')} <b>User:</b> {h(user['first_name'])} (<code>{user_id}</code>)\n"
            f"{pe('fly_money')} <b>Amount:</b> ₹{amount}\n"
            f"{pe('link')} <b>UPI:</b> <code>{upi_id}</code>\n"
            f"{pe('money')} <b>Remaining:</b> ₹{user['balance'] - tax['total_debit']:.2f}\n"
            f"{pe('thumbs_up')} <b>Referrals:</b> {user['referral_count']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML",
            reply_markup=admin_markup
        )
    except Exception as e:
        print(f"Admin notify error: {e}")

# ======================== ADMIN APPROVE / REJECT ========================
@bot.callback_query_handler(func=lambda call: call.data.startswith("apprv|"))
def admin_approve(call):
    if not is_admin(call.from_user.id):
        safe_answer(call, "❌ Not authorized!", True)
        return
    try:
        w_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Invalid!", True)
        return
    wd = db_execute("SELECT * FROM withdrawals WHERE id=?", (w_id,), fetchone=True)
    if not wd:
        safe_answer(call, "Not found!", True)
        return
    if wd["status"] != "pending":
        safe_answer(call, f"Already {wd['status']}!", True)
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    txn = generate_txn_id()
    db_execute("UPDATE withdrawals SET status='approved', processed_at=?, txn_id=? WHERE id=?", (now, txn, w_id))
    uid = wd["user_id"]
    amt = wd["amount"]
    u = get_user(uid)
    if u:
        update_user(uid, total_withdrawn=u["total_withdrawn"] + amt)
    log_admin_action(call.from_user.id, "approve_withdrawal", f"Approved WD #{w_id} ₹{amt} for {uid}")
    safe_answer(call, "✅ Approved!")
    try:
        safe_edit(
            call.message.chat.id, call.message.message_id,
            (call.message.text or "") + f"\n\n{pe('check')} <b>APPROVED ✅</b>\nTXN: <code>{txn}</code>"
        )
    except:
        pass
    try:
        safe_send(
            uid,
            f"{pe('party')} <b>Withdrawal Approved!</b> {pe('check')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('fly_money')} <b>Amount:</b> ₹{amt}\n"
            f"{pe('link')} <b>UPI:</b> {wd['upi_id']}\n"
            f"{pe('bookmark')} <b>TXN:</b> <code>{txn}</code>\n\n"
            f"{pe('check')} Money will arrive shortly!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
    except:
        pass
    send_public_withdrawal_notification(uid, amt, wd["upi_id"], "approved", txn)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rejct|"))
def admin_reject(call):
    if not is_admin(call.from_user.id):
        safe_answer(call, "❌ Not authorized!", True)
        return
    try:
        w_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Invalid!", True)
        return
    wd = db_execute("SELECT * FROM withdrawals WHERE id=?", (w_id,), fetchone=True)
    if not wd:
        safe_answer(call, "Not found!", True)
        return
    if wd["status"] != "pending":
        safe_answer(call, f"Already {wd['status']}!", True)
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute("UPDATE withdrawals SET status='rejected', processed_at=? WHERE id=?", (now, w_id))
    uid = wd["user_id"]
    amt = wd["amount"]
    u = get_user(uid)
    if u:
        update_user(uid, balance=u["balance"] + amt)
    log_admin_action(call.from_user.id, "reject_withdrawal", f"Rejected WD #{w_id} ₹{amt} for {uid}")
    safe_answer(call, "❌ Rejected & Refunded!")
    try:
        safe_edit(
            call.message.chat.id, call.message.message_id,
            (call.message.text or "") + f"\n\n{pe('cross')} <b>REJECTED ❌</b> (Balance Refunded)"
        )
    except:
        pass
    try:
        safe_send(
            uid,
            f"{pe('cross')} <b>Withdrawal Rejected</b>\n\n"
            f"{pe('fly_money')} Amount: ₹{amt}\n"
            f"{pe('refresh')} Balance refunded!\n"
            f"{pe('info')} Contact {HELP_USERNAME} for details."
        )
    except:
        pass

# ======================== USER INFO (admin) ========================
@bot.callback_query_handler(func=lambda call: call.data.startswith("uinfo|"))
def uinfo_cb(call):
    if not is_admin(call.from_user.id):
        safe_answer(call, "❌ Not authorized!", True)
        return
    try:
        tid = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Invalid!", True)
        return
    safe_answer(call)
    show_user_info(call.message.chat.id, tid)

def show_user_info(chat_id, target_id):
    user = get_user(target_id)
    if not user:
        safe_send(chat_id, f"{pe('cross')} User not found!")
        return
    wd_all = db_execute("SELECT COUNT(*) as cnt FROM withdrawals WHERE user_id=?", (target_id,), fetchone=True)
    wd_ok = db_execute("SELECT COUNT(*) as cnt FROM withdrawals WHERE user_id=? AND status='approved'", (target_id,), fetchone=True)
    task_done = db_execute("SELECT COUNT(*) as cnt FROM task_completions WHERE user_id=?", (target_id,), fetchone=True)
    status = "🔴 Banned" if user["banned"] else "🟢 Active"
    is_adm = "👑 Yes" if is_admin(target_id) else "No"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 Add Balance", callback_data=f"addb|{target_id}"),
        types.InlineKeyboardButton("💸 Deduct", callback_data=f"dedb|{target_id}"),
    )
    markup.add(
        types.InlineKeyboardButton("🚫 Ban" if not user["banned"] else "✅ Unban", callback_data=f"tban|{target_id}"),
        types.InlineKeyboardButton("🔄 Reset", callback_data=f"rstu|{target_id}"),
    )
    markup.add(
        types.InlineKeyboardButton("📩 Send Message", callback_data=f"smsg|{target_id}"),
        types.InlineKeyboardButton("✏️ Edit User DB", callback_data=f"db_edit_u|{target_id}"),
    )
    markup.add(
        types.InlineKeyboardButton("📝 Add Note", callback_data=f"usr_note|{target_id}"),
        types.InlineKeyboardButton("⚠️ Warn User", callback_data=f"usr_warn|{target_id}"),
    )
    markup.add(
        types.InlineKeyboardButton("🏷 Set Tier", callback_data=f"usr_tier|{target_id}"),
        types.InlineKeyboardButton("📜 Activity", callback_data=f"usr_activity|{target_id}"),
    )
    markup.add(
        types.InlineKeyboardButton("👑 Make Admin", callback_data=f"make_admin|{target_id}"),
        types.InlineKeyboardButton("🗑 Delete User", callback_data=f"del_user|{target_id}"),
    )
    safe_send(
        chat_id,
        f"{pe('info')} <b>User Info</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('disguise')} <b>Name:</b> {user['first_name']}\n"
        f"{pe('link')} <b>Username:</b> @{user['username'] or 'None'}\n"
        f"{pe('info')} <b>ID:</b> <code>{target_id}</code>\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Admin:</b> {is_adm}\n\n"
        f"{pe('fly_money')} <b>Balance:</b> ₹{user['balance']:.2f}\n"
        f"{pe('chart_up')} <b>Total Earned:</b> ₹{user['total_earned']:.2f}\n"
        f"{pe('check')} <b>Withdrawn:</b> ₹{user['total_withdrawn']:.2f}\n"
        f"{pe('thumbs_up')} <b>Referrals:</b> {user['referral_count']}\n"
        f"{pe('arrow')} <b>Referred by:</b> {user['referred_by'] or 'None'}\n"
        f"{pe('link')} <b>UPI:</b> {user['upi_id'] or 'Not set'}\n\n"
        f"{pe('task')} <b>Tasks Done:</b> {task_done['cnt'] if task_done else 0}\n"
        f"{pe('calendar')} <b>Joined:</b> {user['joined_at']}\n"
        f"{pe('chart')} <b>Withdrawals:</b> {wd_all['cnt']} ({wd_ok['cnt']} approved)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("make_admin|"))
def make_admin_cb(call):
    if not is_super_admin(call.from_user.id):
        safe_answer(call, "Only main admin can do this!", True)
        return
    try:
        tid = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    if is_admin(tid):
        safe_answer(call, "Already an admin!", True)
        return
    target = get_user(tid)
    fname = target["first_name"] if target else "Unknown"
    uname = target["username"] if target else ""
    add_admin(tid, uname, fname, call.from_user.id)
    log_admin_action(call.from_user.id, "make_admin", f"Made {tid} an admin")
    safe_answer(call, f"✅ {fname} is now an admin!")
    try:
        safe_send(tid, f"{pe('crown')} <b>You are now an Admin!</b>\n\nUse /admin to access the panel.")
    except:
        pass
    show_user_info(call.message.chat.id, tid)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_user|"))
def del_user_cb(call):
    if not is_admin(call.from_user.id):
        safe_answer(call, "Not authorized!", True)
        return
    try:
        tid = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes Delete", callback_data=f"confirm_del_user|{tid}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    safe_answer(call)
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} <b>Delete User <code>{tid}</code>?</b>\n\nThis will delete all their data!",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_del_user|"))
def confirm_del_user(call):
    if not is_admin(call.from_user.id):
        safe_answer(call, "Not authorized!", True)
        return
    try:
        tid = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    db_execute("DELETE FROM users WHERE user_id=?", (tid,))
    db_execute("DELETE FROM withdrawals WHERE user_id=?", (tid,))
    db_execute("DELETE FROM task_completions WHERE user_id=?", (tid,))
    db_execute("DELETE FROM task_submissions WHERE user_id=?", (tid,))
    db_execute("DELETE FROM gift_claims WHERE user_id=?", (tid,))
    log_admin_action(call.from_user.id, "delete_user", f"Deleted user {tid}")
    safe_answer(call, "✅ User deleted!")
    safe_send(call.message.chat.id, f"{pe('check')} User <code>{tid}</code> and all data deleted!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("db_edit_u|"))
def db_edit_u_cb(call):
    if not is_admin(call.from_user.id):
        safe_answer(call, "Not authorized!", True)
        return
    try:
        tid = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call)
    user = get_user(tid)
    if not user:
        safe_send(call.message.chat.id, f"{pe('cross')} User not found!")
        return
    set_state(call.from_user.id, "db_edit_user")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Edit User Database Record</b>\n\n"
        f"{pe('info')} Current values for <code>{tid}</code>:\n"
        f"Balance: {user['balance']}\n"
        f"Total Earned: {user['total_earned']}\n"
        f"Total Withdrawn: {user['total_withdrawn']}\n"
        f"Referral Count: {user['referral_count']}\n"
        f"UPI: {user['upi_id']}\n"
        f"Banned: {user['banned']}\n\n"
        f"{pe('pencil')} Format:\n"
        f"<code>USER_ID FIELD VALUE</code>\n\n"
        f"Fields: balance, total_earned, total_withdrawn,\n"
        f"referral_count, upi_id, banned, username, first_name\n\n"
        f"Example: <code>{tid} balance 100.5</code>"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("addb|"))
def addb_cb(call):
    if not is_admin(call.from_user.id): return
    tid = int(call.data.split("|")[1])
    safe_answer(call)
    set_state(call.from_user.id, "admin_add_balance")
    safe_send(call.message.chat.id, f"{pe('pencil')} Format: <code>{tid} AMOUNT</code>")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dedb|"))
def dedb_cb(call):
    if not is_admin(call.from_user.id): return
    tid = int(call.data.split("|")[1])
    safe_answer(call)
    set_state(call.from_user.id, "admin_deduct_balance")
    safe_send(call.message.chat.id, f"{pe('pencil')} Format: <code>{tid} AMOUNT</code>")

@bot.callback_query_handler(func=lambda call: call.data.startswith("tban|"))
def tban_cb(call):
    if not is_admin(call.from_user.id): return
    try:
        tid = int(call.data.split("|")[1])
    except:
        return
    u = get_user(tid)
    if not u:
        safe_answer(call, "User not found!", True)
        return
    new = 0 if u["banned"] else 1
    update_user(tid, banned=new)
    action = "Banned" if new else "Unbanned"
    log_admin_action(call.from_user.id, action.lower(), f"{action} user {tid}")
    safe_answer(call, f"✅ {action}!")
    show_user_info(call.message.chat.id, tid)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rstu|"))
def rstu_cb(call):
    if not is_admin(call.from_user.id): return
    try:
        tid = int(call.data.split("|")[1])
    except:
        return
    update_user(tid, balance=0.0, total_earned=0.0, total_withdrawn=0.0, referral_count=0)
    log_admin_action(call.from_user.id, "reset_user", f"Reset user {tid}")
    safe_answer(call, "✅ User Reset!")
    show_user_info(call.message.chat.id, tid)

@bot.callback_query_handler(func=lambda call: call.data.startswith("smsg|"))
def smsg_cb(call):
    if not is_admin(call.from_user.id): return
    try:
        tid = int(call.data.split("|")[1])
    except:
        return
    safe_answer(call)
    set_state(call.from_user.id, "admin_send_msg", {"target_id": tid})
    safe_send(call.message.chat.id, f"{pe('pencil')} Type message to send to <code>{tid}</code>:")

