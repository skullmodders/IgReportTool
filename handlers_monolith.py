from core import *

@bot.message_handler(commands=['getdb'])
def send_db(message):
    if is_admin(message.from_user.id):
        with open(DB_PATH, "rb") as f:
            bot.send_document(message.chat.id, f)
        log_admin_action(message.from_user.id, "getdb", "Downloaded database")
# ======================== USER STATES ========================
user_states = {}
states_lock = threading.Lock()

@bot.message_handler(commands=["start"])
def start_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "User"
    chat_id = message.chat.id

    if get_setting("bot_maintenance") and not is_admin(user_id):
        safe_send(
            chat_id,
            f"{pe('gear')} <b>Bot Under Maintenance</b>\n\n"
            f"{pe('hourglass')} We'll be back soon!\n"
            f"{pe('info')} Contact: {HELP_USERNAME}"
        )
        return

    args = message.text.split()
    referred_by = 0
    if len(args) > 1:
        try:
            ref_id = int(args[1])
            if ref_id != user_id:
                referred_by = ref_id
        except:
            pass

    is_new = create_user(user_id, username, first_name, referred_by)
    update_user(user_id, username=username, first_name=first_name)

    if not check_force_join(user_id):
        send_join_message(chat_id)
        return

    send_welcome(chat_id, user_id, first_name, is_new)

    if is_new and not is_admin(user_id):
        try:
            total = get_user_count()
            safe_send(
                ADMIN_ID,
                f"{pe('bell')} <b>New User Joined!</b>\n\n"
                f"{pe('disguise')} <b>Name:</b> {first_name}\n"
                f"{pe('link')} <b>Username:</b> @{username}\n"
                f"{pe('info')} <b>ID:</b> <code>{user_id}</code>\n"
                f"{pe('chart_up')} <b>Total Users:</b> {total}\n"
                f"{pe('arrow')} <b>Referred by:</b> {referred_by or 'None'}"
            )
        except:
            pass

def send_welcome(chat_id, user_id, first_name, is_new=False):
    user = get_user(user_id)
    if not user:
        return
    balance = user["balance"]
    per_refer = get_setting("per_refer")
    min_withdraw = get_setting("min_withdraw")
    welcome_image = get_setting("welcome_image")
    try:
        bot_info = bot.get_me()
        bot_username = bot_info.username
    except:
        bot_username = "bot"
    refer_link = f"https://t.me/{bot_username}?start={user_id}"
    caption = (
        f"{pe('crown')} <b>Welcome to UPI Loot Pay!</b> {pe('fire')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('smile')} Hello, <b>{first_name}</b>!\n\n"
        f"{pe('fly_money')} <b>Your Balance:</b> ₹{balance:.2f}\n"
        f"{pe('star')} <b>Per Refer:</b> ₹{per_refer}\n"
        f"{pe('down_arrow')} <b>Min Withdraw:</b> ₹{min_withdraw}\n\n"
        f"{pe('zap')} <b>How to Earn?</b>\n"
        f"  {pe('play')} Share your referral link\n"
        f"  {pe('play')} Friends complete verification → You earn ₹{per_refer}\n"
        f"  {pe('play')} Complete Tasks & earn more!\n"
        f"  {pe('play')} Withdraw to UPI instantly!\n\n"
        f"{pe('link')} <b>Your Refer Link:</b>\n"
        f"<code>{refer_link}</code>\n\n"
        f"{pe('sparkle')} <i>No limit! Earn unlimited!</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        bot.send_photo(chat_id, welcome_image, caption=caption, parse_mode="HTML", reply_markup=get_main_keyboard(user_id))
    except:
        safe_send(chat_id, caption, reply_markup=get_main_keyboard(user_id))

# ======================== VERIFY JOIN ========================
@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_join(call):
    user_id = call.from_user.id

    if check_force_join(user_id):
        safe_answer(call, "✅ Channel verification complete!")

        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

        user = get_user(user_id)

        if not user:
            create_user(
                user_id,
                call.from_user.username or "",
                call.from_user.first_name or "User"
            )
            user = get_user(user_id)

        if int(user["ip_verified"] or 0) != 1:
            send_ip_verify_message(call.message.chat.id, user_id)
            return

        ok, reason = anticheat.can_pay_referral_bonus(user_id)

        if ok:
            process_referral_bonus(user_id)

        send_welcome(call.message.chat.id, user_id, call.from_user.first_name or "User", True)
    else:
        safe_answer(call, "❌ Please join ALL channels first!", True)


@bot.callback_query_handler(func=lambda call: call.data == "check_ip_verified")
def check_ip_verified(call):
    user_id = call.from_user.id
    user = get_user(user_id)

    if not user:
        safe_answer(call, "❌ User not found!", True)
        return

    if int(user["ip_verified"] or 0) != 1:
        safe_answer(call, "❌ IP verification failed ", True)
        return

    ok, reason = anticheat.can_pay_referral_bonus(user_id)

    if ok:
        process_referral_bonus(user_id)
        safe_answer(call, "✅ IP verification complete!")
    else:
        safe_answer(call, f"❌ {reason}", True)
        return

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

    send_welcome(call.message.chat.id, user_id, call.from_user.first_name or "User", False)
# ======================== BALANCE ========================
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance_handler(message):
    user_id = message.from_user.id
    if not check_force_join(user_id):
        send_join_message(message.chat.id)
        return
    user = get_user(user_id)
    if not user:
        safe_send(message.chat.id, "Please send /start first.")
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🏧 Withdraw", callback_data="open_withdraw"),
        types.InlineKeyboardButton("👥 Refer & Earn", callback_data="open_refer"),
    )
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance"))
    text = (
        f"{pe('money')} <b>Your Wallet</b> {pe('diamond')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('fly_money')} <b>Balance:</b> ₹{user['balance']:.2f}\n"
        f"{pe('chart_up')} <b>Total Earned:</b> ₹{user['total_earned']:.2f}\n"
        f"{pe('check')} <b>Total Withdrawn:</b> ₹{user['total_withdrawn']:.2f}\n"
        f"{pe('thumbs_up')} <b>Total Referrals:</b> {user['referral_count']}\n\n"
        f"{pe('star')} <b>Per Refer:</b> ₹{get_setting('per_refer')}\n"
        f"{pe('down_arrow')} <b>Min Withdraw:</b> ₹{get_setting('min_withdraw')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    safe_send(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "refresh_balance")
def refresh_balance(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user:
        safe_answer(call, "Error!", True)
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🏧 Withdraw", callback_data="open_withdraw"),
        types.InlineKeyboardButton("👥 Refer & Earn", callback_data="open_refer"),
    )
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance"))
    text = (
        f"{pe('money')} <b>Your Wallet</b> {pe('diamond')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('fly_money')} <b>Balance:</b> ₹{user['balance']:.2f}\n"
        f"{pe('chart_up')} <b>Total Earned:</b> ₹{user['total_earned']:.2f}\n"
        f"{pe('check')} <b>Total Withdrawn:</b> ₹{user['total_withdrawn']:.2f}\n"
        f"{pe('thumbs_up')} <b>Total Referrals:</b> {user['referral_count']}\n\n"
        f"{pe('star')} <b>Per Refer:</b> ₹{get_setting('per_refer')}\n"
        f"{pe('down_arrow')} <b>Min Withdraw:</b> ₹{get_setting('min_withdraw')}\n\n"
        f"{pe('refresh')} <i>Just refreshed!</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    safe_edit(call.message.chat.id, call.message.message_id, text, reply_markup=markup)
    safe_answer(call, "✅ Refreshed!")

# ======================== REFER ========================
@bot.message_handler(func=lambda m: m.text == "👥 Refer")
def refer_handler(message):
    user_id = message.from_user.id
    if not check_force_join(user_id):
        send_join_message(message.chat.id)
        return
    user = get_user(user_id)
    if not user:
        safe_send(message.chat.id, "Please send /start first.")
        return
    show_refer(message.chat.id, user_id, user)

@bot.callback_query_handler(func=lambda call: call.data == "open_refer")
def open_refer_cb(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user:
        safe_answer(call, "Error!", True)
        return
    safe_answer(call)
    show_refer(call.message.chat.id, user_id, user)

def show_refer(chat_id, user_id, user):
    per_refer = get_setting("per_refer")
    try:
        bot_username = bot.get_me().username
    except:
        bot_username = "bot"
    refer_link = f"https://t.me/{bot_username}?start={user_id}"
    share_msg = f"💰 Earn ₹{per_refer} per refer! Join {refer_link}"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(
        "📤 Share My Referral Link",
        url=f"https://t.me/share/url?url={refer_link}&text={share_msg}"
    ))
    text = (
        f"{pe('fire')} <b>Refer & Earn</b> {pe('fly_money')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('star')} <b>Earn ₹{per_refer} per referral!</b>\n\n"
        f"{pe('link')} <b>Your Referral Link:</b>\n"
        f"<code>{refer_link}</code>\n\n"
        f"{pe('chart_up')} <b>Your Stats:</b>\n"
        f"  {pe('thumbs_up')} Referrals: {user['referral_count']}\n"
        f"  {pe('money')} Earned: ₹{user['referral_count'] * per_refer:.2f}\n\n"
        f"{pe('zap')} <b>How It Works:</b>\n"
        f"  {pe('play')} Share your link\n"
        f"  {pe('play')} Friend joins the bot\n"
        f"  {pe('play')} Friend joins all required channels and verifies IP\n"
        f"  {pe('play')} You get ₹{per_refer} after full verification!\n\n"
        f"{pe('boom')} <b>Share on:</b> WhatsApp, Instagram,\n"
        f"Telegram groups, Facebook!\n\n"
        f"{pe('crown')} <i>No limit! Earn unlimited!</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    safe_send(chat_id, text, reply_markup=markup)

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
        f"🎟 <b>Redeem Code:</b> minimum ₹{redeem_min:.0f}, multiples of ₹5, +₹{redeem_gst:.0f} GST/fee\n\n"
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
    if amount < get_redeem_min_withdraw() or int(amount) % 5 != 0:
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

    if amount < get_redeem_min_withdraw() or int(amount) % 5 != 0:
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
        safe_answer(call, "Error!", True)
        return
    today = datetime.now().strftime("%Y-%m-%d")
    if user["last_daily"] == today:
        safe_answer(call, "❌ Already claimed today! Come back tomorrow.", True)
        return
    bonus = get_setting("daily_bonus")
    update_user(user_id, balance=user["balance"] + bonus, total_earned=user["total_earned"] + bonus, last_daily=today)
    safe_answer(call, f"🎉 +₹{bonus} Daily Bonus!")
    safe_send(
        call.message.chat.id,
        f"{pe('party')} <b>Daily Bonus Claimed!</b> {pe('check')}\n\n"
        f"{pe('money')} You received <b>₹{bonus}</b>!\n"
        f"{pe('fly_money')} New Balance: <b>₹{user['balance'] + bonus:.2f}</b>\n\n"
        f"{pe('bell')} Come back tomorrow for more!"
    )

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
        if amount > user["balance"]:
            safe_send(message.chat.id, f"{pe('cross')} Insufficient balance! You have ₹{user['balance']:.2f}")
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
        if amount < get_redeem_min_withdraw() or int(amount) % 5 != 0:
            safe_send(message.chat.id, f"{pe('cross')} Amount must be at least ₹{get_redeem_min_withdraw():.0f} and in multiples of ₹5.")
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
        if field == "amount" and (value < get_redeem_min_withdraw() or int(value) % 5 != 0):
            safe_send(message.chat.id, f"{pe('cross')} Amount must be at least ₹{get_redeem_min_withdraw():.0f} and in multiples of ₹5.")
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

    if amount > user["balance"]:
        safe_answer(call, "❌ Insufficient balance!", True)
        return

    # ✅ DAILY LIMIT FINAL CHECK YAHAN
    allowed, reason = withdraw_limit.can_user_withdraw(user_id)
    if not allowed:
        safe_answer(call, "❌ Daily limit reached!", True)
        safe_send(call.message.chat.id, reason)
        return

    update_user(user_id, balance=user["balance"] - amount)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    w_id = db_lastrowid(
        "INSERT INTO withdrawals (user_id, amount, upi_id, status, created_at) VALUES (?,?,?,?,?)",
        (user_id, amount, upi_id, "pending", now)
    )

    safe_answer(call, "✅ Withdrawal request submitted!")
    safe_edit(
        call.message.chat.id, call.message.message_id,
        f"{pe('check')} <b>Withdrawal Submitted!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('fly_money')} <b>Amount:</b> ₹{amount}\n"
        f"{pe('link')} <b>UPI:</b> <code>{upi_id}</code>\n"
        f"{pe('hourglass')} <b>Status:</b> Pending ⏳\n\n"
        f"📋 <i>10% GST deducted for UPI Processing & Management</i>\n"
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
            f"{pe('disguise')} <b>User:</b> {user['first_name']} (<code>{user_id}</code>)\n"
            f"{pe('fly_money')} <b>Amount:</b> ₹{amount}\n"
            f"{pe('link')} <b>UPI:</b> <code>{upi_id}</code>\n"
            f"{pe('money')} <b>Remaining:</b> ₹{user['balance'] - amount:.2f}\n"
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
        f"{pe('info')} Min Redeem: ₹{get_redeem_min_withdraw():.0f} | GST: ₹{get_redeem_gst_cut():.0f}",
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
    safe_send(call.message.chat.id, f"{pe('gear')} Min: ₹{get_redeem_min_withdraw():.0f}\nGST: ₹{get_redeem_gst_cut():.0f}\nEnabled: {'Yes' if toggle else 'No'}", reply_markup=markup)

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


# ======================== USER PANEL SWITCH ========================
@bot.message_handler(func=lambda m: m.text == "🔙 User Panel" and is_admin(m.from_user.id))
def back_user_panel(message):
    safe_send(
        message.chat.id,
        f"{pe('check')} Switched to User Panel.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


# ======================== HELP ========================
@bot.message_handler(commands=["help"])
def help_cmd(message):
    safe_send(
        message.chat.id,
        f"{pe('question')} <b>Help & Support</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('arrow')} /start — Start the bot\n"
        f"{pe('arrow')} 💰 Balance — Check wallet\n"
        f"{pe('arrow')} 👥 Refer — Get referral link\n"
        f"{pe('arrow')} 🏧 Withdraw — Withdraw earnings\n"
        f"{pe('arrow')} 🎁 Gift — Gift codes & daily bonus\n"
        f"{pe('arrow')} 📋 Tasks — Complete tasks & earn\n\n"
        f"{pe('info')} Support: {HELP_USERNAME}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
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


# ======================== RUN BOT ========================
print("=" * 50)
print("  UPI Loot Pay Bot Starting...")
print(f"  Admin ID: {ADMIN_ID}")
print(f"  Force Join: {FORCE_JOIN_CHANNELS}")
print(f"  Notification Channel: {NOTIFICATION_CHANNEL}")

