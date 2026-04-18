import os
import json
import random
import logging
from datetime import datetime, timedelta

from flask import jsonify, render_template, request
from anticheat import create_verification_app
from core import (
    DB_PATH, PUBLIC_BASE_URL, db_execute, db_lastrowid, get_setting, get_user, safe_int, safe_float, safe_json,
    parse_dt, generate_code, get_mine_multiplier, get_mine_outcome_mode,
    get_available_game_balance, debit_game_balance, credit_game_winnings,
    get_public_mine_url, get_wallet_breakdown
)

PORT = int(os.environ.get("PORT", 8000))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "NeturalPredictorbot")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.info("🚀 Starting Web Server with Mine Mini App...")

app = create_verification_app(DB_PATH=DB_PATH, BOT_USERNAME=BOT_USERNAME)

SOURCE_LABELS = {
    "main": "Main Balance",
    "referral": "Referral Balance",
    "daily_bonus": "Daily Bonus Balance",
    "gift": "Gift Code Balance",
}


def _json_ok(**kwargs):
    payload = {"ok": True}
    payload.update(kwargs)
    return jsonify(payload)


def _json_fail(message, status=400, **kwargs):
    payload = {"ok": False, "message": message}
    payload.update(kwargs)
    return jsonify(payload), status


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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


def _active_mine_session(user_id):
    return db_execute(
        "SELECT * FROM mine_game_sessions WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1",
        (safe_int(user_id),), fetchone=True
    )


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


def _cleanup_stale_sessions(user_id=None, stale_minutes=120):
    params = []
    query = "SELECT * FROM mine_game_sessions WHERE status='active'"
    if user_id is not None:
        query += " AND user_id=?"
        params.append(safe_int(user_id))
    rows = db_execute(query, tuple(params), fetch=True) or []
    cutoff = datetime.now() - timedelta(minutes=stale_minutes)
    for row in rows:
        dt = parse_dt(row["updated_at"]) or parse_dt(row["created_at"])
        if dt and dt < cutoff:
            _finalize_session(row, "loss", 0.0, 0.0, 0.0)


def _get_consecutive_stats(user_id, limit=20):
    rows = db_execute(
        "SELECT result FROM mine_game_history WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (safe_int(user_id), limit), fetch=True
    ) or []
    wins = 0
    losses = 0
    for row in rows:
        if str(row["result"]).lower() == "cashout":
            wins += 1
        else:
            break
    for row in rows:
        if str(row["result"]).lower() == "loss":
            losses += 1
        else:
            break
    return {"wins": wins, "losses": losses}


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


def _create_session(user_id, chat_id, bet_amount, mines_count, source_balance):
    grid_size, _, min_mines, max_mines = _mine_bounds()
    mines_count = max(min_mines, min(max_mines, safe_int(mines_count, min_mines)))
    board = _build_empty_board(grid_size)
    safe_target, outcome_mode = _determine_safe_target(user_id, mines_count, grid_size)
    now = _now_str()
    session_id = db_lastrowid(
        "INSERT INTO mine_game_sessions (user_id, chat_id, source_balance, bet_amount, mines_count, grid_size, board_json, revealed_json, gems_found, safe_target, current_multiplier, payout_amount, status, outcome_mode, first_pick_safe, created_at, updated_at, client_seed, server_seed) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            safe_int(user_id), safe_int(chat_id), source_balance, round(safe_float(bet_amount), 2), mines_count, grid_size,
            json.dumps(board), json.dumps([]), 0, safe_target, 1.0, 0.0, "active", outcome_mode,
            1 if bool(get_setting("mine_force_safe_first_tile")) else 0,
            now, now, generate_code(8), generate_code(16)
        )
    )
    return db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session_id,), fetchone=True)


def _finalize_session(session, result, gross_payout=0.0, tax_amount=0.0, gst_amount=0.0):
    board = _normalize_board_for_finish(session, result)
    net_payout = max(0.0, round(safe_float(gross_payout) - safe_float(tax_amount) - safe_float(gst_amount), 2))
    now = _now_str()
    db_execute(
        "UPDATE mine_game_sessions SET board_json=?, status=?, payout_amount=?, finished_at=?, updated_at=? WHERE id=?",
        (json.dumps(board), result, net_payout, now, now, session["id"])
    )
    db_execute(
        "INSERT INTO mine_game_history (user_id, session_id, source_balance, bet_amount, mines_count, grid_size, gems_found, multiplier, gross_payout, tax_amount, gst_amount, net_payout, result, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            session["user_id"], session["id"], session["source_balance"], session["bet_amount"], session["mines_count"],
            session["grid_size"], session["gems_found"], session["current_multiplier"], gross_payout,
            tax_amount, gst_amount, net_payout, result, now
        )
    )
    finished = db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session["id"],), fetchone=True)
    return finished, net_payout


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


def _serialize_session(session):
    if not session:
        return None
    board = safe_json(session["board_json"], [])
    revealed = set(safe_json(session["revealed_json"], []))
    total = safe_int(session["grid_size"], 5) ** 2
    if len(board) < total:
        board.extend(["hidden"] * (total - len(board)))
    public_board = []
    for idx in range(total):
        if session["status"] != "active" or idx in revealed:
            public_board.append(board[idx])
        else:
            public_board.append("hidden")
    payout = round(float(session["bet_amount"]) * max(1.0, float(session["current_multiplier"])), 2)
    return {
        "id": safe_int(session["id"]),
        "status": str(session["status"]),
        "bet_amount": round(safe_float(session["bet_amount"]), 2),
        "mines_count": safe_int(session["mines_count"]),
        "grid_size": safe_int(session["grid_size"], 5),
        "gems_found": safe_int(session["gems_found"]),
        "multiplier": round(safe_float(session["current_multiplier"], 1.0), 2),
        "cashout_value": round(payout, 2),
        "source_balance": str(session["source_balance"]),
        "risk_percent": _risk_percent(session),
        "board": public_board,
        "revealed": list(revealed),
        "safe_target": safe_int(session["safe_target"]),
        "outcome_mode": str(session["outcome_mode"] or "normal"),
    }


def _wallets_for(user_id):
    user = get_user(user_id)
    return get_wallet_breakdown(user) if user else {"main": 0, "referral": 0, "daily_bonus": 0, "gift": 0}


def _can_user_play_web(user_id):
    _cleanup_stale_sessions(user_id)
    if not bool(get_setting("games_section_enabled")):
        return False, "The games section is currently unavailable."
    if not bool(get_setting("mine_game_enabled")):
        return False, "Mine Game is disabled right now."
    if not bool(get_setting("mine_web_enabled")):
        return False, "Web Mine mode is disabled right now."
    user = get_user(user_id)
    if not user:
        return False, "Please send /start first."
    min_refs = max(0, safe_int(get_setting("games_access_min_referrals"), 2))
    if safe_int(user["referral_count"]) < min_refs:
        needed = max(0, min_refs - safe_int(user["referral_count"]))
        return False, f"You need at least {min_refs} referrals to play games. You still need {needed} more."
    blacklist = {safe_int(x) for x in safe_json(get_setting("mine_blacklist_users"), [])}
    if safe_int(user_id) in blacklist:
        return False, "You are blocked from playing Mine Game."
    cooldown = safe_int(get_setting("mine_cooldown_seconds"), 0)
    if cooldown > 0:
        last_row = db_execute(
            "SELECT created_at FROM mine_game_history WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user_id,), fetchone=True
        )
        if last_row:
            last_dt = parse_dt(last_row["created_at"])
            if last_dt and (datetime.now() - last_dt).total_seconds() < cooldown:
                wait = cooldown - int((datetime.now() - last_dt).total_seconds())
                return False, f"Cooldown active. Wait {max(1, wait)}s."
    day_limit = safe_int(get_setting("mine_daily_play_limit"), 0)
    if day_limit > 0:
        row = db_execute(
            "SELECT COUNT(*) AS c FROM mine_game_history WHERE user_id=? AND substr(created_at,1,10)=?",
            (user_id, datetime.now().strftime("%Y-%m-%d")), fetchone=True
        )
        if row and safe_int(row["c"]) >= day_limit:
            return False, "Daily Mine Game limit reached."
    hour_limit = safe_int(get_setting("mine_hourly_play_limit"), 0)
    if hour_limit > 0:
        since = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        row = db_execute(
            "SELECT COUNT(*) AS c FROM mine_game_history WHERE user_id=? AND created_at>=?",
            (user_id, since), fetchone=True
        )
        if row and safe_int(row["c"]) >= hour_limit:
            return False, "Hourly Mine Game limit reached."
    return True, "ok"


@app.route("/")
def home():
    return {
        "status": "running",
        "mine_url": get_public_mine_url(),
        "configured_mine_path": _configured_mine_path(),
        "web_mine_enabled": bool(get_setting("mine_web_enabled")),
    }


@app.route("/mine")
@app.route("/mine/")
@app.route("/mine-game")
@app.route("/mine-game/")
@app.route("/games/mine")
@app.route("/games/mine/")
@app.route("/web/mine")
@app.route("/web/mine/")
def mine_page():
    uid = safe_int(request.args.get("uid"), 0)
    return render_template(
        "mine.html",
        user_id=uid,
        api_base="/api/mine",
        public_base_url=PUBLIC_BASE_URL,
        bot_username=BOT_USERNAME,
    )




@app.route('/favicon.ico')
def favicon_ok():
    return ('', 204)


def _configured_mine_path():
    path = str(get_setting('mine_web_path') or '/mine').strip() or '/mine'
    if not path.startswith('/'):
        path = '/' + path
    return path


def _register_configured_mine_alias():
    path = _configured_mine_path()
    endpoint = 'mine_page_dynamic_alias'
    if path not in {rule.rule for rule in app.url_map.iter_rules()}:
        app.add_url_rule(path, endpoint, mine_page)
        if not path.endswith('/'):
            app.add_url_rule(path + '/', endpoint + '_slash', mine_page)


_register_configured_mine_alias()

@app.get("/api/mine/bootstrap")
def mine_bootstrap():
    user_id = safe_int(request.args.get("uid"), 0)
    user = get_user(user_id)
    if not user:
        return _json_fail("Please open this Mini App from the Telegram bot.", 404)
    ok, reason = _can_user_play_web(user_id)
    session = _active_mine_session(user_id)
    grid_size, _, min_mines, max_mines = _mine_bounds()
    return _json_ok(
        user={
            "id": user_id,
            "name": user["first_name"],
            "balance": round(safe_float(user["balance"]), 2),
            "referrals": safe_int(user["referral_count"]),
            "wallets": _wallets_for(user_id),
        },
        access={"allowed": ok, "message": reason},
        settings={
            "grid_size": grid_size,
            "min_mines": min_mines,
            "max_mines": max_mines,
            "min_bet": round(safe_float(get_setting("mine_min_bet"), 1), 2),
            "max_bet": round(safe_float(get_setting("mine_max_bet"), 1000), 2),
            "sound_enabled": bool(get_setting("mine_sound_effects_enabled")),
            "risk_enabled": bool(get_setting("mine_risk_indicator_enabled")),
            "auto_cashout_enabled": bool(get_setting("mine_auto_cash_out_enabled")),
        },
        session=_serialize_session(session),
    )


@app.post("/api/mine/start")
def mine_start():
    data = request.get_json(silent=True) or {}
    user_id = safe_int(data.get("user_id"), 0)
    bet_amount = round(safe_float(data.get("bet_amount"), 0), 2)
    mines_count = safe_int(data.get("mines_count"), 0)
    source_balance = str(data.get("source_balance") or "main")
    if source_balance not in SOURCE_LABELS:
        return _json_fail("Invalid balance source.")
    ok, reason = _can_user_play_web(user_id)
    if not ok:
        active = _active_mine_session(user_id)
        if active:
            return _json_ok(message="Resuming active session.", session=_serialize_session(active), resumed=True)
        return _json_fail(reason, 403)
    if _active_mine_session(user_id):
        active = _active_mine_session(user_id)
        return _json_ok(message="Resuming active session.", session=_serialize_session(active), resumed=True)
    grid_size, _, min_mines, max_mines = _mine_bounds()
    bet_min = safe_float(get_setting("mine_min_bet"), 1)
    bet_max = safe_float(get_setting("mine_max_bet"), 1000)
    if mines_count < min_mines or mines_count > max_mines:
        return _json_fail(f"Choose mines between {min_mines} and {max_mines}.")
    if bet_amount < bet_min or bet_amount > bet_max:
        return _json_fail(f"Bet must be between ₹{bet_min:.2f} and ₹{bet_max:.2f}.")
    if get_available_game_balance(user_id, source_balance) < bet_amount:
        return _json_fail(f"Not enough {SOURCE_LABELS.get(source_balance, source_balance)}.")
    debited, message = debit_game_balance(user_id, bet_amount, source_balance)
    if not debited:
        return _json_fail(message)
    session = _create_session(user_id, 0, bet_amount, mines_count, source_balance)
    return _json_ok(message="Mine Game started.", session=_serialize_session(session), wallets=_wallets_for(user_id), grid_size=grid_size)


@app.post("/api/mine/pick")
def mine_pick():
    data = request.get_json(silent=True) or {}
    user_id = safe_int(data.get("user_id"), 0)
    session_id = safe_int(data.get("session_id"), 0)
    idx = safe_int(data.get("index"), -1)
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (session_id, user_id), fetchone=True)
    if not session:
        return _json_fail("Session not found.", 404)
    if session["status"] != "active":
        return _json_ok(message="Session already finished.", session=_serialize_session(session), wallets=_wallets_for(user_id))
    total_tiles = safe_int(session["grid_size"], 5) ** 2
    if idx < 0 or idx >= total_tiles:
        return _json_fail("Invalid tile index.")
    revealed = safe_json(session["revealed_json"], [])
    if idx in revealed:
        return _json_ok(message="Tile already revealed.", session=_serialize_session(session), wallets=_wallets_for(user_id))
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
    now = _now_str()
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
            return _cashout_session_web(session, auto_trigger=True)
        return _json_ok(message="Gem found.", event="gem", session=_serialize_session(session), wallets=_wallets_for(user_id))
    db_execute(
        "UPDATE mine_game_sessions SET board_json=?, revealed_json=?, updated_at=? WHERE id=?",
        (json.dumps(board), json.dumps(revealed), now, session["id"])
    )
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session["id"],), fetchone=True)
    finished, _ = _finalize_session(session, "loss", 0.0, 0.0, 0.0)
    return _json_ok(message="Boom! You hit a mine.", event="mine", session=_serialize_session(finished), wallets=_wallets_for(user_id))


def _cashout_session_web(session, auto_trigger=False):
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
    return _json_ok(
        message="Auto cash out triggered." if auto_trigger else "Cashed out successfully.",
        event="cashout",
        payout={
            "gross": round(payout, 2),
            "tax": round(tax_amount, 2),
            "gst": round(gst_amount, 2),
            "net": round(net_payout, 2),
        },
        session=_serialize_session(finished),
        wallets=_wallets_for(session["user_id"]),
    )


@app.post("/api/mine/cashout")
def mine_cashout():
    data = request.get_json(silent=True) or {}
    user_id = safe_int(data.get("user_id"), 0)
    session_id = safe_int(data.get("session_id"), 0)
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (session_id, user_id), fetchone=True)
    if not session:
        return _json_fail("Session not found.", 404)
    if session["status"] != "active":
        return _json_ok(message="Session already finished.", session=_serialize_session(session), wallets=_wallets_for(user_id))
    if safe_int(session["gems_found"]) <= 0:
        return _json_fail("Reveal at least one gem first.")
    return _cashout_session_web(session, auto_trigger=False)


@app.post("/api/mine/end")
def mine_end():
    data = request.get_json(silent=True) or {}
    user_id = safe_int(data.get("user_id"), 0)
    session_id = safe_int(data.get("session_id"), 0)
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (session_id, user_id), fetchone=True)
    if not session:
        return _json_fail("Session not found.", 404)
    if session["status"] != "active":
        return _json_ok(message="Session already finished.", session=_serialize_session(session), wallets=_wallets_for(user_id))
    finished, _ = _finalize_session(session, "loss", 0.0, 0.0, 0.0)
    return _json_ok(message="Game ended.", event="end", session=_serialize_session(finished), wallets=_wallets_for(user_id))


@app.route("/debug")
def debug_info():
    return {
        "status": "running",
        "db_path": DB_PATH,
        "bot": BOT_USERNAME,
        "mine_url": get_public_mine_url(),
        "mine_web_enabled": bool(get_setting("mine_web_enabled")),
        "env_vars": list(os.environ.keys())
    }


@app.route("/ping")
def ping():
    return "pong"


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not Found", "message": "Invalid route"}), 404


@app.errorhandler(500)
def server_error(e):
    logging.exception("Server error: %s", e)
    return jsonify({"error": "Server Error", "message": "Something went wrong"}), 500


if __name__ == "__main__":
    logging.info("🌐 Running on port %s", PORT)
    app.run(host="0.0.0.0", port=PORT)
