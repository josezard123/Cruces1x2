import itertools
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import app as a


def market(**changes):
    m = {"canonicalMarket": "MATCH_RESULT", "rawName": "Full Time Result", "period": "FULL_TIME", "isActive": True,
         "selections": [{"canonicalOutcome": k, "odds": v, "isActive": True} for k, v in [("HOME", 2.1), ("DRAW", 3.2), ("AWAY", 3.4)]]}
    m.update(changes)
    return m


def q(source="bet365", home="Spain", away="Croatia", league="UEFA Nations League", country="", minutes=60):
    return a.SourceQuote(source, a.SOURCE_DEFS[source]["label"], source, home, away, league, country,
                         datetime.now(timezone.utc) + timedelta(minutes=minutes), {"1": 2.1, "X": 3.2, "2": 3.4})


class AppTests(unittest.TestCase):
    def test_cross_calculator_preserves_three_decimal_prices(self):
        calc=a.optimized_stakes(10,2.1,6.255,3.4)
        calc.update(q1=2.1,qX=6.255,q2=3.4,book1='A',bookX='B',book2='C',market1='',marketX='',market2='',url1='',urlX='',url2='')
        with a.app.test_request_context('/'):
            widget=str(a.app.jinja_env.get_template('cross_calculator.html').module.cross_calculator(calc,'precision','Partido'))
        self.assertIn('value="6.255"',widget)
        self.assertNotIn('value="6.25"',widget)

    def test_cross_calculators_render_for_every_assignment(self):
        from html.parser import HTMLParser
        a.write_config({'max_loss':100})
        response=a.app.test_client().get('/demo')
        self.assertEqual(response.status_code,200)
        html=response.data.decode()
        self.assertEqual(html.count('data-cross-calculator role='),6)
        self.assertEqual(html.count('data-inline-toggle='),5)
        self.assertNotIn('Llevar a la calculadora',html)
        self.assertIn('/static/cross_calculator.js',html)
        self.assertIn('cruces-calculator-edit',html)
        class Inputs(HTMLParser):
            def __init__(self): super().__init__();self.ids=[];self.fields=[]
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if 'id' in attrs:self.ids.append(attrs['id'])
                if 'data-calc-field' in attrs:self.fields.append(attrs)
        parsed=Inputs();parsed.feed(html)
        self.assertEqual(len(parsed.ids),len(set(parsed.ids)))
        self.assertEqual(len(parsed.fields),36)
        self.assertTrue(all(field.get('value') and field.get('aria-label') for field in parsed.fields))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [patch.object(a, "CONFIG_PATH", root/"config.json"), patch.object(a, "RATE_STATE_PATH", root/"rate.json"),
                        patch.object(a, "ENCRYPTED_KEY_PATH", root/"key.dpapi"), patch.object(a, "_session_api_key", None),
                        patch.object(a, "BET365_BROWSER_PATH", root/"bet365.json"), patch.object(a,"QUOTE_CACHE_PATH",root/"quotes.json"),
                        patch.object(a, "LAST_DIAG_PATH", root/"diag.json"), patch.object(a, "get_api_key", return_value=None)]
        self.patches.extend([patch.object(a,'SCAN_RESULT_PATH',root/'scan.json')])
        self.patches.extend([patch.object(a,'SPORTIUM_BROWSER_PATH',root/'sportium.json')])
        for p in self.patches:
            p.start()
        # These tests also cover the retained legacy API implementation explicitly.
        a.write_config({'odds_mode':'pulsescore','bet365_mode':'pulsescore'})
        a._page_cache.clear()
        a._last_result.clear()
        a._last_groups.clear()
        a._scan_status.clear()
        a._browser_results.clear()
        a._update_cancel.clear()
        a._update_progress.clear()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_routes_no_network(self):
        with patch.object(a.requests, "get", side_effect=AssertionError("unexpected network")):
            c = a.app.test_client()
            for path in ("/", "/demo"):
                self.assertEqual(c.get(path).status_code, 200)
            for path in ("/update", "/check-api"):
                self.assertEqual(c.get(path).status_code, 405)
                self.assertEqual(c.post(path).status_code, 200)

    def test_one_hour_policy_overrides_saved_five_hours(self):
        a.write_config({'max_source_age_minutes':300})
        self.assertEqual(a.read_config()['max_source_age_minutes'],60)
        quote=q()
        quote.received_at=datetime.now(timezone.utc)-timedelta(minutes=59)
        self.assertTrue(a.quote_is_fresh(quote))
        quote.received_at-=timedelta(minutes=2)
        self.assertFalse(a.quote_is_fresh(quote))
        pages=a.app.test_client()
        self.assertNotIn('PulseScore',pages.get('/').data.decode())
        self.assertNotIn('PulseScore',pages.get('/freebets').data.decode())

    def test_bet365_cross_only_draw_uses_enhanced_and_survives_restore(self):
        quote=q('bet365')
        quote.enhanced_odds={'1':2.5,'X':3.6,'2':4}
        books={'bet365':quote,'winamax_es':q('winamax_es'),'sportium':q('sportium')}
        group=a.MatchGroup(quote.home,quote.away,quote.league,quote.country,quote.start,'internationals',books)
        alternatives=a.build_crosses([group],20,100)[0]['alternatives']
        for row in alternatives:
            if row['sourceX']=='bet365':
                self.assertEqual(row['qX'],3.6)
                self.assertEqual(row['marketX'],'Cuota mejorada')
            if row['source1']=='bet365':self.assertEqual(row['q1'],2.1)
            if row['source2']=='bet365':self.assertEqual(row['q2'],3.4)
        self.assertEqual(quote.odds,{'1':2.1,'X':3.2,'2':3.4})
        self.assertEqual(a.coverage_rows([group])[0]['books']['bet365']['odds']['X'],3.6)
        a._last_groups[:]=[group]
        html=a.app.test_client().get('/')
        self.assertEqual(html.status_code,200)
        self.assertIn('Cuota mejorada',html.data.decode())
        a.save_quote_cache();a._last_groups.clear();a.restore_quote_cache()
        self.assertEqual(a._last_groups[0].quotes['bet365'].enhanced_odds,quote.enhanced_odds)
        self.assertEqual(a.cross_prices(a._last_groups[0].quotes['bet365'])[0]['X'],3.6)

    def test_spanish_club_aliases_merge_under_winamax_names(self):
        pairs=[('Deportivo de A Coruña','Deportivo'),('Racing De Santander','Racing Santander'),('Athletic Bilbao','Athletic de Bilbao')]
        for first,second in pairs:
            w=q('winamax_es',first,'Valencia','LaLiga','Spain')
            b=q('betfair_sb',second,'Valencia','Spanish La Liga')
            groups=a.group_quotes({'winamax_es':[w,w],'betfair_sb':[b]}, {'laliga'},24)
            self.assertEqual(len(groups),1)
            self.assertEqual(groups[0].home,first)
            self.assertEqual(set(groups[0].quotes),{'winamax_es','betfair_sb'})

    def test_europa_club_names_join_without_merging_youth_or_other_leagues(self):
        pairs=[('Sturm Graz','SK Sturm Graz'),('Rennes','FC Stade Rennes'),('Rennes','Stade Rennais'),
               ('OFI Creta','OFI Crete'),('Marsella','O. Marsella'),('NEC Nijmegen','NEC'),
               ('Ferencvaros','Ferencvarosi TC'),('Ferencvaros','Ferencvarosi'),('Viktoria Plzen','FC Viktoria Pilsen'),
               ('Lillestrøm','Lillestrøm SK'),('Celje','Nk Celje'),('Torreense','Sc União Torreense'),('Lyon','Olympique Lyon')]
        for reference,observed in pairs:
            with self.subTest(reference=reference,observed=observed):
                self.assertEqual(a.canonical_team(reference),a.canonical_team(observed))
                self.assertNotEqual(a.canonical_team(reference),a.canonical_team(observed+' U19'))
                w=q('winamax_es',reference,'Test Rival','Europa League','Europa')
                b=q('sportium',observed,'Test Rival','UEFA Europa League','Europa')
                b.start=w.start
                groups=a.group_quotes({'winamax_es':[w],'sportium':[b]}, {'uel'},24)
                self.assertEqual(len(groups),1)
                self.assertEqual(set(groups[0].quotes),{'winamax_es','sportium'})
                b.league='UEFA Conference League'
                self.assertNotIn('sportium',a.group_quotes({'winamax_es':[w],'sportium':[b]}, {'uel'},24)[0].quotes)

    def test_champions_names_merge_without_other_leagues_or_youth(self):
        pairs=[('PSV Eindhoven','PSV'),('Nápoles','Napoli'),('Galatasaray','Galatasaray SK'),('Viking','Viking FK'),
               ('Inter Milán','Inter de Milán'),('Sporting Portugal','Sporting'),('Sporting Portugal','Sporting Lisboa'),
               ('Sporting Portugal','Sporting CP'),('Slavia Praga','SK Slavia Praha'),('Slavia Praga','SK Slavia Praga'),
               ('Slavia Praga','Slavia Prague'),('Atlético Madrid','At. Madrid'),('Manchester United','Man. United'),
               ('Lille','Lille OSC'),('Bayern Múnich','Bayern M.'),('Lens','RC Lens')]
        for reference,observed in pairs:
            with self.subTest(reference=reference,observed=observed):
                self.assertEqual(a.canonical_team(reference),a.canonical_team(observed))
                self.assertNotEqual(a.canonical_team(reference),a.canonical_team(observed+' U19'))
                w=q('winamax_es',reference,'Test Rival','Champions League','Europa')
                b=q('sportium',observed,'Test Rival','UEFA Champions League','Europa');b.start=w.start
                groups=a.group_quotes({'winamax_es':[w],'sportium':[b]},{'ucl'},24)
                self.assertEqual(len(groups),1);self.assertEqual(set(groups[0].quotes),{'winamax_es','sportium'})
                b.league='UEFA Europa League'
                self.assertNotIn('sportium',a.group_quotes({'winamax_es':[w],'sportium':[b]},{'ucl'},24)[0].quotes)

    def test_bet365_bare_spanish_league_needs_unique_reference(self):
        a.write_config({'selected_leagues':['laliga'],'bet365_mode':'browser_auto'})
        ref=q('winamax_es','Valencia','Levante','LaLiga','Spain')
        a._last_groups[:]=a.group_quotes({'winamax_es':[ref]}, {'laliga'},24)
        payload=self.web_payload()
        payload['events'][0].update(home=ref.home,away=ref.away,start=ref.start.isoformat(),league='Primera División')
        client=a.app.test_client()
        self.assertEqual(client.post('/bet365-scan-observation',json=payload).status_code,200)
        self.assertIn('bet365',a._last_groups[0].quotes)
        payload['events'][0]['league']='Guatemala - Liga Nacional'
        self.assertEqual(client.post('/bet365-scan-observation',json=payload).status_code,400)

    def test_sportium_only_targets_48_hours(self):
        a.write_config({'hours':168,'selected_leagues':['laliga']})
        a._last_groups[:]=a.group_quotes({'winamax_es':[q('winamax_es','Valencia','Levante','LaLiga','Spain',minutes=47*60),q('winamax_es','Betis','Osasuna','LaLiga','Spain',minutes=49*60)]},{'laliga'},168)
        result=a.app.test_client().get('/bet365-targets?source=sportium').json
        self.assertEqual(len(result['targets']),1)
        self.assertEqual(result['outside_window'],1)

    def test_busy_update_attaches_progress_without_network(self):
        a._update_lock.acquire()
        try:
            a._update_progress.update(source='Winamax ES',page=4)
            with patch.object(a.requests,'get',side_effect=AssertionError('unexpected network')):
                c=a.app.test_client()
                self.assertIn(b'watchProviderUpdate(true)',c.post('/update').data)
                self.assertEqual(c.get('/update-status').json['page'],4)
                self.assertTrue(c.post('/stop-update').json['running'])
                self.assertTrue(c.get('/update-status').json['cancelled'])
        finally:
            a._update_lock.release()

    def test_cancelled_update_preserves_previous_quotes_and_skips_next_source(self):
        old=q('winamax_es')
        a._last_groups[:]=a.group_quotes({'winamax_es':[old]},{'internationals'},24)
        previous=list(a._last_groups)
        def fetch(*args):
            a.app.test_client().post('/stop-update')
            return [q('winamax_es')],{'with_1x2':1}
        with patch.object(a,'get_api_key',return_value='test-secret'),patch.object(a,'fetch_source',side_effect=fetch) as calls:
            html=a.app.test_client().post('/update').data.decode()
        self.assertEqual(calls.call_count,1)
        self.assertEqual(a._last_groups,previous)
        self.assertIn('Actualización detenida',html)
        self.assertNotIn('test-secret',html)
        self.assertFalse(a._update_lock.locked())

    def test_simple_update_saves_visible_filters_before_fetch(self):
        a.write_config({'hours':24,'selected_leagues':['internationals'],'api_plan':'PRO','bet365_mode':'pulsescore','odds_mode':'pulsescore'})
        target=q('winamax_es','Valencia','Levante','LaLiga','Spain',minutes=48*60)
        def fetch(source,*args):
            cfg=a.read_config()
            self.assertEqual(cfg['hours'],72)
            self.assertEqual(cfg['selected_leagues'],['laliga'])
            self.assertEqual(cfg['api_plan'],'BASIC')
            self.assertEqual(cfg['bet365_mode'],'browser_auto')
            self.assertNotEqual(source,'bet365')
            return ([target] if source=='winamax_es' else []),{'with_1x2':1,'api_calls':0}
        with patch.object(a,'get_api_key',return_value='test-secret'),patch.object(a,'fetch_source',side_effect=fetch):
            response=a.app.test_client().post('/update',data={'settings_version':'simple','base_stake':'10','hours':'72','max_loss':'2','leagues':'laliga'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(len(a._last_groups),1)
            self.assertIn(b'Valencia',response.data)
            self.assertNotIn(b'test-secret',response.data)

    def test_simple_update_invalid_filters_never_fetch_or_write(self):
        original=a.read_config()
        with patch.object(a,'fetch_source',side_effect=AssertionError('unexpected provider call')):
            for changes in ({'hours':'bad'},{'base_stake':'NaN'},{'leagues':[]},{'max_loss':'-1'}):
                data={'settings_version':'simple','base_stake':'10','hours':'72','max_loss':'2','leagues':'laliga'}
                data.update(changes)
                self.assertEqual(a.app.test_client().post('/update',data=data).status_code,200)
                self.assertEqual(a.read_config(),original)

    def test_empty_selected_window_explained_without_empty_browser_scan(self):
        a.write_config({'bet365_mode':'browser_auto','hours':24,'selected_leagues':['laliga'],'odds_mode':'pulsescore'})
        unrelated=q('winamax_es',league='Brazil Serie B',country='Brazil')
        with patch.object(a,'get_api_key',return_value='test-secret'),patch.object(a,'fetch_source',return_value=([unrelated],{'with_1x2':1,'api_calls':0})):
            html=a.app.test_client().post('/update').data.decode()
            self.assertIn('próximas 24 horas',html)
            self.assertIn('Amplía',html)
            self.assertNotIn('Preparando búsqueda automática',html)

    def test_simple_home_hides_redundant_controls(self):
        html=a.app.test_client().get('/').data.decode()
        self.assertNotIn('name="api_plan"',html)
        self.assertNotIn('name="bet365_mode"',html)
        self.assertNotIn('Guardar competiciones',html)
        self.assertNotIn('Probar modo demo',html)
        self.assertIn('name="settings_version" value="simple"',html)
        self.assertIn('Herramientas y ayuda',html)

    def test_manual_calculator_optimized_no_provider(self):
        data={'q1':'8,50','qX':'6,25','q2':'1,27','stake1':'10'}
        with patch.object(a.requests,'get',side_effect=AssertionError('unexpected provider call')):
            reply=a.app.test_client().post('/calculate-manual',json=data)
        self.assertEqual(reply.status_code,200)
        result=reply.json['result']
        expected=a.optimized_stakes(10,8.5,6.25,1.27)
        for key in ('stake1','stakeX','stake2','total','worst_profit'):self.assertEqual(result[key],expected[key])
        self.assertEqual(result['profit1'],a.money(result['return1']-result['total']))

    def test_manual_calculator_custom_amounts_and_invalid(self):
        c=a.app.test_client()
        data={'q1':2,'qX':3,'q2':4,'stake1':10,'stakeX':5,'stake2':5,'manual_stakes':True}
        result=c.post('/calculate-manual',json=data).json['result']
        self.assertEqual((result['total'],result['profit1'],result['profitX'],result['profit2']),(20,0,-5,0))
        for field,value in [('q1',1),('qX','NaN'),('q2','inf'),('stake1',0),('stakeX',True),('stake2',-1)]:
            self.assertEqual(c.post('/calculate-manual',json={**data,field:value}).status_code,400)
        self.assertEqual(c.post('/calculate-manual',json=[]).status_code,400)

    def test_betfair_prefers_explicit_two_goal_market(self):
        early=market(rawName='Resultado – 2 Goles de Ventaja')
        early['selections']=[{**row,'odds':odd} for row,odd in zip(early['selections'],(2.0,3.1,3.3))]
        event={'markets':[market(),early]}
        self.assertEqual(a.extract_match_result(event,'A','B',True),{'1':2.0,'X':3.1,'2':3.3})
        self.assertEqual(event['_1x2_kind'],'TWO_GOAL_EARLY_PAYOUT')
        self.assertEqual(a.extract_match_result(event,'A','B'),{'1':2.1,'X':3.2,'2':3.4})
        self.assertNotIn('_1x2_kind',event)
        for changes in ({'period':'FIRST_HALF'},{'isActive':False},{'selections':early['selections'][:2]},{'canonicalMarket':'HANDICAP'}):
            self.assertEqual(a.extract_match_result({'markets':[market(),{**early,**changes}]},'A','B',True),{'1':2.1,'X':3.2,'2':3.4})

    def test_market_regular_time(self):
        self.assertEqual(a.extract_match_result({"markets": [market()]}, "A", "B"), {"1": 2.1, "X": 3.2, "2": 3.4})

    def test_observed_bet365_full_time_not_second_half(self):
        # Values observed in one authenticated event response, without secrets.
        half = market(period="SECOND_HALF", rawName="2nd Half Result")
        full = market()
        for selection, value in zip(half["selections"], (6.5, 3.2, 1.5333)):
            selection["odds"] = value
        for selection, value in zip(full["selections"], (8, 6, 1.3)):
            selection["odds"] = value
        self.assertEqual(a.extract_match_result({"markets":[half, full]}, "Croatia", "Spain"), {"1":8, "X":6, "2":1.3})

    def test_reject_wrong_markets(self):
        for changes in ({"period": "FIRST_HALF"}, {"rawName": "First Half Result"}, {"canonicalMarket": "HANDICAP"},
                        {"isActive": False}, {"period": "", "rawName": "Unknown"}):
            self.assertIsNone(a.extract_match_result({"markets": [market(**changes)]}, "A", "B"))

    def test_reject_invalid_selection(self):
        for value in (float("nan"), float("inf"), 1, 0, -2):
            m = market()
            m["selections"][0]["odds"] = value
            self.assertIsNone(a.extract_match_result({"markets": [m]}, "A", "B"))
        m = market()
        m["selections"][0]["isActive"] = False
        self.assertIsNone(a.extract_match_result({"markets": [m]}, "A", "B"))

    def test_competitions(self):
        for league,country,expected in [
            ('La Liga','Guatemala',None),('Guatemala||La Liga','',None),
            ('LaLiga','Guatemala',None),('La Liga (Guatemala)','',None),
            ('Liga Nacional de Guatemala','Guatemala',None),
            ('La Liga','Spain','laliga'),('Spain||LaLiga','', 'laliga'),
            ('España / LaLiga EA Sports','', 'laliga'),('LaLiga EA Sports','', 'laliga'),
            ('La Liga','',None),('LaLiga','', 'laliga'),
            ('Spain||La Liga','Guatemala',None),
            ('Segunda División','Guatemala',None),('Segunda División','Spain','segunda'),
            ('LaLiga Hypermotion','', 'segunda')]:
            with self.subTest(league=league,country=country):
                self.assertEqual(a.classify_league(q(league=league,country=country)),expected)
        for league, country, expected in [("LaLiga", "Spain", "laliga"), ("UEFA Champions League", "", "ucl"),
                ("England Premier League", "", "premier"), ("Serie A", "Italy", "seriea"), ("Bundesliga", "Germany", "bundesliga"),
                ("Ligue 1", "France", "ligue1"), ("Primeira Liga", "Portugal", "primeira"), ("Eredivisie", "Netherlands", "eredivisie"),
                ("Indian Shillong Premier League", "", None), ("World Cup Qualification", "", "internationals"),
                ("Champions League Qualification", "", "ucl"), ("AFC Champions League", "Asia", None),
                ("Bundesliga", "Austria", None), ("2. Bundesliga", "Germany", None), ("UEFA Europa League", "", "uel")]:
            with self.subTest(league=league):
                self.assertEqual(a.classify_league(q(league=league, country=country)), expected)

    def test_reject_youth_virtual(self):
        for home in ("Spain U-21", "Spain Sub 19", "Spain Women", "Spain SRL"):
            self.assertIsNone(a.classify_league(q(home=home)))

    def test_merge_aliases(self):
        groups = a.group_quotes({"bet365": [q()], "winamax_es": [q("winamax_es", "España", "Croacia")],
                                 "betfair_sb": [q("betfair_sb")]}, {"internationals"}, 72)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].quotes), 3)

    def test_reject_false_matches(self):
        for home, away, minutes in [("Northern Ireland", "Croatia", 60), ("Spain", "Croatia", 180), ("Croatia", "Spain", 60)]:
            groups = a.group_quotes({"bet365": [q()], "winamax_es": [q("winamax_es", home, away, minutes=minutes)]}, {"internationals"}, 72)
            self.assertEqual(len(groups), 2)

    def test_hour_difference_visible_but_cross_blocked(self):
        quotes = {"bet365":[q(minutes=120)], "winamax_es":[q("winamax_es")], "betfair_sb":[q("betfair_sb")]}
        groups = a.group_quotes(quotes, {"internationals"}, 72)
        self.assertEqual(len(groups), 1)
        self.assertTrue(a.group_time_conflict(groups[0]))
        coverage = a.coverage_rows(groups)
        self.assertTrue(coverage[0]["books"]["bet365"]["has_quote"])
        self.assertTrue(coverage[0]["time_warning"])
        self.assertEqual(a.build_crosses(groups, 10, 100), [])

    def test_expired_odds_still_visible_with_reason(self):
        quote = q()
        quote.received_at -= timedelta(minutes=301)
        group = a.MatchGroup("Spain", "Croatia", "Nations League", "", quote.start, "internationals", {"bet365":quote})
        book = a.coverage_rows([group])[0]["books"]["bet365"]
        self.assertTrue(book["has_quote"])
        self.assertFalse(book["available"])
        self.assertTrue(book["reason"])
        self.assertEqual(book["odds"]["1"], 2.1)

    def test_stale_no_cross(self):
        quotes = {s: q(s) for s in ('bet365','winamax_es','betfair_sb')}
        quotes["bet365"].updated = (datetime.now(timezone.utc)-timedelta(minutes=301)).isoformat()
        g = a.MatchGroup("Spain", "Croatia", "Nations League", "", q().start, "internationals", quotes)
        self.assertEqual(a.build_crosses([g], 10, 100), [])

    def test_six_distinct_assignments(self):
        g = a.MatchGroup("Spain", "Croatia", "Nations League", "", q().start, "internationals", {s:q(s) for s in ('bet365','winamax_es','betfair_sb')})
        rows = a.build_crosses([g], 10, 100)
        self.assertEqual(len(rows[0]["alternatives"]), 6)
        for alt in rows[0]["alternatives"]:
            self.assertEqual(len({alt["source1"], alt["sourceX"], alt["source2"]}), 3)

    def test_optimizer_against_exhaustive(self):
        for odds in itertools.product((1.1, 2, 3.5, 8), repeat=3):
            base = .10
            result = a.optimized_stakes(base, *odds)
            brute = max(min(base*odds[0], x/100*odds[1], y/100*odds[2]) - base - x/100 - y/100
                        for x in range(1, 82) for y in range(1, 82))
            self.assertAlmostEqual(result["score"], brute, places=8)

    def test_four_books_choose_three_and_ignore_stale_fourth(self):
        quotes={s:q(s) for s in ('bet365','winamax_es','betfair_sb','sportium')}
        g=a.MatchGroup('Spain','Croatia','Nations League','',q().start,'internationals',quotes)
        rows=a.build_crosses([g],10,100)
        self.assertEqual(len(rows[0]['alternatives']),24)
        for alt in rows[0]['alternatives']:
            self.assertEqual(len({alt['source1'],alt['sourceX'],alt['source2']}),3)
        quotes['bet365'].updated=(datetime.now(timezone.utc)-timedelta(minutes=301)).isoformat()
        alternatives=a.build_crosses([g],10,100)[0]['alternatives']
        self.assertEqual(len(alternatives),6)
        self.assertTrue(all('bet365' not in (v['source1'],v['sourceX'],v['source2']) for v in alternatives))
        quotes['bet365'].updated=''
        quotes['bet365'].start+=timedelta(hours=1)
        self.assertEqual(len(a.build_crosses([g],10,100)[0]['alternatives']),6)

    def test_five_books_include_retabet_in_sixty_distinct_assignments(self):
        quotes={s:q(s) for s in a.SOURCE_DEFS}
        g=a.MatchGroup('Spain','Croatia','Nations League','',q().start,'internationals',quotes)
        alternatives=a.build_crosses([g],10,100)[0]['alternatives']
        self.assertEqual(len(alternatives),60)
        self.assertTrue(any('retabet' in (v['source1'],v['sourceX'],v['source2']) for v in alternatives))
        self.assertTrue(all(len({v['source1'],v['sourceX'],v['source2']})==3 for v in alternatives))

    def test_sportium_scan_verified_public_only_zero_provider_requests(self):
        a.write_config({'bet365_mode':'browser_auto'})
        target=q('winamax_es','Croacia','España')
        a._last_groups[:]=a.group_quotes({'winamax_es':[target]},{'internationals'},72)
        payload=self.web_payload()
        payload['source_url']='https://www.sportium.es/apuestas/sports/soccer/events/19514722'
        payload['events'][0].update(home='Croacia',away='España',start=target.start.isoformat(),league='Fútbol Internacional / UEFA Nations League')
        payload['private_extra']='must-not-persist'
        with patch.object(a.requests,'get',side_effect=AssertionError('unexpected network')):
            client=a.app.test_client()
            self.assertEqual(client.post('/sportium-scan-observation',json=payload).status_code,200)
            self.assertNotIn('must-not-persist',a.SPORTIUM_BROWSER_PATH.read_text())
            self.assertEqual(a.read_config()['bet365_mode'],'browser_auto')
            self.assertIn('sportium',a._last_groups[0].quotes)
            self.assertEqual(a.read_browser_web('sportium',72)[1]['api_calls'],0)
            self.assertIn(b'"sources": ["sportium"]',client.post('/refresh-sportium').data)
            payload['source_url']='https://example.com/events/19514722'
            self.assertEqual(client.post('/sportium-scan-observation',json=payload).status_code,400)

    def test_sportium_catalogue_quotes_keep_capture_time_and_exact_reference(self):
        a.write_config({'odds_mode':'browser_direct','bet365_mode':'browser_auto','selected_leagues':['ucl'],'hours':48})
        pairs=[('Como','Como 1907','Manchester United','Man. United'),('Lille','Lille OSC','Galatasaray','Galatasaray'),
               ('Bayern Múnich','Bayern M.','Arsenal','Arsenal FC'),('Aston Villa','Aston Villa','Viking','Viking FK'),
               ('Inter Milán','Inter','Shakhtar Donetsk','Shakhtar Donetsk'),('Sporting Portugal','Sporting Lisboa','LASK','LASK Linz'),
               ('Club Brujas','Club Brujas','Lens','RC Lens'),('Real Betis','Betis','Feyenoord','Feyenoord'),
               ('Real Madrid','R. Madrid','RB Leipzig','RB Leipzig')]
        refs=[q('winamax_es',home,away,'Champions League','Europa') for home,_,away,_ in pairs]
        a._last_groups[:]=a.group_quotes({'winamax_es':refs},{'ucl'},48)
        captured=(datetime.now(timezone.utc)-timedelta(seconds=30)).isoformat()
        client=a.app.test_client()
        with patch.object(a.requests,'get',side_effect=AssertionError('unexpected network')):
            for index,((_,home,_,away),ref) in enumerate(zip(pairs,refs)):
                payload={'source_url':f'https://www.sportium.es/apuestas/sports/soccer/events/{1000+index}',
                         'observed_at':captured,'events':[{'event_id':str(1000+index),'home':home,'away':away,
                         'league':'Champions League (Competiciones UEFA (Clubs))','start':ref.start.isoformat(),
                         'market':'FULL_TIME_1X2','odds':{'1':2.15,'X':3.75,'2':3.00}}]}
                self.assertEqual(client.post('/sportium-scan-observation',json=payload).status_code,200)
            quotes,_=a.read_browser_web('sportium',48)
            self.assertEqual(len(quotes),9)
            self.assertTrue(all(quote.updated==captured and quote.odds['X']==3.75 for quote in quotes))
            self.assertTrue(all('sportium' in group.quotes for group in a._last_groups))
            payload['events'][0]['league']='Europa League'
            self.assertEqual(client.post('/sportium-scan-observation',json=payload).status_code,400)
            payload['events'][0]['league']='Champions League (Competiciones UEFA (Clubs))'
            payload['events'][0]['start']=(refs[-1].start+timedelta(hours=1)).isoformat()
            self.assertEqual(client.post('/sportium-scan-observation',json=payload).status_code,400)
            before=a.SPORTIUM_BROWSER_PATH.read_bytes()
            client.post('/stop-update')
            self.assertEqual(client.post('/sportium-scan-observation',json=payload).status_code,409)
            self.assertEqual(a.SPORTIUM_BROWSER_PATH.read_bytes(),before)

    def test_friendlies_aliases_and_sportium_group(self):
        groups=a.group_quotes({'winamax_es':[q('winamax_es','Jordania','Venezuela',league='Partidos amistosos internacionales')],
                              'bet365':[q('bet365','Jordan','Venezuela',league='International Match')],
                              'sportium':[q('sportium','Jordania','Venezuela',league='Amistosos Selecciones')]},{'internationals'},72)
        self.assertEqual(len(groups),1)
        self.assertEqual(len(groups[0].quotes),3)
        for left,right in [('Macedonia N.','Macedonia del Norte'),('Luxembourg','Luxemburgo'),('R. Checa','República Checa'),('Turks and Caicos Islands','Islas Turcas y Caicos'),('Shakhtar','Shakhtar Donetsk'),('AEK de Atenas','AEK Atenas')]:
            self.assertEqual(a.canonical_team(left),a.canonical_team(right))

    def test_missing_targets_skip_only_fresh_matching_source(self):
        target=q('winamax_es','Croacia','España')
        sport=q('sportium','Croacia','España')
        a._last_groups[:]=a.group_quotes({'winamax_es':[target],'sportium':[sport]},{'internationals'},72)
        client=a.app.test_client()
        self.assertEqual(len(client.get('/bet365-targets?missing=1&source=sportium').json['targets']),0)
        self.assertEqual(len(client.get('/bet365-targets?missing=1&source=bet365').json['targets']),1)
        sport.updated=(datetime.now(timezone.utc)-timedelta(minutes=301)).isoformat()
        self.assertEqual(len(client.get('/bet365-targets?missing=1&source=sportium').json['targets']),1)

    def test_rate_cache_and_restart(self):
        response = a.requests.Response()
        response.status_code = 200
        response._content = b'{"events": [], "hasNextPage": false}'
        with patch.object(a.requests, "get", return_value=response) as get:
            trace = []
            a._throttled_get("bet365", "test-secret", page=1, limit=30, trace=trace)
            a._throttled_get("bet365", "test-secret", page=1, limit=30, trace=trace)
            self.assertEqual(get.call_count, 1)
            a._page_cache.clear()
            with self.assertRaises(a.PulseScoreError):
                a._throttled_get("bet365", "test-secret", page=1, limit=30, trace=trace)
            self.assertEqual(get.call_count, 1)

    def test_429_secret_not_echoed(self):
        r = a.requests.Response()
        r.status_code = 429
        r._content = b'{"error":"test-secret"}'
        r.headers["Retry-After"] = "120"
        with patch.object(a.requests, "get", return_value=r) as get:
            trace = []
            a._throttled_get("bet365", "test-secret", page=1, limit=30, trace=trace)
            with self.assertRaises(a.PulseScoreError):
                a._throttled_get("bet365", "test-secret", page=2, limit=30, trace=trace)
            self.assertEqual(get.call_count, 1)
            self.assertNotIn("test-secret", json.dumps(trace)+a.safe_error(r))

    def test_network_check_handled(self):
        with patch.object(a, "get_api_key", return_value="test-secret"), patch.object(a.requests, "get", side_effect=a.requests.ConnectionError("test-secret")):
            response = a.app.test_client().post("/check-api")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(b"test-secret", response.data)

    def test_mock_update_and_diagnostic(self):
        with patch.object(a, "get_api_key", return_value="test-secret"), patch.object(a, "fetch_source", side_effect=lambda s, *args: ([q(s)], {"raw_events":1, "with_1x2":1})):
            client = a.app.test_client()
            self.assertEqual(client.post("/update").status_code, 200)
            self.assertIn(b"Spain", client.get("/").data)
            diagnostic = a.LAST_DIAG_PATH.read_text()
            self.assertNotIn("test-secret", diagnostic)
            self.assertEqual(json.loads(diagnostic)["summary"]["with_three"], 1)

    def test_full_update_reuses_pages(self):
        start = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        event = {"eventId":"e1", "home":"Spain", "away":"Croatia", "league":"UEFA Nations League", "startTime":start,
                 "live":False, "slug":"/match/e1", "markets":[market()]}
        r = a.requests.Response()
        r.status_code = 200
        r._content = json.dumps({"events":[event], "hasNextPage":False}).encode()
        with patch.object(a, "get_api_key", return_value="test-secret"), patch.object(a.requests, "get", return_value=r) as get:
            c = a.app.test_client()
            self.assertEqual(c.post("/update").status_code, 200)
            self.assertEqual(get.call_count, 3)
            diag = json.loads(a.LAST_DIAG_PATH.read_text())
            self.assertEqual(diag["summary"]["with_three"], 1)
            self.assertEqual(diag["summary"]["api_calls"], 3)
            self.assertEqual(c.post("/update").status_code, 200)
            self.assertEqual(get.call_count, 3)
            self.assertEqual(json.loads(a.LAST_DIAG_PATH.read_text())["summary"]["api_calls"], 0)

    def test_expired_cached_page_waits_before_request(self):
        a.write_config({'api_plan':'BASIC'})
        clock=[1000.0]
        event={'eventId':'1','home':'Spain','away':'Croatia','league':'UEFA Nations League',
               'startTime':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'markets':[market()]}
        first=a.requests.Response();first.status_code=200
        first._content=json.dumps({'events':[event],'hasNextPage':True}).encode()
        second=a.requests.Response();second.status_code=200
        second._content=json.dumps({'events':[{**event,'eventId':'2'}],'hasNextPage':False}).encode()
        a._page_cache[('winamax_es',2,a.PAGE_LIMIT)]=(0,second)
        def advance(delay):clock[0]+=delay
        with patch.object(a.time,'time',side_effect=lambda:clock[0]),patch.object(a.time,'sleep',side_effect=advance) as sleep,patch.object(a.requests,'get',side_effect=[first,second]) as get:
            quotes,stats=a.fetch_source('winamax_es','test-secret',72)
        self.assertEqual(len(quotes),2)
        self.assertEqual(get.call_count,2)
        self.assertAlmostEqual(sum(call.args[0] for call in sleep.call_args_list),a.MIN_SECONDS_PER_BOOKMAKER)
        self.assertTrue(all(call.args[0]<=.25 for call in sleep.call_args_list))

    def test_guatemala_does_not_enter_spanish_groups_or_targets(self):
        spanish=q('winamax_es','Valencia','Levante','Spain||LaLiga')
        foreign=q('winamax_es','Antigua','Municipal','Guatemala||La Liga')
        groups=a.group_quotes({'winamax_es':[spanish,foreign]},{'laliga'},72)
        self.assertEqual(len(groups),1)
        self.assertEqual(groups[0].home,'Valencia')
        a._last_groups[:]=groups
        self.assertEqual(len(a.app.test_client().get('/bet365-targets').json['targets']),1)

    def test_horizon_stops_pagination(self):
        event = {"home":"A", "away":"B", "startTime":(datetime.now(timezone.utc)+timedelta(hours=73)).isoformat()}
        r = a.requests.Response()
        r.status_code = 200
        r._content = json.dumps({"events":[event], "hasNextPage":True}).encode()
        with patch.object(a.requests, "get", return_value=r) as get:
            quotes, stats = a.fetch_source("bet365", "test-secret", 72)
            self.assertEqual(get.call_count, 1)
            self.assertEqual(quotes, [])
            self.assertTrue(stats["coverage_complete"])

    def test_schema_error_is_not_empty_success(self):
        r = a.requests.Response()
        r.status_code = 200
        r._content = b'{"unexpected": []}'
        with patch.object(a.requests, "get", return_value=r):
            with self.assertRaises(a.PulseScoreError):
                a.fetch_source("bet365", "test-secret", 72)

    def test_basic_monthly_budget(self):
        a.RATE_STATE_PATH.write_text(json.dumps({"usage_month": datetime.now(timezone.utc).strftime("%Y-%m"), "usage_count":500}))
        with patch.object(a.requests, "get") as get:
            with self.assertRaises(a.PulseScoreError):
                a._throttled_get("bet365", "test-secret", page=1, limit=30, trace=[])
            get.assert_not_called()

    def test_starter_interval(self):
        a.write_config({"api_plan":"STARTER"})
        r = a.requests.Response()
        r.status_code = 200
        with patch.object(a.requests, "get", return_value=r):
            a._throttled_get("bet365", "test-secret", page=1, limit=30, trace=[])
            state = json.loads(a.RATE_STATE_PATH.read_text())
            self.assertGreater(state["bet365"]-a.time.time(), 59)

    def test_old_market_new_event_timestamp(self):
        stale = (datetime.now(timezone.utc)-timedelta(minutes=30)).isoformat()
        event = {"updatedAt": datetime.now(timezone.utc).isoformat(), "markets":[market(updatedAt=stale)]}
        a.extract_match_result(event, "A", "B")
        self.assertEqual(a.find_updated_at(event), stale)

    def test_invalid_settings(self):
        a.CONFIG_PATH.unlink(missing_ok=True)
        c = a.app.test_client()
        for value in ("NaN", "inf", "-1", "invalid"):
            self.assertEqual(c.post("/save-settings", data={"base_stake":value}).status_code, 200)
            self.assertFalse(a.CONFIG_PATH.exists())

    def test_keyring_failure_memory_fallback(self):
        with patch.object(a.keyring, "set_password", side_effect=OSError(1312, "unavailable")), patch.object(a, "_windows_protect", side_effect=OSError(2, "unavailable")):
            message = a.save_api_key("synthetic-storage-test")
            self.assertIn("solo en memoria", message)
            self.assertEqual(a._session_api_key, "synthetic-storage-test")
            self.assertFalse(a.ENCRYPTED_KEY_PATH.exists())

    def test_encrypted_storage_fallback(self):
        def protect(data, *, decrypt=False):
            return b"synthetic-storage-test" if decrypt else b"encrypted-test-data"
        with patch.object(a.keyring, "set_password", side_effect=OSError(1312, "unavailable")), patch.object(a, "_windows_protect", side_effect=protect):
            message = a.save_api_key("synthetic-storage-test")
            self.assertIn("DPAPI", message)
            self.assertEqual(a.ENCRYPTED_KEY_PATH.read_bytes(), b"encrypted-test-data")
            self.assertNotIn(b"synthetic-storage-test", a.ENCRYPTED_KEY_PATH.read_bytes())

    def test_save_route_with_unavailable_windows_storage(self):
        with patch.object(a.keyring, "set_password", side_effect=OSError(1312, "unavailable")), patch.object(a, "_windows_protect", side_effect=OSError(2, "unavailable")):
            response = a.app.test_client().post("/save-settings", data={"api_key":"synthetic-storage-test", "base_stake":"10", "hours":"72", "max_loss":"5"})
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"solo en memoria", response.data)
            self.assertNotIn(b"synthetic-storage-test", response.data)
            self.assertNotIn("synthetic-storage-test", a.CONFIG_PATH.read_text())

    def test_check_reports_actual_safe_cause(self):
        with patch.object(a, "get_api_key", return_value="test-secret"), patch.object(a, "_throttled_get", side_effect=a.PulseScoreError("Winamax ES: pausa activa; vuelve en 60 s.")):
            response = a.app.test_client().post("/check-api")
            self.assertIn(b"pausa activa", response.data)
            self.assertNotIn(b"PulseScoreError", response.data)

    def test_blocked_socket_diagnosis_without_exception_text(self):
        inner = OSError(10013, "test-secret")
        exc = a.requests.ConnectionError(inner)
        label = a.connection_error_label(exc)
        self.assertIn("10013", label)
        self.assertNotIn("test-secret", label)

    def web_payload(self):
        return {"source_url":"https://www.bet365.es/#/AC/B1/C1/D8/E201151094/F3/I1/P30026/H1/", "observed_at":datetime.now(timezone.utc).isoformat(),
                "events":[{"event_id":"201151094", "home":"Croacia", "away":"España", "league":"UEFA Nations League - Liga A",
                           "start":q().start.isoformat(), "market":"FULL_TIME_1X2", "odds":{"1":8.5,"X":6.25,"2":1.27}}]}

    def test_web_bet365_bypasses_pulsescore(self):
        a.write_config({"bet365_mode":"web"})
        a.BET365_BROWSER_PATH.write_text(json.dumps(self.web_payload()))
        with patch.object(a.requests,"get",side_effect=AssertionError("No API call expected")):
            quotes,meta=a.fetch_source("bet365","test-secret",72)
            self.assertEqual(quotes[0].odds,{"1":8.5,"X":6.25,"2":1.27})
            self.assertEqual(meta["api_calls"],0)
            self.assertIn("Web Bet365",quotes[0].origin)

    def test_expired_web_no_wrong_api_fallback(self):
        a.write_config({"bet365_mode":"web"})
        payload=self.web_payload()
        payload["observed_at"]=(datetime.now(timezone.utc)-timedelta(minutes=301)).isoformat()
        a.BET365_BROWSER_PATH.write_text(json.dumps(payload))
        with patch.object(a.requests,"get",side_effect=AssertionError("No API fallback")):
            with self.assertRaises(a.PulseScoreError): a.fetch_source("bet365","test-secret",72)

    def test_web_import_recalculates_real_three_book_assignment(self):
        win=q("winamax_es","Croacia","España")
        bf=q("betfair_sb","Croatia","Spain")
        win.odds={"1":8.5,"X":6.25,"2":1.26}
        bf.odds={"1":10.5,"X":6.,"2":1.25}
        a._last_groups[:]=a.group_quotes({"winamax_es":[win],"betfair_sb":[bf]}, {"internationals"},72)
        with patch.object(a.requests,"get",side_effect=AssertionError("No network on import")):
            response=a.app.test_client().post("/bet365-import",data={"payload":json.dumps(self.web_payload())},follow_redirects=True)
            self.assertEqual(response.status_code,200)
            self.assertIn(b"8.50 / 6.25 / 1.27",response.data)
            self.assertFalse(a.group_time_conflict(a._last_groups[0]))
            self.assertTrue(a._last_result["rows"])

    def test_import_enhanced_keeps_normal_and_whitelists_prices(self):
        payload=self.web_payload()
        payload['events'][0]['enhanced_odds']={'1':8.75,'X':6.5,'2':1.3,'private':'synthetic-ignore'}
        with patch.object(a.requests,'get',side_effect=AssertionError('No network')):
            response=a.app.test_client().post('/bet365-import',json=payload)
            self.assertEqual(response.status_code,200)
            stored=json.loads(a.BET365_BROWSER_PATH.read_text(encoding='utf-8'))['events'][0]
            self.assertEqual(stored['enhanced_odds'],{'1':8.75,'X':6.5,'2':1.3})
            self.assertNotIn('synthetic-ignore',a.BET365_BROWSER_PATH.read_text(encoding='utf-8'))
            quotes,_=a.read_browser_web('bet365',72)
            self.assertEqual(quotes[0].odds,payload['events'][0]['odds'])
            self.assertEqual(quotes[0].enhanced_odds,stored['enhanced_odds'])
            payload['events'][0]['enhanced_odds']['X']=None
            self.assertEqual(a.app.test_client().post('/bet365-import',json=payload).status_code,400)

    def test_web_import_invalid_origin_and_markets(self):
        for invalid in ("origin","market","odds"):
            payload=self.web_payload()
            if invalid=="origin": payload["source_url"]="https://example.com"
            if invalid=="market": payload["events"][0]["market"]="FIRST_HALF"
            if invalid=="odds": payload["events"][0]["odds"]["X"]=None
            response=a.app.test_client().post("/bet365-import",data={"payload":json.dumps(payload)})
            self.assertEqual(response.status_code,400)
            self.assertFalse(a.BET365_BROWSER_PATH.exists())

    def test_quote_cache_preserves_capture_age(self):
        quote=q()
        quote.received_at-=timedelta(minutes=301)
        a._last_groups[:]=[a.MatchGroup("Spain","Croatia","UEFA Nations League","",quote.start,"internationals",{"bet365":quote})]
        a.save_quote_cache()
        a._last_groups.clear()
        a.restore_quote_cache()
        self.assertFalse(a.quote_is_fresh(a._last_groups[0].quotes["bet365"]))

    def test_observed_international_aliases_join_betfair(self):
        for spanish,english in [('Kazajistán','Kazakhstan'),('Islas Feroe','Faroe Islands'),('Moldavia','Moldova'),('República Checa','Czechia'),('Suiza','Switzerland'),('Macedonia del Norte','North Macedonia'),('Bielorrusia','Belarus'),('Arabia Saudí','Saudi Arabia')]:
            self.assertEqual(a.canonical_team(spanish),a.canonical_team(english))
        win=q('winamax_es','Moldavia','Eslovaquia')
        bf=q('betfair_sb','Moldova','Slovakia')
        groups=a.group_quotes({'winamax_es':[win],'betfair_sb':[bf]}, {'internationals'},72)
        self.assertEqual(len(groups),1)
        self.assertEqual(len(groups[0].quotes),2)

    def test_auto_reader_strict_search_matching(self):
        from bet365_auto import matching_indices
        target=q('winamax_es','Croacia','España')
        self.assertEqual(matching_indices(['Croacia sub-21 v España sub-21','Croacia v España','España v Croacia'],target,a.canonical_team),[1])

    def test_auto_reader_validates_event_without_provider_key(self):
        payload=self.web_payload()
        target=q('winamax_es','Croacia','España')
        def collect(targets,canonical,validate):
            self.assertTrue(validate(payload,target))
            wrong=json.loads(json.dumps(payload));wrong['events'][0]['start']=(target.start+timedelta(hours=1)).isoformat()
            self.assertFalse(validate(wrong,target))
            wrong=json.loads(json.dumps(payload));wrong['events'][0]['away']='España sub-21'
            self.assertFalse(validate(wrong,target))
            return [payload],[]
        with patch('bet365_auto.collect',side_effect=collect),patch.object(a.requests,'get',side_effect=AssertionError('No provider requests')):
            quotes,meta=a.fetch_bet365_auto([target,target],72)
            self.assertEqual(meta['targets'],1)
            self.assertEqual(meta['api_calls'],0)
            self.assertEqual(quotes[0].odds['1'],8.5)

    def test_auto_blocked_has_no_wrong_fallback(self):
        from bet365_auto import ReadBlocked
        with patch('bet365_auto.collect',side_effect=ReadBlocked('Bet365 ES: HTTP 403')),patch.object(a.requests,'get',side_effect=AssertionError('No fallback')):
            with self.assertRaisesRegex(a.PulseScoreError,'HTTP 403'):
                a.fetch_bet365_auto([q('winamax_es')],72)

    def test_browser_automatic_targets_contain_only_public_data(self):
        target=q('winamax_es','Croacia','España')
        a._last_groups[:]=a.group_quotes({'winamax_es':[target]}, {'internationals'},72)
        with patch.object(a,'get_api_key',return_value='test-secret'):
            response=a.app.test_client().get('/bet365-targets')
            self.assertNotIn(b'test-secret',response.data)
            self.assertEqual(response.json['targets'][0]['canonical_home'],'croacia')

    def test_browser_scan_validates_and_keeps_automatic_mode(self):
        a.write_config({'bet365_mode':'browser_auto'})
        target=q('winamax_es','Croacia','España')
        a._last_groups[:]=a.group_quotes({'winamax_es':[target]}, {'internationals'},72)
        a._last_result['stats']={'api_calls':12,'sources':{}}
        with patch.object(a.requests,'get',side_effect=AssertionError('No API requests on scan')):
            client=a.app.test_client()
            wrong=self.web_payload();wrong['events'][0]['start']=(target.start+timedelta(hours=1)).isoformat()
            self.assertEqual(client.post('/bet365-scan-observation',json=wrong).status_code,400)
            self.assertEqual(client.post('/bet365-scan-observation',json=self.web_payload()).status_code,200)
            self.assertEqual(a.read_config()['bet365_mode'],'browser_auto')
            self.assertEqual(a._last_result['stats']['api_calls'],12)
            self.assertEqual(client.post('/refresh-bet365').status_code,200)
            self.assertEqual(a._last_result['stats']['api_calls'],0)

    def test_browser_mode_update_never_queries_provider_bet365(self):
        a.write_config({'bet365_mode':'browser_auto'})
        target=q('winamax_es','Croacia','España')
        def source(name,*args):
            self.assertNotEqual(name,'bet365')
            return ([target] if name=='winamax_es' else []), {'api_calls':0,'with_1x2':1}
        with patch.object(a,'get_api_key',return_value='test-secret'),patch.object(a,'fetch_source',side_effect=source):
            response=a.app.test_client().post('/update')
            self.assertEqual(response.status_code,200)
            self.assertIn(b'cruces-automatic-bet365',response.data)
            self.assertNotIn(b'test-secret',response.data)

    def test_specific_browser_search_filters_one_match(self):
        a.write_config({'bet365_mode':'browser_auto'})
        targets=[q('winamax_es','Croacia','España'),q('winamax_es','Moldavia','Eslovaquia')]
        a._last_groups[:]=a.group_quotes({'winamax_es':targets},{'internationals'},72)
        client=a.app.test_client()
        result=client.get('/bet365-targets',query_string={'home':'Croatia','away':'Spain'}).json
        self.assertEqual(len(result['targets']),1)
        self.assertEqual(result['targets'][0]['home'],'Croacia')
        page=client.post('/refresh-bet365',data={'home':'Croacia','away':'España'}).data
        self.assertIn(b'detail:{"away":',page)
        self.assertIn(b'"home": "Croacia"',page)

    def test_scan_progress_and_failure_redact_credentials(self):
        client=a.app.test_client()
        with patch.object(a,'get_api_key',return_value='test-secret'):
            result=client.post('/bet365-scan-status',json={'running':True,'total':1,'processed':0,'current':'Croacia','last_error':'test-secret'}).json
            self.assertEqual(result['last_error'],'[REDACTED]')
            response=client.post('/bet365-scan-complete',json={'captured':0,'failures':['test-secret']})
            self.assertEqual(response.status_code,200)
            self.assertNotIn('test-secret',a.SCAN_RESULT_PATH.read_text())
            self.assertFalse(client.get('/bet365-scan-status').json['running'])


if __name__ == "__main__":
    unittest.main()
