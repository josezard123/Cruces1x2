import unittest,tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import app as a

class DirectTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
  self.patches=[patch.object(a,'CONFIG_PATH',root/'cfg.json'),patch.object(a,'QUOTE_CACHE_PATH',root/'quotes.json'),patch.object(a,'restore_quote_cache'),patch.object(a,'_last_groups',[]),patch.object(a,'_last_result',{}),patch.object(a,'_scan_status',{}),patch.object(a,'_browser_results',{}),patch.object(a,'get_api_key',return_value=None),patch.object(a.requests,'get',side_effect=AssertionError('No PulseScore'))]
  for p in self.patches:p.start()
  a.write_config(dict(a.read_config(),odds_mode='browser_direct',selected_leagues=['laliga'],hours=168))
  a._update_cancel.clear();self.client=a.app.test_client();self.start=datetime.now(timezone.utc)+timedelta(hours=48)
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def payload(self,source='winamax_es'):
  url='https://www.winamax.es/apuestas-deportivas/match/123' if source=='winamax_es' else 'https://www.betfair.es/apuestas/f%C3%BAtbol/la-liga-espa%C3%B1ola/valencia-levante/e-123'
  return dict(observed_at=datetime.now(timezone.utc).isoformat(),events=[dict(event_id='123',home='Valencia',away='Levante',league='LaLiga',country='España',start=self.start.isoformat(),odds={'1':2.1,'X':3.2,'2':3.4},market='FULL_TIME_1X2',payout='normal',source_url=url)])
 def test_update_needs_no_api_key_and_calls_no_api(self):
  response=self.client.post('/update');self.assertEqual(response.status_code,200)
  self.assertIn(b'winamax_es',response.data);self.assertIn(b'betfair_sb',response.data)
  self.assertEqual(a._last_result['stats']['api_calls'],0)
 def test_scan_progress_timestamps_and_clean_ui(self):
  self.client.post('/bet365-scan-status',json=dict(source='betfair_sb',running=True,current='Descubriendo',processed=0,total=0))
  self.assertIn('last_seen_at',self.client.get('/bet365-scan-status').json)
  with patch.object(a.time,'time',return_value=a._scan_status['last_seen_at']+130):
   status=self.client.get('/bet365-scan-status').json
   self.assertTrue(status['stale']);self.assertGreaterEqual(status['phase_elapsed_seconds'],130)
  html=self.client.get('/').data.decode()
  self.assertIn('scan-progress',html)
  self.assertNotIn('Actualizar solo lectores',html);self.assertNotIn('se ha confirmado una discrepancia',html)
 def test_real_two_sources_join_and_whitelist(self):
  p=self.payload();p['secret']='synthetic-ignore';p['events'][0]['secret']='synthetic-ignore'
  self.assertEqual(self.client.post('/direct-observation/winamax_es',json=p).json['captured'],1)
  p=self.payload('betfair_sb');p['events'][0]['payout']='two_goals'
  self.assertEqual(self.client.post('/direct-observation/betfair_sb',json=p).json['captured'],1)
  self.assertEqual(len(a._last_groups),1);self.assertEqual(len(a._last_groups[0].quotes),2)
  self.assertIn('2 goles de ventaja',a._last_groups[0].quotes['betfair_sb'].origin)
  self.assertNotIn('synthetic-ignore',a.QUOTE_CACHE_PATH.read_text(encoding='utf-8'))
 def test_rejects_bad_origin_market_time_and_duplicates(self):
  for field,value in [('source_url','https://evil.example/123'),('source_url','https://www.winamax.es/apuestas-deportivas/match/123?key=synthetic'),('market','FIRST_HALF'),('odds',{'1':2,'X':float('nan'),'2':3}),('odds',{'1':True,'X':3,'2':4}),('start','bad')]:
   p=self.payload();p['events'][0][field]=value
   self.assertEqual(self.client.post('/direct-observation/winamax_es',json=p).status_code,400)
  p=self.payload();p['events']*=2;self.assertEqual(self.client.post('/direct-observation/winamax_es',json=p).status_code,400)
  p=self.payload();p['observed_at']=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
  self.assertEqual(self.client.post('/direct-observation/winamax_es',json=p).status_code,400)
 def test_partial_keeps_previous_and_cancellation(self):
  self.client.post('/direct-observation/winamax_es',json=self.payload())
  self.assertEqual(self.client.post('/direct-observation/winamax_es',json=dict(observed_at=datetime.now(timezone.utc).isoformat(),events=[])).status_code,200)
  self.assertEqual(len(a._last_groups),1)
  a._update_cancel.set();self.assertEqual(self.client.post('/direct-observation/winamax_es',json=self.payload()).status_code,409)
  a._update_cancel.clear()
 def test_foreign_league_excluded(self):
  p=self.payload();p['events'][0]['country']='Guatemala'
  self.assertEqual(self.client.post('/direct-observation/winamax_es',json=p).json['captured'],0)
  self.assertEqual(a._last_groups,[])
 def test_sportsbook_requires_two_goal_market(self):
  p=self.payload('betfair_sb')
  self.assertEqual(self.client.post('/direct-observation/betfair_sb',json=p).status_code,400)
  self.assertEqual(a._last_groups,[])
if __name__=='__main__':unittest.main()
