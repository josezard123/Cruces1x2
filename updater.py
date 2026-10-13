"""Public GitHub release metadata; never reads credentials or odds caches."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import requests
from runtime_paths import RESOURCE_DIR, VERSION, data_dir

MAX_INSTALLER_BYTES = 200 * 1024 * 1024

def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value or '')
    if not match:
        raise ValueError('Versión no válida.')
    return tuple(map(int, match.groups()))

def repository(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', value or ''):
        raise ValueError('Introduce usuario/repositorio de GitHub.')
    return value

def channel():
    path = data_dir() / 'actualizaciones.json'
    if not path.exists():
        path = RESOURCE_DIR / 'release_channel.json'
    try:
        return repository(json.loads(path.read_text(encoding='utf-8')).get('repository'))
    except (OSError, ValueError, TypeError):
        return None

def release_info(repo, payload):
    repository(repo)
    if payload.get('draft') or payload.get('prerelease'):
        raise ValueError('La publicación no es una versión estable.')
    tag = payload.get('tag_name', '')
    parts = version_tuple(tag)
    name = f'Cruces-Setup-{".".join(map(str, parts))}.exe'
    assets = [a for a in payload.get('assets', []) if a.get('name') == name]
    if len(assets) != 1:
        raise ValueError('La versión no incluye un instalador único.')
    asset = assets[0]
    url = asset.get('browser_download_url', '')
    expected = f'https://github.com/{repo}/releases/download/{tag}/{name}'
    digest = asset.get('digest', '')
    if url != expected or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('No se puede verificar el instalador de esta publicación.')
    size = asset.get('size')
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_INSTALLER_BYTES:
        raise ValueError('Tamaño de instalador no válido.')
    return {'version': '.'.join(map(str, parts)), 'url': url, 'sha256': digest[7:], 'size': size,
            'available': parts > version_tuple(VERSION), 'page': f'https://github.com/{repo}/releases/tag/{tag}'}

def check_release(repo):
    repository(repo)
    response = requests.get(f'https://api.github.com/repos/{repo}/releases/latest',
                            headers={'Accept': 'application/vnd.github+json'}, timeout=(5, 15))
    response.raise_for_status()
    return release_info(repo, response.json())

def download_installer(info, directory=None):
    directory = Path(directory) if directory else data_dir() / 'actualizaciones'
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f'Cruces-Setup-{info["version"]}.exe'
    temporary = destination.with_suffix('.part')
    url = info['url']
    allowed = {'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}
    response = None
    try:
        for _ in range(6):
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.username or parsed.password:
                raise ValueError('Origen de descarga no permitido.')
            response = requests.get(url, stream=True, allow_redirects=False, timeout=(5, 30))
            if response.status_code in (301, 302, 303, 307, 308):
                url = response.headers.get('Location', '')
                response.close()
                continue
            response.raise_for_status()
            break
        else:
            raise ValueError('Demasiadas redirecciones.')
        digest = hashlib.sha256()
        size = 0
        with temporary.open('wb') as output:
            for block in response.iter_content(65536):
                size += len(block)
                if size > info['size'] or size > MAX_INSTALLER_BYTES:
                    raise ValueError('Descarga de tamaño inesperado.')
                digest.update(block)
                output.write(block)
        if size != info['size'] or digest.hexdigest() != info['sha256']:
            raise ValueError('El instalador no coincide con la publicación; no se ejecutará.')
        temporary.replace(destination)
        return destination
    finally:
        if response is not None:
            response.close()
        temporary.unlink(missing_ok=True)
