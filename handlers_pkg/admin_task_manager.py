from core import *

# ======================== ADMIN TASK MANAGER ========================
@bot.message_handler(func=lambda m: m.text == "📋 Task Manager" and is_admin(m.from_user.id))
def admin_task_manager(message):
    show_task_manager(message.chat.id)


def show_task_manager(chat_id):
    active = db_execute("SELECT COUNT(*) as c FROM tasks WHERE status='active'", fetchone=True)
    paused = db_execute("SELECT COUNT(*) as c FROM tasks WHERE status='paused'", fetchone=True)
    completed = db_execute("SELECT COUNT(*) as c FROM tasks WHERE status='completed'", fetchone=True)
    total = db_execute("SELECT COUNT(*) as c FROM tasks", fetchone=True)
    pending_subs = db_execute("SELECT COUNT(*) as c FROM task_submissions WHERE status='pending'", fetchone=True)
    total_comp = db_execute("SELECT COUNT(*) as c FROM task_completions", fetchone=True)
    total_paid = db_execute("SELECT SUM(reward_paid) as t FROM task_completions", fetchone=True)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Create Task", callback_data="tm_create"),
        types.InlineKeyboardButton(f"📋 All Tasks ({total['c']})", callback_data="tm_all_tasks"),
    )
    markup.add(
        types.InlineKeyboardButton(f"✅ Active ({active['c']})", callback_data="tm_active_tasks"),
        types.InlineKeyboardButton(f"⏸ Paused ({paused['c']})", callback_data="tm_paused_tasks"),
    )
    markup.add(
        types.InlineKeyboardButton(f"🏁 Completed ({completed['c']})", callback_data="tm_completed_tasks"),
        types.InlineKeyboardButton(f"⏳ Pending Subs ({pending_subs['c']})", callback_data="admin_task_pending_subs"),
    )
    markup.add(
        types.InlineKeyboardButton("📊 Task Analytics", callback_data="tm_analytics"),
        types.InlineKeyboardButton("🔄 Refresh", callback_data="tm_refresh"),
    )
    markup.add(
        types.InlineKeyboardButton("✅ Approve All Subs", callback_data="tm_approve_all_subs"),
        types.InlineKeyboardButton("❌ Reject All Subs", callback_data="tm_reject_all_subs"),
    )
    markup.add(
        types.InlineKeyboardButton("📥 Export Task Data", callback_data="tm_export"),
        types.InlineKeyboardButton("🗑 Delete All Tasks", callback_data="tm_delete_all"),
    )
    markup.add(
        types.InlineKeyboardButton("➕ Add Task DB Record", callback_data="tm_add_db_record"),
    )
    safe_send(
        chat_id,
        f"{pe('rocket')} <b>Task Manager</b> {pe('gear')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('active')} <b>Active Tasks:</b> {active['c']}\n"
        f"{pe('pause')} <b>Paused Tasks:</b> {paused['c']}\n"
        f"{pe('done')} <b>Completed Tasks:</b> {completed['c']}\n"
        f"{pe('chart')} <b>Total Tasks:</b> {total['c']}\n\n"
        f"{pe('pending2')} <b>Pending Submissions:</b> {pending_subs['c']}\n"
        f"{pe('trophy')} <b>Total Completions:</b> {total_comp['c']}\n"
        f"{pe('coins')} <b>Total Paid:</b> ₹{total_paid['t'] or 0:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "tm_add_db_record")
def tm_add_db_record(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "db_add_task")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Add Task DB Record</b>\n\n"
        f"Format:\n"
        f"<code>title|description|reward|task_type|task_url|status</code>\n\n"
        f"Example:\n"
        f"<code>Join Channel|Join our TG channel|5|channel|https://t.me/test|active</code>\n\n"
        f"Status options: active, paused, completed"
    )


@bot.callback_query_handler(func=lambda call: call.data == "tm_refresh")
def tm_refresh(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call, "🔄 Refreshed!")
    show_task_manager(call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "tm_create")
def tm_create(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    set_state(call.from_user.id, "admin_task_create_title", {})
    safe_send(
        call.message.chat.id,
        f"{pe('rocket')} <b>Create New Task</b> {pe('sparkle')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('pencil')} <b>Step 1/7: Title</b>\n\n"
        f"Enter the task title:\n"
        f"(e.g. 'Join Our Telegram Channel')"
    )


@bot.callback_query_handler(func=lambda call: call.data == "tm_all_tasks")
def tm_all_tasks(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    tasks = get_all_tasks()
    if not tasks:
        safe_send(call.message.chat.id, f"{pe('info')} No tasks found! Create one first.")
        return
    for task in tasks[:20]:
        show_admin_task_card(call.message.chat.id, task)


@bot.callback_query_handler(func=lambda call: call.data == "tm_active_tasks")
def tm_active_tasks(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    tasks = db_execute(
        "SELECT * FROM tasks WHERE status='active' ORDER BY order_num ASC, id DESC",
        fetch=True
    ) or []
    if not tasks:
        safe_send(call.message.chat.id, f"{pe('info')} No active tasks!")
        return
    for task in tasks[:20]:
        show_admin_task_card(call.message.chat.id, task)


@bot.callback_query_handler(func=lambda call: call.data == "tm_paused_tasks")
def tm_paused_tasks(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    tasks = db_execute(
        "SELECT * FROM tasks WHERE status='paused' ORDER BY id DESC",
        fetch=True
    ) or []
    if not tasks:
        safe_send(call.message.chat.id, f"{pe('info')} No paused tasks!")
        return
    for task in tasks[:20]:
        show_admin_task_card(call.message.chat.id, task)


@bot.callback_query_handler(func=lambda call: call.data == "tm_completed_tasks")
def tm_completed_tasks(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    tasks = db_execute(
        "SELECT * FROM tasks WHERE status='completed' ORDER BY id DESC",
        fetch=True
    ) or []
    if not tasks:
        safe_send(call.message.chat.id, f"{pe('info')} No completed tasks!")
        return
    for task in tasks[:20]:
        show_admin_task_card(call.message.chat.id, task)


def show_admin_task_card(chat_id, task):
    emoji = get_task_type_emoji(task["task_type"])
    stats = get_task_stats(task["id"])
    status_emoji = {
        "active": "🟢", "paused": "🟡",
        "completed": "🏁", "deleted": "🔴"
    }.get(task["status"], "⚪")
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📊 Details", callback_data=f"tm_detail|{task['id']}"))
    if task["status"] == "active":
        markup.add(
            types.InlineKeyboardButton("⏸ Pause", callback_data=f"tm_pause|{task['id']}"),
            types.InlineKeyboardButton("✏️ Edit", callback_data=f"tm_edit|{task['id']}"),
        )
    elif task["status"] == "paused":
        markup.add(
            types.InlineKeyboardButton("▶️ Activate", callback_data=f"tm_activate|{task['id']}"),
            types.InlineKeyboardButton("✏️ Edit", callback_data=f"tm_edit|{task['id']}"),
        )
    markup.add(types.InlineKeyboardButton("🗑 Delete", callback_data=f"tm_delete|{task['id']}"))
    mc = task["max_completions"]
    mc_text = f"/{mc}" if mc > 0 else ""
    safe_send(
        chat_id,
        f"{status_emoji} {emoji} <b>#{task['id']}: {task['title']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{pe('coins')} Reward: ₹{task['reward']} | Type: {task['task_type']}\n"
        f"{pe('chart')} Subs: {stats['total']} | "
        f"✅ {stats['approved']} | ⏳ {stats['pending']} | ❌ {stats['rejected']}\n"
        f"Completions: {task['total_completions']}{mc_text}\n"
        f"Status: {task['status'].upper()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("tm_detail|"))
def tm_detail_cb(call):
    if not is_admin(call.from_user.id): return
    try:
        task_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call)
    task = get_task(task_id)
    if not task:
        safe_send(call.message.chat.id, f"{pe('cross')} Task not found!")
        return
    show_admin_task_detail(call.message.chat.id, task)


def show_admin_task_detail(chat_id, task):
    emoji = get_task_type_emoji(task["task_type"])
    stats = get_task_stats(task["id"])
    status_emoji = {
        "active": "🟢", "paused": "🟡",
        "completed": "🏁", "deleted": "🔴"
    }.get(task["status"], "⚪")
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✏️ Title", callback_data=f"tm_ef|{task['id']}|title"),
        types.InlineKeyboardButton("✏️ Description", callback_data=f"tm_ef|{task['id']}|description"),
    )
    markup.add(
        types.InlineKeyboardButton("✏️ Reward", callback_data=f"tm_ef|{task['id']}|reward"),
        types.InlineKeyboardButton("✏️ URL", callback_data=f"tm_ef|{task['id']}|task_url"),
    )
    markup.add(
        types.InlineKeyboardButton("✏️ Channel", callback_data=f"tm_ef|{task['id']}|task_channel"),
        types.InlineKeyboardButton("✏️ Max Comp", callback_data=f"tm_ef|{task['id']}|max_completions"),
    )
    markup.add(
        types.InlineKeyboardButton("✏️ Category", callback_data=f"tm_ef|{task['id']}|category"),
        types.InlineKeyboardButton("✏️ Image URL", callback_data=f"tm_ef|{task['id']}|image_url"),
    )
    if task["status"] == "active":
        markup.add(types.InlineKeyboardButton("⏸ Pause", callback_data=f"tm_pause|{task['id']}"))
    elif task["status"] == "paused":
        markup.add(types.InlineKeyboardButton("▶️ Activate", callback_data=f"tm_activate|{task['id']}"))
    elif task["status"] == "completed":
        markup.add(types.InlineKeyboardButton("🔄 Reactivate", callback_data=f"tm_activate|{task['id']}"))
    markup.add(
        types.InlineKeyboardButton(f"⏳ View Subs ({stats['pending']})", callback_data=f"tm_task_subs|{task['id']}"),
        types.InlineKeyboardButton("🗑 Delete", callback_data=f"tm_delete|{task['id']}"),
    )
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="tm_refresh"))
    max_txt = f"{task['max_completions']}" if task["max_completions"] > 0 else "Unlimited"
    safe_send(
        chat_id,
        f"{status_emoji} {emoji} <b>Task #{task['id']} Details</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('task')} <b>Title:</b> {task['title']}\n"
        f"{pe('info')} <b>Description:</b>\n{task['description'][:300]}\n\n"
        f"{pe('coins')} <b>Reward:</b> ₹{task['reward']}\n"
        f"{pe('zap')} <b>Type:</b> {task['task_type']}\n"
        f"{pe('link')} <b>URL:</b> {task['task_url'] or 'None'}\n"
        f"{pe('megaphone')} <b>Channel:</b> {task['task_channel'] or 'None'}\n"
        f"{pe('bookmark')} <b>Category:</b> {task['category']}\n"
        f"{pe('thumbs_up')} <b>Max Completions:</b> {max_txt}\n"
        f"{pe('chart')} <b>Total Completions:</b> {task['total_completions']}\n\n"
        f"{pe('chart_up')} <b>Submissions:</b>\n"
        f"  Total: {stats['total']} | ✅ {stats['approved']} | ⏳ {stats['pending']} | ❌ {stats['rejected']}\n\n"
        f"{pe('calendar')} <b>Created:</b> {task['created_at']}\n"
        f"{pe('refresh')} <b>Updated:</b> {task['updated_at']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("tm_ef|"))
def tm_edit_field(call):
    if not is_admin(call.from_user.id): return
    try:
        parts = call.data.split("|")
        task_id = int(parts[1])
        field = parts[2]
    except:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call)
    set_state(call.from_user.id, "admin_task_edit_field", {"task_id": task_id, "field": field})
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Edit Task #{task_id}</b>\n\n"
        f"Editing: <b>{field}</b>\n\n"
        f"Enter new value:"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("tm_edit|"))
def tm_edit(call):
    if not is_admin(call.from_user.id): return
    try:
        task_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call)
    task = get_task(task_id)
    if not task:
        safe_send(call.message.chat.id, f"{pe('cross')} Task not found!")
        return
    show_admin_task_detail(call.message.chat.id, task)


@bot.callback_query_handler(func=lambda call: call.data.startswith("tm_pause|"))
def tm_pause(call):
    if not is_admin(call.from_user.id): return
    try:
        task_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute("UPDATE tasks SET status='paused', updated_at=? WHERE id=?", (now, task_id))
    log_admin_action(call.from_user.id, "pause_task", f"Paused task #{task_id}")
    safe_answer(call, "⏸ Task Paused!")
    task = get_task(task_id)
    if task:
        show_admin_task_detail(call.message.chat.id, task)


@bot.callback_query_handler(func=lambda call: call.data.startswith("tm_activate|"))
def tm_activate(call):
    if not is_admin(call.from_user.id): return
    try:
        task_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute("UPDATE tasks SET status='active', updated_at=? WHERE id=?", (now, task_id))
    log_admin_action(call.from_user.id, "activate_task", f"Activated task #{task_id}")
    safe_answer(call, "▶️ Task Activated!")
    task = get_task(task_id)
    if task:
        show_admin_task_detail(call.message.chat.id, task)


@bot.callback_query_handler(func=lambda call: call.data.startswith("tm_delete|"))
def tm_delete(call):
    if not is_admin(call.from_user.id): return
    try:
        task_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes, Delete", callback_data=f"tm_confirm_del|{task_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    safe_answer(call)
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} <b>Delete Task #{task_id}?</b>\n\nThis will also delete all submissions!",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("tm_confirm_del|"))
def tm_confirm_del(call):
    if not is_admin(call.from_user.id): return
    try:
        task_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    db_execute("DELETE FROM tasks WHERE id=?", (task_id,))
    db_execute("DELETE FROM task_submissions WHERE task_id=?", (task_id,))
    db_execute("DELETE FROM task_completions WHERE task_id=?", (task_id,))
    log_admin_action(call.from_user.id, "delete_task", f"Deleted task #{task_id}")
    safe_answer(call, "✅ Task Deleted!")
    safe_send(call.message.chat.id, f"{pe('check')} Task #{task_id} and all its data deleted!")


@bot.callback_query_handler(func=lambda call: call.data.startswith("tm_task_subs|"))
def tm_task_subs(call):
    if not is_admin(call.from_user.id): return
    try:
        task_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call)
    subs = db_execute(
        "SELECT ts.*, t.title as task_title, t.reward as task_reward "
        "FROM task_submissions ts JOIN tasks t ON ts.task_id=t.id "
        "WHERE ts.task_id=? AND ts.status='pending' ORDER BY ts.submitted_at DESC LIMIT 20",
        (task_id,), fetch=True
    ) or []
    if not subs:
        safe_send(call.message.chat.id, f"{pe('check')} No pending submissions for task #{task_id}!")
        return
    for s in subs:
        user = get_user(s["user_id"])
        name = user["first_name"] if user else "Unknown"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"tsub_approve|{s['id']}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"tsub_reject|{s['id']}"),
        )
        markup.add(types.InlineKeyboardButton("👤 User Info", callback_data=f"uinfo|{s['user_id']}"))
        proof_preview = s["proof_text"][:150] if s["proof_text"] else "No text"
        sub_text = (
            f"{pe('pending2')} <b>Submission #{s['id']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('task')} <b>Task:</b> {s['task_title']}\n"
            f"{pe('disguise')} <b>User:</b> {name} (<code>{s['user_id']}</code>)\n"
            f"{pe('coins')} <b>Reward:</b> ₹{s['task_reward']}\n"
            f"{pe('info')} <b>Proof:</b> {proof_preview}\n"
            f"{pe('calendar')} <b>Submitted:</b> {s['submitted_at']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        if s["proof_file_id"]:
            try:
                bot.send_photo(
                    call.message.chat.id, s["proof_file_id"],
                    caption=sub_text, parse_mode="HTML", reply_markup=markup
                )
                continue
            except:
                pass
        safe_send(call.message.chat.id, sub_text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "admin_task_pending_subs")
def admin_task_pending_subs(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    subs = get_pending_task_submissions()
    if not subs:
        safe_send(call.message.chat.id, f"{pe('check')} <b>No pending task submissions!</b>")
        return
    safe_send(
        call.message.chat.id,
        f"{pe('pending2')} <b>Pending Task Submissions ({len(subs)})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    for s in subs[:25]:
        user = get_user(s["user_id"])
        name = user["first_name"] if user else "Unknown"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"tsub_approve|{s['id']}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"tsub_reject|{s['id']}"),
        )
        markup.add(types.InlineKeyboardButton("👤 User", callback_data=f"uinfo|{s['user_id']}"))
        proof_preview = s["proof_text"][:100] if s["proof_text"] else "No text"
        sub_text = (
            f"{pe('hourglass')} <b>Sub #{s['id']}</b> | {s['task_title']}\n"
            f"{pe('disguise')} {name} (<code>{s['user_id']}</code>)\n"
            f"{pe('coins')} ₹{s['task_reward']} | {pe('info')} {proof_preview}\n"
            f"{pe('calendar')} {s['submitted_at']}"
        )
        if s["proof_file_id"]:
            try:
                bot.send_photo(
                    call.message.chat.id, s["proof_file_id"],
                    caption=sub_text, parse_mode="HTML", reply_markup=markup
                )
                continue
            except:
                pass
        safe_send(call.message.chat.id, sub_text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "tm_approve_all_subs")
def tm_approve_all_subs(call):
    if not is_admin(call.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes, Approve All", callback_data="tm_confirm_approve_all"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    safe_answer(call)
    pending_count = db_execute(
        "SELECT COUNT(*) as c FROM task_submissions WHERE status='pending'",
        fetchone=True
    )
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} <b>Approve ALL {pending_count['c']} pending task submissions?</b>\n\n"
        f"All users will receive their rewards.",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "tm_confirm_approve_all")
def tm_confirm_approve_all(call):
    if not is_admin(call.from_user.id): return
    subs = get_pending_task_submissions()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = 0
    for s in subs:
        reward = s["task_reward"]
        uid = s["user_id"]
        task_id = s["task_id"]
        db_execute(
            "UPDATE task_submissions SET status='approved', reviewed_at=?, reward_paid=? WHERE id=?",
            (now, reward, s["id"])
        )
        existing_comp = get_task_completion(task_id, uid)
        if not existing_comp:
            db_execute(
                "INSERT INTO task_completions (task_id, user_id, completed_at, reward_paid) VALUES (?,?,?,?)",
                (task_id, uid, now, reward)
            )
            db_execute("UPDATE tasks SET total_completions=total_completions+1 WHERE id=?", (task_id,))
        user = get_user(uid)
        if user:
            update_user(uid, balance=user["balance"] + reward, total_earned=user["total_earned"] + reward)
        try:
            safe_send(
                uid,
                f"{pe('party')} <b>Task Approved!</b>\n"
                f"{pe('task')} {s['task_title']}\n"
                f"{pe('coins')} +₹{reward}"
            )
        except:
            pass
        count += 1
    log_admin_action(call.from_user.id, "approve_all_subs", f"Approved {count} task submissions")
    safe_answer(call, f"✅ Approved {count}!")
    safe_send(call.message.chat.id, f"{pe('check')} <b>Approved {count} task submissions!</b>")


@bot.callback_query_handler(func=lambda call: call.data == "tm_reject_all_subs")
def tm_reject_all_subs(call):
    if not is_admin(call.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes, Reject All", callback_data="tm_confirm_reject_all"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    safe_answer(call)
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} <b>Reject ALL pending task submissions?</b>",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "tm_confirm_reject_all")
def tm_confirm_reject_all(call):
    if not is_admin(call.from_user.id): return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subs = get_pending_task_submissions()
    db_execute(
        "UPDATE task_submissions SET status='rejected', reviewed_at=?, admin_note='Bulk rejected' WHERE status='pending'",
        (now,)
    )
    for s in subs:
        try:
            safe_send(
                s["user_id"],
                f"{pe('cross')} <b>Task Rejected</b>\n"
                f"{pe('task')} {s['task_title']}\n"
                f"{pe('info')} Reason: Bulk rejected by admin"
            )
        except:
            pass
    log_admin_action(call.from_user.id, "reject_all_subs", f"Rejected {len(subs)} task submissions")
    safe_answer(call, f"❌ Rejected {len(subs)}!")
    safe_send(call.message.chat.id, f"{pe('check')} Rejected {len(subs)} submissions!")


@bot.callback_query_handler(func=lambda call: call.data == "tm_analytics")
def tm_analytics(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call)
    total_tasks = db_execute("SELECT COUNT(*) as c FROM tasks", fetchone=True)
    active_tasks = db_execute("SELECT COUNT(*) as c FROM tasks WHERE status='active'", fetchone=True)
    total_subs = db_execute("SELECT COUNT(*) as c FROM task_submissions", fetchone=True)
    approved_subs = db_execute("SELECT COUNT(*) as c FROM task_submissions WHERE status='approved'", fetchone=True)
    rejected_subs = db_execute("SELECT COUNT(*) as c FROM task_submissions WHERE status='rejected'", fetchone=True)
    pending_subs = db_execute("SELECT COUNT(*) as c FROM task_submissions WHERE status='pending'", fetchone=True)
    total_comp = db_execute("SELECT COUNT(*) as c FROM task_completions", fetchone=True)
    total_paid = db_execute("SELECT SUM(reward_paid) as t FROM task_completions", fetchone=True)
    unique_users = db_execute("SELECT COUNT(DISTINCT user_id) as c FROM task_completions", fetchone=True)
    avg_reward = db_execute("SELECT AVG(reward_paid) as a FROM task_completions", fetchone=True)
    today = datetime.now().strftime("%Y-%m-%d")
    today_comp = db_execute(
        "SELECT COUNT(*) as c, SUM(reward_paid) as t FROM task_completions WHERE completed_at LIKE ?",
        (f"{today}%",), fetchone=True
    )
    today_subs = db_execute(
        "SELECT COUNT(*) as c FROM task_submissions WHERE submitted_at LIKE ?",
        (f"{today}%",), fetchone=True
    )
    top_task = db_execute(
        "SELECT t.title, t.total_completions FROM tasks t ORDER BY t.total_completions DESC LIMIT 1",
        fetchone=True
    )
    safe_send(
        call.message.chat.id,
        f"{pe('chart')} <b>Task Analytics</b> {pe('rocket')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('fire')} <b>═══ Overview ═══</b>\n"
        f"  {pe('chart')} Total Tasks: {total_tasks['c']}\n"
        f"  {pe('active')} Active: {active_tasks['c']}\n\n"
        f"{pe('trophy')} <b>═══ Submissions ═══</b>\n"
        f"  {pe('chart_up')} Total: {total_subs['c']}\n"
        f"  {pe('check')} Approved: {approved_subs['c']}\n"
        f"  {pe('cross')} Rejected: {rejected_subs['c']}\n"
        f"  {pe('hourglass')} Pending: {pending_subs['c']}\n\n"
        f"{pe('coins')} <b>═══ Rewards ═══</b>\n"
        f"  {pe('done')} Total Completions: {total_comp['c']}\n"
        f"  {pe('fly_money')} Total Paid: ₹{total_paid['t'] or 0:.2f}\n"
        f"  {pe('star')} Avg Reward: ₹{avg_reward['a'] or 0:.2f}\n"
        f"  {pe('thumbs_up')} Unique Earners: {unique_users['c']}\n\n"
        f"{pe('calendar')} <b>═══ Today ═══</b>\n"
        f"  {pe('new_tag')} Submissions: {today_subs['c']}\n"
        f"  {pe('done')} Completions: {today_comp['c']}\n"
        f"  {pe('coins')} Paid: ₹{today_comp['t'] or 0:.2f}\n\n"
        f"{pe('crown')} <b>═══ Top Task ═══</b>\n"
        f"  {top_task['title'] if top_task else 'None'} "
        f"({top_task['total_completions'] if top_task else 0} completions)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


@bot.callback_query_handler(func=lambda call: call.data == "tm_export")
def tm_export(call):
    if not is_admin(call.from_user.id): return
    safe_answer(call, "Generating...")
    tasks = get_all_tasks()
    if not tasks:
        safe_send(call.message.chat.id, "No tasks!")
        return
    lines = ["ID,Title,Reward,Type,Status,Completions,MaxComp,CreatedAt\n"]
    for t in tasks:
        lines.append(
            f"{t['id']},{t['title']},{t['reward']},{t['task_type']},"
            f"{t['status']},{t['total_completions']},{t['max_completions']},{t['created_at']}\n"
        )
    filename = "tasks_export.csv"
    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(lines)
    with open(filename, "rb") as f:
        bot.send_document(
            call.message.chat.id, f,
            caption=f"{pe('check')} Exported {len(tasks)} tasks",
            parse_mode="HTML"
        )
    os.remove(filename)
    subs_data = db_execute(
        "SELECT ts.*, t.title as task_title FROM task_submissions ts "
        "JOIN tasks t ON ts.task_id=t.id ORDER BY ts.submitted_at DESC",
        fetch=True
    ) or []
    if subs_data:
        lines2 = ["SubID,TaskID,TaskTitle,UserID,Status,Reward,SubmittedAt,ReviewedAt\n"]
        for s in subs_data:
            lines2.append(
                f"{s['id']},{s['task_id']},{s['task_title']},{s['user_id']},"
                f"{s['status']},{s['reward_paid']},{s['submitted_at']},{s['reviewed_at']}\n"
            )
        filename2 = "task_submissions_export.csv"
        with open(filename2, "w", encoding="utf-8") as f:
            f.writelines(lines2)
        with open(filename2, "rb") as f:
            bot.send_document(
                call.message.chat.id, f,
                caption=f"{pe('check')} Exported {len(subs_data)} submissions",
                parse_mode="HTML"
            )
        os.remove(filename2)
    log_admin_action(call.from_user.id, "export_tasks", f"Exported {len(tasks)} tasks")


@bot.callback_query_handler(func=lambda call: call.data == "tm_delete_all")
def tm_delete_all(call):
    if not is_admin(call.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⚠️ Yes, Delete ALL", callback_data="tm_confirm_delete_all"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
    )
    safe_answer(call)
    safe_send(
        call.message.chat.id,
        f"{pe('siren')} <b>DELETE ALL TASKS?</b>\n\n"
        f"This deletes all tasks, submissions, and completions!",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "tm_confirm_delete_all")
def tm_confirm_delete_all(call):
    if not is_admin(call.from_user.id): return
    db_execute("DELETE FROM tasks")
    db_execute("DELETE FROM task_submissions")
    db_execute("DELETE FROM task_completions")
    log_admin_action(call.from_user.id, "delete_all_tasks", "Deleted all tasks")
    safe_answer(call, "✅ All tasks deleted!")
    safe_send(call.message.chat.id, f"{pe('check')} <b>All tasks, submissions & completions deleted!</b>")


