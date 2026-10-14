import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import app as a
import freebets as f
import test_direct

class RetabetTests(unittest.TestCase):
    def setUp(self):
        self._restore=a.restore_quote_cache
        test_direct.DirectTests.setUp(self)
        extra=[patch.object(f,'CACHE',Path(self.tmp.name)/'exchange.json'),patch.dict(f._lays,{},clear=True)]
        for p in extra:p.start()
        self.patches.extend(extra)
        self.client.post('/direct-observation/winamax_es',json=test_direct.DirectTests.payload(self))

    def tearDown(self):test_direct.DirectTests.tearDown(self)

    def payload(self):
        p=test_direct.DirectTests.payload(self)
        p['events'][0].update(event_id='456',payout='two_goals',source_url='https://apuestas.retabet.es/deportes/futbol/espana/laliga/valencia-levante/456')
        return p

    def test_public_club_variants_keep_youth_separate(self):
        self.assertEqual(a.canonical_team('F.C. Barcelona'),a.canonical_team('FC Barcelona'))
        self.assertEqual(a.canonical_team('Celta'),a.canonical_team('Celta Vigo'))
        self.assertNotEqual(a.canonical_team('F.C. Barcelona U19'),a.canonical_team('FC Barcelona'))

    def test_market_import_join_restore_and_freebets(self):
        result=self.client.post('/direct-observation/retabet',json=self.payload())
        self.assertEqual(result.json['captured'],1)
        self.assertEqual(len(a._last_groups),1)
        self.assertEqual(set(a._last_groups[0].quotes),{'winamax_es','retabet'})
        self.assertIn('2 goles de ventaja',a._last_groups[0].quotes['retabet'].origin)
        self.assertIn('RETAbet ES',self.client.get('/').data.decode())
        self.assertIn('value="retabet"',self.client.get('/freebets').data.decode())
        self.assertEqual(self.client.get('/freebets/targets?source=retabet').json['targets'][0]['league_key'],'laliga')
        self.assertEqual(self.client.get('/retabet-targets').json['targets'][0]['league_key'],'laliga')
        a._last_groups.clear()
        # The real restore routine is covered with this isolated cache.
        with patch.object(a,'restore_quote_cache',self._restore):
            a.restore_quote_cache()
            self.assertEqual(set(a._last_groups[0].quotes),{'winamax_es','retabet'})
        import json
        saved=json.loads(a.QUOTE_CACHE_PATH.read_text(encoding='utf-8'))
        self.assertEqual({q['source'] for q in saved},{'winamax_es','retabet'})

    def test_wrong_market_event_teams_time_and_country_are_rejected(self):
        for field,value in [('payout','normal'),('source_url','https://www.retabet.es/deportes/futbol/espana/laliga/valencia-levante/456'),
                            ('home','Valencia U19'),('country','Guatemala'),('start',(self.start+timedelta(hours=1)).isoformat()),('event_id','999')]:
            p=self.payload();p['events'][0][field]=value
            self.assertEqual(self.client.post('/direct-observation/retabet',json=p).status_code,400)
            self.assertNotIn('retabet',a._last_groups[0].quotes)

    def test_partial_preserves_other_houses_and_normal_rank(self):
        self.client.post('/direct-observation/retabet',json=self.payload())
        p=self.payload();p['events']=[]
        self.assertEqual(self.client.post('/direct-observation/retabet',json=p).json['captured'],0)
        self.assertEqual(set(a._last_groups[0].quotes),{'winamax_es','retabet'})
        exchange={'market':'MATCH_ODDS','currency':'EUR','observed_at':p['observed_at'],'events':[dict(home='Valencia',away='Levante',start=self.start.isoformat(),market_id='1.123456789',url='https://www.betfair.es/exchange/plus/es/fútbol/valencia-levante-apuestas-123456',lays={'X':{'price':3.5,'size':100}})]}
        self.assertEqual(self.client.post('/freebets/exchange-observation',json=exchange).json['captured'],1)
        ranking=self.client.get('/freebets/opportunities?source=retabet').json
        self.assertEqual(ranking['eligible_matches'],1)
        self.assertEqual(len(ranking['rows']),1)
        self.assertEqual(ranking['rows'][0]['book'],'RETAbet ES')

    def test_normal_draw_cross_and_both_freebet_markets(self):
        p=self.payload()
        normal={'1':2.2,'X':3.99,'2':3.5}
        p['events'][0]['normal_odds']={**normal,'private':'synthetic-ignore'}
        self.assertEqual(self.client.post('/direct-observation/retabet',json=p).json['captured'],1)
        group=a._last_groups[0];quote=group.quotes['retabet']
        self.assertEqual(quote.normal_odds,normal)
        self.assertNotIn('synthetic-ignore',a.QUOTE_CACHE_PATH.read_text(encoding='utf-8'))
        group.quotes['sportium']=a.SourceQuote('sportium','Sportium ES','123',quote.home,quote.away,quote.league,quote.country,self.start,{'1':2.1,'X':3.2,'2':3.4})
        alternatives=a.build_crosses([group],100,1000)[0]['alternatives']
        for row in alternatives:
            if row['sourceX']=='retabet':
                self.assertEqual(row['qX'],3.99);self.assertEqual(row['marketX'],'Cuota normal')
            if row['source1']=='retabet':self.assertEqual(row['q1'],quote.odds['1'])
            if row['source2']=='retabet':self.assertEqual(row['q2'],quote.odds['2'])
        a.save_quote_cache();a._last_groups.clear()
        with patch.object(a,'restore_quote_cache',self._restore):a.restore_quote_cache()
        self.assertEqual(a._last_groups[0].quotes['retabet'].normal_odds,normal)
        exchange={'market':'MATCH_ODDS','currency':'EUR','observed_at':p['observed_at'],'events':[dict(home='Valencia',away='Levante',start=self.start.isoformat(),market_id='1.123456789',url='https://www.betfair.es/exchange/plus/es/fútbol/valencia-levante-apuestas-123456',lays={'X':{'price':4.0,'size':1000}})]}
        self.client.post('/freebets/exchange-observation',json=exchange)
        ranking=self.client.get('/freebets/opportunities?source=retabet&freebet=100').json['rows']
        self.assertEqual(len(ranking),2)
        self.assertEqual(ranking[0]['variant'],'normal');self.assertEqual(ranking[0]['back'],3.99)
        self.assertGreater(ranking[0]['rating'],ranking[1]['rating'])
        self.assertEqual(len(self.client.get('/freebets/opportunities?source=retabet&variant=normal').json['rows']),1)
        self.assertEqual(self.client.get('/freebets/opportunities?source=retabet&variant=two_goals').json['rows'][0]['variant_label'],'Ventaja 2 goles')

    def test_invalid_optional_normal_market_cannot_replace_verified_quotes(self):
        self.client.post('/direct-observation/retabet',json=self.payload())
        original=a._last_groups[0].quotes['retabet'].odds
        for bad in [{'X':3.99},{'1':True,'X':3.99,'2':3.5},{'1':2.2,'X':float('nan'),'2':3.5}]:
            p=self.payload();p['events'][0]['normal_odds']=bad
            self.assertEqual(self.client.post('/direct-observation/retabet',json=p).status_code,400)
            self.assertEqual(a._last_groups[0].quotes['retabet'].odds,original)
            self.assertIsNone(a._last_groups[0].quotes['retabet'].normal_odds)

if __name__=='__main__':unittest.main()
