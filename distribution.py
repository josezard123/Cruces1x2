"""Explicit, integrity-checked updates for the installed local application."""
import os
import subprocess
import threading
import time
from flask import Blueprint, request
from runtime_paths import VERSION, PACKAGED
import updater

bp = Blueprint('distribution', __name__)
_lock = threading.Lock()
_checked_at = 0
_state = {'version': VERSION, 'checking': False, 'available': False, 'message': ''}
_release = None

def register(application):
    application.register_blueprint(bp)
    application.context_processor(lambda: {'distribution_version': VERSION, 'distribution_installed': PACKAGED})

def local_action():
    return request.remote_addr in ('127.0.0.1', '::1') and request.headers.get('Origin') in ('http://127.0.0.1:8802', 'http://localhost:8802') and request.is_json

def check_worker():
    global _release, _checked_at
    try:
        repo = updater.channel()
        if not repo:
            _state.update(message='Falta configurar el repositorio de actualizaciones.', available=False)
            return
        _release = updater.check_release(repo)
        _state.update(available=_release['available'], latest=_release['version'],
                      message=f'Nueva versión {_release["version"]} disponible.' if _release['available'] else 'Tienes la última versión.')
    except Exception:
        _release = None
        _state.update(available=False, message='No se pudo comprobar la versión. Puedes seguir usando la app.')
    finally:
        _checked_at = time.monotonic()
        _state.update(checking=False)
        _lock.release()

@bp.get('/app-version')
def version():
    return {'application': 'Cruces', 'version': VERSION, 'packaged': PACKAGED}

@bp.get('/app-updates')
def state():
    return dict(_state, packaged=PACKAGED, repository=updater.channel())

@bp.post('/app-updates/check')
def check():
    if not local_action():
        return {'ok': False}, 403
    if _checked_at and time.monotonic() - _checked_at < 900:
        return dict(_state, ok=True)
    if _lock.acquire(blocking=False):
        _state.update(checking=True, message='Comprobando versión…')
        threading.Thread(target=check_worker, daemon=True).start()
    return dict(_state, ok=True)

@bp.post('/app-updates/install')
def install():
    if not local_action():
        return {'ok': False}, 403
    if not PACKAGED:
        return {'ok': False, 'message': 'Esta copia de desarrollo se actualiza desde el código; el botón funciona en la app instalada.'}, 409
    if not _release or not _release['available'] or not _lock.acquire(blocking=False):
        return {'ok': False, 'message': 'Comprueba la versión o espera a que termine la descarga.'}, 409
    info = dict(_release)
    _state.update(installing=True, message='Descargando y verificando el instalador…')
    def worker():
        try:
            path = updater.download_installer(info)
            subprocess.Popen([str(path), '--update', '--parent-pid', str(os.getpid())], creationflags=subprocess.CREATE_NO_WINDOW)
            _state.update(message='Instalador verificado. La app se reiniciará; recarga esta página en unos segundos.')
            threading.Timer(2, lambda: os._exit(0)).start()
        except Exception:
            _state.update(installing=False, message='No se pudo instalar. La versión actual y tus datos se conservan.')
        finally:
            _lock.release()
    threading.Thread(target=worker, daemon=True).start()
    return {'ok': True}
