"""Bounded local diagnostics of public sports labels; never account or page dumps."""
import json
import re
import threading
from datetime import datetime, timezone
from flask import Blueprint, request
from runtime_paths import data_dir

bp = Blueprint('reader_diagnostics', __name__)
_lock = threading.Lock()
DIAGNOSTIC_PATH = data_dir() / 'diagnostico' / 'lector_publico.json'
COUNTS = {'main', 'event_links', 'competition_links', 'match_cards', 'price_buttons',
          'date_nodes', 'home_nodes', 'away_nodes', 'market_nodes', 'candidate_pairs'}

def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError()
    return value

def label(value, limit=200, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not value and not empty):
        raise ValueError()
    if re.search(r'[@<>=€£$]|password|contrase|correo|email|saldo|balance|usuario|account|sesion|sesión|token|cookie|api.?key', value, re.I):
        raise ValueError()
    if any(not (c.isalnum() or c.isspace() or c in ".,:;()[]/+%•·–—^'-") for c in value):
        raise ValueError()
    return value

def sequence(value, maximum):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError()
    return value

def identifier(value, empty=False):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,24}' if not empty else r'\d{0,24}', value):
        raise ValueError()

def path(value):
    for node in sequence(value, 4):
        exact(node, ('tag', 'classes', 'role'))
        if not isinstance(node['tag'], str) or not re.fullmatch(r'[a-z0-9-]{0,24}', node['tag']):
            raise ValueError()
        if node['role'] not in ('', 'button', 'heading', 'main', 'link', 'group', 'list', 'listitem', 'row', 'cell'):
            raise ValueError()
        for name in sequence(node['classes'], 8):
            if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,90}', name):
                raise ValueError()

def validate(data):
    exact(data, ('schema', 'reader_version', 'source', 'phase', 'target', 'event_id',
                 'counts', 'nodes', 'competitions', 'rows', 'cards'))
    if type(data['schema']) is not int or data['schema'] != 1 or data['reader_version'] not in ('2.0.5', '2.0.6', '2.0.7'):
        raise ValueError()
    allowed = {'bet365': ('search', 'event'), 'betfair_sb': ('discover', 'coupon'),
               'winamax_es': ('discover', 'coupon'), 'sportium': ('catalogue',)}
    if data['source'] not in allowed or data['phase'] not in allowed[data['source']]:
        raise ValueError()
    exact(data['target'], ('home', 'away'))
    for value in data['target'].values():
        label(value, 120, empty=True)
    identifier(data['event_id'], empty=True)
    exact(data['counts'], COUNTS)
    if any(type(v) is not int or not 0 <= v <= 100000 for v in data['counts'].values()):
        raise ValueError()
    for node in sequence(data['nodes'], 40):
        exact(node, ('kind', 'text', 'path'))
        if node['kind'] not in ('date', 'home', 'away', 'pair', 'market'):
            raise ValueError()
        label(node['text']);path(node['path'])
    for competition in sequence(data['competitions'], 40):
        exact(competition, ('name', 'path'));label(competition['name'], 120)
        if not isinstance(competition['path'], str) or not re.fullmatch(r'(?:/apuestas/)?f%C3%BAtbol/[^/?#@]+/c-\d+', competition['path'], re.I):
            raise ValueError()
    for row in sequence(data['rows'], 20):
        exact(row, ('id', 'teams', 'date', 'prices', 'path'));identifier(row['id'])
        if len(sequence(row['teams'], 2)) != 2:
            raise ValueError()
        for team in row['teams']:
            label(team, 120)
        label(row['date'], 100, empty=True);path(row['path'])
        for price in sequence(row['prices'], 12):
            exact(price, ('price', 'active'))
            if not isinstance(price['price'], str) or not re.fullmatch(r'\d{1,6}(?:[.,]\d{1,6})?', price['price']) or type(price['active']) is not bool:
                raise ValueError()
    for card in sequence(data['cards'], 40):
        exact(card, ('id', 'lines'));identifier(card['id'])
        for line in sequence(card['lines'], 14):
            label(line, 120)
    return data

@bp.post('/reader-diagnostic')
def receive():
    origin = request.headers.get('Origin', '')
    if request.remote_addr not in ('127.0.0.1', '::1') or (origin and origin not in ('http://127.0.0.1:8802', 'http://127.0.0.1:8803') and not re.fullmatch(r'chrome-extension://[a-p]{32}', origin)):
        return {'ok': False}, 403
    if not request.is_json or request.content_length is None or request.content_length > 64000:
        return {'ok': False}, 400
    try:
        data = validate(request.get_json(silent=True))
        with _lock:
            try:
                records = json.loads(DIAGNOSTIC_PATH.read_text(encoding='utf-8'))
                if not isinstance(records, list):
                    records = []
            except (OSError, ValueError):
                records = []
            identity = (data['source'], data['phase'], data['target']['home'], data['target']['away'])
            records = [r for r in records if isinstance(r, dict) and
                       (r.get('source'), r.get('phase'), r.get('target', {}).get('home'), r.get('target', {}).get('away')) != identity]
            records.append({**data, 'captured_at': datetime.now(timezone.utc).isoformat()})
            DIAGNOSTIC_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = DIAGNOSTIC_PATH.with_suffix('.tmp')
            temporary.write_text(json.dumps(records[-24:], ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(DIAGNOSTIC_PATH)
        return {'ok': True, 'api_calls': 0}
    except (ValueError, TypeError, KeyError, AttributeError):
        return {'ok': False}, 400
