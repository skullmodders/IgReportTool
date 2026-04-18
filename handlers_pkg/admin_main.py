from core import *

# ======================== ADMIN PANEL ========================
@bot.message_handler(commands=["admin", "panel"])
def admin_cmd(message):
    if not is_admin(message.from_user.id):
        safe_send(message.chat.id, f"{pe('no_entry')} Access Denied!")
        return
    safe_send(
        message.chat.id,
        f"{pe('crown')} <b>Admin Panel</b> {pe('gear')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Welcome, Admin! Use the keyboard below.",
        reply_markup=get_admin_keyboard()
    )


# ======================== ADMIN DASHBOARD ========================
@bot.message_handler(func=lambda m: m.text == "📊 Dashboard" and is_admin(m.from_user.id))
def admin_dashboard(message):
    show_dashboard(message.chat.id)


def show_dashboard(chat_id):
    total_users = get_user_count()
    total_withdrawn = get_total_withdrawn()
    total_refs = get_total_referrals()
    pending = get_total_pending()
    today = datetime.now().strftime("%Y-%m-%d")
    banned = db_execute("SELECT COUNT(*) as cnt FROM users WHERE banned=1", fetchone=True)
    total_bal = db_execute("SELECT SUM(balance) as t FROM users", fetchone=True)
    today_users = db_execute(
        "SELECT COUNT(*) as cnt FROM users WHERE joined_at LIKE ?",
        (f"{today}%",), fetchone=True
    )
    today_wd = db_execute(
        "SELECT COUNT(*) as cnt, SUM(amount) as t FROM withdrawals "
        "WHERE status='approved' AND processed_at LIKE ?",
        (f"{today}%",), fetchone=True
    )
    active_gifts = db_execute(
        "SELECT COUNT(*) as cnt FROM gift_codes WHERE is_active=1", fetchone=True
    )
    active_tasks = db_execute(
        "SELECT COUNT(*) as cnt FROM tasks WHERE status='active'", fetchone=True
    )
    pending_task_subs = db_execute(
        "SELECT COUNT(*) as cnt FROM task_submissions WHERE status='pending'", fetchone=True
    )
    total_task_comp = db_execute(
        "SELECT COUNT(*) as cnt FROM task_completions", fetchone=True
    )
    total_task_paid = db_execute(
        "SELECT SUM(reward_paid) as t FROM task_completions", fetchone=True
    )
    total_admins = db_execute(
        "SELECT COUNT(*) as cnt FROM admins WHERE is_active=1", fetchone=True
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 Refresh", callback_data="dash_refresh"),
        types.InlineKeyboardButton("🔍 User Lookup", callback_data="dash_user_lookup"),
    )
    markup.add(
        types.InlineKeyboardButton("📥 Export CSV", callback_data="dash_export"),
        types.InlineKeyboardButton("🗑 Clear Pending", callback_data="dash_clear_pending"),
    )
    markup.add(
        types.InlineKeyboardButton(
            f"📋 Task Subs ({pending_task_subs['cnt']})",
            callback_data="admin_task_pending_subs"
        ),
        types.InlineKeyboardButton("📜 Admin Logs", callback_data="view_admin_logs"),
    )
    safe_send(
        chat_id,
        f"{pe('chart')} <b>Admin Dashboard</b> {pe('crown')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('thumbs_up')} <b>Total Users:</b> {total_users}\n"
        f"{pe('new_tag')} <b>Today's Joins:</b> {today_users['cnt']}\n"
        f"{pe('no_entry')} <b>Banned:</b> {banned['cnt']}\n"
        f"{pe('admin')} <b>Total Admins:</b> {total_admins['cnt']}\n\n"
        f"{pe('chart_up')} <b>Total Referrals:</b> {total_refs}\n"
        f"{pe('fly_money')} <b>All Users Balance:</b> ₹{total_bal['t'] or 0:.2f}\n\n"
        f"{pe('check')} <b>Total Withdrawn:</b> ₹{total_withdrawn:.2f}\n"
        f"{pe('hourglass')} <b>Pending WDs:</b> {pending}\n"
        f"{pe('calendar')} <b>Today Approved:</b> {today_wd['cnt']} "
        f"(₹{today_wd['t'] or 0:.2f})\n\n"
        f"{pe('party')} <b>Active Gift Codes:</b> {active_gifts['cnt']}\n\n"
        f"{pe('rocket')} <b>═══ Task Stats ═══</b>\n"
        f"{pe('active')} <b>Active Tasks:</b> {active_tasks['cnt']}\n"
        f"{pe('pending2')} <b>Pending Submissions:</b> {pending_task_subs['cnt']}\n"
        f"{pe('trophy')} <b>Total Completions:</b> {total_task_comp['cnt']}\n"
        f"{pe('coins')} <b>Total Task Paid:</b> ₹{total_task_paid['t'] or 0:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "dash_refresh")
def dash_refresh(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call, "Refreshed!")
    show_dashboard(call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "dash_user_lookup")
def dash_user_lookup(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "admin_user_info")
    safe_send(call.message.chat.id, f"{pe('pencil')} Enter User ID:")


@bot.callback_query_handler(func=lambda call: call.data == "dash_export")
def dash_export(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call, "Generating CSV...")
    users = get_all_users()
    if not users:
        safe_send(call.message.chat.id, "No users!")
        return
    lines = ["ID,Username,Name,Balance,Earned,Withdrawn,Referrals,Banned,Joined\n"]
    for u in users:
        lines.append(
            f"{u['user_id']},{u['username']},{u['first_name']},"
            f"{u['balance']},{u['total_earned']},{u['total_withdrawn']},"
            f"{u['referral_count']},{u['banned']},{u['joined_at']}\n"
        )
    filename = "users_export.csv"
    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(lines)
    with open(filename, "rb") as f:
        bot.send_document(
            call.message.chat.id, f,
            caption=f"{pe('check')} Exported {len(users)} users",
            parse_mode="HTML"
        )
    os.remove(filename)
    log_admin_action(call.from_user.id, "export_csv", f"Exported {len(users)} users")


@bot.callback_query_handler(func=lambda call: call.data == "dash_clear_pending")
def dash_clear_pending(call):
    if not is_admin(call.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes, Reject All", callback_data="confirm_clear_pending"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")
    )
    safe_answer(call)
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} <b>Reject ALL pending withdrawals?</b>\n(Balances will be refunded)",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "confirm_clear_pending")
def confirm_clear_pending(call):
    if not is_admin(call.from_user.id): return
    pending = db_execute("SELECT * FROM withdrawals WHERE status='pending'", fetch=True) or []
    for w in pending:
        u = get_user(w["user_id"])
        if u:
            update_user(w["user_id"], balance=u["balance"] + w["amount"])
    db_execute("UPDATE withdrawals SET status='rejected' WHERE status='pending'")
    log_admin_action(call.from_user.id, "clear_pending", f"Cleared {len(pending)} pending WDs")
    safe_answer(call, f"✅ {len(pending)} rejected!")
    safe_send(call.message.chat.id, f"{pe('check')} Cleared {len(pending)} pending withdrawals (all refunded).")


@bot.callback_query_handler(func=lambda call: call.data == "cancel_action")
def cancel_action(call):
    safe_answer(call, "Cancelled!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass


@bot.callback_query_handler(func=lambda call: call.data == "view_admin_logs")
def view_admin_logs(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    logs = get_admin_logs(30)
    if not logs:
        safe_send(call.message.chat.id, f"{pe('info')} No admin logs yet!")
        return
    text = f"{pe('list')} <b>Recent Admin Logs (30)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for log in logs:
        text += (
            f"{pe('arrow')} <b>{log['action']}</b>\n"
            f"   Admin: <code>{log['admin_id']}</code>\n"
            f"   {log['details']}\n"
            f"   🕐 {log['created_at']}\n\n"
        )
    # Split if too long
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    safe_send(call.message.chat.id, text)


# ======================== ADMIN ALL USERS ========================
@bot.message_handler(func=lambda m: m.text == "👥 All Users" and is_admin(m.from_user.id))
def admin_all_users(message):
    total = get_user_count()
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 Find User", callback_data="dash_user_lookup"),
        types.InlineKeyboardButton("🏆 Top Referrers", callback_data="top_referrers"),
    )
    markup.add(
        types.InlineKeyboardButton("💰 Top Balance", callback_data="top_balance"),
        types.InlineKeyboardButton("🆕 Recent Users", callback_data="recent_users"),
    )
    markup.add(
        types.InlineKeyboardButton("🚫 Banned List", callback_data="banned_list"),
        types.InlineKeyboardButton("📥 Export All", callback_data="dash_export"),
    )
    markup.add(
        types.InlineKeyboardButton("🏆 Top Task Earners", callback_data="top_task_earners"),
        types.InlineKeyboardButton("🔍 Search by Name", callback_data="search_by_name"),
    )
    markup.add(
        types.InlineKeyboardButton("📊 User Statistics", callback_data="user_statistics"),
    )
    safe_send(
        message.chat.id,
        f"{pe('thumbs_up')} <b>User Management</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('chart')} <b>Total Users:</b> {total}",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "search_by_name")
def search_by_name(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_search_user")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Search User</b>\n\n"
        f"Enter name, username, or user ID to search:"
    )


@bot.callback_query_handler(func=lambda call: call.data == "user_statistics")
def user_statistics(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    total = get_user_count()
    active = db_execute("SELECT COUNT(*) as c FROM users WHERE banned=0", fetchone=True)
    banned = db_execute("SELECT COUNT(*) as c FROM users WHERE banned=1", fetchone=True)
    with_upi = db_execute("SELECT COUNT(*) as c FROM users WHERE upi_id != ''", fetchone=True)
    with_referrals = db_execute("SELECT COUNT(*) as c FROM users WHERE referral_count > 0", fetchone=True)
    avg_balance = db_execute("SELECT AVG(balance) as a FROM users WHERE banned=0", fetchone=True)
    avg_earned = db_execute("SELECT AVG(total_earned) as a FROM users WHERE banned=0", fetchone=True)
    total_balance = db_execute("SELECT SUM(balance) as s FROM users", fetchone=True)
    premium = db_execute("SELECT COUNT(*) as c FROM users WHERE is_premium=1", fetchone=True)
    today = datetime.now().strftime("%Y-%m-%d")
    today_joined = db_execute(
        "SELECT COUNT(*) as c FROM users WHERE joined_at LIKE ?",
        (f"{today}%",), fetchone=True
    )
    this_week = db_execute(
        "SELECT COUNT(*) as c FROM users WHERE joined_at >= date('now', '-7 days')",
        fetchone=True
    )
    this_month = db_execute(
        "SELECT COUNT(*) as c FROM users WHERE joined_at >= date('now', '-30 days')",
        fetchone=True
    )
    safe_send(
        call.message.chat.id,
        f"{pe('chart')} <b>User Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('thumbs_up')} <b>Total Users:</b> {total}\n"
        f"{pe('green')} <b>Active:</b> {active['c']}\n"
        f"{pe('red')} <b>Banned:</b> {banned['c']}\n"
        f"{pe('star')} <b>Premium:</b> {premium['c']}\n\n"
        f"{pe('calendar')} <b>Growth:</b>\n"
        f"  Today: {today_joined['c']}\n"
        f"  This Week: {this_week['c']}\n"
        f"  This Month: {this_month['c']}\n\n"
        f"{pe('coins')} <b>Balance Stats:</b>\n"
        f"  Total Balance: ₹{total_balance['s'] or 0:.2f}\n"
        f"  Avg Balance: ₹{avg_balance['a'] or 0:.2f}\n"
        f"  Avg Earned: ₹{avg_earned['a'] or 0:.2f}\n\n"
        f"{pe('link')} <b>UPI Linked:</b> {with_upi['c']}\n"
        f"{pe('fire')} <b>Active Referrers:</b> {with_referrals['c']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


@bot.callback_query_handler(func=lambda call: call.data == "top_referrers")
def top_referrers(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute("SELECT * FROM users ORDER BY referral_count DESC LIMIT 15", fetch=True) or []
    text = f"{pe('crown')} <b>Top 15 Referrers</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(rows, 1):
        m = medals[i - 1] if i <= 3 else f"{i}."
        text += (
            f"{m} <b>{u['first_name']}</b>\n"
            f"     Refs: {u['referral_count']} | Bal: ₹{u['balance']:.0f}\n"
            f"     ID: <code>{u['user_id']}</code>\n\n"
        )
    safe_send(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "top_balance")
def top_balance(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute("SELECT * FROM users ORDER BY balance DESC LIMIT 15", fetch=True) or []
    text = f"{pe('money')} <b>Top 15 by Balance</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(rows, 1):
        m = medals[i - 1] if i <= 3 else f"{i}."
        text += f"{m} <b>{u['first_name']}</b> — ₹{u['balance']:.2f}\n     ID: <code>{u['user_id']}</code>\n\n"
    safe_send(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "recent_users")
def recent_users(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute("SELECT * FROM users ORDER BY joined_at DESC LIMIT 15", fetch=True) or []
    text = f"{pe('new_tag')} <b>Recent 15 Users</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for u in rows:
        text += f"{pe('arrow')} <b>{u['first_name']}</b> — <code>{u['user_id']}</code>\n     {u['joined_at']}\n\n"
    safe_send(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "banned_list")
def banned_list(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute("SELECT * FROM users WHERE banned=1", fetch=True) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('check')} No banned users!")
        return
    text = f"{pe('no_entry')} <b>Banned Users</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for u in rows:
        text += f"{pe('red')} {u['first_name']} — <code>{u['user_id']}</code>\n"
    safe_send(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "top_task_earners")
def top_task_earners(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT user_id, SUM(reward_paid) as total_earned, COUNT(*) as total_tasks "
        "FROM task_completions GROUP BY user_id ORDER BY total_earned DESC LIMIT 15",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} No task completions yet!")
        return
    text = f"{pe('trophy')} <b>Top 15 Task Earners</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows, 1):
        m = medals[i - 1] if i <= 3 else f"{i}."
        user = get_user(r["user_id"])
        name = user["first_name"] if user else "Unknown"
        text += (
            f"{m} <b>{name}</b>\n"
            f"     Tasks: {r['total_tasks']} | Earned: ₹{r['total_earned']:.2f}\n"
            f"     ID: <code>{r['user_id']}</code>\n\n"
        )
    safe_send(call.message.chat.id, text)


# ======================== ADMIN WITHDRAWALS ========================
@bot.message_handler(func=lambda m: m.text == "💳 Withdrawals" and is_admin(m.from_user.id))
def admin_withdrawals(message):
    pending_count = get_total_pending()
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"📋 Pending ({pending_count})", callback_data="wdlist_pending"),
        types.InlineKeyboardButton("✅ Approved", callback_data="wdlist_approved"),
    )
    markup.add(
        types.InlineKeyboardButton("❌ Rejected", callback_data="wdlist_rejected"),
        types.InlineKeyboardButton("📊 WD Stats", callback_data="wd_stats"),
    )
    markup.add(
        types.InlineKeyboardButton("✅ Approve ALL Pending", callback_data="approve_all_pending"),
        types.InlineKeyboardButton("🔍 Search WD", callback_data="search_withdrawal"),
    )
    markup.add(
        types.InlineKeyboardButton("➕ Add Manual WD", callback_data="add_manual_wd"),
    )
    safe_send(
        message.chat.id,
        f"{pe('fly_money')} <b>Withdrawal Management</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('hourglass')} <b>Pending:</b> {pending_count}",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "add_manual_wd")
def add_manual_wd(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_add_withdrawal")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Add Manual Withdrawal Record</b>\n\n"
        f"Format:\n"
        f"<code>USER_ID AMOUNT UPI_ID STATUS</code>\n\n"
        f"Status options: pending, approved, rejected\n\n"
        f"Example:\n"
        f"<code>123456789 100 name@paytm approved</code>"
    )


@bot.callback_query_handler(func=lambda call: call.data == "search_withdrawal")
def search_withdrawal(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Search Withdrawal</b>\n\n"
        f"Enter User ID to see their withdrawals:"
    )
    set_state(call.from_user.id, "admin_user_info")


@bot.callback_query_handler(func=lambda call: call.data == "wdlist_pending")
def wdlist_pending(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM withdrawals WHERE status='pending' ORDER BY created_at DESC LIMIT 20",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('check')} No pending withdrawals!")
        return
    for w in rows:
        u = get_user(w["user_id"])
        name = u["first_name"] if u else "Unknown"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"apprv|{w['id']}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rejct|{w['id']}"),
        )
        markup.add(types.InlineKeyboardButton("👤 Info", callback_data=f"uinfo|{w['user_id']}"))
        safe_send(
            call.message.chat.id,
            f"{pe('hourglass')} <b>Pending #{w['id']}</b>\n\n"
            f"{pe('disguise')} {name} (<code>{w['user_id']}</code>)\n"
            f"{pe('fly_money')} ₹{w['amount']}\n"
            f"{pe('link')} <code>{w['upi_id']}</code>\n"
            f"{pe('calendar')} {w['created_at']}",
            reply_markup=markup
        )


@bot.callback_query_handler(func=lambda call: call.data == "wdlist_approved")
def wdlist_approved(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM withdrawals WHERE status='approved' ORDER BY processed_at DESC LIMIT 15",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, "No approved withdrawals yet!")
        return
    text = f"{pe('check')} <b>Recent Approved</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for w in rows:
        u = get_user(w["user_id"])
        name = u["first_name"] if u else "Unknown"
        text += f"#{w['id']} | {name} | ₹{w['amount']} | {w['processed_at']}\n"
    safe_send(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "wdlist_rejected")
def wdlist_rejected(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM withdrawals WHERE status='rejected' ORDER BY processed_at DESC LIMIT 15",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, "No rejected withdrawals!")
        return
    text = f"{pe('cross')} <b>Recent Rejected</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for w in rows:
        u = get_user(w["user_id"])
        name = u["first_name"] if u else "Unknown"
        text += f"#{w['id']} | {name} | ₹{w['amount']} | {w['processed_at']}\n"
    safe_send(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "wd_stats")
def wd_stats(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    a = db_execute("SELECT COUNT(*) as c, SUM(amount) as s FROM withdrawals WHERE status='approved'", fetchone=True)
    r = db_execute("SELECT COUNT(*) as c, SUM(amount) as s FROM withdrawals WHERE status='rejected'", fetchone=True)
    p = db_execute("SELECT COUNT(*) as c, SUM(amount) as s FROM withdrawals WHERE status='pending'", fetchone=True)
    today = datetime.now().strftime("%Y-%m-%d")
    td = db_execute(
        "SELECT COUNT(*) as c, SUM(amount) as s FROM withdrawals "
        "WHERE status='approved' AND processed_at LIKE ?",
        (f"{today}%",), fetchone=True
    )
    avg_wd = db_execute("SELECT AVG(amount) as a FROM withdrawals WHERE status='approved'", fetchone=True)
    max_wd = db_execute("SELECT MAX(amount) as m FROM withdrawals WHERE status='approved'", fetchone=True)
    min_wd = db_execute("SELECT MIN(amount) as m FROM withdrawals WHERE status='approved' AND amount > 0", fetchone=True)
    safe_send(
        call.message.chat.id,
        f"{pe('chart')} <b>Withdrawal Stats</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('check')} Approved: {a['c']} (₹{a['s'] or 0:.2f})\n"
        f"{pe('cross')} Rejected: {r['c']} (₹{r['s'] or 0:.2f})\n"
        f"{pe('hourglass')} Pending: {p['c']} (₹{p['s'] or 0:.2f})\n\n"
        f"{pe('calendar')} Today Approved: {td['c']} (₹{td['s'] or 0:.2f})\n\n"
        f"{pe('chart_up')} Avg WD: ₹{avg_wd['a'] or 0:.2f}\n"
        f"{pe('up')} Max WD: ₹{max_wd['m'] or 0:.2f}\n"
        f"{pe('down')} Min WD: ₹{min_wd['m'] or 0:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


@bot.callback_query_handler(func=lambda call: call.data == "approve_all_pending")
def approve_all_pending(call):
    if not is_admin(call.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes, Approve All", callback_data="confirm_approve_all"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    safe_answer(call)
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} <b>Approve ALL pending withdrawals?</b>",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "confirm_approve_all")
def confirm_approve_all(call):
    if not is_admin(call.from_user.id): return
    rows = db_execute("SELECT * FROM withdrawals WHERE status='pending'", fetch=True) or []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = 0
    for w in rows:
        txn = generate_txn_id()
        db_execute(
            "UPDATE withdrawals SET status='approved', processed_at=?, txn_id=? WHERE id=?",
            (now, txn, w["id"])
        )
        u = get_user(w["user_id"])
        if u:
            update_user(w["user_id"], total_withdrawn=u["total_withdrawn"] + w["amount"])
        try:
            safe_send(
                w["user_id"],
                f"{pe('party')} <b>Withdrawal Approved!</b>\n₹{w['amount']} | TXN: <code>{txn}</code>"
            )
        except:
            pass
        send_public_withdrawal_notification(w["user_id"], w["amount"], w["upi_id"], "approved", txn)
        count += 1
    log_admin_action(call.from_user.id, "approve_all", f"Approved {count} withdrawals")
    safe_answer(call, f"✅ Approved {count}!")
    safe_send(call.message.chat.id, f"{pe('check')} Approved {count} withdrawals!")


# ======================== ADMIN SETTINGS ========================
@bot.message_handler(func=lambda m: m.text == "⚙️ Settings" and is_admin(m.from_user.id))
def admin_settings(message):
    show_settings(message.chat.id)


def show_settings(chat_id):
    pr = get_setting("per_refer")
    mw = get_setting("min_withdraw")
    wb = get_setting("welcome_bonus")
    db_val = get_setting("daily_bonus")
    mx = get_setting("max_withdraw_per_day")
    ws = get_setting("withdraw_time_start")
    we = get_setting("withdraw_time_end")
    wd_en = get_setting("withdraw_enabled")
    rf_en = get_setting("refer_enabled")
    gf_en = get_setting("gift_enabled")
    mn = get_setting("bot_maintenance")
    tk_en = get_setting("tasks_enabled")
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"💰 Per Refer: ₹{pr}", callback_data="s_per_refer"),
        types.InlineKeyboardButton(f"📉 Min WD: ₹{mw}", callback_data="s_min_wd"),
    )
    markup.add(
        types.InlineKeyboardButton(f"🎉 Welcome: ₹{wb}", callback_data="s_welcome"),
        types.InlineKeyboardButton(f"📅 Daily: ₹{db_val}", callback_data="s_daily"),
    )
    markup.add(
        types.InlineKeyboardButton(f"📈 Max WD: ₹{mx}", callback_data="s_max_wd"),
        types.InlineKeyboardButton(f"⏰ Time: {ws}-{we}h", callback_data="s_wd_time"),
    )
    markup.add(
        types.InlineKeyboardButton(f"{'🟢' if wd_en else '🔴'} Withdraw", callback_data="tog_withdraw"),
        types.InlineKeyboardButton(f"{'🟢' if rf_en else '🔴'} Refer", callback_data="tog_refer"),
    )
    markup.add(
        types.InlineKeyboardButton(f"{'🟢' if gf_en else '🔴'} Gift", callback_data="tog_gift"),
        types.InlineKeyboardButton(f"{'🟢' if tk_en else '🔴'} Tasks", callback_data="tog_tasks"),
    )
    markup.add(
        types.InlineKeyboardButton(
            f"{'🔴 Maintenance ON' if mn else '🟢 Maintenance OFF'}",
            callback_data="tog_maintenance"
        ),
    )
    markup.add(
        types.InlineKeyboardButton("🖼 Welcome Image", callback_data="s_welcome_img"),
        types.InlineKeyboardButton("🖼 Withdraw Image", callback_data="s_wd_img"),
    )
    markup.add(
        types.InlineKeyboardButton("🚫 Ban User", callback_data="s_ban"),
        types.InlineKeyboardButton("✅ Unban User", callback_data="s_unban"),
    )
    markup.add(
        types.InlineKeyboardButton("🔄 Reset User", callback_data="s_reset_user"),
        types.InlineKeyboardButton("💰 Add Balance", callback_data="s_add_bal"),
    )
    markup.add(
        types.InlineKeyboardButton("💸 Deduct Balance", callback_data="s_deduct_bal"),
        types.InlineKeyboardButton("👤 User Info", callback_data="dash_user_lookup"),
    )
    markup.add(
        types.InlineKeyboardButton("🧠 Advanced Settings", callback_data="open_advanced_settings"),
        types.InlineKeyboardButton("🗑 RESET ALL DATA", callback_data="s_reset_all"),
    )
    safe_send(
        chat_id,
        f"{pe('gear')} <b>Bot Settings</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 = Enabled | 🔴 = Disabled\n"
        f"Tap to change any setting.",
        reply_markup=markup
    )


def settings_ask(call, state, prompt):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, state)
    safe_send(call.message.chat.id, prompt)


@bot.callback_query_handler(func=lambda call: call.data == "s_per_refer")
def s_per_refer(call):
    settings_ask(call, "admin_set_per_refer", f"{pe('pencil')} Enter new Per Refer amount (₹):")

@bot.callback_query_handler(func=lambda call: call.data == "s_min_wd")
def s_min_wd(call):
    settings_ask(call, "admin_set_min_withdraw", f"{pe('pencil')} Enter new Min Withdraw (₹):")

@bot.callback_query_handler(func=lambda call: call.data == "s_welcome")
def s_welcome(call):
    settings_ask(call, "admin_set_welcome_bonus", f"{pe('pencil')} Enter new Welcome Bonus (₹):")

@bot.callback_query_handler(func=lambda call: call.data == "s_daily")
def s_daily(call):
    settings_ask(call, "admin_set_daily_bonus", f"{pe('pencil')} Enter new Daily Bonus (₹):")

@bot.callback_query_handler(func=lambda call: call.data == "s_max_wd")
def s_max_wd(call):
    settings_ask(call, "admin_set_max_withdraw", f"{pe('pencil')} Enter new Max Withdraw Per Day (₹):")

@bot.callback_query_handler(func=lambda call: call.data == "s_wd_time")
def s_wd_time(call):
    settings_ask(
        call, "admin_set_withdraw_time",
        f"{pe('pencil')} Enter withdraw time range:\nFormat: <code>START-END</code>\nExample: <code>10-18</code>"
    )

@bot.callback_query_handler(func=lambda call: call.data == "s_welcome_img")
def s_welcome_img(call):
    settings_ask(call, "admin_set_welcome_image", f"{pe('pencil')} Send new Welcome Image URL:")

@bot.callback_query_handler(func=lambda call: call.data == "s_wd_img")
def s_wd_img(call):
    settings_ask(call, "admin_set_withdraw_image", f"{pe('pencil')} Send new Withdraw Image URL:")

@bot.callback_query_handler(func=lambda call: call.data == "s_ban")
def s_ban(call):
    settings_ask(call, "admin_ban_user", f"{pe('pencil')} Enter User ID to ban:")

@bot.callback_query_handler(func=lambda call: call.data == "s_unban")
def s_unban(call):
    settings_ask(call, "admin_unban_user", f"{pe('pencil')} Enter User ID to unban:")

@bot.callback_query_handler(func=lambda call: call.data == "s_reset_user")
def s_reset_user(call):
    settings_ask(call, "admin_reset_user", f"{pe('pencil')} Enter User ID to reset:")

@bot.callback_query_handler(func=lambda call: call.data == "s_add_bal")
def s_add_bal(call):
    settings_ask(call, "admin_add_balance", f"{pe('pencil')} Format: <code>USER_ID AMOUNT</code>")

@bot.callback_query_handler(func=lambda call: call.data == "s_deduct_bal")
def s_deduct_bal(call):
    settings_ask(call, "admin_deduct_balance", f"{pe('pencil')} Format: <code>USER_ID AMOUNT</code>")

@bot.callback_query_handler(func=lambda call: call.data == "tog_withdraw")
def tog_withdraw(call):
    if not is_admin(call.from_user.id): return
    cur = get_setting("withdraw_enabled")
    set_setting("withdraw_enabled", not cur)
    safe_answer(call, f"Withdraw {'Enabled' if not cur else 'Disabled'}!")
    show_settings(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "tog_refer")
def tog_refer(call):
    if not is_admin(call.from_user.id): return
    cur = get_setting("refer_enabled")
    set_setting("refer_enabled", not cur)
    safe_answer(call, f"Refer {'Enabled' if not cur else 'Disabled'}!")
    show_settings(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "tog_gift")
def tog_gift(call):
    if not is_admin(call.from_user.id): return
    cur = get_setting("gift_enabled")
    set_setting("gift_enabled", not cur)
    safe_answer(call, f"Gift {'Enabled' if not cur else 'Disabled'}!")
    show_settings(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "tog_tasks")
def tog_tasks(call):
    if not is_admin(call.from_user.id): return
    cur = get_setting("tasks_enabled")
    set_setting("tasks_enabled", not cur)
    safe_answer(call, f"Tasks {'Enabled' if not cur else 'Disabled'}!")
    show_settings(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "tog_maintenance")
def tog_maintenance(call):
    if not is_admin(call.from_user.id): return
    cur = get_setting("bot_maintenance")
    set_setting("bot_maintenance", not cur)
    safe_answer(call, f"Maintenance {'ON' if not cur else 'OFF'}!")
    show_settings(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "s_reset_all")
def s_reset_all(call):
    if not is_admin(call.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⚠️ YES RESET EVERYTHING", callback_data="confirm_reset_all"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    safe_answer(call)
    safe_send(
        call.message.chat.id,
        f"{pe('siren')} <b>DANGER!</b>\n\n"
        f"This will DELETE ALL users, withdrawals, gift codes, tasks!\n\n"
        f"<b>Are you 100% sure?</b>",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "confirm_reset_all")
def confirm_reset_all(call):
    if not is_admin(call.from_user.id): return
    db_execute("DELETE FROM users")
    db_execute("DELETE FROM withdrawals")
    db_execute("DELETE FROM gift_codes")
    db_execute("DELETE FROM gift_claims")
    db_execute("DELETE FROM bonus_history")
    db_execute("DELETE FROM broadcasts")
    db_execute("DELETE FROM tasks")
    db_execute("DELETE FROM task_submissions")
    db_execute("DELETE FROM task_completions")
    log_admin_action(call.from_user.id, "reset_all", "Reset ALL bot data")
    safe_answer(call, "✅ All data reset!")
    safe_send(call.message.chat.id, f"{pe('check')} <b>All data has been reset!</b>")


# ======================== ADMIN BROADCAST ========================
@bot.message_handler(func=lambda m: m.text == "📢 Broadcast" and is_admin(m.from_user.id))
def admin_broadcast(message):
    set_state(message.from_user.id, "admin_broadcast")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast"))
    safe_send(
        message.chat.id,
        f"{pe('megaphone')} <b>Broadcast to All Users</b>\n\n"
        f"{pe('pencil')} Type your message below.\n"
        f"{pe('info')} HTML formatting supported.",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "cancel_broadcast")
def cancel_broadcast(call):
    clear_state(call.from_user.id)
    safe_answer(call, "Cancelled!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass


def do_broadcast(text, admin_chat_id):
    users = get_all_users()
    sent = 0
    failed = 0
    for u in users:
        try:
            bot.send_message(u["user_id"], text, parse_mode="HTML")
            sent += 1
        except:
            failed += 1
        time.sleep(0.04)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute(
        "INSERT INTO broadcasts (message, sent_count, failed_count, created_at) VALUES (?,?,?,?)",
        (text, sent, failed, now)
    )
    try:
        safe_send(
            admin_chat_id,
            f"{pe('check')} <b>Broadcast Done!</b>\n\n"
            f"{pe('green')} Sent: {sent}\n"
            f"{pe('red')} Failed: {failed}\n"
            f"{pe('chart')} Total: {sent + failed}"
        )
    except:
        pass


# ======================== ADMIN GIFT MANAGER ========================
@bot.message_handler(func=lambda m: m.text == "🎁 Gift Manager" and is_admin(m.from_user.id))
def admin_gift_manager(message):
    active = db_execute("SELECT COUNT(*) as cnt FROM gift_codes WHERE is_active=1", fetchone=True)
    total = db_execute("SELECT COUNT(*) as cnt FROM gift_codes", fetchone=True)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Create Code", callback_data="gm_create"),
        types.InlineKeyboardButton("📋 Active Codes", callback_data="gm_active"),
    )
    markup.add(
        types.InlineKeyboardButton("📊 Gift Stats", callback_data="gm_stats"),
        types.InlineKeyboardButton("🗑 Delete All", callback_data="gm_delete_all"),
    )
    markup.add(
        types.InlineKeyboardButton("📋 All Codes", callback_data="gm_all_codes"),
        types.InlineKeyboardButton("🔍 Check Code", callback_data="gm_check_code"),
    )
    safe_send(
        message.chat.id,
        f"{pe('party')} <b>Gift Manager</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('green')} Active Codes: {active['cnt']}\n"
        f"{pe('chart')} Total Created: {total['cnt']}",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "gm_create")
def gm_create(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "admin_create_gift")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Create Gift Code</b>\n\n"
        f"Format: <code>AMOUNT MAX_CLAIMS [CUSTOM_CODE]</code>\n\n"
        f"Examples:\n"
        f"<code>50 10</code> — ₹50, 10 uses, random code\n"
        f"<code>100 1 VIP100</code> — ₹100, 1 use, code: VIP100"
    )


@bot.callback_query_handler(func=lambda call: call.data == "gm_active")
def gm_active(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM gift_codes WHERE is_active=1 ORDER BY created_at DESC LIMIT 20",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} No active gift codes!")
        return
    text = f"{pe('party')} <b>Active Gift Codes</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for g in rows:
        text += (
            f"{pe('star')} <code>{g['code']}</code> — ₹{g['amount']}\n"
            f"     Claims: {g['total_claims']}/{g['max_claims']} | Type: {g['gift_type']}\n\n"
        )
    safe_send(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "gm_all_codes")
def gm_all_codes(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM gift_codes ORDER BY created_at DESC LIMIT 30",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} No gift codes found!")
        return
    text = f"{pe('list')} <b>All Gift Codes (Last 30)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for g in rows:
        status = "🟢" if g["is_active"] else "🔴"
        text += (
            f"{status} <code>{g['code']}</code> — ₹{g['amount']}\n"
            f"     {g['total_claims']}/{g['max_claims']} | {g['gift_type']} | {g['created_at'][:10]}\n\n"
        )
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    safe_send(call.message.chat.id, text)


@bot.callback_query_handler(func=lambda call: call.data == "gm_check_code")
def gm_check_code(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_search_gift_code")
    safe_send(call.message.chat.id, f"{pe('pencil')} Enter gift code to check:")


@bot.callback_query_handler(func=lambda call: call.data == "gm_stats")
def gm_stats(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    total = db_execute("SELECT COUNT(*) as c FROM gift_codes", fetchone=True)
    active = db_execute("SELECT COUNT(*) as c FROM gift_codes WHERE is_active=1", fetchone=True)
    claims = db_execute("SELECT COUNT(*) as c FROM gift_claims", fetchone=True)
    amt = db_execute("SELECT SUM(amount * total_claims) as s FROM gift_codes", fetchone=True)
    adm = db_execute("SELECT COUNT(*) as c FROM gift_codes WHERE gift_type='admin'", fetchone=True)
    usr = db_execute("SELECT COUNT(*) as c FROM gift_codes WHERE gift_type='user'", fetchone=True)
    safe_send(
        call.message.chat.id,
        f"{pe('chart')} <b>Gift Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Total Codes: {total['c']}\nActive: {active['c']}\n"
        f"Total Claims: {claims['c']}\nTotal Distributed: ₹{amt['s'] or 0:.2f}\n\n"
        f"Admin Created: {adm['c']}\nUser Created: {usr['c']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


@bot.callback_query_handler(func=lambda call: call.data == "gm_delete_all")
def gm_delete_all(call):
    if not is_admin(call.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes, Delete", callback_data="gm_confirm_delete"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    safe_answer(call)
    safe_send(call.message.chat.id, f"{pe('warning')} Delete ALL gift codes?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "gm_confirm_delete")
def gm_confirm_delete(call):
    if not is_admin(call.from_user.id): return
    db_execute("DELETE FROM gift_codes")
    db_execute("DELETE FROM gift_claims")
    log_admin_action(call.from_user.id, "delete_all_gifts", "Deleted all gift codes")
    safe_answer(call, "✅ All gift codes deleted!")
    safe_send(call.message.chat.id, f"{pe('check')} All gift codes deleted!")


@bot.message_handler(func=lambda m: m.text == "🎟 Redeem Codes" and is_admin(m.from_user.id))
def admin_redeem_manager(message):
    total = db_execute("SELECT COUNT(*) as c FROM redeem_codes", fetchone=True)
    active = db_execute("SELECT COUNT(*) as c FROM redeem_codes WHERE is_active=1 AND assigned_to=0", fetchone=True)
    used = db_execute("SELECT COUNT(*) as c FROM redeem_codes WHERE assigned_to!=0", fetchone=True)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Add Code", callback_data="rm_add"),
        types.InlineKeyboardButton("📦 Active Stock", callback_data="rm_active"),
    )
    markup.add(
        types.InlineKeyboardButton("✅ Used Codes", callback_data="rm_used"),
        types.InlineKeyboardButton("🔍 Check/Edit", callback_data="rm_check"),
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ Redeem Settings", callback_data="rm_settings"),
        types.InlineKeyboardButton("🗑 Delete Code", callback_data="rm_delete_prompt"),
    )
    safe_send(
        message.chat.id,
        f"{pe('tag')} <b>Redeem Code Manager</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('chart')} Total Codes: {total['c'] if total else 0}\n"
        f"{pe('green')} Active Stock: {active['c'] if active else 0}\n"
        f"{pe('check')} Used Codes: {used['c'] if used else 0}\n"
        f"{pe('info')} Min Redeem: ₹{get_redeem_min_withdraw():.0f} | Multiple: ₹{get_redeem_multiple_of():.0f} | GST: ₹{get_redeem_gst_cut():.0f}",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "rm_add")
def rm_add(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "admin_add_redeem_code")
    safe_send(call.message.chat.id, f"{pe('pencil')} Send:\n<code>PLATFORM | AMOUNT | CODE | NOTE(optional)</code>\nExample:\n<code>Amazon | 20 | ABCD-EFGH-IJKL | Fast card</code>")

@bot.callback_query_handler(func=lambda call: call.data == "rm_active")
def rm_active(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = get_active_redeem_codes(limit=50)
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} No active redeem codes in stock.")
        return
    text = f"{pe('list')} <b>Active Redeem Stock</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for r in rows[:40]:
        text += f"#{r['id']} • {r['platform']} • ₹{r['amount']:.0f} • <code>{r['code']}</code>\n"
    safe_send(call.message.chat.id, text[:4000])

@bot.callback_query_handler(func=lambda call: call.data == "rm_used")
def rm_used(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM redeem_codes WHERE assigned_to!=0 ORDER BY assigned_at DESC LIMIT 40",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} No used redeem codes yet.")
        return
    text = f"{pe('check')} <b>Used Redeem Codes</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for r in rows:
        text += f"#{r['id']} • {r['platform']} • ₹{r['amount']:.0f} • user <code>{r['assigned_to']}</code> • {r['assigned_at'][:16]}\n"
    safe_send(call.message.chat.id, text[:4000])

@bot.callback_query_handler(func=lambda call: call.data == "rm_check")
def rm_check(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "admin_check_redeem_code")
    safe_send(call.message.chat.id, f"{pe('pencil')} Enter redeem code ID or exact code to inspect.")

@bot.callback_query_handler(func=lambda call: call.data == "rm_settings")
def rm_settings(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("Set Min Redeem", callback_data="rm_set_min"))
    markup.add(types.InlineKeyboardButton("Set GST Cut", callback_data="rm_set_gst"))
    toggle = bool(get_setting("redeem_withdraw_enabled"))
    markup.add(types.InlineKeyboardButton(f"{'🟢' if toggle else '🔴'} Toggle Redeem Withdraw", callback_data="rm_toggle"))
    markup.add(types.InlineKeyboardButton("Edit Code", callback_data="rm_edit"))
    safe_send(call.message.chat.id, f"{pe('gear')} Min: ₹{get_redeem_min_withdraw():.0f}\nMultiple: ₹{get_redeem_multiple_of():.0f}\nGST: ₹{get_redeem_gst_cut():.0f}\nEnabled: {'Yes' if toggle else 'No'}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "rm_set_min")
def rm_set_min(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "admin_set_redeem_min")
    safe_send(call.message.chat.id, f"{pe('pencil')} Enter minimum redeem amount (15 or more, multiple of 5).")

@bot.callback_query_handler(func=lambda call: call.data == "rm_set_gst")
def rm_set_gst(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "admin_set_redeem_gst")
    safe_send(call.message.chat.id, f"{pe('pencil')} Enter GST cut amount (minimum ₹5).")

@bot.callback_query_handler(func=lambda call: call.data == "rm_toggle")
def rm_toggle(call):
    if not is_admin(call.from_user.id): return
    cur = bool(get_setting("redeem_withdraw_enabled"))
    set_setting("redeem_withdraw_enabled", not cur)
    safe_answer(call, "Updated!")
    safe_send(call.message.chat.id, f"{pe('check')} Redeem code withdrawals {'enabled' if not cur else 'disabled'}.")

@bot.callback_query_handler(func=lambda call: call.data == "rm_edit")
def rm_edit(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "admin_edit_redeem_code")
    safe_send(call.message.chat.id, f"{pe('pencil')} Send:\n<code>ID | FIELD | VALUE</code>\nFields: platform, amount, code, note, is_active, gst_cut")

@bot.callback_query_handler(func=lambda call: call.data == "rm_delete_prompt")
def rm_delete_prompt(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "admin_delete_redeem_code")
    safe_send(call.message.chat.id, f"{pe('trash')} Enter redeem code ID to delete permanently.")



@bot.message_handler(func=lambda m: m.text == "🧠 Advanced Settings" and is_admin(m.from_user.id))
def advanced_settings_entry(message):
    show_advanced_settings(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "open_advanced_settings")
def open_advanced_settings(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    show_advanced_settings(call.message.chat.id)


def show_advanced_settings(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔐 Verification", callback_data="adv_verification"),
        types.InlineKeyboardButton("👥 Referral", callback_data="adv_referral"),
    )
    markup.add(
        types.InlineKeyboardButton("🎁 Bonus", callback_data="adv_bonus"),
        types.InlineKeyboardButton("💸 Tax & GST", callback_data="adv_tax"),
    )
    markup.add(
        types.InlineKeyboardButton("📉 Inactivity", callback_data="adv_inactivity"),
        types.InlineKeyboardButton("🌐 Web Verify", callback_data="adv_web_verify"),
    )
    markup.add(
        types.InlineKeyboardButton("👤 User Controls", callback_data="adv_users"),
        types.InlineKeyboardButton("🏧 Withdrawal Controls", callback_data="adv_withdrawals"),
    )
    safe_send(chat_id, f"{pe('gear')} <b>Advanced Settings</b>\n━━━━━━━━━━━━━━━━━━━━━━\nAll major controls are grouped below.", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "adv_verification")
def adv_verification(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    enabled = bool(get_setting("ip_verification_enabled"))
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"{'🟢' if enabled else '🔴'} Toggle IP Verification", callback_data="tog_ip_verify"),
        types.InlineKeyboardButton("🔁 Manual Verify Fallback", callback_data="noop_manual_verify"),
    )
    safe_send(call.message.chat.id, f"{pe('shield')} <b>Verification Control</b>\n\nIP verification: <b>{'ON' if enabled else 'OFF'}</b>\nAuto welcome after verify: <b>ON</b>\nManual verify button fallback: <b>ON</b>", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "adv_referral")
def adv_referral(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🟢/🔴 Enable Referral", callback_data="tog_referral_system"),
        types.InlineKeyboardButton("🏆 Leaderboard", callback_data="top_referrers"),
    )
    markup.add(
        types.InlineKeyboardButton("Level 1", callback_data="adv_ref_level_1"),
        types.InlineKeyboardButton("Level 2", callback_data="adv_ref_level_2"),
    )
    markup.add(types.InlineKeyboardButton("Level 3", callback_data="adv_ref_level_3"))
    markup.add(
        types.InlineKeyboardButton("Min refs for daily bonus", callback_data="adv_ref_min_bonus"),
        types.InlineKeyboardButton("Min refs for redeem", callback_data="adv_ref_min_redeem"),
    )
    safe_send(call.message.chat.id, f"{pe('people')} <b>Referral Management</b>\n\nSystem: <b>{'ON' if bool(get_setting('referral_system_enabled')) else 'OFF'}</b>\nL1: <b>{get_setting('referral_level_1_type')} {get_setting('referral_level_1_value')}</b>\nL2: <b>{get_setting('referral_level_2_type')} {get_setting('referral_level_2_value')}</b>\nL3: <b>{get_setting('referral_level_3_type')} {get_setting('referral_level_3_value')}</b>\nMin refs for daily bonus: <b>{get_setting('referral_min_activity_for_bonus')}</b>\nMin refs for redeem: <b>{get_setting('referral_min_activity_for_redeem')}</b>", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "adv_bonus")
def adv_bonus(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎉 Set Daily Bonus", callback_data="s_daily"),
        types.InlineKeyboardButton("🎲 Toggle Random Bonus", callback_data="tog_random_daily_bonus"),
    )
    markup.add(types.InlineKeyboardButton("🎯 Random Bonus Range", callback_data="adv_random_bonus_range"))
    safe_send(call.message.chat.id, f"{pe('party')} <b>Bonus Management</b>\n\nDaily bonus enabled: <b>{'ON' if bool(get_setting('daily_bonus_enabled')) else 'OFF'}</b>\nFixed daily bonus: <b>₹{get_setting('daily_bonus')}</b>\nRandom daily bonus: <b>{'ON' if bool(get_setting('random_daily_bonus_enabled')) else 'OFF'}</b>\nRange: <b>₹{get_setting('random_daily_bonus_min')} - ₹{get_setting('random_daily_bonus_max')}</b>", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "adv_tax")
def adv_tax(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Toggle Bonus WD Tax", callback_data="tog_bonus_tax"),
        types.InlineKeyboardButton("Set Bonus WD Tax %", callback_data="adv_bonus_tax_percent"),
    )
    safe_send(call.message.chat.id, f"{pe('money')} <b>Tax & GST Management</b>\n\nBonus balance withdrawal tax enabled: <b>{'ON' if bool(get_setting('withdraw_bonus_balance_tax_enabled')) else 'OFF'}</b>\nBonus balance withdrawal tax: <b>{get_setting('withdraw_bonus_balance_tax_percent')}%</b>\nUPI GST: <b>{get_setting('withdraw_upi_gst_percent')}%</b>\nRedeem code GST: <b>{get_setting('redeem_code_gst_percent')}%</b>\nGame winnings GST: <b>{get_setting('game_winnings_gst_percent')}%</b>", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "adv_inactivity")
def adv_inactivity(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Toggle Inactivity Rule", callback_data="tog_inactivity"),
        types.InlineKeyboardButton("Set Deduction %", callback_data="adv_inactivity_percent"),
    )
    markup.add(
        types.InlineKeyboardButton("Set Period Days", callback_data="adv_inactivity_days"),
        types.InlineKeyboardButton("Set Balance Floor", callback_data="adv_inactivity_floor"),
    )
    safe_send(call.message.chat.id, f"{pe('chart_down')} <b>Inactivity Deduction</b>\n\nEnabled: <b>{'ON' if bool(get_setting('inactivity_deduction_enabled')) else 'OFF'}</b>\nDeduction: <b>{get_setting('inactivity_deduction_percent')}%</b>\nPeriod: <b>{get_setting('inactivity_period_days')} day(s)</b>\nFloor: <b>₹{get_setting('inactivity_min_balance_floor')}</b>\nDefinition: <b>{get_setting('inactivity_definition')}</b>", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "adv_web_verify")
def adv_web_verify(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    base_url = normalize_public_base_url(os.environ.get("PUBLIC_BASE_URL", "") or PUBLIC_BASE_URL)
    ip_verify_enabled = bool(get_setting("ip_verification_enabled"))
    web_verify_link = f"{base_url}/ip-verify" if base_url else "Not configured"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔐 Verification Controls", callback_data="adv_verification"),
        types.InlineKeyboardButton("🏧 Withdrawal Controls", callback_data="adv_withdrawals"),
    )
    safe_send(
        call.message.chat.id,
        f"{pe('globe')} <b>Web Verification Status</b>\n\n"
        f"Base URL: <code>{html.escape(base_url or 'Not configured')}</code>\n"
        f"Verify page: <code>{html.escape(web_verify_link)}</code>\n"
        f"HTTPS ready: <b>{'YES' if base_url.startswith('https://') else 'NO'}</b>\n"
        f"IP verification: <b>{'ON' if ip_verify_enabled else 'OFF'}</b>\n"
        f"Bot username: <code>@{html.escape(os.environ.get('BOT_USERNAME', 'realupilootbot'))}</code>\n\n"
        f"This panel replaces the old game controls block and gives you something actually useful: a quick check that the Telegram web-app verify URL is configured correctly.",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "adv_users")
def adv_users(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    safe_send(call.message.chat.id, f"{pe('admin')} <b>User Management</b>\n\nUse All Users, User Lookup, Ban/Unban, Add/Deduct Balance, Reset User, and User Info from the main admin panel for full user controls.")


@bot.callback_query_handler(func=lambda call: call.data == "adv_withdrawals")
def adv_withdrawals(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    safe_send(call.message.chat.id, f"{pe('wallet')} <b>Withdrawal Management</b>\n\nUse Withdrawals section for pending approvals and limits. Tax/GST is controlled from Tax & GST Management.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("adv_ref_level_"))
def adv_ref_level(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    level = int(call.data.rsplit('_', 1)[1])
    settings_ask(call, f"admin_set_ref_level_{level}", f"{pe('pencil')} Enter level {level} referral rule:\n<code>fixed 2</code> or <code>percent 10</code>")



@bot.callback_query_handler(func=lambda call: call.data == "adv_ref_min_bonus")
def adv_ref_min_bonus(call):
    settings_ask(call, "admin_set_referral_min_bonus", f"{pe('pencil')} Enter minimum referrals required for daily bonus:")


@bot.callback_query_handler(func=lambda call: call.data == "adv_ref_min_redeem")
def adv_ref_min_redeem(call):
    settings_ask(call, "admin_set_referral_min_redeem", f"{pe('pencil')} Enter minimum referrals required for redeem code:")


@bot.callback_query_handler(func=lambda call: call.data == "adv_random_bonus_range")
def adv_random_bonus_range(call):
    settings_ask(call, "admin_set_random_bonus_range", f"{pe('pencil')} Enter random bonus range:\n<code>0.5 2</code>")



@bot.callback_query_handler(func=lambda call: call.data == "adv_bonus_tax_percent")
def adv_bonus_tax_percent(call):
    settings_ask(call, "admin_set_bonus_tax_percent", f"{pe('pencil')} Enter bonus balance withdrawal tax percent:")


@bot.callback_query_handler(func=lambda call: call.data == "adv_inactivity_percent")
def adv_inactivity_percent(call):
    settings_ask(call, "admin_set_inactivity_percent", f"{pe('pencil')} Enter inactivity deduction percent:")


@bot.callback_query_handler(func=lambda call: call.data == "adv_inactivity_days")
def adv_inactivity_days(call):
    settings_ask(call, "admin_set_inactivity_days", f"{pe('pencil')} Enter inactivity period in days:")


@bot.callback_query_handler(func=lambda call: call.data == "adv_inactivity_floor")
def adv_inactivity_floor(call):
    settings_ask(call, "admin_set_inactivity_floor", f"{pe('pencil')} Enter minimum balance floor:")


@bot.callback_query_handler(func=lambda call: call.data == "tog_ip_verify")
def tog_ip_verify(call):
    if not is_admin(call.from_user.id):
        return
    cur = bool(get_setting("ip_verification_enabled"))
    set_setting("ip_verification_enabled", not cur)
    safe_answer(call, f"IP Verification {'Enabled' if not cur else 'Disabled'}")
    adv_verification(call)


@bot.callback_query_handler(func=lambda call: call.data == "tog_referral_system")
def tog_referral_system(call):
    if not is_admin(call.from_user.id):
        return
    cur = bool(get_setting("referral_system_enabled"))
    set_setting("referral_system_enabled", not cur)
    safe_answer(call, f"Referral system {'Enabled' if not cur else 'Disabled'}")
    adv_referral(call)


@bot.callback_query_handler(func=lambda call: call.data == "tog_random_daily_bonus")
def tog_random_daily_bonus(call):
    if not is_admin(call.from_user.id):
        return
    cur = bool(get_setting("random_daily_bonus_enabled"))
    set_setting("random_daily_bonus_enabled", not cur)
    safe_answer(call, f"Random daily bonus {'Enabled' if not cur else 'Disabled'}")
    adv_bonus(call)


@bot.callback_query_handler(func=lambda call: call.data == "tog_bonus_tax")
def tog_bonus_tax(call):
    if not is_admin(call.from_user.id):
        return
    cur = bool(get_setting("withdraw_bonus_balance_tax_enabled"))
    set_setting("withdraw_bonus_balance_tax_enabled", not cur)
    safe_answer(call, f"Bonus withdrawal tax {'Enabled' if not cur else 'Disabled'}")
    adv_tax(call)


@bot.callback_query_handler(func=lambda call: call.data == "tog_inactivity")
def tog_inactivity(call):
    if not is_admin(call.from_user.id):
        return
    cur = bool(get_setting("inactivity_deduction_enabled"))
    set_setting("inactivity_deduction_enabled", not cur)
    safe_answer(call, f"Inactivity deduction {'Enabled' if not cur else 'Disabled'}")
    adv_inactivity(call)


@bot.callback_query_handler(func=lambda call: call.data == "noop_manual_verify")
def noop_manual_verify(call):
    safe_answer(call, "Manual verify button remains available.")
