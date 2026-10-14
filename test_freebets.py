import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import app as a
import freebets as f


class FreebetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [patch.object(f,'CACHE',root/'ex.json'),patch.object(a,'QUOTE_CACHE_PATH',root/'quotes.json'),
                        patch.object(a,'CONFIG_PATH',root/'cfg.json'),patch.object(a,'restore_quote_cache'),
                        patch.object(a,'_last_groups',[]),patch.object(a.requests,'get',side_effect=AssertionError('network'))]
        for p in self.patches:p.start()
        f._lays.clear()
        self.client = a.app.test_client()
        self.start=datetime.now(timezone.utc)+timedelta(hours=4)
        self.q=a.SourceQuote('winamax_es','Winamax ES','abc','Valencia','Levante','LaLiga','Spain',self.start,{'1':2.4,'X':3.4,'2':3.8})
        a._last_groups.append(a.MatchGroup('Valencia','Levante','LaLiga','Spain',self.start,'laliga',{'winamax_es':self.q}))

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        f._lays.clear()
        self.tmp.cleanup()

    def payload(self,**changes):
        event=dict(home='Valencia',away='Levante',start=self.start.isoformat(),market_id='1.123456789',
                   url='https://www.betfair.es/exchange/plus/es/fútbol/valencia-levante-apuestas-123456',
                   lays={'1':{'price':2.5,'size':100},'X':{'price':3.5,'size':100},'2':{'price':4,'size':100}})
        event.update(changes)
        return dict(market='MATCH_ODDS',currency='EUR',observed_at=datetime.now(timezone.utc).isoformat(),events=[event])

    def test_snr_example_and_commission(self):
        r=f.calculate(10,'3,40','3,50',2)
        self.assertEqual(r['gross'],24)
        self.assertEqual(r['lay_stake'],6.9)
        self.assertEqual(r['liability'],17.25)
        self.assertEqual(r['profit'],6.75)
        self.assertEqual(r['rating'],67.5)
        self.assertGreater(f.calculate(10,3.4,3.5,0)['rating'],r['rating'])
        self.assertLess(f.calculate(10,3.4,3.5,5)['rating'],r['rating'])

    def test_exchange_diagnostic_whitelists_only_numeric_counts(self):
        response=self.client.post('/freebets/status',json={'state':'price_format','captured':0,
            'inspection':{'tables':3,'rows':48,'prices':0,'api_key':'test-secret'},'api_key':'test-secret'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['inspection']['rows'],48)
        self.assertNotIn('test-secret',response.data.decode())
        self.assertNotIn('api_key',response.json['inspection'])

    def test_exchange_club_aliases_do_not_duplicate_rating(self):
        self.q.home='Real Sociedad';self.q.away='Deportivo de A Coruña'
        other=a.SourceQuote('betfair_sb','Betfair Sportsbook','other','Real Sociedad','Deportivo',
                            'Spanish La Liga','',self.start,{'1':2.5,'X':3.5,'2':4})
        a._last_groups[:]=a.group_quotes({'winamax_es':[self.q],'betfair_sb':[other]}, {'laliga'},24)
        payload=self.payload(home='Real Sociedad',away='Deportivo')
        self.assertEqual(self.client.post('/freebets/exchange-observation',json=payload).json['captured'],1)
        ranking=self.client.get('/freebets/opportunities?source=winamax_es').json
        self.assertEqual(ranking['eligible_matches'],1)
        self.assertEqual(len(ranking['rows']),3)
        self.assertEqual(ranking['rows'][0]['away'],'Deportivo de A Coruña')

    def test_bet365_enhanced_is_separate_and_optional(self):
        import json
        self.q.source='bet365';self.q.label='Bet365 ES'
        a._last_groups[0].quotes={'bet365':self.q}
        self.client.post('/freebets/exchange-observation',json=self.payload())
        path=Path(self.tmp.name)/'bet365.json'
        event=dict(event_id='abc',home=self.q.home,away=self.q.away,start=self.start.isoformat(),
                   market='FULL_TIME_1X2',odds=self.q.odds,enhanced_odds={'1':2.5,'X':3.6,'2':4},
                   observed_at=self.q.received_at.isoformat())
        with patch.object(a,'BET365_BROWSER_PATH',path):
            path.write_text(json.dumps({'events':[event]}),encoding='utf-8')
            rows=self.client.get('/freebets/opportunities?source=bet365').json['rows']
            self.assertEqual(len(rows),6)
            normal=self.client.get('/freebets/opportunities?source=bet365&variant=normal').json['rows']
            enhanced=self.client.get('/freebets/opportunities?source=bet365&variant=enhanced').json['rows']
            self.assertEqual(len(normal),3);self.assertEqual(len(enhanced),3)
            for sign in ('1','X','2'):
                self.assertGreater(next(r['rating'] for r in enhanced if r['sign']==sign),
                                   next(r['rating'] for r in normal if r['sign']==sign))
            self.assertEqual(self.q.odds,{'1':2.4,'X':3.4,'2':3.8})
            event['start']=(self.start+timedelta(days=1)).isoformat()
            path.write_text(json.dumps({'events':[event]}),encoding='utf-8')
            self.assertEqual(self.client.get('/freebets/opportunities?source=bet365&variant=enhanced').json['rows'],[])
            self.assertEqual(len(self.client.get('/freebets/opportunities?source=bet365').json['rows']),3)

    def test_exchange_and_book_expire_after_one_hour(self):
        now=datetime.now(timezone.utc)
        event=dict(observed_at=(now-timedelta(minutes=59)).isoformat(),start=self.start.isoformat())
        self.assertTrue(f.fresh(event,now))
        event['observed_at']=(now-timedelta(minutes=61)).isoformat()
        self.assertFalse(f.fresh(event,now))
        self.client.post('/freebets/exchange-observation',json=self.payload())
        self.q.received_at=now-timedelta(minutes=61)
        self.assertEqual(self.client.get('/freebets/opportunities').json['rows'],[])

    def test_legacy_enhanced_does_not_mix_captures(self):
        import json
        self.q.source='bet365';a._last_groups[0].quotes={'bet365':self.q}
        event=dict(event_id='abc',home=self.q.home,away=self.q.away,start=self.start.isoformat(),market='FULL_TIME_1X2',odds=self.q.odds,
                   enhanced_odds={'1':2.5,'X':3.6,'2':4},observed_at=(self.q.received_at-timedelta(minutes=5)).isoformat())
        path=Path(self.tmp.name)/'bet365.json'
        with patch.object(a,'BET365_BROWSER_PATH',path):
            path.write_text(json.dumps({'events':[event]}),encoding='utf-8')
            self.assertIsNone(f.enhanced_prices(self.q))
        self.q.enhanced_odds=event['enhanced_odds']
        self.client.post('/freebets/exchange-observation',json=self.payload())
        rows=self.client.get('/freebets/opportunities?source=bet365&variant=enhanced').json['rows']
        self.assertEqual(len(rows),3)
        self.assertEqual(next(row['back'] for row in rows if row['sign']=='X'),3.6)

    def test_cent_rounding_globally_optimal(self):
        for back,lay in [(3.4,3.5),(8.5,9),(1.01,100),(12.75,12.5),(2.1,1.8)]:
            r=f.calculate(10,back,lay,2)
            ideal=10*(back-1)/(lay-.02)
            for cents in range(max(1,int(ideal*100)-5),int(ideal*100)+6):
                stake=cents/100
                import math
                liability=math.ceil((stake*(lay-1)-1e-9)*100)/100
                expected=min(math.floor((10*(back-1)-liability+1e-9)*100)/100,math.floor((stake*.98+1e-9)*100)/100)
                self.assertGreaterEqual(r['profit']+1e-9,expected)

    def test_invalid_and_routes(self):
        self.assertEqual(self.client.get('/freebets').status_code,200)
        for key,value in [('freebet',0),('freebet',True),('back',1),('lay','nan'),('lay','inf'),('commission',-1),('commission',100)]:
            data=dict(freebet=10,back=3.4,lay=3.5,commission=2);data[key]=value
            self.assertEqual(self.client.post('/freebets/calculate',json=data).status_code,400)
        self.assertEqual(self.client.post('/freebets/calculate',json=[]).status_code,400)

    def test_ranking_house_filter_no_network(self):
        self.assertEqual(self.client.post('/freebets/exchange-observation',json=self.payload()).json['captured'],1)
        r=self.client.get('/freebets/opportunities?source=winamax_es&freebet=10&commission=2').json
        self.assertEqual(len(r['rows']),3)
        self.assertEqual([row['rating'] for row in r['rows']],sorted([row['rating'] for row in r['rows']],reverse=True))
        self.assertEqual(r['api_calls'],0)
        self.assertEqual(self.client.get('/freebets/opportunities?source=bet365').json['rows'],[])
        filtered=self.client.get('/freebets/opportunities?source=winamax_es&min_odds=3.5').json
        self.assertEqual(len(filtered['rows']),1)
        self.assertEqual(filtered['rows'][0]['sign'],'2')

    def test_excludes_insufficient_expired_ambiguous(self):
        data=self.payload(lays={'X':{'price':3.5,'size':6.89}})
        self.client.post('/freebets/exchange-observation',json=data)
        r=self.client.get('/freebets/opportunities').json
        self.assertEqual(r['rows'],[]);self.assertEqual(r['insufficient_liquidity'],1)
        f._lays.clear()
        self.client.post('/freebets/exchange-observation',json=self.payload())
        f._lays['1.123456789']['observed_at']=(datetime.now(timezone.utc)-timedelta(minutes=59)).isoformat()
        self.assertEqual(len(self.client.get('/freebets/opportunities').json['rows']),3)
        f._lays['1.123456789']['observed_at']=(datetime.now(timezone.utc)-timedelta(seconds=3601)).isoformat()
        self.assertEqual(self.client.get('/freebets/opportunities').json['rows'],[])
        f._lays.clear()
        self.client.post('/freebets/exchange-observation',json=self.payload())
        self.client.post('/freebets/exchange-observation',json=self.payload(market_id='1.987654321'))
        self.assertEqual(self.client.get('/freebets/opportunities').json['rows'],[])
        f._lays.clear()
        self.client.post('/freebets/exchange-observation',json=self.payload())
        self.q.received_at=datetime.now(timezone.utc)-timedelta(minutes=59)
        self.assertEqual(len(self.client.get('/freebets/opportunities').json['rows']),3)
        self.q.received_at=datetime.now(timezone.utc)-timedelta(minutes=301)
        self.assertEqual(self.client.get('/freebets/opportunities').json['rows'],[])

    def test_rejects_wrong_event_time_market_currency(self):
        for changes in [dict(home='Otro equipo'),dict(home='Levante',away='Valencia'),dict(start=(self.start+timedelta(minutes=2)).isoformat()),dict(url='https://evil.example/exchange/plus/'),dict(market_id='bad')]:
            self.assertEqual(self.client.post('/freebets/exchange-observation',json=self.payload(**changes)).json['captured'],0)
        for key,value in [('market','TOTAL_GOALS'),('currency','GBP'),('observed_at',(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat())]:
            data=self.payload();data[key]=value
            self.assertEqual(self.client.post('/freebets/exchange-observation',json=data).status_code,400)
        data=self.payload();data['secret']='not-to-be-written';data['events'][0]['secret']='not-to-be-written'
        self.client.post('/freebets/exchange-observation',json=data)
        self.assertNotIn('not-to-be-written',f.CACHE.read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
