import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import reader_diagnostics as diagnostics

class PublicDiagnosticTests(unittest.TestCase):
    def sample(self):
        return dict(schema=1, reader_version='2.0.5', source='bet365', phase='event',
                    target={'home': 'LASK', 'away': 'Liverpool'}, event_id='123',
                    counts={k: 0 for k in diagnostics.COUNTS},
                    nodes=[{'kind': 'date', 'text': '14 oct 18:45', 'path': []}],
                    competitions=[], rows=[], cards=[])

    def test_local_capture_and_retention_do_not_change_odds(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(diagnostics, 'DIAGNOSTIC_PATH', Path(directory)/'diagnostic.json'):
            before=list(app._last_groups)
            client=app.app.test_client()
            value=self.sample()
            for number in range(30):
                value['target']['home']='Equipo '+str(number)
                self.assertEqual(client.post('/reader-diagnostic',json=value).status_code,200)
            records=json.loads(diagnostics.DIAGNOSTIC_PATH.read_text(encoding='utf-8'))
            self.assertEqual(len(records),24)
            self.assertEqual(records[-1]['target']['home'],'Equipo 29')
            self.assertEqual(list(app._last_groups),before)
            self.assertEqual(client.post('/reader-diagnostic',json=value).json['api_calls'],0)
            records=json.loads(diagnostics.DIAGNOSTIC_PATH.read_text(encoding='utf-8'))
            self.assertEqual(len(records),24)

    def test_no_page_dumps_credentials_or_private_labels(self):
        for field in ('html','cookies','password','account','input_values','api_key','response_body'):
            value=self.sample();value[field]='PRIVATE'
            with self.assertRaises(ValueError):diagnostics.validate(value)
        for text in ('persona@example.com','Saldo 1200','password: PRIVATE','api_key PRIVATE','10€','<input value=secret>'):
            value=self.sample();value['nodes'][0]['text']=text
            with self.assertRaises(ValueError):diagnostics.validate(value)

    def test_boundaries_and_remote_origin(self):
        client=app.app.test_client()
        self.assertEqual(client.post('/reader-diagnostic',json=self.sample(),headers={'Origin':'https://example.com'}).status_code,403)
        self.assertEqual(client.post('/reader-diagnostic',json=self.sample(),environ_base={'REMOTE_ADDR':'192.168.1.2'}).status_code,403)
        value=self.sample();value['nodes']*=41
        with self.assertRaises(ValueError):diagnostics.validate(value)
        value=self.sample();value['competitions']=[{'name':'Champions League','path':'https://example.com/c-123?token=secret'}]
        with self.assertRaises(ValueError):diagnostics.validate(value)
        self.assertEqual(client.post('/reader-diagnostic',data='{}',content_type='text/plain').status_code,400)

if __name__=='__main__':unittest.main()
