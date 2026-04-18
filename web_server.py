import os, json, random, logging
from datetime import datetime
from flask import jsonify, render_template, request
from anticheat import create_verification_app
from core import DB_PATH, PUBLIC_BASE_URL, db_execute, db_lastrowid, get_setting, get_user, safe_int, safe_float, safe_json, generate_code, get_mine_multiplier, get_mine_outcome_mode, get_available_game_balance, debit_game_balance, credit_game_winnings, get_wallet_breakdown

PORT = int(os.environ.get('PORT', 8000))
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'NeturalPredictorbot')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
app = create_verification_app(DB_PATH=DB_PATH, BOT_USERNAME=BOT_USERNAME)
SOURCE_LABELS = {'main':'Main Balance','referral':'Referral Balance','daily_bonus':'Daily Bonus Balance','gift':'Gift Code Balance'}

def _json_ok(**kwargs):
    p={'ok':True}; p.update(kwargs); return jsonify(p)

def _json_fail(message, status=400, **kwargs):
    p={'ok':False,'message':message}; p.update(kwargs); return jsonify(p), status

def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def _safe_grid_size():
    return max(3, min(10, safe_int(get_setting('mine_grid_size'), 5)))

def _mine_bounds(grid_size=None):
    grid_size=_safe_grid_size() if grid_size is None else max(3, min(10, safe_int(grid_size, 5)))
    total=grid_size*grid_size
    min_m=max(1, safe_int(get_setting('mine_min_mines'),1))
    max_m=min(total-1, max(min_m, safe_int(get_setting('mine_max_mines'), total-1)))
    return grid_size, total, min_m, max_m

def _active_mine_session(user_id):
    return db_execute("SELECT * FROM mine_game_sessions WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1", (safe_int(user_id),), fetchone=True)

def _wallets_for(user_id):
    user=get_user(user_id)
    return get_wallet_breakdown(user) if user else {'main':0,'referral':0,'daily_bonus':0,'gift':0}

def _serialize_session(session):
    if not session: return None
    board=safe_json(session['board_json'], [])
    revealed=set(safe_json(session['revealed_json'], []))
    total=safe_int(session['grid_size'],5)**2
    if len(board)<total: board.extend(['hidden']*(total-len(board)))
    public=[]
    for i in range(total):
        public.append(board[i] if session['status']!='active' or i in revealed else 'hidden')
    return {
        'id': safe_int(session['id']), 'status': str(session['status']), 'bet_amount': round(safe_float(session['bet_amount']),2),
        'mines_count': safe_int(session['mines_count']), 'grid_size': safe_int(session['grid_size'],5), 'gems_found': safe_int(session['gems_found']),
        'multiplier': round(safe_float(session['current_multiplier'],1.0),2), 'cashout_value': round(safe_float(session['bet_amount'])*max(1.0,safe_float(session['current_multiplier'],1.0)),2),
        'source_balance': str(session['source_balance']), 'board': public, 'revealed': list(revealed)
    }

def _normalize_board_for_finish(session, result):
    board=safe_json(session['board_json'], [])
    total=safe_int(session['grid_size'],5)**2
    if len(board)<total: board.extend(['hidden']*(total-len(board)))
    revealed=set(safe_json(session['revealed_json'], []))
    hidden=[i for i in range(total) if i not in revealed]
    mines_needed=max(0, safe_int(session['mines_count'])-sum(1 for x in board if x=='mine'))
    random.shuffle(hidden)
    for idx in hidden[:mines_needed]: board[idx]='mine'
    for idx in range(total):
        if board[idx]=='hidden': board[idx]='gem'
    if result=='loss' and hidden and all(x!='mine' for x in board): board[hidden[0]]='mine'
    return board

def _finalize_session(session, result, gross_payout=0.0, tax_amount=0.0, gst_amount=0.0):
    net=max(0.0, round(safe_float(gross_payout)-safe_float(tax_amount)-safe_float(gst_amount),2))
    board=_normalize_board_for_finish(session, result)
    now=_now()
    db_execute("UPDATE mine_game_sessions SET board_json=?, status=?, payout_amount=?, finished_at=?, updated_at=? WHERE id=?", (json.dumps(board), result, net, now, now, session['id']))
    db_execute("INSERT INTO mine_game_history (user_id, session_id, source_balance, bet_amount, mines_count, grid_size, gems_found, multiplier, gross_payout, tax_amount, gst_amount, net_payout, result, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (session['user_id'], session['id'], session['source_balance'], session['bet_amount'], session['mines_count'], session['grid_size'], session['gems_found'], session['current_multiplier'], gross_payout, tax_amount, gst_amount, net, result, now))
    return db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session['id'],), fetchone=True), net

def _can_user_play_web(user_id):
    if not bool(get_setting('games_section_enabled')): return False, 'The games section is currently unavailable.'
    if not bool(get_setting('mine_game_enabled')): return False, 'Mine Game is disabled right now.'
    if not bool(get_setting('mine_web_enabled')): return False, 'Web Mine mode is disabled right now.'
    user=get_user(user_id)
    if not user: return False, 'Please send /start first.'
    min_refs=max(0, safe_int(get_setting('games_access_min_referrals'), 2))
    if safe_int(user['referral_count']) < min_refs: return False, f'You need at least {min_refs} referrals to play games.'
    return True, 'ok'

def _create_session(user_id, chat_id, bet_amount, mines_count, source_balance):
    grid_size,total,min_m,max_m=_mine_bounds(); mines_count=max(min_m, min(max_m, safe_int(mines_count,min_m)))
    board=['hidden']*total
    mode=get_mine_outcome_mode(user_id)
    if mode=='force_win': safe_target=total-mines_count
    elif mode=='force_loss': safe_target=0
    else: safe_target=random.randint(0, max(1, min(total-mines_count, 3+mines_count//2)))
    if safe_target < (total-mines_count):
        avoid=set(random.sample(range(total), min(max(0,safe_target), total))) if safe_target>0 else set()
        available=[i for i in range(total) if i not in avoid]
        random.shuffle(available)
        for idx in available[:mines_count]: board[idx]='mine'
    now=_now()
    sid=db_lastrowid("INSERT INTO mine_game_sessions (user_id, chat_id, source_balance, bet_amount, mines_count, grid_size, board_json, revealed_json, gems_found, safe_target, current_multiplier, payout_amount, status, outcome_mode, first_pick_safe, created_at, updated_at, client_seed, server_seed) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (safe_int(user_id), safe_int(chat_id), source_balance, round(safe_float(bet_amount),2), mines_count, grid_size, json.dumps(board), json.dumps([]), 0, safe_target, 1.0, 0.0, 'active', mode, 1 if bool(get_setting('mine_force_safe_first_tile')) else 0, now, now, generate_code(8), generate_code(16)))
    return db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (sid,), fetchone=True)

@app.route('/')
def home():
    return {'status':'running','mine_url':'/mine','web_mine_enabled':bool(get_setting('mine_web_enabled')),'public_base_url':PUBLIC_BASE_URL}

def mine_page():
    uid=safe_int(request.args.get('uid'),0)
    return render_template('mine.html', user_id=uid, api_base='/api/mine', public_base_url=PUBLIC_BASE_URL, bot_username=BOT_USERNAME)

for idx, path in enumerate(['/mine','/mine/','/mine-game','/mine-game/','/games/mine','/games/mine/','/web/mine','/web/mine/']):
    if path not in {rule.rule for rule in app.url_map.iter_rules()}:
        app.add_url_rule(path, f'mine_alias_{idx}', mine_page)

@app.route('/favicon.ico')
def favicon():
    return ('',204)

@app.get('/api/mine/bootstrap')
def mine_bootstrap():
    user_id=safe_int(request.args.get('uid'),0)
    user=get_user(user_id)
    if not user: return _json_fail('Please open this Mini App from the Telegram bot.',404)
    ok,reason=_can_user_play_web(user_id)
    grid_size,_,min_m,max_m=_mine_bounds()
    return _json_ok(user={'id':user_id,'name':user['first_name'],'wallets':_wallets_for(user_id)}, access={'allowed':ok,'message':reason}, settings={'grid_size':grid_size,'min_mines':min_m,'max_mines':max_m,'min_bet':round(safe_float(get_setting('mine_min_bet'),1),2),'max_bet':round(safe_float(get_setting('mine_max_bet'),1000),2)}, session=_serialize_session(_active_mine_session(user_id)))

@app.post('/api/mine/start')
def mine_start():
    data=request.get_json(silent=True) or {}
    user_id=safe_int(data.get('user_id'),0); bet=round(safe_float(data.get('bet_amount'),0),2); mines=safe_int(data.get('mines_count'),0); source=str(data.get('source_balance') or 'main')
    if source not in SOURCE_LABELS: return _json_fail('Invalid balance source.')
    ok,reason=_can_user_play_web(user_id)
    if not ok: return _json_fail(reason,403)
    active=_active_mine_session(user_id)
    if active: return _json_ok(message='Resuming active session.', resumed=True, session=_serialize_session(active), wallets=_wallets_for(user_id))
    _,_,min_m,max_m=_mine_bounds()
    if mines<min_m or mines>max_m: return _json_fail(f'Choose mines between {min_m} and {max_m}.')
    min_b=safe_float(get_setting('mine_min_bet'),1); max_b=safe_float(get_setting('mine_max_bet'),1000)
    if bet<min_b or bet>max_b: return _json_fail(f'Bet must be between ₹{min_b:.2f} and ₹{max_b:.2f}.')
    if get_available_game_balance(user_id, source) < bet: return _json_fail(f'Not enough {SOURCE_LABELS[source]}.')
    ok,msg=debit_game_balance(user_id, bet, source)
    if not ok: return _json_fail(msg)
    session=_create_session(user_id,0,bet,mines,source)
    return _json_ok(message='Mine Game started.', session=_serialize_session(session), wallets=_wallets_for(user_id))

@app.post('/api/mine/pick')
def mine_pick():
    data=request.get_json(silent=True) or {}
    user_id=safe_int(data.get('user_id'),0); session_id=safe_int(data.get('session_id'),0); idx=safe_int(data.get('index'),-1)
    session=db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (session_id,user_id), fetchone=True)
    if not session: return _json_fail('Session not found.',404)
    if session['status']!='active': return _json_ok(message='Session already finished.', session=_serialize_session(session), wallets=_wallets_for(user_id))
    total=safe_int(session['grid_size'],5)**2
    if idx<0 or idx>=total: return _json_fail('Invalid tile index.')
    revealed=safe_json(session['revealed_json'],[])
    if idx in revealed: return _json_ok(message='Tile already revealed.', session=_serialize_session(session), wallets=_wallets_for(user_id))
    board=safe_json(session['board_json'],[])
    if len(board)<total: board.extend(['hidden']*(total-len(board)))
    tile=board[idx]; revealed.append(idx)
    if tile=='mine':
        db_execute("UPDATE mine_game_sessions SET board_json=?, revealed_json=?, updated_at=? WHERE id=?", (json.dumps(board), json.dumps(revealed), _now(), session['id']))
        session=db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session['id'],), fetchone=True)
        finished,_=_finalize_session(session,'loss',0.0,0.0,0.0)
        return _json_ok(message='Boom! You hit a mine.', event='mine', session=_serialize_session(finished), wallets=_wallets_for(user_id))
    gems=safe_int(session['gems_found'])+1
    mult=get_mine_multiplier(gems, session['mines_count'], session['grid_size'])
    payout=round(safe_float(session['bet_amount'])*mult,2)
    db_execute("UPDATE mine_game_sessions SET board_json=?, revealed_json=?, gems_found=?, current_multiplier=?, payout_amount=?, updated_at=? WHERE id=?", (json.dumps(board), json.dumps(revealed), gems, mult, payout, _now(), session['id']))
    session=db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session['id'],), fetchone=True)
    return _json_ok(message='Gem found.', event='gem', session=_serialize_session(session), wallets=_wallets_for(user_id))

@app.post('/api/mine/cashout')
def mine_cashout():
    data=request.get_json(silent=True) or {}
    user_id=safe_int(data.get('user_id'),0); session_id=safe_int(data.get('session_id'),0)
    session=db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (session_id,user_id), fetchone=True)
    if not session: return _json_fail('Session not found.',404)
    if session['status']!='active': return _json_ok(message='Session already finished.', session=_serialize_session(session), wallets=_wallets_for(user_id))
    if safe_int(session['gems_found'])<=0: return _json_fail('Reveal at least one gem first.')
    payout=round(safe_float(session['bet_amount'])*max(1.0,safe_float(session['current_multiplier'],1.0)),2)
    gross=max(0.0,payout-safe_float(session['bet_amount']))
    tax=round(gross*safe_float(get_setting('mine_winning_tax_percent'),0)/100.0,2)
    gst=round(gross*safe_float(get_setting('mine_gst_on_winnings'),0)/100.0,2)
    finished,net=_finalize_session(session,'cashout',payout,tax,gst)
    credit_game_winnings(user_id,net,gross)
    return _json_ok(message='Cashed out successfully.', event='cashout', payout={'gross':payout,'tax':tax,'gst':gst,'net':net}, session=_serialize_session(finished), wallets=_wallets_for(user_id))

@app.post('/api/mine/end')
def mine_end():
    data=request.get_json(silent=True) or {}
    user_id=safe_int(data.get('user_id'),0); session_id=safe_int(data.get('session_id'),0)
    session=db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (session_id,user_id), fetchone=True)
    if not session: return _json_fail('Session not found.',404)
    if session['status']!='active': return _json_ok(message='Session already finished.', session=_serialize_session(session), wallets=_wallets_for(user_id))
    finished,_=_finalize_session(session,'loss',0.0,0.0,0.0)
    return _json_ok(message='Game ended.', event='end', session=_serialize_session(finished), wallets=_wallets_for(user_id))

@app.errorhandler(404)
def not_found(e):
    if 'text/html' in (request.headers.get('Accept') or ''):
        return '<h1>Not Found</h1><p>The requested URL was not found on the server.</p>', 404
    return jsonify({'error':'Not Found','message':'Invalid route'}), 404

@app.errorhandler(500)
def server_error(e):
    logging.exception('Server error: %s', e)
    return jsonify({'error':'Server Error','message':'Something went wrong'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
