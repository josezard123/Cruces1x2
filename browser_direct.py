"""Public browser observations for Winamax and Betfair; never calls PulseScore."""
import sys
import math
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote
from flask import Blueprint, request

bp=Blueprint('browser_direct',__name__)
_core=None

def register(application):
    global _core
    _core=sys.modules[application.import_name]
    application.register_blueprint(bp)

@bp.get('/direct-settings')
def settings():
    a=_core;cfg=a.read_config()
    return dict(leagues=cfg['selected_leagues'],hours=cfg['hours'],aliases=a.TEAM_ALIASES,api_calls=0)

@bp.post('/direct-observation/<source>')
def observation(source):
    a=_core
    if source not in ('winamax_es','betfair_sb','retabet'):
        return {'ok':False},400
    if a._update_cancel.is_set():return {'ok':False,'reason':'Actualización detenida.'},409
    try:
        data=request.get_json(silent=True)
        now=datetime.now(timezone.utc);stamp=a.parse_dt(data['observed_at'])
        if not stamp or not -5 <= (now-stamp).total_seconds() <= 60 or not isinstance(data['events'],list) or len(data['events'])>500:
            raise ValueError()
        cfg=a.read_config();accepted=[];seen=set()
        for event in data['events']:
            parsed=urlparse(event['source_url']);path=unquote(parsed.path)
            if parsed.scheme!='https' or parsed.hostname!=urlparse(a.SOURCE_DEFS[source]['site']).hostname or parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise ValueError()
            if source=='winamax_es' and not __import__('re').fullmatch(r'/apuestas-deportivas/match/\d+',path):raise ValueError()
            if source=='betfair_sb' and not __import__('re').fullmatch(r'/apuestas/fútbol/[^/]+/[^/]+/e-\d+',path):raise ValueError()
            if source=='retabet' and not __import__('re').fullmatch(r'/deportes/futbol/[^/]+/[^/]+/[^/]+/\d+',path):raise ValueError()
            if event.get('market')!='FULL_TIME_1X2' or event.get('payout') not in ('normal','two_goals'):raise ValueError()
            if source=='winamax_es' and event['payout']!='normal':raise ValueError()
            if source in ('betfair_sb','retabet') and event['payout']!='two_goals':raise ValueError()
            start=a.parse_dt(event['start'])
            if not start:raise ValueError()
            home,away=event['home'],event['away']
            if not all(isinstance(x,str) and 0<len(x)<=120 for x in (home,away,event['league'],event.get('country',''))):raise ValueError()
            odds={sign:float(event['odds'][sign]) for sign in ('1','X','2')}
            if any(isinstance(event['odds'][sign],bool) for sign in odds) or not all(math.isfinite(v) and 1<v<=1000 for v in odds.values()):raise ValueError()
            event_id=str(event['event_id'])
            if not event_id.isdigit() or not path.endswith('/e-'+event_id if source=='betfair_sb' else '/'+event_id):raise ValueError()
            if event_id in seen:raise ValueError()
            seen.add(event_id)
            origin='Web '+a.SOURCE_DEFS[source]['label']+' · '+('Resultado — 2 goles de ventaja' if event['payout']=='two_goals' else '1X2 normal')
            q=a.SourceQuote(source,a.SOURCE_DEFS[source]['label'],event_id,home,away,event['league'],event['country'],start,odds,
                            direct_url=event['source_url'],received_at=stamp,updated=stamp.isoformat(),origin=origin)
            if source=='retabet':
                a.restore_quote_cache()
                references=[g.quotes['winamax_es'] for g in a._last_groups if 'winamax_es' in g.quotes]
                matches=[r for r in references if a.canonical_team(r.home)==a.canonical_team(home)
                         and a.canonical_team(r.away)==a.canonical_team(away)
                         and abs((r.start-start).total_seconds())<=60 and a.classify_league(r)==a.classify_league(q)]
                if len(matches)!=1:raise ValueError()
            if a.classify_league(q) in cfg['selected_leagues'] and a.quote_in_window(q,cfg['hours']):accepted.append(q)
        # Commit only validated public fields and retain existing quotes on partial scans.
        with a._web_import_lock:
            if a._update_cancel.is_set():return {'ok':False,'reason':'Actualización detenida.'},409
            a.restore_quote_cache()
            by_source={s:[] for s in a.SOURCE_DEFS}
            new_ids={q.event_id for q in accepted}
            for g in a._last_groups:
                for q in g.quotes.values():
                    if q.source!=source or q.event_id not in new_ids:by_source[q.source].append(q)
            by_source[source].extend(accepted)
            a._last_groups[:]=a.group_quotes(by_source,set(cfg['selected_leagues']),cfg['hours'])
            a.save_quote_cache()
            a._last_result.setdefault('stats',{})['api_calls']=0
            a._last_result['coverage']=a.coverage_rows(a._last_groups)
        return {'ok':True,'captured':len(accepted),'api_calls':0}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return {'ok':False,'reason':'Lectura pública incompleta o de origen, fecha o mercado no válidos.'},400
