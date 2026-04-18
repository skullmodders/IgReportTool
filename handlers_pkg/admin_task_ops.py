from core import *
from .admin_task_manager import show_admin_task_detail

# ======================== TASK TYPE SELECTION ========================
@bot.callback_query_handler(func=lambda call: call.data.startswith("task_type_sel|"))
def task_type_sel_cb(call):
    if not is_admin(call.from_user.id): return
    user_id = call.from_user.id
    try:
        task_type = call.data.split("|")[1]
    except:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call)
    data = get_state_data(user_id)
    data["task_type"] = task_type
    set_state(user_id, "admin_task_create_url", data)
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Step 5/7: Task URL</b>\n\n"
        f"Enter the task link/URL\n"
        f"(e.g. https://t.me/channel or YouTube link)\n"
        f"Or type <code>skip</code> if no URL needed:"
    )
# ======================== TASK SUBMISSION APPROVE / REJECT ========================
@bot.callback_query_handler(func=lambda call: call.data.startswith("tsub_approve|"))
def tsub_approve(call):
    if not is_admin(call.from_user.id):
        safe_answer(call, "❌ Not authorized!", True)
        return
    try:
        sub_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Invalid!", True)
        return
    sub = get_task_submission_by_id(sub_id)
    if not sub:
        safe_answer(call, "Submission not found!", True)
        return
    if sub["status"] != "pending":
        safe_answer(call, f"Already {sub['status']}!", True)
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reward = sub["task_reward"]
    uid = sub["user_id"]
    task_id = sub["task_id"]
    db_execute(
        "UPDATE task_submissions SET status='approved', reviewed_at=?, reward_paid=? WHERE id=?",
        (now, reward, sub_id)
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
    task = get_task(task_id)
    if task and task["max_completions"] > 0:
        updated_task = get_task(task_id)
        if updated_task and updated_task["total_completions"] >= updated_task["max_completions"]:
            db_execute("UPDATE tasks SET status='completed' WHERE id=?", (task_id,))
    log_admin_action(call.from_user.id, "approve_task_sub", f"Approved sub #{sub_id} ₹{reward} for {uid}")
    safe_answer(call, "✅ Approved & Rewarded!")
    try:
        safe_edit(
            call.message.chat.id, call.message.message_id,
            (call.message.text or call.message.caption or "") +
            f"\n\n{pe('check')} <b>APPROVED ✅</b>\n"
            f"{pe('coins')} ₹{reward} sent to user!"
        )
    except:
        safe_send(
            call.message.chat.id,
            f"{pe('check')} <b>Submission #{sub_id} APPROVED!</b>\n"
            f"{pe('coins')} ₹{reward} sent to <code>{uid}</code>"
        )
    try:
        safe_send(
            uid,
            f"{pe('party')} <b>Task Approved! 🎉</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('task')} <b>Task:</b> {sub['task_title']}\n"
            f"{pe('coins')} <b>Reward:</b> ₹{reward}\n"
            f"{pe('fly_money')} <b>New Balance:</b> ₹{(user['balance'] + reward) if user else reward:.2f}\n\n"
            f"{pe('trophy')} Keep completing tasks!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
    except:
        pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("tsub_reject|"))
def tsub_reject(call):
    if not is_admin(call.from_user.id):
        safe_answer(call, "❌ Not authorized!", True)
        return
    try:
        sub_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Invalid!", True)
        return
    sub = get_task_submission_by_id(sub_id)
    if not sub:
        safe_answer(call, "Submission not found!", True)
        return
    if sub["status"] != "pending":
        safe_answer(call, f"Already {sub['status']}!", True)
        return
    safe_answer(call)
    markup = types.InlineKeyboardMarkup(row_width=1)
    reasons = [
        "Invalid proof",
        "Screenshot unclear",
        "Task not completed",
        "Fake submission",
        "Duplicate submission",
    ]
    for r in reasons:
        markup.add(types.InlineKeyboardButton(f"❌ {r}", callback_data=f"tsub_rej_reason|{sub_id}|{r}"))
    markup.add(types.InlineKeyboardButton("✏️ Custom Reason", callback_data=f"tsub_rej_custom|{sub_id}"))
    markup.add(types.InlineKeyboardButton("🔙 Cancel", callback_data="cancel_action"))
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} <b>Select Rejection Reason</b>\n\n"
        f"{pe('task')} Task: {sub['task_title']}\n"
        f"{pe('disguise')} User: <code>{sub['user_id']}</code>",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("tsub_rej_reason|"))
def tsub_rej_reason_cb(call):
    if not is_admin(call.from_user.id): return
    try:
        parts = call.data.split("|")
        sub_id = int(parts[1])
        reason = parts[2]
    except:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call, "❌ Rejected!")
    process_task_rejection(call.message.chat.id, sub_id, reason)


@bot.callback_query_handler(func=lambda call: call.data.startswith("tsub_rej_custom|"))
def tsub_rej_custom_cb(call):
    if not is_admin(call.from_user.id): return
    try:
        sub_id = int(call.data.split("|")[1])
    except:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call)
    set_state(call.from_user.id, "admin_task_reject_reason", {"sub_id": sub_id})
    safe_send(call.message.chat.id, f"{pe('pencil')} <b>Enter custom rejection reason:</b>")


def process_task_rejection(chat_id, sub_id, reason):
    sub = get_task_submission_by_id(sub_id)
    if not sub:
        safe_send(chat_id, f"{pe('cross')} Submission not found!")
        return
    if sub["status"] != "pending":
        safe_send(chat_id, f"{pe('cross')} Already {sub['status']}!")
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute(
        "UPDATE task_submissions SET status='rejected', reviewed_at=?, admin_note=? WHERE id=?",
        (now, reason, sub_id)
    )
    safe_send(
        chat_id,
        f"{pe('cross')} <b>Submission #{sub_id} Rejected!</b>\n\n"
        f"{pe('task')} Task: {sub['task_title']}\n"
        f"{pe('disguise')} User: <code>{sub['user_id']}</code>\n"
        f"{pe('info')} Reason: {reason}"
    )
    try:
        safe_send(
            sub["user_id"],
            f"{pe('cross')} <b>Task Submission Rejected</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('task')} <b>Task:</b> {sub['task_title']}\n"
            f"{pe('info')} <b>Reason:</b> {reason}\n\n"
            f"{pe('arrow')} You can try submitting again!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
    except:
        pass


