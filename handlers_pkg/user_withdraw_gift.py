from core import *

# ======================== WITHDRAW ========================
def is_withdraw_time():
    now = datetime.now()
    start = get_setting("withdraw_time_start")
    end = get_setting("withdraw_time_end")
    try:
        return int(start) <= now.hour <= int(end)
    except:
        return True

@bot.message_handler(func=lambda m: m.text == "🏧 Withdraw")
def withdraw_handler(message):
    user_id = message.from_user.id
    if not check_force_join(user_id):
        send_join_message(message.chat.id)
        return
    show_withdraw(message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "open_withdraw")
def open_withdraw_cb(call):
    safe_answer(call)
    show_withdraw(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "open_upi_withdraw")
def open_upi_withdraw_cb(call):
    safe_answer(call)
    show_upi_withdraw(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "open_redeem_withdraw")
def open_redeem_withdraw_cb(call):
    safe_answer(call)
    show_redeem_withdraw(call.message.chat.id, call.from_user.id)

def show_withdraw(chat_id, user_id):
    user = get_user(user_id)
    if not user:
        safe_send(chat_id, "Please send /start first.")
        return

    if user["banned"]:
        safe_send(chat_id, f"{pe('no_entry')} <b>Account Banned!</b>\nContact {HELP_USERNAME} for support.")
        return

    if not get_setting("withdraw_enabled"):
        safe_send(chat_id, f"{pe('no_entry')} <b>Withdrawals Disabled</b>\n{pe('hourglass')} Please try again later.")
        return

    if not is_withdraw_time():
        s = get_setting("withdraw_time_start")
        e = get_setting("withdraw_time_end")
        safe_send(
            chat_id,
            f"{pe('hourglass')} <b>Withdrawal Time Closed!</b>\n\n"
            f"{pe('info')} Available: <b>{s}:00</b> to <b>{e}:00</b>\n"
            f"{pe('bell')} Come back during withdrawal hours!"
        )
        return

    limit_result = withdraw_limit.check_and_send_limit_message(chat_id, user_id)
    if not limit_result["allowed"]:
        return

    min_upi = float(get_setting("min_withdraw") or 5)
    redeem_min = get_redeem_min_withdraw()
    redeem_gst = get_redeem_gst_cut()
    redeem_multiple = get_redeem_multiple_of()
    available_redeem = db_execute(
        "SELECT COUNT(*) as cnt FROM redeem_codes WHERE is_active=1 AND assigned_to=0",
        fetchone=True
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🏦 UPI Withdrawal", callback_data="open_upi_withdraw"))
    markup.add(
        types.InlineKeyboardButton(
            f"🎟 Redeem Code Withdrawal ({available_redeem['cnt'] if available_redeem else 0})",
            callback_data="open_redeem_withdraw"
        )
    )

    safe_send(
        chat_id,
        f"{pe('fly_money')} <b>Choose Withdrawal Method</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('money')} <b>Balance:</b> ₹{user['balance']:.2f}\n"
        f"{pe('calendar')} <b>Daily Limit:</b> {limit_result['used_today']}/{limit_result['daily_limit']} used today\n\n"
        f"🏦 <b>UPI:</b> minimum ₹{min_upi:.0f}\n"
        f"🎟 <b>Redeem Code:</b> minimum ₹{redeem_min:.0f}, multiples of ₹{redeem_multiple:.0f}, +₹{redeem_gst:.0f} GST/fee\n\n"
        f"{pe('info')} Redeem code stock is fully controlled by admin.",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("rwsel|"))
def redeem_select_cb(call):
    user_id = call.from_user.id
    try:
        code_id = int(call.data.split("|")[1])
    except Exception:
        safe_answer(call, "Invalid selection", True)
        return

    code_row = get_redeem_code_by_id(code_id)
    if not code_row or int(code_row["is_active"] or 0) != 1 or int(code_row["assigned_to"] or 0) != 0:
        safe_answer(call, "This code is no longer available.", True)
        return

    amount = float(code_row["amount"] or 0)
    gst_cut = max(get_redeem_gst_cut(), float(code_row["gst_cut"] or 0))
    total_debit = amount + gst_cut
    user = get_user(user_id)
    if not user:
        safe_answer(call, "User not found", True)
        return
    if amount < get_redeem_min_withdraw() or int(amount) % get_redeem_multiple_of() != 0:
        safe_answer(call, "This code is not valid for withdrawal rules.", True)
        return
    if user["balance"] < total_debit:
        safe_answer(call, f"Need ₹{total_debit:.0f} balance for this redemption.", True)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Confirm", callback_data=f"rwcnf|{code_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="open_redeem_withdraw")
    )
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} <b>Confirm Redeem Code Withdrawal</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('tag')} <b>Brand:</b> {code_row['platform']}\n"
        f"{pe('money')} <b>Code Value:</b> ₹{amount:.0f}\n"
        f"{pe('info')} <b>GST/Fee:</b> ₹{gst_cut:.0f}\n"
        f"{pe('fly_money')} <b>Total Deduction:</b> ₹{total_debit:.0f}\n\n"
        f"{pe('warning')} After confirmation, the code will be assigned instantly and cannot be reused.",
        reply_markup=markup
    )
    safe_answer(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rwcnf|"))
def redeem_confirm_cb(call):
    user_id = call.from_user.id
    try:
        code_id = int(call.data.split("|")[1])
    except Exception:
        safe_answer(call, "Invalid request", True)
        return

    code_row = get_redeem_code_by_id(code_id)
    if not code_row:
        safe_answer(call, "Code not found", True)
        return

    amount = float(code_row["amount"] or 0)
    gst_cut = max(get_redeem_gst_cut(), float(code_row["gst_cut"] or 0))
    total_debit = amount + gst_cut

    user = get_user(user_id)
    if not user:
        safe_answer(call, "User not found", True)
        return

    allowed, reason = withdraw_limit.can_user_withdraw(user_id)
    if not allowed:
        safe_answer(call, "Daily limit reached", True)
        safe_send(call.message.chat.id, reason)
        return

    if amount < get_redeem_min_withdraw() or int(amount) % get_redeem_multiple_of() != 0:
        safe_answer(call, "Code amount invalid", True)
        return

    if user["balance"] < total_debit:
        safe_answer(call, f"Need ₹{total_debit:.0f} balance.", True)
        return

    assigned = assign_redeem_code_atomic(code_id, user_id)
    if not assigned:
        safe_answer(call, "This code was just taken. Please choose another one.", True)
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    txn = generate_txn_id()
    update_user(
        user_id,
        balance=user["balance"] - total_debit,
        total_withdrawn=user["total_withdrawn"] + amount
    )
    w_id = db_lastrowid(
        "INSERT INTO withdrawals (user_id, amount, upi_id, status, created_at, processed_at, txn_id, method, redeem_code_id, redeem_product, gst_amount, net_amount, payout_code) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, amount, assigned["platform"], "approved", now, now, txn, "redeem_code", code_id, assigned["platform"], gst_cut, total_debit, assigned["code"])
    )
    log_admin_action(user_id, "redeem_withdraw", f"Redeemed code #{code_id} {assigned['platform']} ₹{amount:.0f}")
    safe_answer(call, "Redeem code sent!")
    safe_edit(
        call.message.chat.id, call.message.message_id,
        f"{pe('check')} <b>Redeem Code Withdrawal Successful!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('tag')} <b>Brand:</b> {assigned['platform']}\n"
        f"{pe('money')} <b>Code Value:</b> ₹{amount:.0f}\n"
        f"{pe('info')} <b>GST/Fee Deducted:</b> ₹{gst_cut:.0f}\n"
        f"{pe('fly_money')} <b>Total Balance Deducted:</b> ₹{total_debit:.0f}\n"
        f"{pe('key')} <b>Your Code:</b> <code>{assigned['code']}</code>\n"
        f"{pe('bookmark')} <b>TXN:</b> <code>{txn}</code>\n\n"
        f"{pe('warning')} Keep this code private. It has been removed from available stock automatically.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        safe_send(
            ADMIN_ID,
            f"{pe('siren')} <b>Redeem Code Withdrawal Used</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"User: {user['first_name']} (<code>{user_id}</code>)\n"
            f"Brand: {assigned['platform']}\n"
            f"Value: ₹{amount:.0f}\n"
            f"GST: ₹{gst_cut:.0f}\n"
            f"Total Deducted: ₹{total_debit:.0f}\n"
            f"Code ID: #{code_id}\n"
            f"Withdrawal ID: #{w_id}\n"
            f"TXN: <code>{txn}</code>"
        )
    except Exception as e:
        print(f"Admin redeem notify error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "use_saved_upi")
def use_saved_upi(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call)
    set_state(user_id, "enter_amount", {"upi_id": user["upi_id"]})
    min_w = get_setting("min_withdraw")
    max_w = get_setting("max_withdraw_per_day")
    safe_send(
        call.message.chat.id,
        f"{pe('money')} <b>Enter Withdrawal Amount</b>\n\n"
        f"{pe('fly_money')} Balance: ₹{user['balance']:.2f}\n"
        f"{pe('down_arrow')} Min: ₹{min_w} | Max: ₹{max_w}\n\n"
        f"{pe('pencil')} Type the amount:"
    )

@bot.callback_query_handler(func=lambda call: call.data == "enter_new_upi")
def enter_new_upi(call):
    user_id = call.from_user.id
    safe_answer(call)
    set_state(user_id, "enter_upi")
    safe_send(call.message.chat.id, f"{pe('pencil')} <b>Enter New UPI ID</b>\n\n{pe('info')} Example: <code>name@paytm</code>")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_withdraw")
def cancel_withdraw(call):
    safe_answer(call, "Cancelled!")
    clear_state(call.from_user.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

# ======================== GIFT ========================
@bot.message_handler(func=lambda m: m.text == "🎁 Gift")
def gift_handler(message):
    user_id = message.from_user.id
    if not check_force_join(user_id):
        send_join_message(message.chat.id)
        return
    user = get_user(user_id)
    if not user:
        safe_send(message.chat.id, "Please send /start first.")
        return
    show_gift_menu(message.chat.id, user)

def show_gift_menu(chat_id, user):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎟 Claim Gift Code", callback_data="redeem_code"),
        types.InlineKeyboardButton("🎁 Create Gift", callback_data="create_gift"),
    )
    markup.add(types.InlineKeyboardButton("🎰 Daily Bonus", callback_data="daily_bonus"))
    safe_send(
        chat_id,
        f"{pe('party')} <b>Gift & Bonus Center</b> {pe('sparkle')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('fly_money')} <b>Balance:</b> ₹{user['balance']:.2f}\n\n"
        f"{pe('star')} <b>What can you do here?</b>\n"
        f"  {pe('arrow')} <b>Redeem Code</b> — Claim a gift code\n"
        f"  {pe('arrow')} <b>Create Gift</b> — Create code from balance\n"
        f"  {pe('arrow')} <b>Daily Bonus</b> — Free daily coins!\n\n"
        f"{pe('bulb')} <i>Share codes with friends!</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "redeem_code")
def redeem_code_cb(call):
    user_id = call.from_user.id
    safe_answer(call)
    set_state(user_id, "enter_gift_code")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Enter Gift Code</b>\n\n"
        f"{pe('info')} Type your gift code below:\n"
        f"{pe('arrow')} Example: <code>GIFT1234</code>"
    )

@bot.callback_query_handler(func=lambda call: call.data == "create_gift")
def create_gift_cb(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user:
        safe_answer(call, "Error!", True)
        return
    min_gift = get_setting("min_gift_amount")
    if user["balance"] < min_gift:
        safe_answer(call, f"❌ Need at least ₹{min_gift} balance to create gift!", True)
        return
    safe_answer(call)
    set_state(user_id, "enter_gift_amount")
    max_gift = get_setting("max_gift_create")
    safe_send(
        call.message.chat.id,
        f"{pe('pencil')} <b>Create Gift Code</b>\n\n"
        f"{pe('fly_money')} Balance: ₹{user['balance']:.2f}\n"
        f"{pe('down_arrow')} Min: ₹{min_gift} | Max: ₹{max_gift}\n\n"
        f"{pe('arrow')} Enter gift amount:"
    )

@bot.callback_query_handler(func=lambda call: call.data == "daily_bonus")
def daily_bonus_cb(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user:
        safe_answer(call, "Please send /start first.", True)
        return
    if not bool(get_setting("daily_bonus_enabled")):
        safe_answer(call, "Daily bonus is disabled.", True)
        return
    today = datetime.now().strftime("%Y-%m-%d")
    if (user["last_daily"] or "") == today:
        safe_answer(call, "Already claimed today!", True)
        return
    min_refs = int(get_setting("referral_min_activity_for_bonus") or 0)
    if int(user["referral_count"] or 0) < min_refs:
        safe_answer(call, f"Need at least {min_refs} referral(s) to claim daily bonus.", True)
        return
    if bool(get_setting("random_daily_bonus_enabled")):
        bonus = round(random.uniform(float(get_setting("random_daily_bonus_min") or 0.5), float(get_setting("random_daily_bonus_max") or 2.0)), 2)
    else:
        bonus = float(get_setting("daily_bonus") or 0)
    update_user(
        user_id,
        balance=user["balance"] + bonus,
        total_earned=user["total_earned"] + bonus,
        last_daily=today,
        bonus_balance=float(user["bonus_balance"] or 0) + bonus,
    )
    mark_user_active(user_id)
    safe_answer(call, f"🎉 +₹{bonus} Daily Bonus!")
    safe_edit(
        call.message.chat.id, call.message.message_id,
        f"{pe('party')} <b>Daily Bonus Claimed!</b> {pe('check')}\n\n"
        f"{pe('money')} You received <b>₹{bonus}</b>!\n"
        f"{pe('fly_money')} New Balance: <b>₹{user['balance'] + bonus:.2f}</b>\n"
        f"{pe('info')} Minimum referrals required: <b>{min_refs}</b>\n\n"
        f"{pe('sparkle')} Come back tomorrow for more rewards!"
    )
