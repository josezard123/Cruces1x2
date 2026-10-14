"""Isolated browser test at 8803, using conspicuously labelled synthetic fixtures."""
from datetime import datetime, timedelta, timezone
import app as a
import freebets as f

if __name__ == '__main__':
    now=datetime.now(timezone.utc)
    start=now+timedelta(hours=4)
    cfg=dict(a.read_config(),selected_leagues=['laliga'])
    a.read_config=lambda:cfg
    q=a.SourceQuote('winamax_es','Winamax ES','test','Valencia [PRUEBA]','Levante [PRUEBA]',
                    'LaLiga','Spain',start,{'1':2.4,'X':3.4,'2':3.8},origin='Datos sintéticos de prueba')
    a._last_groups[:]=[a.MatchGroup(q.home,q.away,q.league,q.country,q.start,'laliga',{'winamax_es':q})]
    import tempfile,json
    from copy import deepcopy
    from pathlib import Path
    temporary=tempfile.TemporaryDirectory()
    for name in ('CONFIG_PATH','QUOTE_CACHE_PATH','LAST_DIAG_PATH','RATE_STATE_PATH','SCAN_RESULT_PATH','SPORTIUM_BROWSER_PATH'):
        setattr(a,name,Path(temporary.name)/name)
    a.BET365_BROWSER_PATH=Path(temporary.name)/'bet365.json'
    boosted=deepcopy(q);boosted.source='bet365';boosted.label='Bet365'
    boosted.enhanced_odds={'1':2.5,'X':3.6,'2':4}
    a._last_groups[0].quotes['bet365']=boosted
    reta=deepcopy(q);reta.source='retabet';reta.label='RETAbet ES'
    reta.normal_odds={'1':2.5,'X':3.99,'2':3.9}
    a._last_groups[0].quotes['retabet']=reta
    a.BET365_BROWSER_PATH.write_text(json.dumps({'events':[dict(event_id='test',home=q.home,away=q.away,
        start=start.isoformat(),market='FULL_TIME_1X2',odds=q.odds,enhanced_odds={'1':2.5,'X':3.6,'2':4},observed_at=now.isoformat())]}),encoding='utf-8')
    a.restore_quote_cache=lambda:None
    a.get_api_key=lambda:None
    f.restore=lambda:None
    f._lays['1.123456789']=dict(market_id='1.123456789',home=q.home,away=q.away,start=start.isoformat(),
                              observed_at=now.isoformat(),url='https://www.betfair.es/exchange/plus/',
                              lays={'1':{'price':2.5,'size':100},'X':{'price':3.5,'size':100},'2':{'price':4,'size':100}})
    a.app.run(host='127.0.0.1',port=8803,debug=False)
