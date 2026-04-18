from core import *

SOURCE_LABELS = {
    "main": "Main Balance",
    "referral": "Referral Balance",
    "daily_bonus": "Daily Bonus Balance",
    "gift": "Gift Code Balance",
}

SETTING_META = [
    ("games_section_enabled", "toggle", "Games Section ON/OFF"),
    ("games_access_min_referrals", "int", "Minimum Referrals To Play"),
    ("mine_game_enabled", "toggle", "Mine Game ON/OFF"),
    ("mine_telegram_enabled", "toggle", "Telegram Mode"),
    ("mine_global_win_rate", "number", "Win Ratio %"),
    ("mine_global_loss_rate", "number", "Loss Ratio %"),
    ("mine_force_win_all", "toggle", "Force Win All"),
    ("mine_force_loss_all", "toggle", "Force Loss All"),
    ("mine_force_win_users", "user_list", "Force Win Users"),
    ("mine_force_loss_users", "user_list", "Force Loss Users"),
    ("mine_base_multiplier", "number", "Base Multiplier"),
    ("mine_progressive_multiplier_rate", "number", "Progressive Rate"),
    ("mine_max_multiplier_cap", "number", "Max Multiplier Cap"),
    ("mine_jackpot_multiplier", "number", "Jackpot Multiplier"),
    ("mine_min_bet", "number", "Min Bet"),
    ("mine_max_bet", "number", "Max Bet"),
    ("mine_grid_size", "int", "Grid Size"),
    ("mine_min_mines", "int", "Min Mines"),
    ("mine_max_mines", "int", "Max Mines"),
    ("mine_daily_play_limit", "int", "Daily Play Limit"),
    ("mine_hourly_play_limit", "int", "Hourly Play Limit"),
    ("mine_cooldown_seconds", "int", "Cooldown Seconds"),
    ("mine_winning_tax_percent", "number", "Winning Tax %"),
    ("mine_gst_on_winnings", "number", "GST On Winnings %"),
    ("mine_max_win_amount_per_session", "number", "Max Win / Session"),
    ("mine_daily_win_cap_per_user", "number", "Daily Win Cap / User"),
    ("mine_house_edge_percent", "number", "House Edge %"),
    ("mine_consecutive_win_limit", "int", "Consecutive Win Limit"),
    ("mine_consecutive_loss_limit", "int", "Consecutive Loss Limit"),
    ("mine_blacklist_users", "user_list", "Blacklist Users"),
    ("mine_sound_effects_enabled", "toggle", "Sound Effects"),
    ("mine_risk_indicator_enabled", "toggle", "Risk Indicator"),
    ("mine_auto_cash_out_enabled", "toggle", "Auto Cash Out"),
    ("mine_force_safe_first_tile", "toggle", "Safe First Tile"),
]
SETTING_META_MAP = {k: {"type": t, "label": lbl} for k, t, lbl in SETTING_META}


def _games_enabled():
    return bool(get_setting("games_section_enabled"))


def _games_unavailable_text():
    return "The games section is currently unavailable."


def _active_mine_session(user_id):
    return db_execute(
        "SELECT * FROM mine_game_sessions WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1",
        (user_id,), fetchone=True
    )


def _safe_grid_size():
    return max(3, min(10, safe_int(get_setting("mine_grid_size"), 5)))


def _mine_bounds(grid_size=None):
    grid_size = _safe_grid_size() if grid_size is None else max(3, min(10, safe_int(grid_size, 5)))
    total = grid_size * grid_size
    min_mines = max(1, safe_int(get_setting("mine_min_mines"), 1))
    max_mines = min(total - 1, max(min_mines, safe_int(get_setting("mine_max_mines"), total - 1)))
    return grid_size, total, min_mines, max_mines


def _build_empty_board(size):
    return ["hidden"] * (size * size)


def _cleanup_stale_sessions(user_id=None, stale_minutes=120):
    params = []
    query = "SELECT * FROM mine_game_sessions WHERE status='active'"
    if user_id is not None:
        query += " AND user_id=?"
        params.append(user_id)
    rows = db_execute(query, tuple(params), fetch=True) or []
    cutoff = datetime.now() - timedelta(minutes=stale_minutes)
    for row in rows:
        dt = parse_dt(row["updated_at"]) or parse_dt(row["created_at"])
        if dt and dt < cutoff:
            _finalize_session(row, "loss", 0.0, 0.0, 0.0)


def _remaining_hidden_count(session):
    total_tiles = safe_int(session["grid_size"], 5) ** 2
    revealed = len(safe_json(session["revealed_json"], []))
    return max(0, total_tiles - revealed)


def _risk_percent(session):
    if not bool(get_setting("mine_risk_indicator_enabled")):
        return None
    remaining_hidden = _remaining_hidden_count(session)
    mines_total = max(1, safe_int(session["mines_count"], 1))
    revealed = safe_json(session["revealed_json"], [])
    safe_revealed = safe_int(session["gems_found"], 0)
    hits_so_far = max(0, len(revealed) - safe_revealed)
    mines_left = max(0, mines_total - hits_so_far)
    if remaining_hidden <= 0:
        return 0.0
    return round((mines_left / max(1, remaining_hidden)) * 100.0, 2)


def _render_session_text(session, final_message=""):
    total_tiles = safe_int(session["grid_size"], 5) ** 2
    safe_tiles = max(1, total_tiles - safe_int(session["mines_count"], 1))
    payout = round(float(session["bet_amount"]) * max(1.0, float(session["current_multiplier"])), 2)
    source = SOURCE_LABELS.get(session["source_balance"], session["source_balance"])
    risk = _risk_percent(session)
    risk_line = f"\n{pe('warning')} <b>Risk:</b> {risk}%" if risk is not None else ""
    sound_line = f"\n{pe('speaker')} <b>Sound:</b> {'ON' if bool(get_setting('mine_sound_effects_enabled')) else 'OFF'}"
    return (
        f"{pe('game')} <b>Mine Game</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('money')} <b>Bet:</b> ₹{float(session['bet_amount']):.2f}\n"
        f"{pe('target')} <b>Mines:</b> {safe_int(session['mines_count'])}\n"
        f"{pe('diamond')} <b>Gems Found:</b> {safe_int(session['gems_found'])}/{safe_tiles}\n"
        f"{pe('chart_up')} <b>Multiplier:</b> x{float(session['current_multiplier']):.2f}\n"
        f"{pe('fly_money')} <b>Cash Out Value:</b> ₹{payout:.2f}\n"
        f"{pe('wallet')} <b>Source:</b> {source}"
        f"{risk_line}{sound_line}\n\n"
        f"{final_message or 'Pick a tile. Cash out anytime after a gem.'}"
    )


def _render_board_markup(session, game_over=False):
    board = safe_json(session["board_json"], [])
    revealed = set(safe_json(session["revealed_json"], []))
    size = safe_int(session["grid_size"], 5)
    total = size * size
    if len(board) < total:
        board.extend(["hidden"] * (total - len(board)))
    markup = types.InlineKeyboardMarkup(row_width=size)
    for r in range(size):
        row = []
        for c in range(size):
            idx = r * size + c
            if idx in revealed or game_over:
                state = board[idx]
                label = "💎" if state == "gem" else "💣" if state == "mine" else "⬜"
                row.append(types.InlineKeyboardButton(label, callback_data="mine_noop"))
            else:
                row.append(types.InlineKeyboardButton("❔", callback_data=f"mine_pick|{session['id']}|{idx}"))
        markup.row(*row)
    if not game_over:
        markup.row(
            types.InlineKeyboardButton("💰 Cash Out", callback_data=f"mine_cashout|{session['id']}"),
            types.InlineKeyboardButton("🛑 End", callback_data=f"mine_end|{session['id']}"),
        )
    else:
        markup.row(types.InlineKeyboardButton("🔁 Play Again", callback_data="mine_play_again"))
    return markup


def _determine_safe_target(user_id, mines_count, grid_size):
    total_tiles = grid_size * grid_size
    safe_tiles = max(1, total_tiles - mines_count)
    outcome_mode = get_mine_outcome_mode(user_id)
    if outcome_mode == "force_win":
        return safe_tiles, outcome_mode
    if outcome_mode == "force_loss":
        return 0, outcome_mode
    win_ratio = max(0.0, safe_float(get_setting("mine_global_win_rate"), 45))
    loss_ratio = max(0.0, safe_float(get_setting("mine_global_loss_rate"), 55))
    total_ratio = win_ratio + loss_ratio
    win_chance = (win_ratio / total_ratio) if total_ratio > 0 else 0.45
    if random.random() <= win_chance:
        target = random.randint(1, max(1, min(safe_tiles, 4 + max(1, mines_count))))
    else:
        target = random.randint(0, min(2, safe_tiles))
    return target, outcome_mode


def _normalize_board_for_finish(session, result):
    board = safe_json(session["board_json"], [])
    total = safe_int(session["grid_size"], 5) ** 2
    if len(board) < total:
        board.extend(["hidden"] * (total - len(board)))
    revealed = set(safe_json(session["revealed_json"], []))
    hidden = [i for i in range(total) if i not in revealed]
    mines_needed = max(0, safe_int(session["mines_count"]) - sum(1 for x in board if x == "mine"))
    random.shuffle(hidden)
    for idx in hidden[:mines_needed]:
        board[idx] = "mine"
    for idx in range(total):
        if board[idx] == "hidden":
            board[idx] = "gem"
    if result == "loss" and hidden and all(x != "mine" for x in board):
        board[hidden[0]] = "mine"
    return board


def _create_session(user_id, chat_id, bet_amount, mines_count, source_balance):
    grid_size, _, min_mines, max_mines = _mine_bounds()
    mines_count = max(min_mines, min(max_mines, safe_int(mines_count, min_mines)))
    board = _build_empty_board(grid_size)
    safe_target, outcome_mode = _determine_safe_target(user_id, mines_count, grid_size)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session_id = db_lastrowid(
        "INSERT INTO mine_game_sessions (user_id, chat_id, source_balance, bet_amount, mines_count, grid_size, board_json, revealed_json, gems_found, safe_target, current_multiplier, payout_amount, status, outcome_mode, first_pick_safe, created_at, updated_at, client_seed, server_seed) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            user_id, chat_id, source_balance, round(safe_float(bet_amount), 2), mines_count, grid_size,
            json.dumps(board), json.dumps([]), 0, safe_target, 1.0, 0.0, "active", outcome_mode,
            1 if bool(get_setting("mine_force_safe_first_tile")) else 0,
            now, now, generate_code(8), generate_code(16)
        )
    )
    return db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session_id,), fetchone=True)


def _finalize_session(session, result, gross_payout=0.0, tax_amount=0.0, gst_amount=0.0):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    net_payout = round(max(0.0, gross_payout - tax_amount - gst_amount), 2)
    board = _normalize_board_for_finish(session, result)
    db_execute(
        "UPDATE mine_game_sessions SET board_json=?, payout_amount=?, status=?, finished_at=?, updated_at=? WHERE id=?",
        (json.dumps(board), gross_payout, result, now, now, session["id"])
    )
    existing = db_execute("SELECT id FROM mine_game_history WHERE session_id=? LIMIT 1", (session["id"],), fetchone=True)
    if not existing:
        db_execute(
            "INSERT INTO mine_game_history (session_id, user_id, source_balance, bet_amount, mines_count, grid_size, gems_found, multiplier, gross_payout, tax_amount, gst_amount, net_payout, result, status, board_json, revealed_json, created_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                session["id"], session["user_id"], session["source_balance"], session["bet_amount"], session["mines_count"],
                session["grid_size"], session["gems_found"], session["current_multiplier"], gross_payout, tax_amount, gst_amount,
                net_payout, result, result, json.dumps(board), session["revealed_json"], session["created_at"], now
            )
        )
    return db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session["id"],), fetchone=True), net_payout


def _resume_active_session(chat_id, user_id):
    _cleanup_stale_sessions(user_id)
    session = _active_mine_session(user_id)
    if not session:
        return False
    safe_send(chat_id, _render_session_text(session, final_message="You already have an active Mine Game. Resuming it below."), reply_markup=_render_board_markup(session))
    return True


def _show_games_home(chat_id, user_id):
    user = get_user(user_id)
    if not user:
        safe_send(chat_id, "Please send /start first.")
        return
    if not _games_enabled():
        safe_send(chat_id, _games_unavailable_text())
        return
    wallets = get_wallet_breakdown(user)
    min_refs = max(0, safe_int(get_setting("games_access_min_referrals"), 2))
    refs = safe_int(user["referral_count"])
    eligible = refs >= min_refs
    markup = types.InlineKeyboardMarkup(row_width=1)
    if bool(get_setting("mine_telegram_enabled")) and bool(get_setting("mine_game_enabled")) and eligible:
        markup.add(types.InlineKeyboardButton("💣 Play Mine Game", callback_data="mine_open"))
    elif not eligible:
        markup.add(types.InlineKeyboardButton("🔒 Unlock Games", callback_data="mine_need_referrals"))
    else:
        markup.add(types.InlineKeyboardButton("⚠️ Mine Game Unavailable", callback_data="mine_disabled_notice"))
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="mine_refresh_home"))
    text = (
        f"{pe('game')} <b>Games Hub</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('money')} <b>Total Balance:</b> ₹{float(user['balance']):.2f}\n"
        f"{pe('people')} <b>Referral Balance:</b> ₹{wallets['referral']:.2f}\n"
        f"{pe('party')} <b>Daily Bonus Balance:</b> ₹{wallets['daily_bonus']:.2f}\n"
        f"{pe('gift')} <b>Gift Balance:</b> ₹{wallets['gift']:.2f}\n\n"
        f"{pe('thumbs_up')} <b>Your Referrals:</b> {refs}\n"
        f"{pe('target')} <b>Required Referrals:</b> {min_refs}\n"
        f"{pe('check')} <b>Access:</b> {'Unlocked' if eligible else 'Locked'}\n\n"
        f"Games Section: <b>{'ON' if _games_enabled() else 'OFF'}</b>\n"
        f"Mine Game: <b>{'ON' if bool(get_setting('mine_game_enabled')) else 'OFF'}</b>\n"
        f"Telegram Mode: <b>{'ON' if bool(get_setting('mine_telegram_enabled')) else 'OFF'}</b>\n\n"
        f"{pe('diamond')} Open Mine Game from here using your real wallet balances inside Telegram."
    )
    safe_send(chat_id, text, reply_markup=markup)


def _start_mine_setup(chat_id, user_id):
    if not _games_enabled():
        safe_send(chat_id, _games_unavailable_text())
        return
    _cleanup_stale_sessions(user_id)
    if _resume_active_session(chat_id, user_id):
        return
    ok, reason = can_user_play_mine(user_id)
    if not ok:
        safe_send(chat_id, f"{pe('warning')} {reason}")
        return
    _, _, min_mines, max_mines = _mine_bounds()
    set_state(user_id, "mine_enter_mines")
    safe_send(chat_id, f"{pe('target')} <b>Mine Game Setup</b>\n\nEnter number of mines between <b>{min_mines}</b> and <b>{max_mines}</b>.")


@bot.message_handler(func=lambda m: m.text == "🎮 Games")
def games_menu_user(message):
    user_id = message.from_user.id
    if not _games_enabled():
        safe_send(message.chat.id, _games_unavailable_text())
        return
    if not check_force_join(user_id):
        send_join_message(message.chat.id)
        return
    _show_games_home(message.chat.id, user_id)


@bot.callback_query_handler(func=lambda call: call.data == "mine_refresh_home")
def mine_refresh_home(call):
    safe_answer(call)
    _show_games_home(call.message.chat.id, call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "mine_disabled_notice")
def mine_disabled_notice(call):
    safe_answer(call, "Mine Game is currently unavailable.", True)

@bot.callback_query_handler(func=lambda call: call.data == "mine_need_referrals")
def mine_need_referrals(call):
    safe_answer(call)
    user = get_user(call.from_user.id)
    min_refs = max(0, safe_int(get_setting("games_access_min_referrals"), 2))
    refs = safe_int(user["referral_count"] if user else 0)
    need = max(0, min_refs - refs)
    safe_send(
        call.message.chat.id,
        f"{pe('warning')} You need at least <b>{min_refs}</b> referrals to play games.\n"
        f"You currently have <b>{refs}</b>. Need <b>{need}</b> more."
    )


@bot.callback_query_handler(func=lambda call: call.data == "mine_open")
def mine_open(call):
    safe_answer(call)
    if not check_force_join(call.from_user.id):
        send_join_message(call.message.chat.id)
        return
    _start_mine_setup(call.message.chat.id, call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "mine_play_again")
def mine_play_again(call):
    safe_answer(call)
    if not check_force_join(call.from_user.id):
        send_join_message(call.message.chat.id)
        return
    clear_state(call.from_user.id)
    _start_mine_setup(call.message.chat.id, call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("mine_source|"))
def mine_source_pick(call):
    if not _games_enabled():
        safe_answer(call, _games_unavailable_text(), True)
        return
    if not check_force_join(call.from_user.id):
        send_join_message(call.message.chat.id)
        return
    safe_answer(call)
    _, source = call.data.split("|", 1)
    data = get_state_data(call.from_user.id) or {}
    bet = safe_float(data.get("bet_amount"), 0)
    mines = safe_int(data.get("mines_count"), 0)
    if get_state(call.from_user.id) != "mine_choose_source":
        safe_answer(call, "Mine setup expired. Start again.", True)
        clear_state(call.from_user.id)
        return
    if source not in SOURCE_LABELS:
        safe_answer(call, "Invalid balance source.", True)
        clear_state(call.from_user.id)
        return
    if bet <= 0 or mines <= 0:
        safe_answer(call, "Session setup expired.", True)
        clear_state(call.from_user.id)
        return
    avail = get_available_game_balance(call.from_user.id, source)
    if avail < bet:
        safe_answer(call, f"Not enough {SOURCE_LABELS.get(source, source)}.", True)
        return
    ok, reason = debit_game_balance(call.from_user.id, bet, source)
    if not ok:
        safe_answer(call, reason, True)
        return
    session = _create_session(call.from_user.id, call.message.chat.id, bet, mines, source)
    clear_state(call.from_user.id)
    safe_send(call.message.chat.id, _render_session_text(session), reply_markup=_render_board_markup(session))


@bot.callback_query_handler(func=lambda call: call.data.startswith("mine_pick|"))
def mine_pick(call):
    if not _games_enabled():
        safe_answer(call, _games_unavailable_text(), True)
        return
    if not check_force_join(call.from_user.id):
        send_join_message(call.message.chat.id)
        return
    safe_answer(call)
    try:
        _, session_id, idx = call.data.split("|")
    except ValueError:
        safe_answer(call, "Invalid move.", True)
        return
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (safe_int(session_id), call.from_user.id), fetchone=True)
    if not session:
        safe_send(call.message.chat.id, f"{pe('warning')} This game session was not found.")
        return
    if session["status"] != "active":
        safe_send(call.message.chat.id, f"{pe('warning')} This game session is no longer active.")
        return
    idx = safe_int(idx)
    total_tiles = safe_int(session["grid_size"], 5) ** 2
    if idx < 0 or idx >= total_tiles:
        safe_answer(call, "Invalid tile.", True)
        return
    revealed = safe_json(session["revealed_json"], [])
    if idx in revealed:
        safe_answer(call)
        return
    board = safe_json(session["board_json"], [])
    if len(board) < total_tiles:
        board.extend(["hidden"] * (total_tiles - len(board)))
    gems_found = safe_int(session["gems_found"])
    safe_target = max(0, safe_int(session["safe_target"]))
    safe_tiles = max(1, total_tiles - safe_int(session["mines_count"]))
    force_first = bool(session["first_pick_safe"]) and gems_found == 0 and bool(get_setting("mine_force_safe_first_tile"))
    should_be_gem = force_first or gems_found < safe_target
    if safe_int(session["mines_count"]) >= total_tiles:
        should_be_gem = False
    board[idx] = "gem" if should_be_gem else "mine"
    revealed.append(idx)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if should_be_gem:
        gems_found += 1
        multiplier = get_mine_multiplier(gems_found, session["mines_count"], session["grid_size"])
        payout = round(float(session["bet_amount"]) * multiplier, 2)
        db_execute(
            "UPDATE mine_game_sessions SET board_json=?, revealed_json=?, gems_found=?, current_multiplier=?, payout_amount=?, updated_at=? WHERE id=?",
            (json.dumps(board), json.dumps(revealed), gems_found, multiplier, payout, now, session["id"])
        )
        session = db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session["id"],), fetchone=True)
        auto_cash = bool(get_setting("mine_auto_cash_out_enabled")) and gems_found >= max(1, min(3, safe_target if safe_target > 0 else 3))
        if gems_found >= safe_tiles:
            auto_cash = True
        if auto_cash:
            _cashout_session(call, session, auto_trigger=True)
            return
        safe_edit(call.message.chat.id, call.message.message_id, _render_session_text(session, final_message="💎 Safe tile! Keep going or cash out."), reply_markup=_render_board_markup(session))
        return
    db_execute(
        "UPDATE mine_game_sessions SET board_json=?, revealed_json=?, updated_at=? WHERE id=?",
        (json.dumps(board), json.dumps(revealed), now, session["id"])
    )
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session["id"],), fetchone=True)
    finished, _ = _finalize_session(session, "loss", 0.0, 0.0, 0.0)
    safe_edit(call.message.chat.id, call.message.message_id, _render_session_text(finished, final_message="💣 Boom! You hit a mine and lost this round."), reply_markup=_render_board_markup(finished, game_over=True))


def _cashout_session(call, session, auto_trigger=False):
    payout = round(float(session["bet_amount"]) * max(1.0, float(session["current_multiplier"])), 2)
    max_win = safe_float(get_setting("mine_max_win_amount_per_session"), 0)
    if max_win > 0:
        payout = min(payout, max_win)
    today = datetime.now().strftime("%Y-%m-%d")
    daily_cap = safe_float(get_setting("mine_daily_win_cap_per_user"), 0)
    if daily_cap > 0:
        row = db_execute(
            "SELECT SUM(net_payout) AS s FROM mine_game_history WHERE user_id=? AND substr(created_at,1,10)=? AND result='cashout'",
            (session["user_id"], today), fetchone=True
        )
        already = safe_float(row["s"] if row else 0)
        payout = min(payout, max(0.0, daily_cap - already))
    gross_profit = max(0.0, payout - float(session["bet_amount"]))
    tax_amount = round(gross_profit * safe_float(get_setting("mine_winning_tax_percent"), 0) / 100.0, 2)
    gst_amount = round(gross_profit * safe_float(get_setting("mine_gst_on_winnings"), 0) / 100.0, 2)
    finished, net_payout = _finalize_session(session, "cashout", payout, tax_amount, gst_amount)
    credit_game_winnings(session["user_id"], net_payout, gross_profit)
    note = "🤖 Auto cash out triggered." if auto_trigger else "💰 Cashed out successfully."
    safe_edit(
        call.message.chat.id,
        call.message.message_id,
        _render_session_text(finished, final_message=f"{note}\nGross: ₹{payout:.2f} | Tax: ₹{tax_amount:.2f} | GST: ₹{gst_amount:.2f} | Net: ₹{net_payout:.2f}"),
        reply_markup=_render_board_markup(finished, game_over=True)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("mine_cashout|"))
def mine_cashout(call):
    safe_answer(call)
    try:
        _, session_id = call.data.split("|")
    except ValueError:
        return
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (safe_int(session_id), call.from_user.id), fetchone=True)
    if not session or session["status"] != "active":
        safe_send(call.message.chat.id, f"{pe('warning')} Session not active.")
        return
    if safe_int(session["gems_found"]) <= 0:
        safe_answer(call, "Reveal at least one gem first.", True)
        return
    _cashout_session(call, session)


@bot.callback_query_handler(func=lambda call: call.data.startswith("mine_end|"))
def mine_end(call):
    safe_answer(call)
    try:
        _, session_id = call.data.split("|")
    except ValueError:
        return
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (safe_int(session_id), call.from_user.id), fetchone=True)
    if not session or session["status"] != "active":
        return
    finished, _ = _finalize_session(session, "loss", 0.0, 0.0, 0.0)
    safe_edit(call.message.chat.id, call.message.message_id, _render_session_text(finished, final_message="🛑 Game ended. Bet forfeited."), reply_markup=_render_board_markup(finished, game_over=True))


@bot.callback_query_handler(func=lambda call: call.data == "mine_noop")
def mine_noop(call):
    safe_answer(call)


# ---------------- Admin controls ----------------

def _mine_admin_value(key):
    val = get_setting(key)
    if isinstance(val, list):
        return ", ".join(str(x) for x in val[:20]) or "—"
    if isinstance(val, bool):
        return "ON" if val else "OFF"
    return str(val)


def _mine_admin_buttons(keys, back="mineadm_home"):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for key in keys:
        meta = SETTING_META_MAP.get(key)
        if not meta:
            continue
        markup.add(types.InlineKeyboardButton(meta["label"][:28], callback_data=f"mineadm_set|{key}"))
    markup.add(types.InlineKeyboardButton("🧹 Close Stale Sessions", callback_data="mineadm_cleanup"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back))
    return markup


def _mine_admin_overview_text():
    return (
        f"{pe('game')} <b>Games & Mine Control Center</b>\n\n"
        f"<b>Section Status</b>\n"
        f"• Games Section: <b>{_mine_admin_value('games_section_enabled')}</b>\n"
        f"• Minimum Referrals To Play: <b>{_mine_admin_value('games_access_min_referrals')}</b>\n"
        f"• Mine Game: <b>{_mine_admin_value('mine_game_enabled')}</b>\n"
        f"• Telegram Mode: <b>{_mine_admin_value('mine_telegram_enabled')}</b>\n\n"
        f"<b>Outcome Engine</b>\n"
        f"• Win Ratio: <b>{_mine_admin_value('mine_global_win_rate')}%</b>\n"
        f"• Loss Ratio: <b>{_mine_admin_value('mine_global_loss_rate')}%</b>\n"
        f"• Force Win All: <b>{_mine_admin_value('mine_force_win_all')}</b>\n"
        f"• Force Loss All: <b>{_mine_admin_value('mine_force_loss_all')}</b>\n\n"
        f"<b>Payout & Limits</b>\n"
        f"• Bet Range: <b>₹{get_setting('mine_min_bet')} - ₹{get_setting('mine_max_bet')}</b>\n"
        f"• Grid Size: <b>{get_setting('mine_grid_size')}x{get_setting('mine_grid_size')}</b>\n"
        f"• Mine Range: <b>{get_setting('mine_min_mines')} - {get_setting('mine_max_mines')}</b>\n"
        f"• House Edge: <b>{_mine_admin_value('mine_house_edge_percent')}%</b>\n"
        f"• Safe First Tile: <b>{_mine_admin_value('mine_force_safe_first_tile')}</b>\n"
        f"• Auto Cash Out: <b>{_mine_admin_value('mine_auto_cash_out_enabled')}</b>\n"
        f"• Risk Indicator: <b>{_mine_admin_value('mine_risk_indicator_enabled')}</b>\n"
        f"• Sound Effects: <b>{_mine_admin_value('mine_sound_effects_enabled')}</b>"
    )


def show_mine_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🧩 Section & Access", callback_data="mineadm_access"),
        types.InlineKeyboardButton("🎯 Outcome Engine", callback_data="mineadm_engine"),
    )
    markup.add(
        types.InlineKeyboardButton("💸 Bets & Multipliers", callback_data="mineadm_core"),
        types.InlineKeyboardButton("🛡 Limits & Safety", callback_data="mineadm_limits"),
    )
    markup.add(
        types.InlineKeyboardButton("👥 User Controls", callback_data="mineadm_userctl"),
        types.InlineKeyboardButton("🎛 Telegram UI", callback_data="mineadm_ui"),
    )
    markup.add(
        types.InlineKeyboardButton("📊 Stats", callback_data="mineadm_stats"),
        types.InlineKeyboardButton("🧾 History", callback_data="mineadm_history"),
    )
    markup.add(
        types.InlineKeyboardButton("🟢 Active Sessions", callback_data="mineadm_active"),
        types.InlineKeyboardButton("🔄 Refresh", callback_data="mineadm_home"),
    )
    safe_send(chat_id, _mine_admin_overview_text(), reply_markup=markup)


def mine_admin_entry(message):
    show_mine_admin_panel(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_access")
def mineadm_access(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    keys = [
        "games_section_enabled", "games_access_min_referrals", "mine_game_enabled", "mine_telegram_enabled",
    ]
    safe_send(
        call.message.chat.id,
        f"{pe('gear')} <b>Section & Access</b>\n\nControl who can access games and whether the whole section is available.",
        reply_markup=_mine_admin_buttons(keys)
    )
@bot.callback_query_handler(func=lambda call: call.data == "mineadm_engine")
def mineadm_engine(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    keys = [
        "mine_global_win_rate", "mine_global_loss_rate", "mine_force_win_all", "mine_force_loss_all",
        "mine_force_win_users", "mine_force_loss_users", "mine_consecutive_win_limit", "mine_consecutive_loss_limit",
    ]
    safe_send(
        call.message.chat.id,
        f"{pe('target')} <b>Outcome Engine</b>\n\nControl win/loss ratio, forced results, and streak protection.",
        reply_markup=_mine_admin_buttons(keys)
    )


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_core")
def mineadm_core(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    keys = [
        "mine_base_multiplier", "mine_progressive_multiplier_rate", "mine_max_multiplier_cap", "mine_jackpot_multiplier",
        "mine_grid_size", "mine_min_mines", "mine_max_mines", "mine_min_bet", "mine_max_bet",
    ]
    safe_send(call.message.chat.id, f"{pe('money')} <b>Bets & Multipliers</b>", reply_markup=_mine_admin_buttons(keys))


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_limits")
def mineadm_limits(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    keys = [
        "mine_daily_play_limit", "mine_hourly_play_limit", "mine_cooldown_seconds",
        "mine_winning_tax_percent", "mine_gst_on_winnings", "mine_max_win_amount_per_session",
        "mine_daily_win_cap_per_user", "mine_house_edge_percent",
    ]
    safe_send(call.message.chat.id, f"{pe('warning')} <b>Limits & Safety</b>", reply_markup=_mine_admin_buttons(keys))


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_userctl")
def mineadm_userctl(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    keys = [
        "mine_blacklist_users", "mine_force_win_users", "mine_force_loss_users", "games_access_min_referrals",
    ]
    safe_send(call.message.chat.id, f"{pe('people')} <b>User Controls</b>", reply_markup=_mine_admin_buttons(keys))


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_ui")
def mineadm_ui(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    keys = [
        "games_section_enabled", "mine_game_enabled", "mine_telegram_enabled",
        "mine_sound_effects_enabled", "mine_risk_indicator_enabled", "mine_auto_cash_out_enabled",
        "mine_force_safe_first_tile",
    ]
    safe_send(
        call.message.chat.id,
        f"{pe('gear')} <b>Telegram UI</b>\n\nEasy controls for the user-facing game experience.",
        reply_markup=_mine_admin_buttons(keys)
    )


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_cleanup")
def mineadm_cleanup(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    rows = db_execute("SELECT COUNT(*) AS c FROM mine_game_sessions WHERE status='active'", fetchone=True)
    before = safe_int(rows["c"] if rows else 0)
    _cleanup_stale_sessions(None)
    rows2 = db_execute("SELECT COUNT(*) AS c FROM mine_game_sessions WHERE status='active'", fetchone=True)
    after = safe_int(rows2["c"] if rows2 else 0)
    safe_send(call.message.chat.id, f"{pe('check')} Cleanup finished. Active sessions: {before} → {after}")


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_home")
def mineadm_home(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    show_mine_admin_panel(call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("mineadm_set|"))
def mineadm_set(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    _, key = call.data.split("|", 1)
    meta = SETTING_META_MAP.get(key)
    if not meta:
        return
    if meta["type"] == "toggle":
        set_setting(key, not bool(get_setting(key)))
        safe_send(call.message.chat.id, f"{pe('check')} {meta['label']} set to {_mine_admin_value(key)}")
        return
    prompt = f"{pe('pencil')} <b>{meta['label']}</b>\nCurrent: <code>{h(_mine_admin_value(key))}</code>\n\nSend new value."
    if meta["type"] == "user_list":
        prompt += "\nFormat: <code>12345,67890</code> or <code>empty</code>"
    elif meta["type"] == "text":
        prompt += "\nExample: <code>/mine</code>"
    set_state(call.from_user.id, f"mine_admin_setting|{key}")
    safe_send(call.message.chat.id, prompt)


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_stats")
def mineadm_stats(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    row = db_execute(
        "SELECT COUNT(*) AS plays, SUM(bet_amount) AS wagered, SUM(net_payout) AS paid, SUM(CASE WHEN result='cashout' THEN 1 ELSE 0 END) AS wins, SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END) AS losses FROM mine_game_history",
        fetchone=True
    )
    active = db_execute("SELECT COUNT(*) AS c FROM mine_game_sessions WHERE status='active'", fetchone=True)
    today = datetime.now().strftime("%Y-%m-%d")
    today_row = db_execute(
        "SELECT COUNT(*) AS plays, SUM(bet_amount) AS wagered, SUM(net_payout) AS paid FROM mine_game_history WHERE substr(created_at,1,10)=?",
        (today,), fetchone=True
    )
    plays = safe_int(row["plays"] if row else 0)
    wagered = safe_float(row["wagered"] if row else 0)
    paid = safe_float(row["paid"] if row else 0)
    rtp = round((paid / wagered) * 100.0, 2) if wagered > 0 else 0.0
    safe_send(
        call.message.chat.id,
        f"{pe('chart')} <b>Mine Game Analytics</b>\n\n"
        f"Total Plays: <b>{plays}</b>\n"
        f"Wins: <b>{safe_int(row['wins'] if row else 0)}</b> | Losses: <b>{safe_int(row['losses'] if row else 0)}</b>\n"
        f"Wagered: <b>₹{wagered:.2f}</b>\n"
        f"Paid Out: <b>₹{paid:.2f}</b>\n"
        f"House Profit: <b>₹{(wagered - paid):.2f}</b>\n"
        f"RTP: <b>{rtp:.2f}%</b>\n"
        f"Active Sessions: <b>{safe_int(active['c'] if active else 0)}</b>\n\n"
        f"Today → Plays: <b>{safe_int(today_row['plays'] if today_row else 0)}</b>, Wagered: <b>₹{safe_float(today_row['wagered'] if today_row else 0):.2f}</b>, Paid: <b>₹{safe_float(today_row['paid'] if today_row else 0):.2f}</b>"
    )


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_history")
def mineadm_history(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    rows = db_execute("SELECT * FROM mine_game_history ORDER BY id DESC LIMIT 25", fetch=True) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} No Mine Game history yet.")
        return
    text = f"{pe('list')} <b>Mine Game History</b>\n\n"
    for row in rows:
        text += (
            f"#{row['id']} | User <code>{row['user_id']}</code> | {row['result']}\n"
            f"Bet ₹{float(row['bet_amount']):.2f} | Mult x{float(row['multiplier']):.2f} | Net ₹{float(row['net_payout']):.2f}\n"
            f"Gems {safe_int(row['gems_found'])} | Mines {safe_int(row['mines_count'])} | {row['created_at'][:16]}\n\n"
        )
    safe_send(call.message.chat.id, text[:4000])


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_active")
def mineadm_active(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    rows = db_execute("SELECT * FROM mine_game_sessions WHERE status='active' ORDER BY id DESC LIMIT 25", fetch=True) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} No active Mine Game sessions.")
        return
    text = f"{pe('active')} <b>Active Mine Sessions</b>\n\n"
    for row in rows:
        text += (
            f"Session #{row['id']} | User <code>{row['user_id']}</code>\n"
            f"Bet ₹{float(row['bet_amount']):.2f} | Gems {safe_int(row['gems_found'])} | x{float(row['current_multiplier']):.2f}\n"
            f"Mode: {row['outcome_mode']} | Safe Target: {safe_int(row['safe_target'])} | {row['created_at'][:16]}\n\n"
        )
    safe_send(call.message.chat.id, text[:4000])
