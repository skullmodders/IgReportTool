from core import *

# ======================== TASKS SECTION (USER) ========================
@bot.message_handler(func=lambda m: m.text == "📋 Tasks")
def tasks_handler(message):
    user_id = message.from_user.id
    if not check_force_join(user_id):
        send_join_message(message.chat.id)
        return
    user = get_user(user_id)
    if not user:
        safe_send(message.chat.id, "Please send /start first.")
        return
    if not get_setting("tasks_enabled"):
        safe_send(
            message.chat.id,
            f"{pe('no_entry')} <b>Tasks Disabled!</b>\n"
            f"{pe('hourglass')} Tasks are temporarily unavailable.\n"
            f"{pe('info')} Contact {HELP_USERNAME} for info."
        )
        return
    show_tasks_menu(message.chat.id, user_id)

def show_tasks_menu(chat_id, user_id):
    user = get_user(user_id)
    if not user:
        return
    active_tasks = get_active_tasks()
    completed_tasks = get_user_completed_tasks(user_id)
    completed_ids = [c["task_id"] for c in completed_tasks]
    pending_subs = db_execute(
        "SELECT COUNT(*) as c FROM task_submissions WHERE user_id=? AND status='pending'",
        (user_id,), fetchone=True
    )
    pending_count = pending_subs["c"] if pending_subs else 0
    available = [t for t in active_tasks if t["id"] not in completed_ids]
    done_count = len(completed_ids)
    total_task_earned = sum(c["reward_paid"] for c in completed_tasks)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"📋 All Tasks ({len(available)})", callback_data="tasks_list"),
        types.InlineKeyboardButton(f"✅Completed ({done_count})", callback_data="tasks_my_completed"),
    )
    markup.add(
        types.InlineKeyboardButton(f"⏳ Pending ({pending_count})", callback_data="tasks_my_pending"),
        types.InlineKeyboardButton("🔄 Refresh", callback_data="tasks_refresh"),
    )
    text = (
        f"{pe('rocket')} <b>Task Center</b> {pe('trophy')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('zap')} <b>Earn real money by completing tasks!</b>\n\n"
        f"{pe('coins')} <b>Your Task Stats:</b>\n"
        f"  {pe('check')} Completed: <b>{done_count}</b>\n"
        f"  {pe('pending2')} Under Review: <b>{pending_count}</b>\n"
        f"  {pe('trophy')} Total Earned: <b>₹{total_task_earned:.2f}</b>\n\n"
        f"{pe('active')} <b>Available Tasks:</b> {len(available)}\n"
        f"{pe('fire')} <b>Your Balance:</b> ₹{user['balance']:.2f}\n\n"
        f"{pe('bulb')} <i>Complete tasks to earn instant rewards!</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    safe_send(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "tasks_refresh")
def tasks_refresh(call):
    safe_answer(call, "🔄 Refreshed!")
    show_tasks_menu(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "tasks_list")
def tasks_list(call):
    user_id = call.from_user.id
    safe_answer(call)
    active_tasks = get_active_tasks()
    if not active_tasks:
        safe_send(
            call.message.chat.id,
            f"{pe('info')} <b>No Tasks Available</b>\n\n"
            f"{pe('hourglass')} New tasks coming soon!\n"
            f"{pe('bell')} Stay tuned for updates."
        )
        return
    completed_ids = [c["task_id"] for c in get_user_completed_tasks(user_id)]
    text = (
        f"{pe('rocket')} <b>Available Tasks</b> {pe('fire')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('zap')} <b>Tap any task to view details & complete it!</b>\n\n"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    shown = 0
    for task in active_tasks:
        if task["max_completions"] > 0 and task["total_completions"] >= task["max_completions"]:
            continue
        emoji = get_task_type_emoji(task["task_type"])
        done_mark = ""
        if task["id"] in completed_ids:
            done_mark = " ✅"
        else:
            sub = get_task_submission(task["id"], user_id)
            if sub and sub["status"] == "pending":
                done_mark = " ⏳"
            elif sub and sub["status"] == "rejected":
                done_mark = " ❌"
        btn_text = f"{emoji} {task['title']} — ₹{task['reward']}{done_mark}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"task_view|{task['id']}"))
        shown += 1
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="tasks_back"))
    if shown == 0:
        safe_send(
            call.message.chat.id,
            f"{pe('check')} <b>All tasks completed!</b>\n"
            f"{pe('trophy')} Amazing work! Check back later for new tasks.",
            reply_markup=markup
        )
        return
    safe_send(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "tasks_back")
def tasks_back(call):
    safe_answer(call)
    show_tasks_menu(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("task_view|"))
def task_view(call):
    user_id = call.from_user.id
    try:
        task_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call)
    task = get_task(task_id)
    if not task or task["status"] != "active":
        safe_send(call.message.chat.id, f"{pe('cross')} <b>Task not available!</b>")
        return
    show_task_detail(call.message.chat.id, user_id, task)

def show_task_detail(chat_id, user_id, task):
    emoji = get_task_type_emoji(task["task_type"])
    completed = get_task_completion(task["id"], user_id)
    sub = get_task_submission(task["id"], user_id)
    slots_text = ""
    if task["max_completions"] > 0:
        remaining = task["max_completions"] - task["total_completions"]
        slots_text = f"\n{pe('hourglass')} <b>Slots Left:</b> {remaining}"
    markup = types.InlineKeyboardMarkup(row_width=1)
    if completed:
        status_text = f"\n\n{pe('done')} <b>✅ You have completed this task!</b>\n{pe('coins')} Earned: ₹{completed['reward_paid']}"
        markup.add(types.InlineKeyboardButton("🔙 Back to Tasks", callback_data="tasks_list"))
    elif sub and sub["status"] == "pending":
        status_text = f"\n\n{pe('pending2')} <b>⏳ Your submission is under review!</b>\n{pe('info')} Wait for admin approval."
        markup.add(types.InlineKeyboardButton("🔙 Back to Tasks", callback_data="tasks_list"))
    elif sub and sub["status"] == "rejected":
        status_text = (
            f"\n\n{pe('reject')} <b>❌ Previous submission rejected!</b>\n"
            f"{pe('info')} Reason: {sub['admin_note'] or 'No reason given'}\n"
            f"{pe('arrow')} You can try again!"
        )
        if task["task_url"]:
            markup.add(types.InlineKeyboardButton(f"{emoji} Go to Task", url=task["task_url"]))
        markup.add(types.InlineKeyboardButton("📤 Submit Again", callback_data=f"task_submit|{task['id']}"))
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="tasks_list"))
    else:
        status_text = ""
        if task["task_url"]:
            markup.add(types.InlineKeyboardButton(f"{emoji} Open Task Link", url=task["task_url"]))
        markup.add(types.InlineKeyboardButton("📤 Submit Proof", callback_data=f"task_submit|{task['id']}"))
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="tasks_list"))
    category_text = f"\n{pe('bookmark')} <b>Category:</b> {task['category'].capitalize()}" if task["category"] else ""
    repeatable_text = f"\n{pe('refresh')} <b>Repeatable:</b> Yes" if task["is_repeatable"] else ""
    text = (
        f"{emoji} <b>{task['title']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('info')} <b>Description:</b>\n{task['description']}\n\n"
        f"{pe('coins')} <b>Reward:</b> ₹{task['reward']}\n"
        f"{pe('zap')} <b>Type:</b> {task['task_type'].capitalize()}\n"
        f"{pe('check')} <b>Action:</b> {task['required_action'].capitalize()}"
        f"{category_text}{repeatable_text}{slots_text}"
        f"{status_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    if task["image_url"]:
        try:
            bot.send_photo(chat_id, task["image_url"], caption=text, parse_mode="HTML", reply_markup=markup)
            return
        except:
            pass
    safe_send(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("task_submit|"))
def task_submit_cb(call):
    user_id = call.from_user.id
    try:
        task_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    task = get_task(task_id)
    if not task or task["status"] != "active":
        safe_answer(call, "Task not available!", True)
        return
    safe_answer(call)
    if task["task_type"] == "channel" and task["task_channel"]:
        try:
            member = bot.get_chat_member(task["task_channel"], user_id)
            if member.status not in ["member", "administrator", "creator"]:
                markup = types.InlineKeyboardMarkup(row_width=1)
                if task["task_url"]:
                    markup.add(types.InlineKeyboardButton("📢 Join Channel", url=task["task_url"]))
                markup.add(types.InlineKeyboardButton(
                    "✅ I Joined - Verify",
                    callback_data=f"task_verify_join|{task_id}"
                ))
                safe_send(
                    call.message.chat.id,
                    f"{pe('warning')} <b>Join Required!</b>\n\n"
                    f"{pe('arrow')} Please join the channel first, then verify.",
                    reply_markup=markup
                )
                return
            else:
                auto_complete_channel_task(call.message.chat.id, user_id, task)
                return
        except:
            pass
    set_state(user_id, "task_submit_proof", {"task_id": task_id})
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Submit Proof for Task</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('task')} <b>Task:</b> {task['title']}\n"
        f"{pe('coins')} <b>Reward:</b> ₹{task['reward']}\n\n"
        f"{pe('info')} <b>Instructions:</b>\n"
        f"  {pe('play')} Send a screenshot or text proof\n"
        f"  {pe('play')} Admin will verify & approve\n"
        f"  {pe('play')} Reward credited after approval\n\n"
        f"{pe('pencil')} <b>Send your proof now:</b>\n"
        f"<i>(Photo, screenshot, or text description)</i>"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("task_verify_join|"))
def task_verify_join_cb(call):
    user_id = call.from_user.id
    try:
        task_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    task = get_task(task_id)
    if not task:
        safe_answer(call, "Task not found!", True)
        return
    if task["task_channel"]:
        try:
            member = bot.get_chat_member(task["task_channel"], user_id)
            if member.status in ["member", "administrator", "creator"]:
                safe_answer(call, "✅ Verified!")
                auto_complete_channel_task(call.message.chat.id, user_id, task)
                return
            else:
                safe_answer(call, "❌ Please join first!", True)
                return
        except:
            pass
    safe_answer(call)
    set_state(user_id, "task_submit_proof", {"task_id": task_id})
    safe_send(call.message.chat.id, f"{pe('pencil')} <b>Send proof of joining:</b>")

def auto_complete_channel_task(chat_id, user_id, task):
    existing_comp = get_task_completion(task["id"], user_id)
    if existing_comp:
        safe_send(chat_id, f"{pe('check')} <b>Task already completed!</b>")
        return
    existing_sub = get_task_submission(task["id"], user_id)
    if existing_sub and existing_sub["status"] == "pending":
        safe_send(chat_id, f"{pe('pending2')} <b>Already submitted for review!</b>")
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = get_user(user_id)
    if not user:
        return
    reward = task["reward"]
    db_execute(
        "INSERT INTO task_completions (task_id, user_id, completed_at, reward_paid) VALUES (?,?,?,?)",
        (task["id"], user_id, now, reward)
    )
    db_execute(
        "UPDATE tasks SET total_completions=total_completions+1 WHERE id=?",
        (task["id"],)
    )
    update_user(user_id, balance=user["balance"] + reward, total_earned=user["total_earned"] + reward)
    if task["max_completions"] > 0:
        updated = get_task(task["id"])
        if updated and updated["total_completions"] >= updated["max_completions"]:
            db_execute("UPDATE tasks SET status='completed' WHERE id=?", (task["id"],))
    safe_send(
        chat_id,
        f"{pe('party')} <b>Task Completed! 🎉</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('done')} <b>Task:</b> {task['title']}\n"
        f"{pe('coins')} <b>Reward:</b> ₹{reward}\n"
        f"{pe('fly_money')} <b>New Balance:</b> ₹{user['balance'] + reward:.2f}\n\n"
        f"{pe('trophy')} Keep completing tasks to earn more!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        safe_send(
            ADMIN_ID,
            f"{pe('check')} <b>Task Auto-Completed!</b>\n\n"
            f"{pe('task')} Task: {task['title']}\n"
            f"{pe('disguise')} User: {user['first_name']} (<code>{user_id}</code>)\n"
            f"{pe('coins')} Reward: ₹{reward}"
        )
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "tasks_my_completed")
def tasks_my_completed(call):
    user_id = call.from_user.id
    safe_answer(call)
    completed = get_user_completed_tasks(user_id)
    if not completed:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 Browse Tasks", callback_data="tasks_list"))
        safe_send(
            call.message.chat.id,
            f"{pe('info')} <b>No completed tasks yet!</b>\n\n"
            f"{pe('arrow')} Start completing tasks to earn rewards!",
            reply_markup=markup
        )
        return
    text = f"{pe('trophy')} <b>Your Completed Tasks</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    total_earned = 0
    for c in completed:
        text += (
            f"{pe('done')} <b>{c['task_title']}</b>\n"
            f"  {pe('coins')} ₹{c['reward_paid']} | {c['completed_at'][:10]}\n\n"
        )
        total_earned += c["reward_paid"]
    text += f"━━━━━━━━━━━━━━━━━━━━━━\n{pe('fly_money')} <b>Total Earned from Tasks: ₹{total_earned:.2f}</b>"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="tasks_back"))
    safe_send(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "tasks_my_pending")
def tasks_my_pending(call):
    user_id = call.from_user.id
    safe_answer(call)
    subs = db_execute(
        "SELECT ts.*, t.title as task_title, t.reward as task_reward "
        "FROM task_submissions ts JOIN tasks t ON ts.task_id=t.id "
        "WHERE ts.user_id=? AND ts.status='pending' ORDER BY ts.submitted_at DESC",
        (user_id,), fetch=True
    ) or []
    if not subs:
        safe_send(
            call.message.chat.id,
            f"{pe('info')} <b>No pending submissions!</b>\n\n"
            f"{pe('check')} All your submissions have been reviewed.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Back", callback_data="tasks_back")
            )
        )
        return
    text = f"{pe('pending2')} <b>Pending Submissions</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for s in subs:
        text += (
            f"{pe('hourglass')} <b>{s['task_title']}</b>\n"
            f"  {pe('coins')} ₹{s['task_reward']} | Submitted: {s['submitted_at'][:10]}\n"
            f"  {pe('info')} Status: Under Review\n\n"
        )
    text += f"━━━━━━━━━━━━━━━━━━━━━━\n{pe('bell')} <i>You'll be notified when reviewed!</i>"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="tasks_back"))
    safe_send(call.message.chat.id, text, reply_markup=markup)

