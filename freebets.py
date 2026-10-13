"""Freebets SNR: independent views, public Exchange quotes, no betting operations."""
import json
import math
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, render_template, request

bp = Blueprint('freebets', __name__)
_lock = threading.Lock()
_lays = {}
_status = {'running': False, 'captured': 0, 'message': 'Exchange pendiente de lectura.'}
from runtime_paths import data_dir
CACHE = data_dir() / 'exchange_quotes.json'
_core = None


def number(value, minimum, maximum):
    if isinstance(value, bool):
        raise ValueError('Introduce números válidos.')
    try:
        result = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        raise ValueError('Introduce números válidos.') from None
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f'El valor debe estar entre {minimum} y {maximum}.')
    return result


def calculate(freebet, back, lay, commission=2):
    f = number(freebet, .01, 10000)
    b = number(back, 1.01, 1000)
    l = number(lay, 1.01, 1000)
    c = number(commission, 0, 20) / 100
    gross = f * (b - 1)
    ideal = gross / (l - c)
    # Optimize the worse of the two outcomes after real cent rounding.
    def outcome(cents):
        stake = cents / 100
        liability = math.ceil((stake * (l - 1) - 1e-9) * 100) / 100
        win = math.floor((gross - liability + 1e-9) * 100) / 100
        lose = math.floor((stake * (1 - c) + 1e-9) * 100) / 100
        return stake, liability, win, lose
    choices = [outcome(n) for n in {max(1, math.floor(ideal * 100)), max(1, math.ceil(ideal * 100))}]
    stake, liability, win, lose = max(choices, key=lambda v: (min(v[2:]), -abs(v[2]-v[3]), -v[1]))
    profit = min(win, lose)
    return dict(freebet=f, back=b, lay=l, commission=c*100, gross=round(gross, 2),
                lay_stake=stake, liability=liability, profit_win=win, profit_lose=lose,
                profit=profit, rating=round(profit/f*100, 2))


def register(application):
    global _core
    _core = sys.modules[application.import_name]
    application.register_blueprint(bp)


def core():
    return _core


def fresh(event, now=None):
    a = core()
    now = now or datetime.now(timezone.utc)
    observed, start = a.parse_dt(event.get('observed_at')), a.parse_dt(event.get('start'))
    return bool(observed and start and -5 <= (now-observed).total_seconds() <= a.read_config()['max_source_age_minutes']*60 and start > now)


def restore():
    with _lock:
        if _lays or not CACHE.exists():
            return
        try:
            events = json.loads(CACHE.read_text(encoding='utf-8'))
            for event in events:
                if fresh(event):
                    _lays[event['market_id']] = event
        except (OSError, ValueError, TypeError, KeyError):
            _lays.clear()


@bp.get('/freebets')
def page():
    return render_template('freebets.html', sources=core().SOURCE_DEFS)


@bp.post('/freebets/calculate')
def calculator():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {'ok': False, 'error': 'Introduce una freebet y las dos cuotas.'}, 400
    try:
        return {'ok': True, 'result': calculate(data.get('freebet'), data.get('back'), data.get('lay'), data.get('commission', 2))}
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}, 400


@bp.get('/freebets/targets')
def targets():
    a = core()
    a.restore_quote_cache()
    source = request.args.get('source', 'winamax_es')
    cfg = a.read_config()
    result = []
    for group in list(a._last_groups):
        q = group.quotes.get(source)
        if q and group.league_key in cfg['selected_leagues'] and a.quote_in_window(q, cfg['hours']) and a.quote_is_fresh(q):
            result.append(dict(home=q.home, away=q.away, start=q.start.isoformat(),league_key=group.league_key,
                               canonical_home=a.canonical_team(q.home), canonical_away=a.canonical_team(q.away)))
    return {'targets': result, 'aliases': a.TEAM_ALIASES}


@bp.post('/freebets/exchange-observation')
def observation():
    a = core()
    data = request.get_json(silent=True)
    try:
        if not isinstance(data, dict) or data.get('market') != 'MATCH_ODDS' or data.get('currency') != 'EUR':
            raise ValueError()
        now = datetime.now(timezone.utc)
        stamp = a.parse_dt(data['observed_at'])
        if not stamp or not -5 <= (now-stamp).total_seconds() <= 30 or len(data['events']) > 200:
            raise ValueError()
        a.restore_quote_cache()
        accepted = []
        for event in data['events']:
            start = a.parse_dt(event.get('start'))
            parsed = urlparse(event.get('url', ''))
            market_id = str(event.get('market_id', ''))
            if not start or start <= now or parsed.scheme != 'https' or parsed.hostname != 'www.betfair.es' or not parsed.path.startswith('/exchange/plus/') or parsed.query or parsed.fragment or parsed.username or parsed.password:
                continue
            if not __import__('re').fullmatch(r'1\.\d{6,14}', market_id):
                continue
            matches = [g for g in a._last_groups if a.canonical_team(g.home)==a.canonical_team(event.get('home'))
                       and a.canonical_team(g.away)==a.canonical_team(event.get('away'))
                       and abs((g.start-start).total_seconds()) <= 60]
            if len(matches) != 1:
                continue
            g = matches[0]
            lays = {}
            for sign in ('1', 'X', '2'):
                item = event.get('lays', {}).get(sign)
                if item:
                    lays[sign] = {'price': number(item.get('price'), 1.01, 1000), 'size': number(item.get('size'), .01, 100000000)}
            if lays:
                accepted.append(dict(market_id=market_id, home=g.home, away=g.away, start=start.isoformat(),
                                     observed_at=stamp.isoformat(), lays=lays, url=event['url']))
        with _lock:
            for event in accepted:
                _lays[event['market_id']] = event
            valid = [e for e in _lays.values() if fresh(e, now)]
            _lays.clear()
            _lays.update({e['market_id']:e for e in valid})
            # Only whitelisted public data; no submitted bodies or credentials.
            CACHE.write_text(json.dumps(valid, ensure_ascii=False), encoding='utf-8')
        return {'ok': True, 'captured': len(accepted)}
    except (ValueError, TypeError, KeyError, AttributeError):
        return {'ok': False, 'error': 'La lectura del Exchange no es válida.'}, 400


@bp.route('/freebets/status', methods=['GET', 'POST'])
def status():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        try:
            with _lock:
                # Fixed messages prevent accidental inclusion of keys in status/logs.
                code = data.get('state')
                messages = {'reading':'Leyendo cuotas lay del Exchange…', 'done':'Lectura terminada.',
                            'partial':'Lectura parcial: se alcanzó el límite de páginas.',
                            'blocked':'Exchange no mostró las cuotas públicas esperadas.',
                            'empty':'No hay cuotas recientes de la casa seleccionada. Actualízalas en Cruces.',
                            'error':'No se pudo completar la lectura del Exchange.'}
                messages.update(connection='No se pudo conectar con el lector de la pestaña Exchange. Recarga la extensión y comprueba su permiso para Betfair.',
                                date_format='No se pudo interpretar el formato de fecha mostrado por Exchange.',
                                time_window='Los partidos leídos del Exchange quedan fuera del intervalo prepartido.',
                                lay_buttons='Exchange no mostró botones lay activos en las filas leídas.',
                                price_format='No se pudo interpretar el formato de las cuotas o importes lay en euros.',
                                no_lay='Exchange mostró partidos, pero no se pudieron leer sus cuotas lay activas.',
                                teams='Se leyeron cuotas del Exchange, pero sus equipos no coinciden con las referencias de la casa.',
                                time='Se encontraron los equipos en el Exchange, pero la fecha u hora no coincide con la casa.',
                                market='Exchange no mostró el mercado «Cuotas de partido».',
                                layout='El formato de las cuotas del Exchange no se pudo leer.',
                                loading='Exchange no cargó la tabla de partidos antes del límite de espera.')
                _status.update(running=code=='reading', captured=int(number(data.get('captured', 0), 0, 5000)),
                               read=int(number(data.get('read',0),0,10000)),teams=int(number(data.get('teams',0),0,10000)),
                               message=messages.get(code, 'Exchange pendiente de lectura.'))
                public_counts=data.get('inspection') or {}
                _status['inspection']={name:int(number(public_counts.get(name,0),0,10000))
                                       for name in ('tables','headers','rows','teams','dates','future','buttons','prices')}
        except (ValueError, TypeError):
            return {'ok':False},400
    return dict(_status)


def enhanced_prices(q):
    """Read optional Bet365 prices without altering normal quotes used by Cruces."""
    a = core()
    try:
        data = json.loads(a.BET365_BROWSER_PATH.read_text(encoding='utf-8'))
        matches = [e for e in data.get('events', [])
                   if a.canonical_team(e.get('home')) == a.canonical_team(q.home)
                   and a.canonical_team(e.get('away')) == a.canonical_team(q.away)
                   and a.parse_dt(e.get('start')) == q.start
                   and e.get('market') == 'FULL_TIME_1X2'
                   and fresh(dict(e, observed_at=e.get('observed_at', data.get('observed_at'))))]
        if len(matches) != 1 or not matches[0].get('enhanced_odds'):
            return None
        return {sign:number(matches[0]['enhanced_odds'].get(sign), 1.01, 1000) for sign in ('1','X','2')}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


@bp.get('/freebets/opportunities')
def opportunities():
    a = core()
    a.restore_quote_cache()
    restore()
    source = request.args.get('source', 'winamax_es')
    if source not in a.SOURCE_DEFS:
        return {'ok':False, 'error':'Casa no reconocida.'},400
    try:
        f = number(request.args.get('freebet', 10), .01, 10000)
        c = number(request.args.get('commission', 2), 0, 20)
        min_odds = number(request.args.get('min_odds', 1.01), 1.01, 1000)
    except ValueError as exc:
        return {'ok':False, 'error':str(exc)},400
    variant = request.args.get('variant', 'both')
    if variant not in ('both', 'normal', 'enhanced'):
        return {'ok':False, 'error':'Tipo de cuota no reconocido.'},400
    cfg = a.read_config()
    rows = []
    eligible = 0
    insufficient = 0
    with _lock:
        events = [dict(e) for e in _lays.values() if fresh(e)]
    for group in list(a._last_groups):
        q = group.quotes.get(source)
        if not q or group.league_key not in cfg['selected_leagues'] or not a.quote_in_window(q,cfg['hours']) or not a.quote_is_fresh(q):
            continue
        eligible += 1
        matches = [e for e in events if a.canonical_team(e['home'])==a.canonical_team(q.home)
                   and a.canonical_team(e['away'])==a.canonical_team(q.away)
                   and abs((a.parse_dt(e['start'])-q.start).total_seconds())<=60]
        if len(matches)!=1:
            continue
        ex = matches[0]
        variants = [('normal', q.odds)]
        if source == 'bet365':
            improved = enhanced_prices(q)
            if improved:
                variants.append(('enhanced', improved))
            variants = [(kind, prices) for kind, prices in variants if variant == 'both' or kind == variant]
        for kind, prices in variants:
            for sign, lay in ex['lays'].items():
                if prices.get(sign,0)<min_odds:
                    continue
                calculation = calculate(f,prices[sign],lay['price'],c)
                if calculation['lay_stake']>lay['size']:
                    insufficient+=1
                    continue
                rows.append(dict(calculation, home=q.home,away=q.away,sign=sign,
                                 selection={'1':q.home,'X':'Empate','2':q.away}[sign], start=a.local_time_label(q.start),
                                 variant=kind, variant_label='Cuota mejorada' if kind=='enhanced' else 'Cuota normal',
                                 book=a.SOURCE_DEFS[source]['label'], book_url=q.direct_url or a.make_direct_url(source,q.slug),
                                 exchange_url=ex['url'], liquidity=lay['size'], observed_at=ex['observed_at'],
                                 book_received_at=q.received_at.isoformat()))
    rows.sort(key=lambda r:(-r['rating'], r['liability'], r['home'],r['sign']))
    return {'ok':True,'rows':rows,'eligible_matches':eligible,'exchange_matches':len(events),
            'insufficient_liquidity':insufficient,'api_calls':0,'status':dict(_status)}
