"""Exercise the real installer and real EXE with isolated disposable data."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
from runtime_paths import VERSION

root = Path(__file__).resolve().parent
installed = root / 'distribucion' / 'prueba_instalada'
data = installed / 'datos'
data.mkdir(parents=True, exist_ok=True)
config = {'odds_mode':'browser_direct', 'bet365_mode':'browser_auto', 'base_stake':17.25, 'hours':48}
(data / 'config.json').write_text(json.dumps(config), encoding='utf-8')
(data / 'conservar.txt').write_text('datos de prueba que deben sobrevivir', encoding='utf-8')
setup = root / 'distribucion' / 'salida' / f'Cruces-Setup-{VERSION}.exe'
for _ in range(2):
    subprocess.run([str(setup), '--test-root', str(installed), '--no-launch'], check=True, timeout=45)
    assert json.loads((data/'config.json').read_text()) == config
    assert (data/'conservar.txt').read_text() == 'datos de prueba que deben sobrevivir'
assert (installed/'programa'/'Cruces.anterior.exe').exists()
with socket.socket() as sock:
    if sock.connect_ex(('127.0.0.1',8804)) == 0:
        raise RuntimeError('El puerto de prueba ya está ocupado.')
environment = dict(os.environ, CRUCES_INSTALL_ROOT=str(installed), CRUCES_DATA_DIR=str(data))
process = subprocess.Popen([str(installed/'programa'/'Cruces.exe'),'--port','8804','--no-browser','--smoke-test'],
                           cwd=installed, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
deadline = time.monotonic()+20
while time.monotonic()<deadline:
    try:
        with urllib.request.urlopen('http://127.0.0.1:8804/app-version',timeout=1) as response:
            version=json.load(response)
        break
    except OSError:
        time.sleep(.25)
else:
    raise RuntimeError('El ejecutable no inició su servidor.')
assert version == {'application':'Cruces','version':VERSION,'packaged':True}
for path in ('/','/freebets','/static/app_updates.js','/bet365-extension','/bet365-extension.zip','/demo'):
    with urllib.request.urlopen('http://127.0.0.1:8804'+path,timeout=5) as response:
        assert response.status==200
        body=response.read()
        if path=='/':
            assert b'data-cruces-installed="1"' in body and b'17.25' in body
        if path=='/bet365-extension':
            assert str(installed/'lector').encode() in body
assert (installed/'lector'/'manifest.json').exists()
assert json.loads((data/'config.json').read_text()) == config
process.wait(timeout=40)
with socket.socket() as sock:
    assert sock.connect_ex(('127.0.0.1',8804)) != 0
print('EXE real: instalación, segunda instalación, conservación de ajustes, Cruces, Freebets, demo y lector comprobados. Servidor de prueba cerrado.')
