from core import *

# ======================== ADMIN MANAGER ========================
@bot.message_handler(func=lambda m: m.text == "👮 Admin Manager" and is_admin(m.from_user.id))
def admin_manager(message):
    if not is_super_admin(message.from_user.id):
        safe_send(
            message.chat.id,
            f"{pe('no_entry')} <b>Only main admin can manage admins!</b>"
        )
        return
    show_admin_manager(message.chat.id)


def show_admin_manager(chat_id):
    admins = get_all_admins()
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Add Admin", callback_data="am_add"),
        types.InlineKeyboardButton("📋 List Admins", callback_data="am_list"),
    )
    markup.add(
        types.InlineKeyboardButton("❌ Remove Admin", callback_data="am_remove"),
        types.InlineKeyboardButton("📜 Admin Logs", callback_data="view_admin_logs"),
    )
    markup.add(
        types.InlineKeyboardButton("📊 Admin Stats", callback_data="am_stats"),
    )
    safe_send(
        chat_id,
        f"{pe('crown')} <b>Admin Manager</b> {pe('shield')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('admin')} <b>Total Active Admins:</b> {len(admins)}\n\n"
        f"{pe('info')} Only the main admin can add/remove admins.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "am_add")
def am_add(call):
    if not is_super_admin(call.from_user.id):
        safe_answer(call, "Only main admin!", True)
        return
    safe_answer(call)
    set_state(call.from_user.id, "admin_add_new")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Add New Admin</b>\n\n"
        f"Enter the <b>User ID</b> of the person to make admin:\n\n"
        f"{pe('info')} The user must have started the bot first.\n"
        f"{pe('warning')} They will get full admin access."
    )


@bot.callback_query_handler(func=lambda call: call.data == "am_list")
def am_list(call):
    if not is_super_admin(call.from_user.id):
        safe_answer(call, "Only main admin!", True)
        return
    safe_answer(call)
    admins = get_all_admins()
    if not admins:
        safe_send(call.message.chat.id, f"{pe('info')} No admins found!")
        return
    text = f"{pe('crown')} <b>Admin List</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, adm in enumerate(admins, 1):
        is_main = "👑 Main" if int(adm["user_id"]) == int(ADMIN_ID) else "👮 Sub"
        text += (
            f"{i}. {is_main}\n"
            f"   {pe('disguise')} {adm['first_name'] or 'Unknown'}\n"
            f"   {pe('link')} @{adm['username'] or 'None'}\n"
            f"   {pe('info')} ID: <code>{adm['user_id']}</code>\n"
            f"   {pe('shield')} Perms: {adm['permissions']}\n"
            f"   {pe('calendar')} Added: {adm['added_at'][:10]}\n\n"
        )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Remove an Admin", callback_data="am_remove"))
    safe_send(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "am_remove")
def am_remove(call):
    if not is_super_admin(call.from_user.id):
        safe_answer(call, "Only main admin!", True)
        return
    safe_answer(call)
    admins = get_all_admins()
    sub_admins = [a for a in admins if int(a["user_id"]) != int(ADMIN_ID)]
    if not sub_admins:
        safe_send(call.message.chat.id, f"{pe('info')} No sub-admins to remove!")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for adm in sub_admins:
        btn_text = f"❌ {adm['first_name'] or 'Unknown'} ({adm['user_id']})"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"am_confirm_remove|{adm['user_id']}"))
    markup.add(types.InlineKeyboardButton("🔙 Cancel", callback_data="cancel_action"))
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} <b>Select admin to remove:</b>",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("am_confirm_remove|"))
def am_confirm_remove(call):
    if not is_super_admin(call.from_user.id):
        safe_answer(call, "Only main admin!", True)
        return
    try:
        tid = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    if int(tid) == int(ADMIN_ID):
        safe_answer(call, "Cannot remove main admin!", True)
        return
    remove_admin(tid)
    log_admin_action(call.from_user.id, "remove_admin", f"Removed admin {tid}")
    safe_answer(call, "✅ Admin removed!")
    safe_send(call.message.chat.id, f"{pe('check')} Admin <code>{tid}</code> removed!")
    try:
        safe_send(tid, f"{pe('warning')} Your admin access has been revoked.")
    except:
        pass


@bot.callback_query_handler(func=lambda call: call.data == "am_stats")
def am_stats(call):
    if not is_super_admin(call.from_user.id):
        safe_answer(call, "Only main admin!", True)
        return
    safe_answer(call)
    total_admins = db_execute("SELECT COUNT(*) as c FROM admins WHERE is_active=1", fetchone=True)
    total_actions = db_execute("SELECT COUNT(*) as c FROM admin_logs", fetchone=True)
    today = datetime.now().strftime("%Y-%m-%d")
    today_actions = db_execute(
        "SELECT COUNT(*) as c FROM admin_logs WHERE created_at LIKE ?",
        (f"{today}%",), fetchone=True
    )
    most_active = db_execute(
        "SELECT admin_id, COUNT(*) as cnt FROM admin_logs GROUP BY admin_id ORDER BY cnt DESC LIMIT 5",
        fetch=True
    ) or []
    text = (
        f"{pe('chart')} <b>Admin Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('admin')} Total Admins: {total_admins['c']}\n"
        f"{pe('list')} Total Actions Logged: {total_actions['c']}\n"
        f"{pe('calendar')} Today's Actions: {today_actions['c']}\n\n"
        f"{pe('fire')} <b>Most Active Admins:</b>\n"
    )
    for r in most_active:
        u = get_user(r["admin_id"])
        name = u["first_name"] if u else f"Admin {r['admin_id']}"
        text += f"  {pe('arrow')} {name}: {r['cnt']} actions\n"
    safe_send(call.message.chat.id, text)


