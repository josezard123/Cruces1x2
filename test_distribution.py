import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import app
import installer
import updater
from runtime_paths import VERSION

class DistributionTests(unittest.TestCase):
    def test_club_variants_keep_age_groups_separate(self):
        for left,right in [('Bodø/Glimt','Bodo/Glimt'),('AS Roma','Roma'),('LASK Linz','LASK'),('Oporto','FC Porto'),('Stuttgart','VfB Stuttgart'),('AEK','AEK Atenas'),('Como 1907','Como'),('B. Dortmund','Borussia Dortmund')]:
            self.assertEqual(app.canonical_team(left),app.canonical_team(right))
        self.assertNotEqual(app.canonical_team('AS Roma U19'),app.canonical_team('Roma'))

    def release(self):
        return {'tag_name':'v4.4.0','assets':[{'name':'Cruces-Setup-4.4.0.exe','size':3,
            'browser_download_url':'https://github.com/josezard123/Cruces1x2/releases/download/v4.4.0/Cruces-Setup-4.4.0.exe',
            'digest':'sha256:'+hashlib.sha256(b'new').hexdigest()}]}

    def test_release_validation(self):
        self.assertTrue(updater.release_info('josezard123/Cruces1x2',self.release())['available'])
        for mutation in ('digest','url','size','duplicate','prerelease'):
            value=self.release()
            if mutation=='digest':value['assets'][0]['digest']=None
            if mutation=='url':value['assets'][0]['browser_download_url']='https://evil.example/installer.exe'
            if mutation=='size':value['assets'][0]['size']=updater.MAX_INSTALLER_BYTES+1
            if mutation=='duplicate':value['assets']*=2
            if mutation=='prerelease':value['prerelease']=True
            with self.assertRaises((ValueError,TypeError)):updater.release_info('josezard123/Cruces1x2',value)

    def test_origin_required(self):
        client=app.app.test_client()
        for origin in (None,'https://evil.example'):
            headers={'Origin':origin} if origin else {}
            self.assertEqual(client.post('/app-updates/install',json={},headers=headers).status_code,403)
        self.assertEqual(client.post('/app-updates/install',json={},headers={'Origin':'http://127.0.0.1:8802'}).status_code,409)

    def test_download_hash(self):
        info=updater.release_info('josezard123/Cruces1x2',self.release())
        response=Mock(status_code=200);response.iter_content.return_value=[b'new']
        with tempfile.TemporaryDirectory() as folder,patch('updater.requests.get',return_value=response):
            self.assertEqual(updater.download_installer(info,folder).read_bytes(),b'new')
            response.iter_content.return_value=[b'bad']
            with self.assertRaises(ValueError):updater.download_installer(info,folder)
            self.assertEqual((Path(folder)/'Cruces-Setup-4.4.0.exe').read_bytes(),b'new')
            self.assertFalse(list(Path(folder).glob('*.part')))

    def test_bad_redirect(self):
        info=updater.release_info('josezard123/Cruces1x2',self.release())
        response=Mock(status_code=302,headers={'Location':'http://evil.example/installer.exe'})
        with tempfile.TemporaryDirectory() as folder,patch('updater.requests.get',return_value=response):
            with self.assertRaises(ValueError):updater.download_installer(info,folder)

    def test_installer_preserves_data_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'installed';payload=Path(folder)/'payload';payload.mkdir()
            data=root/'datos';data.mkdir(parents=True);(data/'config.json').write_text('KEEP')
            (payload/'Cruces.exe').write_bytes(b'first');(payload/'Cruces.sha256').write_text(hashlib.sha256(b'first').hexdigest())
            target=installer.install(payload,root);self.assertEqual(target.read_bytes(),b'first')
            (payload/'Cruces.exe').write_bytes(b'next');(payload/'Cruces.sha256').write_text(hashlib.sha256(b'next').hexdigest())
            installer.install(payload,root);self.assertEqual(target.read_bytes(),b'next')
            self.assertEqual((target.parent/'Cruces.anterior.exe').read_bytes(),b'first')
            self.assertEqual((data/'config.json').read_text(),'KEEP')
            (payload/'Cruces.exe').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):installer.install(payload,root)
            self.assertEqual(target.read_bytes(),b'next')

    def test_update_ui_and_resources(self):
        client=app.app.test_client()
        for page in ('/','/freebets'):
            response=client.get(page);self.assertEqual(response.status_code,200)
            self.assertIn(b'app-update-check',response.data)
        self.assertEqual(client.get('/static/app_updates.js').status_code,200)
        self.assertEqual(client.get('/app-version').json['version'],VERSION)

if __name__=='__main__':unittest.main()
