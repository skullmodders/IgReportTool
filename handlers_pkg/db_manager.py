from core import *

# ======================== DATABASE MANAGER ========================
@bot.message_handler(func=lambda m: m.text == "🗄 DB Manager" and is_admin(m.from_user.id))
def admin_db_manager(message):
    show_db_manager(message.chat.id)


def show_db_manager(chat_id):
    user_count = get_user_count()
    wd_count = db_execute("SELECT COUNT(*) as c FROM withdrawals", fetchone=True)
    task_count = db_execute("SELECT COUNT(*) as c FROM tasks", fetchone=True)
    gift_count = db_execute("SELECT COUNT(*) as c FROM gift_codes", fetchone=True)
    sub_count = db_execute("SELECT COUNT(*) as c FROM task_submissions", fetchone=True)
    comp_count = db_execute("SELECT COUNT(*) as c FROM task_completions", fetchone=True)
    admin_count = db_execute("SELECT COUNT(*) as c FROM admins WHERE is_active=1", fetchone=True)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👥 Users Table", callback_data="db_table_users"),
        types.InlineKeyboardButton("💳 Withdrawals Table", callback_data="db_table_withdrawals"),
    )
    markup.add(
        types.InlineKeyboardButton("📋 Tasks Table", callback_data="db_table_tasks"),
        types.InlineKeyboardButton("🎁 Gift Codes Table", callback_data="db_table_gifts"),
    )
    markup.add(
        types.InlineKeyboardButton("📤 Submissions Table", callback_data="db_table_submissions"),
        types.InlineKeyboardButton("✅ Completions Table", callback_data="db_table_completions"),
    )
    markup.add(
        types.InlineKeyboardButton("👮 Admins Table", callback_data="db_table_admins"),
        types.InlineKeyboardButton("📜 Admin Logs", callback_data="db_table_logs"),
    )
    markup.add(
        types.InlineKeyboardButton("➕ Add User", callback_data="db_btn_add_user"),
        types.InlineKeyboardButton("✏️ Edit User", callback_data="db_btn_edit_user"),
    )
    markup.add(
        types.InlineKeyboardButton("➕ Add Withdrawal", callback_data="db_btn_add_wd"),
        types.InlineKeyboardButton("✏️ Edit Withdrawal", callback_data="db_btn_edit_wd"),
    )
    markup.add(
        types.InlineKeyboardButton("➕ Add Gift Code", callback_data="db_btn_add_gift"),
        types.InlineKeyboardButton("➕ Add Task", callback_data="db_btn_add_task"),
    )
    markup.add(
        types.InlineKeyboardButton("➕ Add Completion", callback_data="db_btn_add_completion"),
        types.InlineKeyboardButton("🔍 Search User", callback_data="db_btn_search_user"),
    )
    markup.add(
        types.InlineKeyboardButton("🗑 Delete User", callback_data="db_btn_delete_user"),
        types.InlineKeyboardButton("🗑 Delete WD", callback_data="db_btn_delete_wd"),
    )
    markup.add(
        types.InlineKeyboardButton("⚡ Raw SQL Query", callback_data="db_btn_raw_query"),
        types.InlineKeyboardButton("📥 Full DB Backup", callback_data="db_btn_backup"),
    )
    markup.add(
        types.InlineKeyboardButton("📊 DB Stats", callback_data="db_btn_stats"),
        types.InlineKeyboardButton("🔄 Refresh", callback_data="db_btn_refresh"),
    )

    safe_send(
        chat_id,
        f"{pe('database')} <b>Database Manager</b> {pe('gear')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('thumbs_up')} <b>Users:</b> {user_count}\n"
        f"{pe('fly_money')} <b>Withdrawals:</b> {wd_count['c']}\n"
        f"{pe('task')} <b>Tasks:</b> {task_count['c']}\n"
        f"{pe('party')} <b>Gift Codes:</b> {gift_count['c']}\n"
        f"{pe('pending2')} <b>Task Submissions:</b> {sub_count['c']}\n"
        f"{pe('done')} <b>Task Completions:</b> {comp_count['c']}\n"
        f"{pe('admin')} <b>Admins:</b> {admin_count['c']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{pe('bulb')} Use buttons to manage database directly.",
        reply_markup=markup
    )


# ======================== DB TABLE VIEWERS ========================
@bot.callback_query_handler(func=lambda call: call.data == "db_table_users")
def db_table_users(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT user_id, username, first_name, balance, total_earned, referral_count, banned, joined_at "
        "FROM users ORDER BY joined_at DESC LIMIT 20",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} Users table is empty!")
        return
    text = f"{pe('database')} <b>Users Table (Last 20)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for u in rows:
        ban = "🔴" if u["banned"] else "🟢"
        text += (
            f"{ban} <code>{u['user_id']}</code> | <b>{u['first_name']}</b>\n"
            f"   @{u['username'] or 'none'} | ₹{u['balance']:.2f} | Refs:{u['referral_count']}\n"
            f"   Joined: {u['joined_at'][:10]}\n\n"
        )
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated, showing first 20)"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Add User", callback_data="db_btn_add_user"),
        types.InlineKeyboardButton("✏️ Edit User", callback_data="db_btn_edit_user"),
    )
    markup.add(
        types.InlineKeyboardButton("🔍 Search", callback_data="db_btn_search_user"),
        types.InlineKeyboardButton("📥 Export", callback_data="dash_export"),
    )
    safe_send(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "db_table_withdrawals")
def db_table_withdrawals(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM withdrawals ORDER BY created_at DESC LIMIT 20",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} Withdrawals table is empty!")
        return
    text = f"{pe('database')} <b>Withdrawals Table (Last 20)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    status_icons = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    for w in rows:
        icon = status_icons.get(w["status"], "❓")
        text += (
            f"{icon} <b>#{w['id']}</b> | User: <code>{w['user_id']}</code>\n"
            f"   ₹{w['amount']} → <code>{w['upi_id']}</code>\n"
            f"   Status: {w['status']} | {w['created_at'][:10]}\n\n"
        )
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Add WD Record", callback_data="db_btn_add_wd"),
        types.InlineKeyboardButton("✏️ Edit WD", callback_data="db_btn_edit_wd"),
    )
    markup.add(
        types.InlineKeyboardButton("🗑 Delete WD", callback_data="db_btn_delete_wd"),
    )
    safe_send(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "db_table_tasks")
def db_table_tasks(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT id, title, reward, task_type, status, total_completions, max_completions, created_at "
        "FROM tasks ORDER BY id DESC LIMIT 20",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} Tasks table is empty!")
        return
    text = f"{pe('database')} <b>Tasks Table (Last 20)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    status_icons = {"active": "🟢", "paused": "🟡", "completed": "🏁"}
    for t in rows:
        icon = status_icons.get(t["status"], "⚪")
        mc = f"/{t['max_completions']}" if t["max_completions"] > 0 else "/∞"
        text += (
            f"{icon} <b>#{t['id']}</b> | {t['title']}\n"
            f"   ₹{t['reward']} | {t['task_type']} | {t['total_completions']}{mc}\n"
            f"   Created: {t['created_at'][:10]}\n\n"
        )
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Add Task", callback_data="db_btn_add_task"),
        types.InlineKeyboardButton("📊 Task Manager", callback_data="tm_refresh"),
    )
    safe_send(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "db_table_gifts")
def db_table_gifts(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM gift_codes ORDER BY created_at DESC LIMIT 25",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} Gift codes table is empty!")
        return
    text = f"{pe('database')} <b>Gift Codes Table (Last 25)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for g in rows:
        active = "🟢" if g["is_active"] else "🔴"
        text += (
            f"{active} <code>{g['code']}</code> | ₹{g['amount']}\n"
            f"   Claims: {g['total_claims']}/{g['max_claims']} | {g['gift_type']}\n"
            f"   By: <code>{g['created_by']}</code> | {g['created_at'][:10]}\n\n"
        )
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("➕ Add Gift Code", callback_data="db_btn_add_gift"))
    safe_send(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "db_table_submissions")
def db_table_submissions(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT ts.id, ts.task_id, ts.user_id, ts.status, ts.reward_paid, ts.submitted_at, "
        "t.title as task_title FROM task_submissions ts "
        "JOIN tasks t ON ts.task_id=t.id "
        "ORDER BY ts.submitted_at DESC LIMIT 20",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} Task submissions table is empty!")
        return
    text = f"{pe('database')} <b>Task Submissions (Last 20)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    status_icons = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    for s in rows:
        icon = status_icons.get(s["status"], "❓")
        text += (
            f"{icon} <b>Sub#{s['id']}</b> | Task: {s['task_title'][:20]}\n"
            f"   User: <code>{s['user_id']}</code> | ₹{s['reward_paid']}\n"
            f"   {s['submitted_at'][:10]}\n\n"
        )
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            f"⏳ View Pending ({db_execute('SELECT COUNT(*) as c FROM task_submissions WHERE status=?', ('pending',), fetchone=True)['c']})",
            callback_data="admin_task_pending_subs"
        )
    )
    safe_send(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "db_table_completions")
def db_table_completions(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT tc.id, tc.task_id, tc.user_id, tc.reward_paid, tc.completed_at, "
        "t.title as task_title FROM task_completions tc "
        "JOIN tasks t ON tc.task_id=t.id "
        "ORDER BY tc.completed_at DESC LIMIT 20",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} Task completions table is empty!")
        return
    text = f"{pe('database')} <b>Task Completions (Last 20)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for c in rows:
        text += (
            f"{pe('done')} <b>Comp#{c['id']}</b> | {c['task_title'][:20]}\n"
            f"   User: <code>{c['user_id']}</code> | ₹{c['reward_paid']}\n"
            f"   {c['completed_at'][:10]}\n\n"
        )
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("➕ Add Completion", callback_data="db_btn_add_completion"))
    safe_send(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "db_table_admins")
def db_table_admins(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute("SELECT * FROM admins ORDER BY added_at DESC", fetch=True) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} Admins table is empty!")
        return
    text = f"{pe('database')} <b>Admins Table</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for a in rows:
        active = "🟢" if a["is_active"] else "🔴"
        is_main = "👑" if int(a["user_id"]) == int(ADMIN_ID) else "👮"
        text += (
            f"{active} {is_main} <b>{a['first_name'] or 'Unknown'}</b>\n"
            f"   ID: <code>{a['user_id']}</code> | @{a['username'] or 'none'}\n"
            f"   Perms: {a['permissions']} | Added: {a['added_at'][:10]}\n"
            f"   Added by: <code>{a['added_by']}</code>\n\n"
        )
    safe_send(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "db_table_logs")
def db_table_logs(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM admin_logs ORDER BY created_at DESC LIMIT 30",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} Admin logs table is empty!")
        return
    text = f"{pe('database')} <b>Admin Logs (Last 30)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for log in rows:
        text += (
            f"{pe('arrow')} <b>{log['action']}</b>\n"
            f"   Admin: <code>{log['admin_id']}</code>\n"
            f"   {log['details'][:80]}\n"
            f"   🕐 {log['created_at']}\n\n"
        )
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    safe_send(call.message.chat.id, text)


# ======================== DB MANAGER BUTTONS ========================
@bot.callback_query_handler(func=lambda call: call.data == "db_btn_add_user")
def db_btn_add_user(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_add_user")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Add User to Database</b>\n\n"
        f"Format (all fields required):\n"
        f"<code>USER_ID USERNAME FIRST_NAME BALANCE TOTAL_EARNED REFERRAL_COUNT REFERRED_BY UPI_ID</code>\n\n"
        f"Example:\n"
        f"<code>123456789 johndoe John 50.0 100.0 5 0 john@paytm</code>\n\n"
        f"{pe('info')} For empty fields use: <code>-</code>\n"
        f"Example with empty UPI: <code>123456789 johndoe John 0 0 0 0 -</code>"
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_edit_user")
def db_btn_edit_user(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_edit_user")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Edit User Database Record</b>\n\n"
        f"Format:\n"
        f"<code>USER_ID FIELD VALUE</code>\n\n"
        f"Available fields:\n"
        f"• <code>balance</code> — Set balance\n"
        f"• <code>total_earned</code> — Set total earned\n"
        f"• <code>total_withdrawn</code> — Set total withdrawn\n"
        f"• <code>referral_count</code> — Set referral count\n"
        f"• <code>referred_by</code> — Set referrer ID\n"
        f"• <code>upi_id</code> — Set UPI ID\n"
        f"• <code>banned</code> — 0=active, 1=banned\n"
        f"• <code>username</code> — Set username\n"
        f"• <code>first_name</code> — Set name\n"
        f"• <code>is_premium</code> — 0 or 1\n"
        f"• <code>last_daily</code> — Set last daily date\n\n"
        f"Example:\n"
        f"<code>123456789 balance 500.0</code>\n"
        f"<code>123456789 banned 1</code>"
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_add_wd")
def db_btn_add_wd(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_add_withdrawal")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Add Withdrawal Record</b>\n\n"
        f"Format:\n"
        f"<code>USER_ID AMOUNT UPI_ID STATUS</code>\n\n"
        f"Status options: <code>pending</code>, <code>approved</code>, <code>rejected</code>\n\n"
        f"Example:\n"
        f"<code>123456789 100.0 name@paytm approved</code>\n\n"
        f"{pe('info')} TXN ID will be auto-generated for approved."
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_edit_wd")
def db_btn_edit_wd(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_edit_withdrawal")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Edit Withdrawal Record</b>\n\n"
        f"Format:\n"
        f"<code>WD_ID FIELD VALUE</code>\n\n"
        f"Available fields:\n"
        f"• <code>status</code> — pending/approved/rejected\n"
        f"• <code>amount</code> — Change amount\n"
        f"• <code>upi_id</code> — Change UPI\n"
        f"• <code>txn_id</code> — Set TXN ID\n"
        f"• <code>admin_note</code> — Add note\n\n"
        f"Example:\n"
        f"<code>42 status approved</code>\n"
        f"<code>42 txn_id TXN1234567890</code>"
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_add_gift")
def db_btn_add_gift(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_add_gift")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Add Gift Code to Database</b>\n\n"
        f"Format:\n"
        f"<code>CODE AMOUNT MAX_CLAIMS GIFT_TYPE</code>\n\n"
        f"Gift types: <code>admin</code>, <code>user</code>\n\n"
        f"Examples:\n"
        f"<code>SUMMER50 50.0 10 admin</code>\n"
        f"<code>WELCOME10 10.0 1 user</code>\n\n"
        f"{pe('info')} Code must be unique. Use uppercase."
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_add_task")
def db_btn_add_task(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_add_task")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Add Task to Database</b>\n\n"
        f"Format (use | as separator):\n"
        f"<code>title|description|reward|task_type|task_url|status</code>\n\n"
        f"Task types: channel, youtube, instagram, twitter,\n"
        f"facebook, website, app, survey, custom, video, follow\n\n"
        f"Status: active, paused, completed\n\n"
        f"Example:\n"
        f"<code>Join Channel|Join our TG channel|5.0|channel|https://t.me/test|active</code>\n\n"
        f"{pe('info')} Max completions defaults to 0 (unlimited)."
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_add_completion")
def db_btn_add_completion(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_add_task_completion")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Add Task Completion Record</b>\n\n"
        f"Format:\n"
        f"<code>TASK_ID USER_ID REWARD</code>\n\n"
        f"Example:\n"
        f"<code>1 123456789 5.0</code>\n\n"
        f"{pe('info')} This will also update user balance.\n"
        f"{pe('warning')} Make sure task and user exist!"
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_search_user")
def db_btn_search_user(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_search_user")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Search User</b>\n\n"
        f"Enter any of:\n"
        f"• User ID (e.g. <code>123456789</code>)\n"
        f"• Username (e.g. <code>johndoe</code>)\n"
        f"• Name (e.g. <code>John</code>)"
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_delete_user")
def db_btn_delete_user(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_delete_user")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Delete User</b>\n\n"
        f"Enter User ID to delete:\n"
        f"<code>USER_ID</code>\n\n"
        f"{pe('warning')} This will delete the user and ALL their data!\n"
        f"(withdrawals, task completions, submissions, gift claims)"
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_delete_wd")
def db_btn_delete_wd(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_delete_withdrawal")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Delete Withdrawal Record</b>\n\n"
        f"Enter Withdrawal ID to delete:\n"
        f"<code>WD_ID</code>\n\n"
        f"{pe('warning')} This only deletes the record, it does NOT refund balance!"
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_raw_query")
def db_btn_raw_query(call):
    if not is_super_admin(call.from_user.id):
        safe_answer(call, "Only main admin can run raw queries!", True)
        return
    safe_answer(call)
    set_state(call.from_user.id, "db_raw_query")
    safe_send(
        call.message.chat.id,
        f"{pe('siren')} <b>Raw SQL Query</b>\n\n"
        f"{pe('warning')} <b>DANGER ZONE!</b> Be very careful!\n\n"
        f"Type your SQL query:\n\n"
        f"Examples:\n"
        f"<code>SELECT * FROM users LIMIT 5</code>\n"
        f"<code>UPDATE users SET balance=100 WHERE user_id=123456</code>\n"
        f"<code>SELECT COUNT(*) FROM withdrawals WHERE status='pending'</code>\n\n"
        f"{pe('info')} SELECT queries show results.\n"
        f"Other queries execute and show affected rows."
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_backup")
def db_btn_backup(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call, "Creating backup...")
    try:
        import shutil
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(DB_PATH, backup_name)
        with open(backup_name, "rb") as f:
            bot.send_document(
                call.message.chat.id,
                f,
                caption=(
                    f"{pe('check')} <b>Database Backup</b>\n\n"
                    f"{pe('calendar')} Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"{pe('database')} File: {backup_name}"
                ),
                parse_mode="HTML"
            )
        os.remove(backup_name)
        log_admin_action(call.from_user.id, "db_backup", "Created database backup")
    except Exception as e:
        safe_send(call.message.chat.id, f"{pe('cross')} Backup failed: {e}")


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_stats")
def db_btn_stats(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    try:
        db_size = os.path.getsize(DB_PATH) / 1024
        db_size_str = f"{db_size:.1f} KB" if db_size < 1024 else f"{db_size/1024:.2f} MB"
    except:
        db_size_str = "Unknown"

    user_count = get_user_count()
    wd_count = db_execute("SELECT COUNT(*) as c FROM withdrawals", fetchone=True)
    task_count = db_execute("SELECT COUNT(*) as c FROM tasks", fetchone=True)
    gift_count = db_execute("SELECT COUNT(*) as c FROM gift_codes", fetchone=True)
    sub_count = db_execute("SELECT COUNT(*) as c FROM task_submissions", fetchone=True)
    comp_count = db_execute("SELECT COUNT(*) as c FROM task_completions", fetchone=True)
    log_count = db_execute("SELECT COUNT(*) as c FROM admin_logs", fetchone=True)
    broadcast_count = db_execute("SELECT COUNT(*) as c FROM broadcasts", fetchone=True)
    gift_claims_count = db_execute("SELECT COUNT(*) as c FROM gift_claims", fetchone=True)
    bonus_count = db_execute("SELECT COUNT(*) as c FROM bonus_history", fetchone=True)

    safe_send(
        call.message.chat.id,
        f"{pe('database')} <b>Database Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('info')} <b>File Size:</b> {db_size_str}\n"
        f"{pe('calendar')} <b>Last Checked:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"{pe('chart')} <b>Table Records:</b>\n"
        f"  👥 Users: {user_count}\n"
        f"  💳 Withdrawals: {wd_count['c']}\n"
        f"  📋 Tasks: {task_count['c']}\n"
        f"  🎁 Gift Codes: {gift_count['c']}\n"
        f"  🎟 Gift Claims: {gift_claims_count['c']}\n"
        f"  📤 Task Submissions: {sub_count['c']}\n"
        f"  ✅ Task Completions: {comp_count['c']}\n"
        f"  📜 Admin Logs: {log_count['c']}\n"
        f"  📢 Broadcasts: {broadcast_count['c']}\n"
        f"  🎰 Bonus History: {bonus_count['c']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


@bot.callback_query_handler(func=lambda call: call.data == "db_btn_refresh")
def db_btn_refresh(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call, "🔄 Refreshed!")
    show_db_manager(call.message.chat.id)


# ======================== DB HANDLER FUNCTIONS ========================
def handle_db_add_user(chat_id, text):
    try:
        parts = text.split()
        if len(parts) < 8:
            safe_send(
                chat_id,
                f"{pe('cross')} Not enough fields!\n\n"
                f"Format: <code>USER_ID USERNAME FIRST_NAME BALANCE TOTAL_EARNED REFERRAL_COUNT REFERRED_BY UPI_ID</code>"
            )
            return
        user_id = int(parts[0])
        username = parts[1] if parts[1] != "-" else ""
        first_name = parts[2] if parts[2] != "-" else "User"
        balance = float(parts[3])
        total_earned = float(parts[4])
        referral_count = int(parts[5])
        referred_by = int(parts[6])
        upi_id = parts[7] if parts[7] != "-" else ""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        existing = get_user(user_id)
        if existing:
            safe_send(
                chat_id,
                f"{pe('warning')} User <code>{user_id}</code> already exists!\n\n"
                f"Use Edit User to modify existing records."
            )
            return

        db_execute(
            "INSERT INTO users (user_id, username, first_name, balance, total_earned, "
            "total_withdrawn, referral_count, referred_by, upi_id, banned, joined_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, username, first_name, balance, total_earned,
             0.0, referral_count, referred_by, upi_id, 0, now)
        )
        log_admin_action(ADMIN_ID, "db_add_user", f"Added user {user_id} manually")
        safe_send(
            chat_id,
            f"{pe('check')} <b>User Added to Database!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('info')} ID: <code>{user_id}</code>\n"
            f"{pe('disguise')} Name: {first_name}\n"
            f"{pe('link')} Username: @{username or 'none'}\n"
            f"{pe('fly_money')} Balance: ₹{balance}\n"
            f"{pe('chart_up')} Total Earned: ₹{total_earned}\n"
            f"{pe('thumbs_up')} Referrals: {referral_count}\n"
            f"{pe('link')} UPI: {upi_id or 'Not set'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
    except ValueError as e:
        safe_send(chat_id, f"{pe('cross')} Invalid format: {e}\n\nCheck numbers and try again.")
    except Exception as e:
        safe_send(chat_id, f"{pe('cross')} Error: {e}")


def handle_db_edit_user(chat_id, text):
    allowed_fields = [
        "balance", "total_earned", "total_withdrawn", "referral_count",
        "referred_by", "upi_id", "banned", "username", "first_name",
        "is_premium", "last_daily"
    ]
    numeric_fields = ["balance", "total_earned", "total_withdrawn", "referral_count",
                      "referred_by", "banned", "is_premium"]
    try:
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            safe_send(
                chat_id,
                f"{pe('cross')} Format: <code>USER_ID FIELD VALUE</code>"
            )
            return
        user_id = int(parts[0])
        field = parts[1].lower()
        value = parts[2]

        if field not in allowed_fields:
            safe_send(
                chat_id,
                f"{pe('cross')} Invalid field: <code>{field}</code>\n\n"
                f"Allowed: {', '.join(allowed_fields)}"
            )
            return

        user = get_user(user_id)
        if not user:
            safe_send(chat_id, f"{pe('cross')} User <code>{user_id}</code> not found!")
            return

        if field in numeric_fields:
            try:
                if field in ["referral_count", "referred_by", "banned", "is_premium"]:
                    value = int(value)
                else:
                    value = float(value)
            except ValueError:
                safe_send(chat_id, f"{pe('cross')} {field} must be a number!")
                return

        old_value = user[field]
        db_execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))
        log_admin_action(ADMIN_ID, "db_edit_user", f"Edited {user_id}.{field}: {old_value} → {value}")
        safe_send(
            chat_id,
            f"{pe('check')} <b>User Updated!</b>\n\n"
            f"{pe('info')} User: <code>{user_id}</code>\n"
            f"{pe('edit')} Field: <b>{field}</b>\n"
            f"{pe('cross')} Old: <code>{old_value}</code>\n"
            f"{pe('check')} New: <code>{value}</code>"
        )
    except ValueError as e:
        safe_send(chat_id, f"{pe('cross')} Invalid format: {e}")
    except Exception as e:
        safe_send(chat_id, f"{pe('cross')} Error: {e}")


def handle_db_add_withdrawal(chat_id, text):
    try:
        parts = text.split(maxsplit=3)
        if len(parts) < 4:
            safe_send(
                chat_id,
                f"{pe('cross')} Format: <code>USER_ID AMOUNT UPI_ID STATUS</code>"
            )
            return
        user_id = int(parts[0])
        amount = float(parts[1])
        upi_id = parts[2]
        status = parts[3].lower()

        if status not in ["pending", "approved", "rejected"]:
            safe_send(chat_id, f"{pe('cross')} Status must be: pending, approved, or rejected")
            return

        user = get_user(user_id)
        if not user:
            safe_send(chat_id, f"{pe('cross')} User <code>{user_id}</code> not found!")
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        txn_id = generate_txn_id() if status == "approved" else ""
        processed_at = now if status != "pending" else ""

        wd_id = db_lastrowid(
            "INSERT INTO withdrawals (user_id, amount, upi_id, status, created_at, processed_at, txn_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, amount, upi_id, status, now, processed_at, txn_id)
        )

        if status == "approved":
            update_user(user_id, total_withdrawn=user["total_withdrawn"] + amount)

        log_admin_action(ADMIN_ID, "db_add_withdrawal", f"Added WD #{wd_id} for {user_id} ₹{amount} [{status}]")
        safe_send(
            chat_id,
            f"{pe('check')} <b>Withdrawal Record Added!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('info')} WD ID: #{wd_id}\n"
            f"{pe('disguise')} User: <code>{user_id}</code>\n"
            f"{pe('fly_money')} Amount: ₹{amount}\n"
            f"{pe('link')} UPI: {upi_id}\n"
            f"{pe('check')} Status: {status}\n"
            f"{pe('bookmark')} TXN: {txn_id or 'N/A'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
    except ValueError as e:
        safe_send(chat_id, f"{pe('cross')} Invalid format: {e}")
    except Exception as e:
        safe_send(chat_id, f"{pe('cross')} Error: {e}")


def handle_db_edit_withdrawal(chat_id, text):
    allowed_fields = ["status", "amount", "upi_id", "txn_id", "admin_note"]
    try:
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            safe_send(chat_id, f"{pe('cross')} Format: <code>WD_ID FIELD VALUE</code>")
            return
        wd_id = int(parts[0])
        field = parts[1].lower()
        value = parts[2]

        if field not in allowed_fields:
            safe_send(
                chat_id,
                f"{pe('cross')} Invalid field!\nAllowed: {', '.join(allowed_fields)}"
            )
            return

        wd = db_execute("SELECT * FROM withdrawals WHERE id=?", (wd_id,), fetchone=True)
        if not wd:
            safe_send(chat_id, f"{pe('cross')} Withdrawal #{wd_id} not found!")
            return

        if field == "amount":
            try:
                value = float(value)
            except:
                safe_send(chat_id, f"{pe('cross')} Amount must be a number!")
                return

        if field == "status" and value not in ["pending", "approved", "rejected"]:
            safe_send(chat_id, f"{pe('cross')} Status must be: pending, approved, or rejected")
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        old_value = wd[field]
        db_execute(f"UPDATE withdrawals SET {field}=? WHERE id=?", (value, wd_id))

        if field == "status" and value == "approved" and wd["status"] != "approved":
            if not wd["txn_id"]:
                txn = generate_txn_id()
                db_execute("UPDATE withdrawals SET txn_id=?, processed_at=? WHERE id=?", (txn, now, wd_id))
            u = get_user(wd["user_id"])
            if u:
                update_user(wd["user_id"], total_withdrawn=u["total_withdrawn"] + wd["amount"])

        log_admin_action(ADMIN_ID, "db_edit_wd", f"Edited WD #{wd_id}.{field}: {old_value} → {value}")
        safe_send(
            chat_id,
            f"{pe('check')} <b>Withdrawal #{wd_id} Updated!</b>\n\n"
            f"{pe('edit')} Field: <b>{field}</b>\n"
            f"{pe('cross')} Old: <code>{old_value}</code>\n"
            f"{pe('check')} New: <code>{value}</code>"
        )
    except ValueError as e:
        safe_send(chat_id, f"{pe('cross')} Invalid format: {e}")
    except Exception as e:
        safe_send(chat_id, f"{pe('cross')} Error: {e}")


def handle_db_add_gift(chat_id, text):
    try:
        parts = text.split()
        if len(parts) < 4:
            safe_send(
                chat_id,
                f"{pe('cross')} Format: <code>CODE AMOUNT MAX_CLAIMS GIFT_TYPE</code>"
            )
            return
        code = parts[0].upper()
        amount = float(parts[1])
        max_claims = int(parts[2])
        gift_type = parts[3].lower()

        if gift_type not in ["admin", "user"]:
            safe_send(chat_id, f"{pe('cross')} Gift type must be: admin or user")
            return

        existing = db_execute("SELECT code FROM gift_codes WHERE code=?", (code,), fetchone=True)
        if existing:
            safe_send(chat_id, f"{pe('cross')} Code <code>{code}</code> already exists!")
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_execute(
            "INSERT INTO gift_codes (code, amount, created_by, created_at, gift_type, max_claims, is_active) "
            "VALUES (?,?,?,?,?,?,?)",
            (code, amount, ADMIN_ID, now, gift_type, max_claims, 1)
        )
        log_admin_action(ADMIN_ID, "db_add_gift", f"Added gift code {code} ₹{amount} x{max_claims}")
        safe_send(
            chat_id,
            f"{pe('check')} <b>Gift Code Added!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('star')} Code: <code>{code}</code>\n"
            f"{pe('money')} Amount: ₹{amount}\n"
            f"{pe('thumbs_up')} Max Claims: {max_claims}\n"
            f"{pe('tag')} Type: {gift_type}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
    except ValueError as e:
        safe_send(chat_id, f"{pe('cross')} Invalid format: {e}")
    except Exception as e:
        safe_send(chat_id, f"{pe('cross')} Error: {e}")


def handle_db_add_task(chat_id, text):
    try:
        parts = text.split("|")
        if len(parts) < 6:
            safe_send(
                chat_id,
                f"{pe('cross')} Format: <code>title|description|reward|task_type|task_url|status</code>"
            )
            return
        title = parts[0].strip()
        description = parts[1].strip()
        reward = float(parts[2].strip())
        task_type = parts[3].strip().lower()
        task_url = parts[4].strip()
        status = parts[5].strip().lower()

        valid_types = ["channel", "youtube", "instagram", "twitter", "facebook",
                       "website", "app", "survey", "custom", "video", "follow"]
        if task_type not in valid_types:
            safe_send(chat_id, f"{pe('cross')} Invalid task type!\nValid: {', '.join(valid_types)}")
            return

        if status not in ["active", "paused", "completed"]:
            safe_send(chat_id, f"{pe('cross')} Status must be: active, paused, or completed")
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task_id = db_lastrowid(
            "INSERT INTO tasks (title, description, reward, task_type, task_url, "
            "required_action, status, created_by, created_at, updated_at, max_completions, category) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (title, description, reward, task_type, task_url,
             "complete", status, ADMIN_ID, now, now, 0, "general")
        )
        log_admin_action(ADMIN_ID, "db_add_task", f"Added task #{task_id}: {title}")
        safe_send(
            chat_id,
            f"{pe('check')} <b>Task Added to Database!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('task')} Title: {title}\n"
            f"{pe('coins')} Reward: ₹{reward}\n"
            f"{pe('zap')} Type: {task_type}\n"
            f"{pe('active')} Status: {status}\n"
            f"{pe('info')} Task ID: #{task_id}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
    except ValueError as e:
        safe_send(chat_id, f"{pe('cross')} Invalid format: {e}")
    except Exception as e:
        safe_send(chat_id, f"{pe('cross')} Error: {e}")


def handle_db_add_task_completion(chat_id, text):
    try:
        parts = text.split()
        if len(parts) < 3:
            safe_send(chat_id, f"{pe('cross')} Format: <code>TASK_ID USER_ID REWARD</code>")
            return
        task_id = int(parts[0])
        user_id = int(parts[1])
        reward = float(parts[2])

        task = get_task(task_id)
        if not task:
            safe_send(chat_id, f"{pe('cross')} Task #{task_id} not found!")
            return

        user = get_user(user_id)
        if not user:
            safe_send(chat_id, f"{pe('cross')} User <code>{user_id}</code> not found!")
            return

        existing = get_task_completion(task_id, user_id)
        if existing:
            safe_send(
                chat_id,
                f"{pe('warning')} User already completed this task!\n\n"
                f"Existing completion: ₹{existing['reward_paid']} on {existing['completed_at'][:10]}"
            )
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_execute(
            "INSERT INTO task_completions (task_id, user_id, completed_at, reward_paid) VALUES (?,?,?,?)",
            (task_id, user_id, now, reward)
        )
        db_execute("UPDATE tasks SET total_completions=total_completions+1 WHERE id=?", (task_id,))
        update_user(user_id, balance=user["balance"] + reward, total_earned=user["total_earned"] + reward)
        log_admin_action(ADMIN_ID, "db_add_completion", f"Added completion task#{task_id} user{user_id} ₹{reward}")
        safe_send(
            chat_id,
            f"{pe('check')} <b>Task Completion Added!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('task')} Task: {task['title']}\n"
            f"{pe('disguise')} User: {user['first_name']} (<code>{user_id}</code>)\n"
            f"{pe('coins')} Reward: ₹{reward}\n"
            f"{pe('fly_money')} New Balance: ₹{user['balance'] + reward:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            safe_send(
                user_id,
                f"{pe('party')} <b>Task Reward Added!</b>\n\n"
                f"{pe('task')} {task['title']}\n"
                f"{pe('coins')} +₹{reward} added to your balance!"
            )
        except:
            pass
    except ValueError as e:
        safe_send(chat_id, f"{pe('cross')} Invalid format: {e}")
    except Exception as e:
        safe_send(chat_id, f"{pe('cross')} Error: {e}")


def handle_db_raw_query(chat_id, text):
    try:
        query = text.strip()
        query_upper = query.upper().strip()

        # Safety check - only super admin can do this
        # Check if SELECT query
        if query_upper.startswith("SELECT"):
            results = db_execute(query, fetch=True)
            if not results:
                safe_send(chat_id, f"{pe('info')} Query returned no results.")
                return
            # Format results
            output = f"{pe('database')} <b>Query Results ({len(results)} rows)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, row in enumerate(results[:20], 1):
                output += f"<b>Row {i}:</b>\n"
                for key in row.keys():
                    val = str(row[key])
                    if len(val) > 50:
                        val = val[:50] + "..."
                    output += f"  {key}: <code>{val}</code>\n"
                output += "\n"
                if len(output) > 3500:
                    output += f"\n...(showing first {i} of {len(results)} rows)"
                    break
            safe_send(chat_id, output)
        else:
            # Non-SELECT query
            with DB_LOCK:
                conn = get_db()
                try:
                    c = conn.cursor()
                    c.execute(query)
                    affected = c.rowcount
                    conn.commit()
                    log_admin_action(ADMIN_ID, "raw_sql", f"Executed: {query[:100]}")
                    safe_send(
                        chat_id,
                        f"{pe('check')} <b>Query Executed!</b>\n\n"
                        f"{pe('info')} Affected rows: <b>{affected}</b>\n\n"
                        f"{pe('pencil')} Query:\n<code>{query[:200]}</code>"
                    )
                except Exception as e:
                    conn.rollback()
                    safe_send(chat_id, f"{pe('cross')} Query error: {e}")
                finally:
                    conn.close()
    except Exception as e:
        safe_send(chat_id, f"{pe('cross')} Error executing query: {e}")


def handle_db_search_user(chat_id, text):
    query = text.strip()
    results = []

    # Try by user ID first
    try:
        uid = int(query)
        user = get_user(uid)
        if user:
            results = [user]
    except ValueError:
        pass

    # Try by username
    if not results:
        rows = db_execute(
            "SELECT * FROM users WHERE username LIKE ? LIMIT 10",
            (f"%{query}%",), fetch=True
        )
        if rows:
            results = list(rows)

    # Try by first name
    if not results:
        rows = db_execute(
            "SELECT * FROM users WHERE first_name LIKE ? LIMIT 10",
            (f"%{query}%",), fetch=True
        )
        if rows:
            results = list(rows)

    if not results:
        safe_send(
            chat_id,
            f"{pe('cross')} No users found for: <code>{query}</code>"
        )
        return

    safe_send(
        chat_id,
        f"{pe('search')} <b>Search Results ({len(results)} found)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    for u in results[:10]:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("👤 Full Info", callback_data=f"uinfo|{u['user_id']}"),
            types.InlineKeyboardButton("✏️ Edit", callback_data=f"db_edit_u|{u['user_id']}"),
        )
        markup.add(
            types.InlineKeyboardButton("💰 Add Balance", callback_data=f"addb|{u['user_id']}"),
            types.InlineKeyboardButton("🗑 Delete", callback_data=f"del_user|{u['user_id']}"),
        )
        ban_status = "🔴 Banned" if u["banned"] else "🟢 Active"
        safe_send(
            chat_id,
            f"{pe('disguise')} <b>{u['first_name']}</b> | @{u['username'] or 'none'}\n"
            f"{pe('info')} ID: <code>{u['user_id']}</code>\n"
            f"{pe('fly_money')} Balance: ₹{u['balance']:.2f}\n"
            f"{pe('chart_up')} Earned: ₹{u['total_earned']:.2f}\n"
            f"{pe('thumbs_up')} Refs: {u['referral_count']}\n"
            f"Status: {ban_status}\n"
            f"Joined: {u['joined_at'][:10]}",
            reply_markup=markup
        )


def handle_db_delete_user(chat_id, text):
    try:
        user_id = int(text.strip())
    except ValueError:
        safe_send(chat_id, f"{pe('cross')} Enter a valid User ID!")
        return

    user = get_user(user_id)
    if not user:
        safe_send(chat_id, f"{pe('cross')} User <code>{user_id}</code> not found!")
        return

    if int(user_id) == int(ADMIN_ID):
        safe_send(chat_id, f"{pe('cross')} Cannot delete main admin!")
        return

    # Count related records
    wd_count = db_execute("SELECT COUNT(*) as c FROM withdrawals WHERE user_id=?", (user_id,), fetchone=True)
    comp_count = db_execute("SELECT COUNT(*) as c FROM task_completions WHERE user_id=?", (user_id,), fetchone=True)
    sub_count = db_execute("SELECT COUNT(*) as c FROM task_submissions WHERE user_id=?", (user_id,), fetchone=True)
    claim_count = db_execute("SELECT COUNT(*) as c FROM gift_claims WHERE user_id=?", (user_id,), fetchone=True)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes, Delete ALL", callback_data=f"confirm_del_user|{user_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    safe_send(
        chat_id,
        f"{pe('warning')} <b>Confirm Delete User</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('disguise')} Name: {user['first_name']}\n"
        f"{pe('info')} ID: <code>{user_id}</code>\n"
        f"{pe('fly_money')} Balance: ₹{user['balance']:.2f}\n\n"
        f"{pe('trash')} <b>Will also delete:</b>\n"
        f"  💳 {wd_count['c']} withdrawal(s)\n"
        f"  ✅ {comp_count['c']} task completion(s)\n"
        f"  📤 {sub_count['c']} task submission(s)\n"
        f"  🎁 {claim_count['c']} gift claim(s)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=markup
    )


def handle_db_delete_withdrawal(chat_id, text):
    try:
        wd_id = int(text.strip())
    except ValueError:
        safe_send(chat_id, f"{pe('cross')} Enter a valid Withdrawal ID!")
        return

    wd = db_execute("SELECT * FROM withdrawals WHERE id=?", (wd_id,), fetchone=True)
    if not wd:
        safe_send(chat_id, f"{pe('cross')} Withdrawal #{wd_id} not found!")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_del_wd|{wd_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    u = get_user(wd["user_id"])
    name = u["first_name"] if u else "Unknown"
    safe_send(
        chat_id,
        f"{pe('warning')} <b>Confirm Delete Withdrawal</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('info')} WD ID: #{wd_id}\n"
        f"{pe('disguise')} User: {name} (<code>{wd['user_id']}</code>)\n"
        f"{pe('fly_money')} Amount: ₹{wd['amount']}\n"
        f"{pe('link')} UPI: {wd['upi_id']}\n"
        f"{pe('check')} Status: {wd['status']}\n\n"
        f"{pe('warning')} This only deletes the record!\n"
        f"Balance will NOT be changed.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=markup
    )


def handle_db_edit_task(chat_id, text, data):
    task_id = data.get("task_id")
    if not task_id:
        safe_send(chat_id, f"{pe('cross')} No task ID found!")
        return
    allowed_fields = [
        "title", "description", "reward", "task_type", "task_url",
        "task_channel", "status", "max_completions", "category", "image_url", "order_num"
    ]
    try:
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            safe_send(chat_id, f"{pe('cross')} Format: <code>FIELD VALUE</code>")
            return
        field = parts[0].lower()
        value = parts[1]

        if field not in allowed_fields:
            safe_send(
                chat_id,
                f"{pe('cross')} Invalid field!\nAllowed: {', '.join(allowed_fields)}"
            )
            return

        if field in ["reward"]:
            value = float(value)
        elif field in ["max_completions", "order_num", "is_repeatable"]:
            value = int(value)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_execute(f"UPDATE tasks SET {field}=?, updated_at=? WHERE id=?", (value, now, task_id))
        log_admin_action(ADMIN_ID, "db_edit_task", f"Edited task #{task_id}.{field}={value}")
        safe_send(chat_id, f"{pe('check')} Task #{task_id} field <b>{field}</b> updated to: <code>{value}</code>")
        task = get_task(task_id)
        if task:
            show_admin_task_detail(chat_id, task)
    except ValueError as e:
        safe_send(chat_id, f"{pe('cross')} Invalid value: {e}")
    except Exception as e:
        safe_send(chat_id, f"{pe('cross')} Error: {e}")


# ======================== CONFIRM DELETE WITHDRAWAL ========================
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_del_wd|"))
def confirm_del_wd(call):
    if not is_admin(call.from_user.id):
        safe_answer(call, "Not authorized!", True)
        return
    try:
        wd_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    wd = db_execute("SELECT * FROM withdrawals WHERE id=?", (wd_id,), fetchone=True)
    if not wd:
        safe_answer(call, "Not found!", True)
        return
    db_execute("DELETE FROM withdrawals WHERE id=?", (wd_id,))
    log_admin_action(call.from_user.id, "delete_wd", f"Deleted withdrawal #{wd_id}")
    safe_answer(call, "✅ Deleted!")
    safe_send(
        call.message.chat.id,
        f"{pe('check')} Withdrawal #{wd_id} deleted!\n\n"
        f"{pe('info')} Balance was NOT changed."
    )


# ======================== SEARCH GIFT CODE STATE ========================
# Handle the gift code search state in universal handler
@bot.message_handler(
    content_types=["text"],
    func=lambda m: get_state(m.from_user.id) == "db_search_gift_code" and is_admin(m.from_user.id)
)
def handle_gift_code_search(message):
    code = message.text.strip().upper()
    clear_state(message.from_user.id)
    gift = db_execute("SELECT * FROM gift_codes WHERE code=?", (code,), fetchone=True)
    if not gift:
        safe_send(message.chat.id, f"{pe('cross')} Gift code <code>{code}</code> not found!")
        return
    claims = db_execute(
        "SELECT gc.*, u.first_name FROM gift_claims gc "
        "LEFT JOIN users u ON gc.user_id=u.user_id "
        "WHERE gc.code=? ORDER BY gc.claimed_at DESC",
        (code,), fetch=True
    ) or []
    active = "🟢 Active" if gift["is_active"] else "🔴 Inactive"
    text = (
        f"{pe('star')} <b>Gift Code Details</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('info')} Code: <code>{gift['code']}</code>\n"
        f"{pe('money')} Amount: ₹{gift['amount']}\n"
        f"{pe('thumbs_up')} Claims: {gift['total_claims']}/{gift['max_claims']}\n"
        f"{pe('tag')} Type: {gift['gift_type']}\n"
        f"Status: {active}\n"
        f"{pe('disguise')} Created by: <code>{gift['created_by']}</code>\n"
        f"{pe('calendar')} Created: {gift['created_at']}\n\n"
    )
    if claims:
        text += f"{pe('list')} <b>Claims ({len(claims)}):</b>\n"
        for c in claims[:10]:
            name = c["first_name"] if c["first_name"] else "Unknown"
            text += f"  {pe('arrow')} {name} (<code>{c['user_id']}</code>) — {c['claimed_at'][:10]}\n"
    markup = types.InlineKeyboardMarkup(row_width=2)
    if gift["is_active"]:
        markup.add(
            types.InlineKeyboardButton(
                "🔴 Deactivate",
                callback_data=f"gift_toggle|{gift['code']}|0"
            )
        )
    else:
        markup.add(
            types.InlineKeyboardButton(
                "🟢 Activate",
                callback_data=f"gift_toggle|{gift['code']}|1"
            )
        )
    markup.add(
        types.InlineKeyboardButton(
            "🗑 Delete Code",
            callback_data=f"gift_delete|{gift['code']}"
        )
    )
    safe_send(message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("gift_toggle|"))
def gift_toggle(call):
    if not is_admin(call.from_user.id): return
    try:
        parts = call.data.split("|")
        code = parts[1]
        new_status = int(parts[2])
    except:
        safe_answer(call, "Error!", True)
        return
    db_execute("UPDATE gift_codes SET is_active=? WHERE code=?", (new_status, code))
    status_text = "Activated" if new_status else "Deactivated"
    log_admin_action(call.from_user.id, f"gift_{status_text.lower()}", f"Code {code}")
    safe_answer(call, f"✅ Code {status_text}!")
    safe_send(call.message.chat.id, f"{pe('check')} Gift code <code>{code}</code> {status_text}!")


@bot.callback_query_handler(func=lambda call: call.data.startswith("gift_delete|"))
def gift_delete(call):
    if not is_admin(call.from_user.id): return
    try:
        code = call.data.split("|")[1]
    except:
        safe_answer(call, "Error!", True)
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes Delete", callback_data=f"gift_confirm_delete|{code}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    safe_answer(call)
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} Delete gift code <code>{code}</code>?",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("gift_confirm_delete|"))
def gift_confirm_delete(call):
    if not is_admin(call.from_user.id): return
    try:
        code = call.data.split("|")[1]
    except:
        safe_answer(call, "Error!", True)
        return
    db_execute("DELETE FROM gift_codes WHERE code=?", (code,))
    db_execute("DELETE FROM gift_claims WHERE code=?", (code,))
    log_admin_action(call.from_user.id, "delete_gift", f"Deleted gift code {code}")
    safe_answer(call, "✅ Deleted!")
    safe_send(call.message.chat.id, f"{pe('check')} Gift code <code>{code}</code> deleted!")


