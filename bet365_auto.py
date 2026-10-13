"""Public Bet365 ES search and visible full-time odds. No provider credentials."""
from pathlib import Path
import json
import time


class ReadBlocked(Exception):
    pass


def matching_indices(names, target, canonical):
    return [i for i,name in enumerate(names) if len(parts:=name.split(' v '))==2
            and canonical(parts[0])==canonical(target.home)
            and canonical(parts[1])==canonical(target.away)]


def collect(targets, canonical, validate, max_seconds=180):
    status_path=Path(__file__).with_name('bet365_auto_status.json')
    try:
        last=json.loads(status_path.read_text(encoding='utf-8'))
        if last.get('http_status') in (403,429) and time.time()-last.get('observed_at',status_path.stat().st_mtime)<300:
            raise ReadBlocked(f"Bet365 ES: pausa tras HTTP {last['http_status']}; no se repite la consulta durante cinco minutos.")
    except (OSError,ValueError,TypeError):
        pass
    from playwright.sync_api import sync_playwright, Error
    reader=Path(__file__).with_name('bet365_reader.js').read_text(encoding='utf-8')
    observations=[]
    failures=[]
    started=time.monotonic()
    with sync_playwright() as p:
        # Separate temporary context: no user profile, login, cookies or key.
        browser=p.chromium.launch(channel='msedge',headless=True)
        try:
            context=browser.new_context(locale='es-ES',timezone_id='Europe/Madrid')
            page=context.new_page()
            page.set_default_timeout(15000)
            response=page.goto('https://www.bet365.es/#/AX/',wait_until='domcontentloaded')
            if response and response.status in (403,429):
                status_path.write_text(json.dumps({'stage':'search_load','http_status':response.status,'observed_at':time.time()}),encoding='utf-8')
                raise ReadBlocked(f'Bet365 ES: HTTP {response.status} al navegador automático. Lectura detenida sin reintentos; no se obtuvieron cuotas.')
            try:
                page.get_by_role('textbox').wait_for()
            except Error:
                text=page.locator('body').inner_text()
                status={'stage':'search_load','http_status':response.status if response else None,
                        'body_characters':len(text),'has_search':page.get_by_role('textbox').count()>0,
                        'has_challenge':any(word in text.lower() for word in ('captcha','access denied','verify you are human','acceso denegado')),
                        'has_logo':page.get_by_role('button',name='bet365 Logo',exact=True).count()>0}
                Path(__file__).with_name('bet365_auto_status.json').write_text(json.dumps(status),encoding='utf-8')
                raise
            cookie=page.get_by_role('button',name='Solo esenciales',exact=True)
            if cookie.count(): cookie.click()
            for target in targets:
                if time.monotonic()-started>max_seconds:
                    failures.append('Tiempo máximo de lectura alcanzado; cobertura parcial.')
                    break
                try:
                    if '/AX/' not in page.url:
                        page.goto('https://www.bet365.es/#/AX/',wait_until='domcontentloaded')
                    page.get_by_role('textbox').fill(canonical(target.home))
                    # Wait for the ordinary search UI, not private requests.
                    page.wait_for_timeout(1800)
                    names=page.locator('.ssr-e5').all_inner_texts()
                    indices=matching_indices(names,target,canonical)
                    if len(indices)!=1:
                        failures.append(f'{target.home} — {target.away}: búsqueda sin coincidencia única.')
                        continue
                    page.locator('.ssr-e5').nth(indices[0]).click()
                    page.locator('[role="main"] .rrb-63').first.wait_for()
                    observation=page.evaluate('() => {'+reader+';return readBet365Result();}')
                    if validate(observation,target): observations.append(observation)
                    else: failures.append(f'{target.home} — {target.away}: fecha o competición distinta; excluido.')
                except Error:
                    failures.append(f'{target.home} — {target.away}: no se pudo leer el mercado visible.')
                # Modest serial navigation; never retry a failed event in a loop.
                page.wait_for_timeout(1200)
        finally:
            browser.close()
    return observations, failures
