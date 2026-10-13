"""Windows executable entry point: resources and data live separately."""
import argparse
import json
import logging
import os
import shutil
import threading
import urllib.request
import webbrowser
from runtime_paths import RESOURCE_DIR, data_dir, extension_dir

def prepare():
    destination = extension_dir()
    destination.mkdir(parents=True, exist_ok=True)
    for source in list((RESOURCE_DIR / 'bet365_extension').iterdir()):
        if source.is_file():
            target = destination / source.name
            temp = target.with_suffix(target.suffix + '.new')
            shutil.copyfile(source, temp)
            temp.replace(target)
    config = data_dir() / 'config.json'
    if not config.exists():
        config.write_text(json.dumps({'odds_mode': 'browser_direct', 'bet365_mode': 'browser_auto'}), encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8802)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--smoke-test', action='store_true')
    args = parser.parse_args()
    prepare()
    import app
    url = f'http://127.0.0.1:{args.port}'
    try:
        with urllib.request.urlopen(url + '/app-version', timeout=1) as response:
            existing = json.load(response)
        if existing.get('application') == 'Cruces':
            if not args.no_browser:
                webbrowser.open(url)
            return
    except Exception:
        pass
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    if args.smoke_test:
        threading.Timer(30, lambda: os._exit(0)).start()
    logging.getLogger('werkzeug').disabled = True
    app.app.run(host='127.0.0.1', port=args.port, debug=False, threaded=True)

if __name__ == '__main__':
    main()
