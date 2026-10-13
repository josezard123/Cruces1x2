"""Build only whitelisted resources, never configuration, caches or keys."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from runtime_paths import VERSION

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / 'distribucion'

def freeze(entry, name, resources):
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
               '--name', name, '--distpath', str(BUILD / 'salida'), '--workpath', str(BUILD / 'compilacion' / name),
               '--specpath', str(BUILD / 'especificaciones'), '--exclude-module', 'playwright', '--exclude-module', 'pytest']
    for source, target in resources:
        command += ['--add-data', f'{source};{target}']
    subprocess.run(command + [str(ROOT / entry)], cwd=ROOT, check=True)

def main():
    BUILD.mkdir(exist_ok=True)
    resources = [(ROOT / folder, folder) for folder in ('templates', 'static', 'bet365_extension')]
    resources += [(ROOT / name, '.') for name in ('bet365_reader.js', 'bet365_extension.zip', 'release_channel.json')]
    freeze('desktop.py', 'Cruces', resources)
    payload = BUILD / 'payload'
    payload.mkdir(exist_ok=True)
    binary = (BUILD / 'salida' / 'Cruces.exe').read_bytes()
    (payload / 'Cruces.exe').write_bytes(binary)
    (payload / 'Cruces.sha256').write_text(hashlib.sha256(binary).hexdigest(), encoding='ascii')
    name = f'Cruces-Setup-{VERSION}'
    freeze('installer.py', name, [(payload, 'payload')])
    destination = BUILD / 'salida' / f'{name}.exe'
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.sha256').write_text(digest + '  ' + destination.name, encoding='ascii')
    with zipfile.ZipFile(BUILD / 'salida' / f'Cruces-Lector-{VERSION}.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in (ROOT / 'bet365_extension').iterdir():
            if file.is_file():
                archive.write(file, file.name)
    print('Instalador creado y hash calculado:', destination)

if __name__ == '__main__':
    main()
