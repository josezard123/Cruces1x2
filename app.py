from __future__ import annotations

import itertools
import ctypes
from ctypes import wintypes
import json
import math
import re
import threading
import time
import unicodedata
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, quote
from email.utils import parsedate_to_datetime

import requests
from flask import Flask, redirect, render_template, request, url_for, send_file

try:
    import keyring
except Exception:
    keyring = None

from runtime_paths import RESOURCE_DIR, PACKAGED, data_dir, extension_dir
APP_DIR = data_dir()
CONFIG_PATH = APP_DIR / "config.json"
KEY_FALLBACK_PATH = APP_DIR / ".pulsescore_key"
ENCRYPTED_KEY_PATH = APP_DIR / ".pulsescore_key.dpapi"
BET365_BROWSER_PATH = APP_DIR / "bet365_web.json"
SPORTIUM_BROWSER_PATH = APP_DIR / "sportium_web.json"
_web_import_lock = threading.Lock()
QUOTE_CACHE_PATH = APP_DIR / "quote_cache.json"
SCAN_RESULT_PATH = APP_DIR / 'bet365_scan_result.json'
_session_api_key: str | None = None
SERVICE = "CrucesApuestasPulseScore"
KEY_USER = "pulsescore"
PORT = 8802
API_ROOT = "https://api.pulsescore.net/api"

SOURCE_DEFS: dict[str, dict[str, str]] = {
    "bet365": {
        "label": "Bet365",
        "endpoint": f"{API_ROOT}/v3/bet365/soccer/events",
        "site": "https://www.bet365.es",
    },
    "winamax_es": {
        "label": "Winamax ES",
        "endpoint": f"{API_ROOT}/winamax-es/soccer/events",
        "site": "https://www.winamax.es",
    },
    "betfair_sb": {
        "label": "Betfair Sportsbook",
        "endpoint": f"{API_ROOT}/betfair-sb/soccer/events",
        "site": "https://www.betfair.es",
    },
    "sportium": {"label":"Sportium ES", "site":"https://www.sportium.es", "endpoint":""},
}

LEAGUES: dict[str, str] = {
    "laliga": "LaLiga (España)",
    "segunda": "Segunda División",
    "premier": "Premier League",
    "seriea": "Serie A",
    "bundesliga": "Bundesliga",
    "ligue1": "Ligue 1",
    "primeira": "Primeira Liga",
    "eredivisie": "Eredivisie",
    "ucl": "Champions League",
    "uel": "Europa League",
    "uecl": "Conference League",
    "copadelrey": "Copa del Rey",
    "internationals": "Selecciones absolutas",
}

DEFAULT_LEAGUES = [
    "laliga", "segunda", "premier", "seriea", "bundesliga", "ligue1",
    "primeira", "eredivisie", "ucl", "uel", "uecl", "copadelrey", "internationals",
]

NATIONAL_EXCLUDES = (
    "srl", "simulated", "simulation", "virtual", "esoccer", "e-soccer", "esports", "e-sports",
    "women", "woman", "female", "femen", "feminin", "u17", "u-17", "u18", "u-18", "u19", "u-19",
    "u20", "u-20", "u21", "u-21", "u22", "u-22", "u23", "u-23", "youth", "juvenil", "olympic",
    "futsal", "beach", "reserve", "reserves", "club friendly", "club friendlies", "amistosos clubes",
)
NATIONAL_POSITIVE = (
    "nations league", "liga de naciones", "world cup", "copa del mundo", "world championship",
    "uefa euro", "euro qualification", "euro qualifiers", "european championship", "international friendly",
    "international friendlies", "international match", "friendly international", "amistosos internacionales", "amistoso internacional", "amistosos selecciones",
    "copa america", "africa cup of nations", "afcon", "asian cup", "gold cup", "concacaf nations",
    "world cup qualification", "world cup qualifier", "clasificacion mundial", "clasificación mundial",
    "eurocopa", "qualifier", "qualification", "copa del golfo", "gulf cup",
)

TEAM_ALIASES = {
    "malaga c f":"malaga", "malaga cf":"malaga",
    "r madrid":"real madrid", "r sociedad":"real sociedad", "ath bilbao":"athletic club", "r santander":"racing santander", "sevilla":"sevilla",
    "spain": "espana", "espana": "espana",
    "croatia": "croacia", "croacia": "croacia",
    "germany": "alemania", "alemania": "alemania",
    "france": "francia", "francia": "francia",
    "italy": "italia", "italia": "italia",
    "england": "inglaterra", "inglaterra": "inglaterra",
    "netherlands": "paises bajos", "holland": "paises bajos", "paises bajos": "paises bajos",
    "belgium": "belgica", "belgica": "belgica",
    "switzerland": "suiza", "suiza": "suiza",
    "poland": "polonia", "polonia": "polonia",
    "denmark": "dinamarca", "dinamarca": "dinamarca",
    "sweden": "suecia", "suecia": "suecia",
    "norway": "noruega", "noruega": "noruega",
    "finland": "finlandia", "finlandia": "finlandia",
    "turkey": "turquia", "turkiye": "turquia", "turquia": "turquia",
    "greece": "grecia", "grecia": "grecia",
    "czechia": "chequia", "czech republic": "chequia", "chequia": "chequia",
    "slovakia": "eslovaquia", "eslovaquia": "eslovaquia",
    "slovenia": "eslovenia", "eslovenia": "eslovenia",
    "romania": "rumania", "rumania": "rumania",
    "hungary": "hungria", "hungria": "hungria",
    "ukraine": "ucrania", "ucrania": "ucrania",
    "ireland": "irlanda", "irlanda": "irlanda",
    "northern ireland": "irlanda del norte", "irlanda del norte": "irlanda del norte",
    "scotland": "escocia", "escocia": "escocia", "wales": "gales", "gales": "gales",
    "iceland": "islandia", "islandia": "islandia",
    "south korea": "corea del sur", "korea republic": "corea del sur", "corea del sur": "corea del sur",
    "japan": "japon", "japon": "japon",
    "brazil": "brasil", "brasil": "brasil",
    "united states": "estados unidos", "usa": "estados unidos", "estados unidos": "estados unidos",
    "morocco": "marruecos", "marruecos": "marruecos",
    "algeria": "argelia", "argelia": "argelia",
    "egypt": "egipto", "egipto": "egipto", "tunisia": "tunez", "tunez": "tunez",
    "saudi arabia": "arabia saudita", "arabia saudita": "arabia saudita",
    "united arab emirates": "emiratos arabes unidos", "uae": "emiratos arabes unidos",
    "emiratos arabes unidos": "emiratos arabes unidos",
    "new zealand": "nueva zelanda", "nueva zelanda": "nueva zelanda",
    # Frequent club variants
    "bod glimt": "bodo glimt", "lask linz": "lask", "as roma": "roma",
    "oporto": "porto", "b munich": "bayern munchen", "leipzig": "rb leipzig",
    "stuttgart": "vfb stuttgart", "aek": "aek atenas",
    "como 1907": "como", "b dortmund": "dortmund",
    "man utd": "manchester united", "manchester utd": "manchester united",
    "man city": "manchester city", "manchester city fc": "manchester city",
    "psg": "paris saint germain", "paris sg": "paris saint germain",
    "inter milan": "inter", "inter milano": "inter",
    "atletico madrid": "atletico de madrid", "atl madrid": "atletico de madrid",
    "athletic bilbao": "athletic club", "athletic club bilbao": "athletic club",
    "athletic de bilbao": "athletic club",
    "deportivo": "deportivo de la coruna", "deportivo de a coruna": "deportivo de la coruna",
    "deportivo la coruna": "deportivo de la coruna", "rc deportivo": "deportivo de la coruna",
    "racing de santander": "racing santander", "racing club de santander": "racing santander",
    "celta de vigo": "celta vigo",
    "rcd espanyol": "espanyol", "espanol": "espanyol",
    "deportivo alaves": "alaves",
    "real betis seville": "real betis", "betis": "real betis",
    "bayern munich": "bayern munchen", "bayern de munich": "bayern munchen",
    "borussia dortmund": "dortmund", "bvb": "dortmund",
    "kazakhstan":"kazajistan", "faroe islands":"islas feroe",
    "moldova":"moldavia", "republica checa":"chequia",
    "switzerland":"suiza", "north macedonia":"macedonia del norte", "macedonia n":"macedonia del norte",
    "belarus":"bielorrusia", "arabia saudi":"arabia saudita",
    "antigua and barbuda":"antigua y barbuda",
    "french guyana":"guayana francesa", "french guiana":"guayana francesa",
    "belize":"belice", "st vincent grenadines":"san vicente y las granadinas",
    "jordan":"jordania", "luxembourg":"luxemburgo", "niger":"niger",
    "mexico":"mexico", "colombia":"colombia", "canada":"canada",
    "turks and caicos islands":"islas turcas y caicos", "turks and caicos":"islas turcas y caicos",
    "us virgin islands":"islas virgenes estadounidenses", "united states of america":"estados unidos",
    "r checa":"chequia", "ee uu":"estados unidos", "arabia saudita":"arabia saudita",
}

app = Flask(__name__, template_folder=str(RESOURCE_DIR / 'templates'), static_folder=str(RESOURCE_DIR / 'static'))
_update_lock = threading.Lock()
_update_cancel = threading.Event()
_update_progress: dict[str, Any] = {}
_request_lock = threading.Lock()
MIN_SECONDS_PER_BOOKMAKER = 1.15
RATE_STATE_PATH = APP_DIR / "rate_state.json"
_page_cache: dict[tuple[str, int, int], tuple[float, Any]] = {}
_last_result: dict[str, Any] = {}
_scan_status: dict[str, Any] = {}
_browser_results: dict[str, Any] = {}
_last_groups: list[Any] = []
DIAG_DIR = APP_DIR / "diagnostico"
DIAG_DIR.mkdir(exist_ok=True)
LAST_DIAG_PATH = DIAG_DIR / "ultimo_diagnostico.json"


class PulseScoreError(RuntimeError):
    pass


class UpdateCancelled(RuntimeError):
    pass


def check_update_cancelled():
    if _update_cancel.is_set():
        raise UpdateCancelled()


def connection_error_label(exc: BaseException) -> str:
    """Inspect exception codes without formatting URLs, headers or messages."""
    pending = [exc]
    seen = set()
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if getattr(node, "winerror", None) == 10013 or getattr(node, "errno", None) == 10013:
            return "Windows bloquea la salida a Internet de este proceso (10013). Abre abrir_app.bat desde el Explorador de Windows."
        pending.extend(x for x in getattr(node, "args", ()) if isinstance(x, BaseException))
        pending.extend(x for x in (getattr(node, "reason", None), getattr(node, "__cause__", None), getattr(node, "__context__", None)) if isinstance(x, BaseException))
    if isinstance(exc, requests.Timeout):
        return "Tiempo de espera agotado al conectar con PulseScore."
    if isinstance(exc, requests.exceptions.SSLError):
        return "No se pudo verificar la conexión TLS con PulseScore."
    return f"Fallo de conexión con PulseScore ({type(exc).__name__})."


@dataclass
class SourceQuote:
    source: str
    label: str
    event_id: str
    home: str
    away: str
    league: str
    country: str
    start: datetime
    odds: dict[str, float]
    slug: str = ""
    updated: str = ""
    direct_url: str = ""
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    origin: str = "PulseScore"


@dataclass
class MatchGroup:
    home: str
    away: str
    league: str
    country: str
    start: datetime
    league_key: str
    quotes: dict[str, SourceQuote] = field(default_factory=dict)


def normalize_text(value: Any) -> str:
    s = str(value or "").lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def canonical_team(value: Any) -> str:
    n = normalize_text(value)
    n = TEAM_ALIASES.get(n, n)
    # Strip harmless club affixes.
    words = [w for w in n.split() if w not in {"fc", "cf", "afc", "sc", "ac", "club", "futbol", "football"}]
    n = " ".join(words).strip()
    return normalize_text(TEAM_ALIASES.get(n, n)).replace(" club", "")


def team_similarity(a: str, b: str) -> float:
    aa, bb = canonical_team(a), canonical_team(b)
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    if aa in bb or bb in aa:
        small = min(len(aa), len(bb))
        large = max(len(aa), len(bb))
        if small >= 5:
            return small / max(1, large)
    sa = set(aa.split())
    sb = set(bb.split())
    jaccard = len(sa & sb) / max(1, len(sa | sb))
    seq = SequenceMatcher(None, aa, bb).ratio()
    return max(seq, jaccard)


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        s = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def local_time_label(dt: datetime) -> str:
    try:
        return dt.astimezone().strftime("%d/%m %H:%M")
    except Exception:
        return dt.strftime("%d/%m %H:%M UTC")


def read_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "base_stake": 10.0,
        "hours": 72,
        "max_loss": 5.0,
        "selected_leagues": DEFAULT_LEAGUES,
        "max_source_age_minutes": 300,
        "api_plan": "BASIC",
        "max_pages": 40,
        "bet365_mode": "browser_auto" if PACKAGED else "pulsescore",
        "odds_mode": "browser_direct" if PACKAGED else "pulsescore",
    }
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update({k: v for k, v in loaded.items() if k in cfg})
        except Exception:
            pass
    selected = [x for x in cfg.get("selected_leagues", []) if x in LEAGUES]
    cfg["selected_leagues"] = selected or DEFAULT_LEAGUES
    return cfg


def write_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _windows_protect(data: bytes, *, decrypt: bool = False) -> bytes:
    """DPAPI encryption bound to the current Windows user; no plaintext file."""
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), buffer)
    result = Blob()
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise OSError(ctypes.get_last_error(), "Windows encryption unavailable")
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(result.data)


def save_api_key(value: str) -> str:
    global _session_api_key
    value = value.strip()
    if not value:
        return ""
    if keyring is not None:
        try:
            keyring.set_password(SERVICE, KEY_USER, value)
            _session_api_key = value
            return "Clave guardada en el almacén de credenciales de Windows."
        except Exception:
            pass
    try:
        encrypted = _windows_protect(value.encode("utf-8"))
        if _windows_protect(encrypted, decrypt=True).decode("utf-8") != value:
            raise ValueError("Encryption verification failed")
        ENCRYPTED_KEY_PATH.write_bytes(encrypted)
        _session_api_key = value
        return "Clave guardada cifrada con Windows DPAPI para este usuario."
    except Exception:
        # Restricted logon sessions can deny both Windows stores. Still allow
        # use without ever persisting the credential in plaintext.
        _session_api_key = value
        return "Clave disponible solo en memoria; deberás introducirla otra vez al reiniciar la aplicación. Windows no permite guardarla en esta sesión."


def get_api_key() -> str | None:
    if _session_api_key:
        return _session_api_key
    if ENCRYPTED_KEY_PATH.exists():
        try:
            return _windows_protect(ENCRYPTED_KEY_PATH.read_bytes(), decrypt=True).decode("utf-8").strip() or None
        except Exception:
            pass
    if keyring is not None:
        try:
            value = keyring.get_password(SERVICE, KEY_USER)
            if value:
                return value.strip()
        except Exception:
            pass
    if KEY_FALLBACK_PATH.exists():
        value = KEY_FALLBACK_PATH.read_text(encoding="utf-8").strip()
        return value or None
    return None


def safe_error(response: requests.Response) -> str:
    # Never echo upstream text: it may contain credentials or request headers.
    return {401: "Credenciales no válidas", 403: "Acceso no permitido por el plan",
            429: "Límite alcanzado; pausa guardada"}.get(response.status_code, "Error del proveedor")


PAGE_LIMIT = 30


def _retry_after_seconds(response: requests.Response, attempt: int) -> float:
    # PulseScore documents Retry-After during the temporary pause. Honour it
    # exactly when present; otherwise use conservative exponential backoff.
    raw = response.headers.get("Retry-After")
    if raw:
        try:
            return max(1.2, float(raw))
        except Exception:
            try:
                return max(1.2, (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
            except Exception:
                pass
    try:
        data = response.json()
        if isinstance(data, dict):
            for key in ("retryAfterSec", "retry_after", "retryAfter"):
                if data.get(key) is not None:
                    return max(1.2, float(data[key]))
    except Exception:
        pass
    return 60.0


def _throttled_get(source: str, api_key: str, *, page: int, limit: int, trace: list[dict[str, Any]]) -> requests.Response:
    cache_key = (source, page, limit)
    with _request_lock:
        cached = _page_cache.get(cache_key)
        if cached and time.time() - cached[0] < 120:
            trace.append({"source": SOURCE_DEFS[source]["label"], "page": page, "cached": True})
            return cached[1]
        cfg = read_config()
        interval = 60.1 if cfg.get("api_plan") in ("UNKNOWN", "STARTER") else MIN_SECONDS_PER_BOOKMAKER
        try:
            state = json.loads(RATE_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        remaining = float(state.get(source, 0)) - time.time()
        if remaining > 0:
            raise PulseScoreError(f"{SOURCE_DEFS[source]['label']}: pausa activa; vuelve en {math.ceil(remaining)} s.")
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        if state.get("usage_month") != month:
            state["usage_month"], state["usage_count"] = month, 0
        if cfg.get("api_plan") == "BASIC" and state.get("usage_count", 0) >= 500:
            raise PulseScoreError("BASIC: se ha alcanzado el presupuesto local de 500 peticiones de este mes.")
        state["usage_count"] = state.get("usage_count", 0) + 1
        # Persist the reservation before sending, including network failures.
        state[source] = time.time() + interval
        RATE_STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
        started = time.monotonic()
        try:
            response = requests.get(SOURCE_DEFS[source]["endpoint"],
                headers={"X-Secret": api_key, "Accept-Encoding": "gzip"},
                params={"page": page, "limit": limit}, timeout=30, allow_redirects=False)
        except requests.RequestException as exc:
            trace.append({"source": SOURCE_DEFS[source]["label"], "page": page,
                          "network_error": type(exc).__name__})
            raise PulseScoreError(f"{SOURCE_DEFS[source]['label']}: {connection_error_label(exc)}") from None
        entry = {"source": SOURCE_DEFS[source]["label"], "page": page,
                 "status": response.status_code, "elapsed_ms": round((time.monotonic()-started)*1000)}
        trace.append(entry)
        if response.status_code == 429:
            delay = max(interval, _retry_after_seconds(response, 0))
            state[source] = time.time() + delay
            entry["backoff_seconds"] = delay
        elif response.status_code == 200:
            _page_cache[cache_key] = (time.time(), response)
        # Honour numeric provider reset headers when quota is exhausted.
        try:
            if float(response.headers.get("X-RateLimit-Remaining", "1")) <= 0:
                reset = float(response.headers.get("X-RateLimit-Reset", "0"))
                if 0 < reset < 1_000_000_000:
                    reset += time.time()
                state[source] = max(state[source], reset)
        except (ValueError, TypeError):
            pass
        RATE_STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
        return response


def fetch_source(source: str, api_key: str, hours: int, trace: list[dict[str, Any]] | None = None) -> tuple[list[SourceQuote], dict[str, Any]]:
    """Fetch chronological prematch pages, cached for two minutes.

    Reservations survive restarts. A 429 stops immediately without retries.
    """
    if source=='sportium': return read_browser_web(source,hours)
    if source == "bet365" and read_config().get("bet365_mode") == "web":
        return read_bet365_web(hours)
    if source == 'bet365' and read_config().get('bet365_mode') in ('auto','browser_auto'):
        raise PulseScoreError('Bet365 automático requiere los partidos de referencia de Winamax; no se consulta PulseScore para Bet365.')
    trace = trace if trace is not None else []
    meta = SOURCE_DEFS[source]
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=max(1, hours))
    quotes: list[SourceQuote] = []
    seen: set[tuple[str, str, str, str]] = set()
    skipped_no_1x2 = 0
    raw_events = 0
    api_calls = 0
    pages = 0
    coverage_complete = True
    last_seen_dt: datetime | None = None
    last_status = 200

    for page in range(1, int(read_config().get("max_pages", 40)) + 1):
        check_update_cancelled()
        _update_progress.update(source=meta['label'], page=page)
        if page > 1:
            # Waiting is required for pagination; repeated user clicks never bypass it.
            try:
                rate_state = json.loads(RATE_STATE_PATH.read_text(encoding="utf-8"))
                delay = max(0, float(rate_state.get(source, 0)) - time.time())
                cached = _page_cache.get((source, page, PAGE_LIMIT))
                if not cached or time.time() - cached[0] >= 120:
                    if delay > 65:
                        raise PulseScoreError(f"{meta['label']}: pausa activa; no se esperan reinicios largos del límite.")
                    # Short waits keep cancellation responsive without changing reservations.
                    while delay > 0:
                        check_update_cancelled()
                        step = min(delay, .25)
                        time.sleep(step)
                        delay -= step
            except (OSError, ValueError):
                pass
        r = _throttled_get(source, api_key, page=page, limit=PAGE_LIMIT, trace=trace)
        check_update_cancelled()
        api_calls += 1
        pages += 1
        last_status = r.status_code
        if r.status_code in (401, 403):
            raise PulseScoreError(f"{meta['label']}: API key no válida o sin acceso.")
        if r.status_code == 429:
            raise PulseScoreError(f"{meta['label']}: límite alcanzado; actualización detenida y pausa guardada.")
        if r.status_code != 200:
            raise PulseScoreError(f"{meta['label']}: HTTP {r.status_code} · {safe_error(r)}")
        try:
            payload = r.json()
        except ValueError as exc:
            raise PulseScoreError(f"{meta['label']}: la respuesta no era JSON válido.") from exc

        events = payload.get("events") if isinstance(payload, dict) else None
        if not isinstance(events, list):
            raise PulseScoreError(f"{meta['label']}: esquema de respuesta inesperado.")
        raw_events += len(events)
        page_last_dt: datetime | None = None

        for event in events:
            if not isinstance(event, dict):
                continue
            start = parse_dt(event.get("startTime") or event.get("startDate") or event.get("date"))
            if not start:
                continue
            page_last_dt = max(page_last_dt, start) if page_last_dt else start
            last_seen_dt = start
            if start <= now or start > horizon or event.get("live") is True:
                continue
            home = str(event.get("home") or event.get("participant1") or "").strip()
            away = str(event.get("away") or event.get("participant2") or "").strip()
            if not home or not away:
                continue
            dedupe = (str(event.get("eventId") or event.get("fi") or event.get("id") or ""), home, away, start.isoformat())
            if dedupe in seen:
                continue
            seen.add(dedupe)
            odds = extract_match_result(event, home, away, prefer_early_payout=source=="betfair_sb")
            if not odds:
                skipped_no_1x2 += 1
                continue
            league = str(event.get("league") or event.get("competition") or event.get("tournamentName") or "").strip()
            country = str(event.get("country") or "").strip()
            event_id = str(event.get("eventId") or event.get("fi") or event.get("id") or "")
            slug = str(event.get("slug") or (event.get("moreInfo") or {}).get("site", "")) if isinstance(event.get("moreInfo") or {}, dict) else str(event.get("slug") or "")
            updated = find_updated_at(event)
            stamp = parse_dt(updated)
            if stamp and (now - stamp).total_seconds() > read_config()["max_source_age_minutes"] * 60:
                continue
            direct = make_direct_url(source, slug)
            origin='PulseScore'
            if source=='betfair_sb':
                origin+=' · Resultado — 2 goles de ventaja' if event.get('_1x2_kind')=='TWO_GOAL_EARLY_PAYOUT' else ' · 1X2 normal; mercado de 2 goles no recibido'
            quotes.append(SourceQuote(source, meta["label"], event_id, home, away, league, country, start, odds, slug, updated, direct, origin=origin))

        has_next = bool(payload.get("hasNextPage")) if isinstance(payload, dict) else False
        if page_last_dt is not None and page_last_dt > horizon:
            break
        if not has_next or not events:
            break
    else:
        coverage_complete = False

    return quotes, {
        "http_status": last_status,
        "raw_events": raw_events,
        "with_1x2": len(quotes),
        "without_1x2": skipped_no_1x2,
        "received_at": datetime.now().astimezone().strftime("%H:%M:%S"),
        "pages": pages,
        "api_calls": sum(1 for t in trace if t.get("source") == meta["label"] and not t.get("cached")),
        "coverage_complete": coverage_complete,
        "last_event": local_time_label(last_seen_dt) if last_seen_dt else "",
    }


def read_bet365_web(hours: int) -> tuple[list[SourceQuote], dict[str, Any]]:
    return read_browser_web('bet365',hours)


def read_browser_web(source: str, hours: int) -> tuple[list[SourceQuote], dict[str, Any]]:
    """Read a timestamped observation of the public Spanish web page.

    This is a snapshot, never a promise of automatic refresh or wider coverage.
    """
    try:
        path=BET365_BROWSER_PATH if source=='bet365' else SPORTIUM_BROWSER_PATH
        label=SOURCE_DEFS[source]['label']
        payload = json.loads(path.read_text(encoding="utf-8"))
        captured = parse_dt(payload.get("observed_at"))
        url = payload.get("source_url", "")
        if not captured or urlparse(url).hostname != urlparse(SOURCE_DEFS[source]['site']).hostname:
            raise ValueError("Invalid origin")
        if not -60 <= (datetime.now(timezone.utc)-captured).total_seconds() <= read_config()["max_source_age_minutes"]*60:
            raise PulseScoreError(f"{label}: lectura web caducada; actualiza el lector para obtener cuotas recientes.")
        quotes = []
        for event in payload.get("events", []):
            event_capture = parse_dt(event.get("observed_at")) or captured
            if not -60 <= (datetime.now(timezone.utc)-event_capture).total_seconds() <= read_config()["max_source_age_minutes"]*60:
                continue
            odds = {k:_to_float(event.get("odds", {}).get(k)) for k in ("1","X","2")}
            start = parse_dt(event.get("start"))
            if not start or not all(odds.values()) or not event.get("home") or not event.get("away") or event.get("market") != "FULL_TIME_1X2":
                raise ValueError("Incomplete result market")
            quote = SourceQuote(source, label, str(event.get("event_id") or "web"), event["home"], event["away"],
                                event.get("league", ""), event.get("country", ""), start, odds,
                                updated=event_capture.isoformat(), direct_url=event.get("source_url",url), received_at=event_capture, origin=f"Web {label} · lectura visible")
            if quote_in_window(quote, hours):
                quotes.append(quote)
        return quotes, {"raw_events":len(payload.get("events", [])), "with_1x2":len(quotes), "without_1x2":0,
                        "received_at":local_time_label(captured), "pages":0, "api_calls":0,
                        "coverage_complete":False, "web_snapshot":True,
                        "note":"Solo partidos de la lectura web importada; no se actualiza sola."}
    except PulseScoreError:
        raise
    except (OSError, ValueError, TypeError, AttributeError):
        raise PulseScoreError(f"{SOURCE_DEFS[source]['label']}: falta una lectura web válida del 1-X-2.") from None


def fetch_bet365_auto(targets, hours):
    from bet365_auto import collect, ReadBlocked
    unique={}
    for target in targets:
        if classify_league(target) in read_config()['selected_leagues'] and quote_in_window(target,hours):
            unique[(canonical_team(target.home),canonical_team(target.away),target.start.isoformat())]=target
    def validate(observation,target):
        event=observation['events'][0]
        start=parse_dt(event.get('start'))
        sample=SourceQuote('bet365','Bet365 ES',event['event_id'],event['home'],event['away'],event['league'],'',start,event['odds'])
        return (start is not None and abs((start-target.start).total_seconds())<=900
                and canonical_team(sample.home)==canonical_team(target.home)
                and canonical_team(sample.away)==canonical_team(target.away)
                and classify_league(sample)==classify_league(target))
    if not unique:
        return [], {'api_calls':0,'raw_events':0,'with_1x2':0,'automatic_web':True,'note':'No hay partidos de referencia de Winamax en el intervalo.'}
    try:
        observations, failures=collect(list(unique.values()),canonical_team,validate)
    except ReadBlocked as exc:
        raise PulseScoreError(str(exc)) from None
    except Exception as exc:
        # Never print browser exceptions or their URLs/headers.
        raise PulseScoreError(f'Bet365 ES: el lector automático no pudo iniciar o acceder a la búsqueda ({type(exc).__name__}). No se han sustituido las cuotas por PulseScore.') from None
    if not observations:
        raise PulseScoreError('Bet365 ES: la búsqueda automática no obtuvo ningún 1-X-2 verificable. '+(failures[0] if failures else 'La web no devolvió el mercado.'))
    payload={'source_url':observations[-1]['source_url'],'observed_at':observations[-1]['observed_at'],'events':[]}
    for observation in observations:
        for event in observation['events']:
            payload['events'].append(dict(event,observed_at=observation['observed_at'],source_url=observation['source_url']))
    BET365_BROWSER_PATH.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    quotes,meta=read_bet365_web(hours)
    meta.update(automatic_web=True,web_snapshot=False,coverage_complete=not failures,failures=failures,targets=len(unique),note='Búsqueda automática en Bet365 ES usando partidos de Winamax; solo coincidencias verificadas.')
    return quotes,meta


def collect_event_dicts(payload: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen_nodes: set[int] = set()
    seen_keys: set[tuple[str, str, str, str]] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            oid = id(node)
            if oid in seen_nodes:
                return
            seen_nodes.add(oid)
            home = node.get("home")
            away = node.get("away")
            start = node.get("startTime") or node.get("startDate")
            has_markets = isinstance(node.get("markets"), list) or isinstance(node.get("mg"), list)
            if home and away and start and has_markets:
                key = (str(node.get("eventId") or node.get("fi") or node.get("id") or ""), str(home), str(away), str(start))
                if key not in seen_keys:
                    seen_keys.add(key)
                    found.append(node)
            for val in node.values():
                if isinstance(val, (dict, list)):
                    walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


def _to_float(value: Any) -> float | None:
    try:
        f = float(str(value).replace(",", "."))
        if math.isfinite(f) and 1.0 < f <= 1000:
            return f
    except Exception:
        pass
    return None


EARLY_PAYOUT_NAMES={'resultado 2 goles de ventaja','resultado del partido 2 goles de ventaja',
                    'match result 2 goal lead','match result 2 goals ahead'}


def extract_match_result(event: dict[str, Any], home: str, away: str, prefer_early_payout: bool=False) -> dict[str, float] | None:
    event.pop('_1x2_kind',None)
    event.pop('_1x2_updated',None)
    if prefer_early_payout:
        for market in event.get('markets') or []:
            if not isinstance(market,dict) or normalize_text(market.get('rawName') or market.get('name') or '') not in EARLY_PAYOUT_NAMES:
                continue
            if str(market.get('canonicalMarket') or '').upper() in ('HANDICAP','TOTAL_GOALS','DOUBLE_CHANCE','DRAW_NO_BET'):
                continue
            # The exact public market title identifies 2-goal early payout; keep
            # the normal checks for full time, active selections, teams and prices.
            sample={'markets':[{**market,'canonicalMarket':'MATCH_RESULT','rawName':'Match Result'}]}
            odds=extract_match_result(sample,home,away)
            if odds:
                event['_1x2_kind']='TWO_GOAL_EARLY_PAYOUT'
                if sample.get('_1x2_updated'):event['_1x2_updated']=sample['_1x2_updated']
                return odds
    # Normalized PulseScore schema.
    for market in event.get("markets") or []:
        if not isinstance(market, dict):
            continue
        canonical = str(market.get("canonicalMarket") or "").upper()
        raw = normalize_text(market.get("rawName") or market.get("name") or "")
        if raw in EARLY_PAYOUT_NAMES: continue
        period = str(market.get("period") or "").upper()
        allowed_names = ("match result", "fulltime result", "full time result", "resultado final", "resultado del partido", "match odds", "1x2")
        if canonical and canonical != "MATCH_RESULT":
            continue
        if not canonical and raw not in allowed_names:
            continue
        if period and period not in ("FULL_TIME", "REGULAR_TIME", "MATCH"):
            continue
        if any(x in raw for x in ("half", "parte", "extra", "handicap", "qualif")):
            continue
        if not period and raw not in allowed_names:
            continue
        if market.get("isActive") is False:
            continue
        result: dict[str, float] = {}
        for sel in market.get("selections") or market.get("ma") or []:
            if not isinstance(sel, dict) or sel.get("isActive") is False:
                continue
            outcome = str(sel.get("canonicalOutcome") or "").upper()
            raw_name = str(sel.get("rawName") or sel.get("name") or "")
            odd = _to_float(sel.get("odds") or sel.get("decimal"))
            if odd is None and isinstance(sel.get("pa"), list) and sel["pa"]:
                odd = _to_float((sel["pa"][0] or {}).get("decimal") if isinstance(sel["pa"][0], dict) else None)
            if odd is None:
                continue
            if outcome == "HOME":
                result["1"] = odd
            elif outcome == "DRAW":
                result["X"] = odd
            elif outcome == "AWAY":
                result["2"] = odd
            else:
                rn = normalize_text(raw_name)
                if rn in ("draw", "empate", "x"):
                    result["X"] = odd
                elif rn == "1" or canonical_team(raw_name) == canonical_team(home):
                    result["1"] = odd
                elif rn == "2" or canonical_team(raw_name) == canonical_team(away):
                    result["2"] = odd
        if all(k in result for k in ("1", "X", "2")):
            stamps = [parse_dt(market.get("updatedAt"))]
            stamps.extend(parse_dt(s.get("updatedAt")) for s in market.get("selections", []) if isinstance(s, dict))
            valid = [s for s in stamps if s]
            if valid:
                event["_1x2_updated"] = min(valid).isoformat()
            return result

    # Legacy Bet365-style mg/ma/pa schema.
    for market in event.get("mg") or []:
        if not isinstance(market, dict):
            continue
        name = normalize_text(market.get("name") or market.get("na") or "")
        if name not in ("fulltime result", "full time result", "match result", "resultado final", "1x2") or market.get("isActive") is False:
            continue
        result: dict[str, float] = {}
        for sel in market.get("ma") or []:
            if not isinstance(sel, dict) or sel.get("isActive") is False:
                continue
            rn = str(sel.get("name") or sel.get("na") or "")
            odd = None
            pa = sel.get("pa")
            if isinstance(pa, list) and pa:
                first = pa[0]
                if isinstance(first, dict):
                    odd = _to_float(first.get("decimal") or first.get("odds"))
            odd = odd or _to_float(sel.get("decimal") or sel.get("odds"))
            if odd is None:
                continue
            n = normalize_text(rn)
            if n in ("draw", "empate", "x"):
                result["X"] = odd
            elif n == "1" or canonical_team(rn) == canonical_team(home):
                result["1"] = odd
            elif n == "2" or canonical_team(rn) == canonical_team(away):
                result["2"] = odd
        if all(k in result for k in ("1", "X", "2")):
            return result
    return None


def find_updated_at(event: dict[str, Any]) -> str:
    if event.get("_1x2_updated"):
        return event["_1x2_updated"]
    candidates = [event.get("updatedAt"), event.get("lastSeenAt")]
    settlement = event.get("settlement")
    if isinstance(settlement, dict):
        candidates.append(settlement.get("lastSeenAt"))
    for market in event.get("markets") or []:
        if isinstance(market, dict):
            candidates.append(market.get("updatedAt"))
    for val in candidates:
        dt = parse_dt(val)
        if dt:
            return dt.isoformat()
    return ""


def make_direct_url(source: str, slug: str) -> str:
    if not slug:
        return ""
    if slug.startswith("http://") or slug.startswith("https://"):
        host = urlparse(slug).hostname or ""
        allowed = {"bet365": ("bet365.es", "bet365.com"), "winamax_es": ("winamax.es",), "betfair_sb": ("betfair.es", "betfair.com"), "sportium":("sportium.es",)}[source]
        if not any(host == domain or host.endswith("."+domain) for domain in allowed):
            return ""
        return slug
    base = SOURCE_DEFS[source]["site"]
    if slug.startswith("/"):
        return base + slug
    return base + "/" + slug


def classify_league(q: SourceQuote) -> str | None:
    league = normalize_text(q.league)
    country = normalize_text(q.country)
    if not country and "||" in q.league:
        country = normalize_text(q.league.split("||", 1)[0])
    full = f"{country} {league}".strip()

    # Reject virtual/youth/women first, then identify club UEFA competitions
    # before national-team keywords (otherwise "UEFA Europa" can look like "UEFA Euro").
    full = f"{full} {normalize_text(q.home)} {normalize_text(q.away)}"
    if any(normalize_text(x) in full for x in NATIONAL_EXCLUDES) or re.search(r"\b(?:u|under|sub)\s*\d{2}\b", full):
        return None
    if "champions league" in full and not any(x in full for x in ("afc", "caf", "concacaf", "asia", "africa")):
        return "ucl"
    if "europa league" in full and "conference" not in full:
        return "uel"
    if "conference league" in full:
        return "uecl"
    if any(normalize_text(x) in full for x in NATIONAL_POSITIVE if x not in ("qualifier", "qualification")):
        return "internationals"
    if "copa del rey" in full:
        return "copadelrey"
    # Country takes precedence over a shared name such as Guatemala's "La Liga".
    # Missing country is accepted only for an explicit Spanish label or brand.
    spanish_countries = {'spain','espana','es','esp','spanish'}
    league_country = normalize_text(q.league.split('||',1)[0]) if '||' in q.league else ''
    spanish_context = (not country or country in spanish_countries) and (not league_country or league_country in spanish_countries) and (
        country in spanish_countries or league_country in spanish_countries
        or bool(re.search(r'\b(?:spain|espana|espanola|spanish)\b',league))
        or league in {'laliga','laliga ea sports','la liga ea sports','laliga santander','la liga santander','laliga hypermotion'})
    if spanish_context and ("segunda division" in league or "laliga hypermotion" in league or "la liga 2" in league):
        return "segunda"
    if spanish_context and ("la liga" in league or "laliga" in league or "primera division" in league):
        return "laliga"
    if "premier league" in full and (league == "premier league" and not country or any(x in full for x in ("england", "english", "inglaterra", "united kingdom"))):
        return "premier"
    if re.search(r"(^| )serie a($| )", full) and (league == "serie a" and not country or any(x in full for x in ("italy", "italia", "italian"))):
        return "seriea"
    if "bundesliga" in full and "2 bundesliga" not in full and "2. bundesliga" not in q.league.lower() and (not country and league == "bundesliga" or any(x in full for x in ("germany", "german bundesliga", "alemania", "deutschland"))):
        return "bundesliga"
    if "ligue 1" in full and (not country and league.startswith("ligue 1") or any(x in full for x in ("france", "french ligue", "francia"))):
        return "ligue1"
    if "primeira liga" in full and (not country and league == "primeira liga" or "portugal" in full):
        return "primeira"
    if "eredivisie" in full and (not country and league == "eredivisie" or any(x in full for x in ("netherlands", "paises bajos", "holanda", "dutch eredivisie"))):
        return "eredivisie"
    return None


def quote_in_window(q: SourceQuote, hours: int) -> bool:
    now = datetime.now(timezone.utc)
    return now < q.start <= now + timedelta(hours=hours)


def match_score(q: SourceQuote, g: MatchGroup) -> float:
    delta = abs((q.start - g.start).total_seconds())
    if delta > 15 * 60:
        return 0.0
    hs = team_similarity(q.home, g.home)
    as_ = team_similarity(q.away, g.away)
    if canonical_team(q.home) != canonical_team(g.home) or canonical_team(q.away) != canonical_team(g.away):
        return 0.0
    time_score = max(0.0, 1.0 - delta / (3 * 3600))
    return 0.44 * hs + 0.44 * as_ + 0.12 * time_score


def group_quotes(all_quotes: dict[str, list[SourceQuote]], selected_leagues: set[str], hours: int) -> list[MatchGroup]:
    groups: list[MatchGroup] = []
    # Seed in a stable source order. Using Winamax ES first is useful because it is explicitly the Spanish board.
    order = ["winamax_es", "bet365", "betfair_sb", "sportium"]
    for source in order:
        for q in all_quotes.get(source, []):
            key = classify_league(q)
            if key not in selected_leagues or not quote_in_window(q, hours):
                continue
            best: MatchGroup | None = None
            best_score = 0.0
            for g in groups:
                if g.league_key != key:
                    continue
                score = match_score(q, g)
                if score > best_score:
                    best_score = score
                    best = g
            if best is None:
                # A one-hour feed disagreement can be displayed together,
                # but never used to calculate a cross without matching times.
                candidates = [g for g in groups if g.league_key == key and source not in g.quotes
                              and canonical_team(q.home) == canonical_team(g.home)
                              and canonical_team(q.away) == canonical_team(g.away)
                              and abs(abs((q.start-g.start).total_seconds())-3600) <= 60]
                if len(candidates) == 1:
                    best, best_score = candidates[0], 1.0
            if best is not None and best_score >= 0.78:
                if source in best.quotes:
                    previous = best.quotes[source]
                    # Repeated provider rows must not create a second match or mix odds.
                    if (parse_dt(q.updated) or q.received_at) > (parse_dt(previous.updated) or previous.received_at):
                        best.quotes[source] = q
                    continue
                best.quotes[source] = q
                # Prefer Spanish display names when Winamax is available.
                if source == "winamax_es":
                    best.home, best.away, best.league, best.country, best.start = q.home, q.away, q.league, q.country, q.start
            else:
                groups.append(MatchGroup(q.home, q.away, q.league, q.country, q.start, key, {source: q}))
    groups.sort(key=lambda g: g.start)
    return groups


def money(v: float) -> float:
    return round(v + 1e-9, 2)


def optimized_stakes(base_stake: float, q1: float, qx: float, q2: float) -> dict[str, float]:
    if not all(math.isfinite(v) for v in (base_stake, q1, qx, q2)) or base_stake < .01 or min(q1, qx, q2) <= 1:
        raise ValueError("Importe o cuotas no válidos")
    s1 = money(base_stake)
    target = s1 * q1
    best: dict[str, float] | None = None
    # For a minimum payout t the cheapest stakes are ceil(t/odds) cents.
    # The optimum occurs at a payout breakpoint or the fixed home payout.
    candidates = {min(target, .01 * min(qx, q2)), target}
    for odds in (qx, q2):
        for cents in range(max(1, math.floor(target / odds * 100)-2), math.ceil(target / odds * 100)+1):
            candidates.add(min(target, cents * odds / 100))
    slope = 1 - 1/qx - 1/q2
    lower = min(candidates)
    # Rounding costs less than two cents. This bound excludes breakpoints
    # that cannot beat the initial candidates, while remaining exact.
    initial_profit = max(t - s1 - max(.01, math.ceil(t/qx*100-1e-9)/100) - max(.01, math.ceil(t/q2*100-1e-9)/100) for t in candidates)
    lo, hi = lower, target
    if slope > 1e-12:
        lo = max(lo, (initial_profit+s1)/slope - 1e-8)
    elif slope < -1e-12:
        hi = min(hi, (initial_profit+s1)/slope + 1e-8)
    else:
        # Equal reciprocal sum: the smallest solution gives the same
        # continuous objective; still inspect all rounding breakpoints.
        pass
    for odds in (qx, q2):
        for cents in range(max(1, math.ceil(lo/odds*100-1e-8)), math.floor(hi/odds*100+1e-8)+1):
            candidates.add(min(target, cents * odds / 100))
    for t in sorted(candidates):
            sx = max(.01, math.ceil(t/qx*100-1e-9)/100)
            s2 = max(.01, math.ceil(t/q2*100-1e-9)/100)
            total = s1 + sx + s2
            r1, rx, r2 = s1 * q1, sx * qx, s2 * q2
            worst = min(r1, rx, r2) - total
            spread = max(r1, rx, r2) - min(r1, rx, r2)
            candidate = {
                "stake1": s1, "stakeX": sx, "stake2": s2,
                "return1": money(r1), "returnX": money(rx), "return2": money(r2),
                "total": money(total), "min_return": money(min(r1, rx, r2)),
                "worst_profit": money(worst), "loss": money(max(0.0, -worst)),
                "spread": money(spread),
                "score": worst,
            }
            if best is None or (candidate["score"], -candidate["spread"]) > (best["score"], -best["spread"]):
                best = candidate
    assert best is not None
    return best


def manual_calculation(data: dict[str, Any]) -> dict[str, float]:
    def number(name: str, minimum: float, maximum: float) -> float:
        value=data.get(name)
        if isinstance(value,bool): raise ValueError('Introduce importes y cuotas válidos.')
        try: value=float(str(value).replace(',','.'))
        except (ValueError,TypeError): raise ValueError('Completa las tres cuotas y los importes.') from None
        if not math.isfinite(value) or not minimum<=value<=maximum:
            raise ValueError('Cuotas: mayores que 1 y hasta 1000. Importes: de 0,01 a 1000 euros.')
        return value
    q1,qx,q2=(number(k,1.000001,1000) for k in ('q1','qX','q2'))
    base=number('stake1',.01,1000)
    if data.get('manual_stakes') is True:
        stakes=[money(base),money(number('stakeX',.01,1000)),money(number('stake2',.01,1000))]
        returns=[money(stake*odd) for stake,odd in zip(stakes,(q1,qx,q2))]
        total=money(sum(stakes))
        result=dict(zip(('stake1','stakeX','stake2'),stakes))
        result.update(dict(zip(('return1','returnX','return2'),returns)))
        result.update(total=total,min_return=min(returns),worst_profit=money(min(returns)-total),loss=money(max(0,total-min(returns))))
    else:
        if base*q1*(1/qx+1/q2)*100>200000:
            raise ValueError('Reduce el importe base o introduce los tres importes manualmente para este cálculo.')
        result=optimized_stakes(base,q1,qx,q2)
    for sign in ('1','X','2'): result['profit'+sign]=money(result['return'+sign]-result['total'])
    result.pop('score',None)
    return result


@app.post('/calculate-manual')
def calculate_manual():
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return {'ok':False,'error':'Introduce cuotas e importes.'},400
    try: return {'ok':True,'result':manual_calculation(data)}
    except ValueError as error: return {'ok':False,'error':str(error)},400


def build_crosses(groups: list[MatchGroup], base_stake: float, max_loss: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for g in groups:
        if len(g.quotes) < 3 or not quote_in_window(next(iter(g.quotes.values())), 168):
            continue
        sources = [source for source,q in g.quotes.items() if quote_is_fresh(q)]
        alternatives: list[dict[str, Any]] = []
        for b1, bx, b2 in itertools.permutations(sources, 3):
            starts=[g.quotes[source].start for source in (b1,bx,b2)]
            if (max(starts)-min(starts)).total_seconds()>900: continue
            q1 = g.quotes[b1].odds["1"]
            qx = g.quotes[bx].odds["X"]
            q2 = g.quotes[b2].odds["2"]
            calc = optimized_stakes(base_stake, q1, qx, q2)
            calc.update({
                "source1": b1, "sourceX": bx, "source2": b2,
                "book1": SOURCE_DEFS[b1]["label"], "bookX": SOURCE_DEFS[bx]["label"], "book2": SOURCE_DEFS[b2]["label"],
                "q1": q1, "qX": qx, "q2": q2,
                "url1": g.quotes[b1].direct_url, "urlX": g.quotes[bx].direct_url, "url2": g.quotes[b2].direct_url,
            })
            alternatives.append(calc)
        alternatives.sort(key=lambda x: (x["score"], -x["spread"]), reverse=True)
        if not alternatives:
            continue
        best = alternatives[0]
        if best["loss"] <= max_loss or best["worst_profit"] >= 0:
            rows.append({
                "home": g.home, "away": g.away, "league": g.league, "league_label": LEAGUES.get(g.league_key, g.league),
                "start_time": local_time_label(g.start), "best": best, "alternatives": alternatives,
            })
    rows.sort(key=lambda r: (-r["best"]["worst_profit"], r["start_time"]))
    return rows


def coverage_rows(groups: list[MatchGroup]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for g in groups:
        books: dict[str, Any] = {}
        for source in SOURCE_DEFS:
            q = g.quotes.get(source)
            books[source] = {
                "available": bool(q) and quote_is_fresh(q),
                "has_quote": bool(q),
                "reason": "" if not q or quote_is_fresh(q) else "Cuota caducada o marca de actualización futura; excluida del cálculo",
                "source_start": local_time_label(q.start) if q else "",
                "received_at": q.received_at.isoformat() if q else "",
                "received_label": local_time_label(q.received_at) if q else "",
                "origin": (q.origin+' · tipo de pago anticipado no verificado' if source=='betfair_sb' and q.origin=='PulseScore' else q.origin) if q else "",
                "odds": q.odds if q else {},
                "updated": q.updated if q else "",
                "url": q.direct_url if q else "",
            }
        rows.append({
            "home": g.home, "away": g.away, "league": g.league,
            "league_label": LEAGUES.get(g.league_key, g.league),
            "start_time": local_time_label(g.start), "books": books,
            "time_warning": "Horarios distintos entre casas: se excluyen las combinaciones con horas incompatibles." if group_time_conflict(g) else "",
        })
    return rows


def group_time_conflict(g: MatchGroup) -> bool:
    starts = [q.start for q in g.quotes.values()]
    return bool(starts) and (max(starts)-min(starts)).total_seconds() > 15*60


def quote_is_fresh(q: SourceQuote) -> bool:
    now = datetime.now(timezone.utc)
    stamp = parse_dt(q.updated) or q.received_at
    return -60 <= (now - stamp).total_seconds() <= read_config()["max_source_age_minutes"] * 60 and (now-q.received_at).total_seconds() <= read_config()["max_source_age_minutes"] * 60


def save_quote_cache() -> None:
    quotes = []
    for group in _last_groups:
        for q in group.quotes.values():
            data = dict(vars(q))
            data["start"] = q.start.isoformat()
            data["received_at"] = q.received_at.isoformat()
            quotes.append(data)
    serialized = json.dumps(quotes, ensure_ascii=False)
    key = get_api_key()
    QUOTE_CACHE_PATH.write_text(serialized.replace(key, "[REDACTED]") if key else serialized, encoding="utf-8")


def restore_quote_cache() -> None:
    if _last_groups:
        return
    if not QUOTE_CACHE_PATH.exists():
        restore_diagnostic_sample()
        return
    try:
        by_source = {s:[] for s in SOURCE_DEFS}
        for data in json.loads(QUOTE_CACHE_PATH.read_text(encoding="utf-8")):
            data["start"] = parse_dt(data["start"])
            data["received_at"] = parse_dt(data["received_at"])
            if data["source"] not in by_source or not data["start"] or not data["received_at"]:
                continue
            by_source[data["source"]].append(SourceQuote(**data))
        cfg = read_config()
        _last_groups[:] = group_quotes(by_source, set(cfg["selected_leagues"]), cfg["hours"])
        if _last_groups:
            _last_result.update(message="Últimas cuotas guardadas; revisa la hora de captura y caducidad.", stats={"sources":{}, "api_calls":0})
    except (OSError, ValueError, KeyError, TypeError):
        return


def restore_diagnostic_sample() -> None:
    """Recover recent inspected odds without refetching the same API pages.

    The old diagnostic is a sample, so its limited coverage stays explicit.
    """
    try:
        diagnostic = json.loads(LAST_DIAG_PATH.read_text(encoding="utf-8"))
        reference = parse_dt(diagnostic.get("generated_at"))
        if not reference or (datetime.now(timezone.utc)-reference).total_seconds() > read_config()['max_source_age_minutes']*60:
            return
        by_source = {s:[] for s in SOURCE_DEFS}
        cfg = read_config()
        for match in diagnostic.get("sample_matches", []):
            for source, book in match.get("books", {}).items():
                if source not in by_source or not book.get("has_quote") or source == "bet365" and cfg["bet365_mode"] == "web":
                    continue
                received = parse_dt(book.get("received_at"))
                label = book.get("source_start") or match["start_time"]
                start = datetime.strptime(f"{reference.astimezone().year}/{label}", "%Y/%d/%m %H:%M").astimezone(timezone.utc)
                if not received:
                    continue
                q = SourceQuote(source, SOURCE_DEFS[source]["label"], "diagnostic-sample", match["home"], match["away"],
                                match["league"], "", start, book["odds"], updated=book.get("updated", ""),
                                received_at=received, origin="PulseScore · diagnóstico (muestra)")
                if quote_is_fresh(q):
                    by_source[source].append(q)
        _last_groups[:] = group_quotes(by_source, set(cfg["selected_leagues"]), cfg["hours"])
        if _last_groups:
            _last_result.update(message="Muestra del diagnóstico reciente recuperada sin peticiones.",
                                warnings=["Cobertura parcial: partidos de la muestra del diagnóstico. Actualizar cuotas obtiene la cobertura completa de Winamax y Betfair."],
                                stats={"sources":{},"api_calls":0})
    except (OSError, ValueError, KeyError, TypeError):
        return


def render_home(**kwargs: Any):
    cfg = read_config()
    credential = get_api_key()
    reader = (RESOURCE_DIR / "bet365_reader.js").read_text(encoding="utf-8")
    bookmarklet = "javascript:" + quote("(()=>{try{" + reader + ";const data=readBet365Result();window.open('http://127.0.0.1:8802/bet365-import#'+encodeURIComponent(JSON.stringify(data)),'_blank')}catch(e){alert(e.message)}})()", safe="")
    html = render_template(
        "index.html", cfg=cfg, configured=bool(credential), leagues=LEAGUES, source_defs=SOURCE_DEFS,
        rows=kwargs.get("rows", []), coverage=kwargs.get("coverage", []), stats=kwargs.get("stats", {}),
        error=kwargs.get("error", ""), message=kwargs.get("message", ""), warnings=kwargs.get("warnings", []),
        bet365_bookmarklet=bookmarklet,
        automatic_scan=kwargs.get('automatic_scan',False),
        provider_wait=kwargs.get('provider_wait',False),
        automatic_filter=kwargs.get('automatic_filter',{'sources':['bet365','sportium']}),
    )
    return html.replace(credential, "[REDACTED]") if credential else html


@app.route("/bet365-feed", methods=["POST"])
@app.route("/bet365-import", methods=["GET", "POST"])
def import_bet365():
    with _web_import_lock:
        return _import_bet365()


def _import_bet365():
    return _import_browser('bet365')


def _import_browser(source):
    if request.method == "GET":
        return render_template("bet365_import.html")
    try:
        payload = request.get_json() if request.is_json else json.loads(request.form.get("payload", ""))
        # Whitelist only public match fields. No arbitrary pasted fields persist.
        canonical = {"source_url":payload["source_url"], "observed_at":payload["observed_at"], "events":[
            {k:e[k] for k in ("event_id", "home", "away", "league", "start", "market", "odds")} for e in payload["events"]]}
        if source == 'bet365':
            for submitted, event in zip(payload['events'], canonical['events']):
                enhanced = submitted.get('enhanced_odds')
                if enhanced is not None:
                    if not isinstance(enhanced, dict):
                        raise ValueError('Enhanced market')
                    prices = {sign:_to_float(enhanced.get(sign)) for sign in ('1','X','2')}
                    if not all(price and 1 < price <= 1000 for price in prices.values()):
                        raise ValueError('Enhanced prices')
                    event['enhanced_odds'] = prices
        path=BET365_BROWSER_PATH if source=='bet365' else SPORTIUM_BROWSER_PATH
        parsed_url=urlparse(canonical['source_url'])
        if parsed_url.scheme!='https' or parsed_url.hostname != urlparse(SOURCE_DEFS[source]['site']).hostname or parsed_url.query or parsed_url.username or parsed_url.password:
            raise ValueError("Origin")
        captured = parse_dt(canonical["observed_at"])
        if not captured or not -60 <= (datetime.now(timezone.utc)-captured).total_seconds() <= read_config()['max_source_age_minutes']*60:
            raise ValueError("Age")
        for event in canonical["events"]:
            if event["market"] != "FULL_TIME_1X2" or not parse_dt(event["start"]) or not all(_to_float(event["odds"].get(k)) for k in ("1","X","2")):
                raise ValueError("Market")
            if not event["home"] or not event["away"]:
                raise ValueError("Teams")
            event["observed_at"] = captured.isoformat()
            event["source_url"] = canonical["source_url"]
        if not canonical["events"]:
            raise ValueError("Empty")
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            combined = {e["event_id"]:dict(e, observed_at=e.get("observed_at", previous["observed_at"]), source_url=e.get("source_url", previous["source_url"])) for e in previous["events"]
                        if parse_dt(e.get("observed_at", previous["observed_at"])) and (datetime.now(timezone.utc)-parse_dt(e.get("observed_at", previous["observed_at"]))).total_seconds() < 86400}
        except (OSError, ValueError, KeyError, TypeError):
            combined = {}
        combined.update({e["event_id"]:e for e in canonical["events"]})
        canonical["events"] = list(combined.values())[-500:]
        path.write_text(json.dumps(canonical, ensure_ascii=False, indent=2), encoding="utf-8")
        cfg = read_config()
        if source=='bet365' and cfg.get('bet365_mode')!='browser_auto': cfg["bet365_mode"] = "web"
        write_config(cfg)
        quotes, _ = read_browser_web(source,cfg["hours"])
        restore_quote_cache()
        by_source = {s:[] for s in SOURCE_DEFS}
        for g in _last_groups:
            for book_source, q in g.quotes.items():
                if q.source != source:
                    by_source[q.source].append(q)
        by_source[source] = quotes
        _last_groups[:] = group_quotes(by_source, set(cfg["selected_leagues"]), cfg["hours"])
        save_quote_cache()
        _last_result.update(coverage=coverage_rows(_last_groups), rows=build_crosses(_last_groups,cfg["base_stake"],cfg["max_loss"]),
                            message=f"Lectura de {SOURCE_DEFS[source]['label']} importada. No se han realizado peticiones a PulseScore.",
                            warnings=[f"{SOURCE_DEFS[source]['label']}: lectura web; las cuotas se conservan durante 5 horas."],
                            stats={"groups":len(_last_groups),"with_three":sum(len(g.quotes)>=3 for g in _last_groups),"crosses":len(build_crosses(_last_groups,cfg["base_stake"],cfg["max_loss"])),"api_calls":_last_result.get('stats',{}).get('api_calls',0),"sources":_last_result.get('stats',{}).get('sources',{})})
        if any("(muestra)" in q.origin for g in _last_groups for q in g.quotes.values()):
            _last_result["warnings"].append("Winamax y Betfair: muestra recuperada del diagnóstico reciente; cobertura parcial. No se han repetido peticiones.")
        if request.is_json:
            return {"ok":True, "events":len(quotes), "api_calls":0}
        return redirect(url_for("home"))
    except (ValueError, KeyError, TypeError, AttributeError, PulseScoreError):
        return render_template("bet365_import.html", error="Lectura incompleta, caducada o de origen no válido. Vuelve a capturar Resultado final en Bet365 España."), 400


@app.get("/bet365-extension")
def bet365_extension_help():
    return render_template("bet365_extension.html", folder=str(extension_dir()))


@app.get("/bet365-extension.zip")
def bet365_extension_download():
    return send_file(RESOURCE_DIR / "bet365_extension.zip", as_attachment=True)


@app.get('/bet365-targets')
def bet365_targets():
    restore_quote_cache()
    cfg=read_config()
    targets=[]
    outside_window=0
    for group in _last_groups:
        q=group.quotes.get('winamax_es')
        if q and group.league_key in cfg['selected_leagues'] and quote_in_window(q,cfg['hours']):
            source=request.args.get('source')
            if request.args.get('missing')=='1' and source in ('bet365','sportium'):
                existing=group.quotes.get(source)
                if existing and quote_is_fresh(existing) and abs((q.start-existing.start).total_seconds())<=900: continue
            if request.args.get('home') and request.args.get('away') and (canonical_team(q.home)!=canonical_team(request.args['home']) or canonical_team(q.away)!=canonical_team(request.args['away'])):
                continue
            if source=='sportium' and not quote_in_window(q,48):
                outside_window+=1
                continue
            targets.append({'home':q.home,'away':q.away,'start':q.start.isoformat(),
                            'canonical_home':canonical_team(q.home),'canonical_away':canonical_team(q.away)})
    return {'targets':targets,'aliases':TEAM_ALIASES,'outside_window':outside_window,'leagues':cfg['selected_leagues']}


@app.route('/bet365-scan-status',methods=['GET','POST'])
def bet365_scan_status():
    if request.method=='POST':
        data=request.get_json(silent=True) or {}
        try:
            if _scan_status.get('source')!=data.get('source') or _scan_status.get('current')!=str(data.get('current',''))[:200]:
                _scan_status['phase_started_at']=time.time()
            _scan_status['last_seen_at']=time.time()
            _scan_status.update(running=bool(data.get('running')),processed=max(0,int(data.get('processed',0))),
                                total=max(0,int(data.get('total',0))),captured=max(0,int(data.get('captured',0))),
                                current=str(data.get('current',''))[:200],last_error=str(data.get('last_error',''))[:200])
            _scan_status['source']=data.get('source') if data.get('source') in SOURCE_DEFS else 'bet365'
            _scan_status['label']=SOURCE_DEFS[_scan_status['source']]['label']
        except (ValueError,TypeError): return {'ok':False},400
        credential=get_api_key()
        if credential:
            for field in ('current','last_error'): _scan_status[field]=_scan_status[field].replace(credential,'[REDACTED]')
    state=dict(_scan_status)
    state['phase_elapsed_seconds']=max(0,int(time.time()-state.get('phase_started_at',time.time())))
    state['stale']=bool(state.get('running') and time.time()-state.get('last_seen_at',time.time())>120)
    return state


@app.post('/bet365-scan-observation')
@app.post('/sportium-scan-observation')
def bet365_scan_observation():
    if _update_cancel.is_set():
        return {'ok':False,'reason':'Actualización detenida.'},409
    with _web_import_lock:
        try:
            source='sportium' if request.path.startswith('/sportium') else 'bet365'
            restore_quote_cache()
            observation=request.get_json()
            if len(observation['events'])!=1: return {'ok':False,'reason':'Se requiere un único encuentro por lectura.'},400
            event=observation['events'][0]
            start=parse_dt(event['start'])
            sample=SourceQuote(source,SOURCE_DEFS[source]['label'],event['event_id'],event['home'],event['away'],event['league'],'',start,event['odds'])
            references=[g.quotes['winamax_es'] for g in _last_groups if 'winamax_es' in g.quotes]
            valid=any(canonical_team(q.home)==canonical_team(sample.home) and canonical_team(q.away)==canonical_team(sample.away)
                      and abs((q.start-start).total_seconds())<=900 and classify_league(q)==classify_league(sample) for q in references)
            # Bet365 can show an unqualified "La Liga" / "Primera División".
            # Infer Spain only from one matching Winamax event, never from that title alone.
            if not valid and source=='bet365' and normalize_text(sample.league) in {'la liga','primera division','primera'}:
                matching=[q for q in references if canonical_team(q.home)==canonical_team(sample.home)
                          and canonical_team(q.away)==canonical_team(sample.away)
                          and abs((q.start-start).total_seconds())<=900 and classify_league(q)=='laliga']
                if len(matching)==1:
                    event['league']='Spain||LaLiga'
                    valid=True
            if not valid:
                matching=[q for q in references if canonical_team(q.home)==canonical_team(sample.home) and canonical_team(q.away)==canonical_team(sample.away)]
                reason='Equipos distintos de la referencia de Winamax.' if not matching else 'Hora distinta de la referencia de Winamax.' if not any(abs((q.start-start).total_seconds())<=900 for q in matching) else 'Competición no reconocida o distinta de Winamax.'
                return {'ok':False,'reason':reason},400
        except (KeyError,ValueError,TypeError,AttributeError):
            return {'ok':False,'reason':'Lectura incompleta.'},400
        return _import_browser(source)


@app.post('/bet365-scan-complete')
def bet365_scan_complete():
    if _update_cancel.is_set():
        _scan_status.update(running=False)
        return {'ok':True,'cancelled':True}
    data=request.get_json(silent=True) or {}
    try: captured=max(0,min(500,int(data.get('captured',0))))
    except (ValueError,TypeError): return {'ok':False},400
    credential=get_api_key()
    failures=[str(item)[:200] for item in data.get('failures',[])[:10]]
    if credential: failures=[item.replace(credential,'[REDACTED]') for item in failures]
    source=data.get('source') if data.get('source') in SOURCE_DEFS else 'bet365'
    _browser_results[source]={'captured':captured,'failures':failures}
    _last_result.update(message='Lectura automática terminada: '+' · '.join(f"{SOURCE_DEFS[s]['label']}: {r['captured']} partidos verificados" for s,r in _browser_results.items()),
                        warnings=[f"{SOURCE_DEFS[s]['label']}: {failure}" for s,r in _browser_results.items() for failure in r['failures']])
    _scan_status.update(running=data.get('continuing') is True,captured=captured)
    SCAN_RESULT_PATH.write_text(json.dumps({'captured':captured,'failures':failures},ensure_ascii=False),encoding='utf-8')
    return {'ok':True}


@app.post('/refresh-bet365')
@app.post('/refresh-sportium')
@app.post('/refresh-browser')
def refresh_bet365_only():
    if not _update_lock.acquire(blocking=False):
        return render_home(error='Ya hay una actualización en curso.')
    _update_cancel.clear()
    try:
        restore_quote_cache()
        cfg=read_config()
        sources=['sportium'] if request.path=='/refresh-sportium' else (['winamax_es','betfair_sb','bet365','sportium'] if cfg.get('odds_mode')=='browser_direct' else ['bet365','sportium']) if request.path=='/refresh-browser' else ['bet365']
        if cfg.get('bet365_mode')=='browser_auto' or request.path!='/refresh-bet365':
            _last_result.setdefault('stats',{})['api_calls']=0
            return render_home(coverage=coverage_rows(_last_groups),automatic_scan=True,
                               automatic_filter={'home':request.form.get('home',''),'away':request.form.get('away',''),'sources':sources,'missing':request.form.get('missing')=='1'},
                               message='Buscando automáticamente '+ ' y '.join(SOURCE_DEFS[s]['label'] for s in sources)+' usando las referencias guardadas de Winamax · 0 peticiones a PulseScore.')
        by_source={source:[] for source in SOURCE_DEFS}
        for group in _last_groups:
            for source,quote_item in group.quotes.items(): by_source[source].append(quote_item)
        targets=by_source['winamax_es']
        if request.form.get('home') and request.form.get('away'):
            targets=[q for q in targets if canonical_team(q.home)==canonical_team(request.form['home']) and canonical_team(q.away)==canonical_team(request.form['away'])]
        quotes,meta=fetch_bet365_auto(targets,cfg['hours'])
        keys={(canonical_team(q.home),canonical_team(q.away)) for q in targets}
        by_source['bet365']=[q for q in by_source['bet365'] if (canonical_team(q.home),canonical_team(q.away)) not in keys]+quotes
        _last_groups[:]=group_quotes(by_source,set(cfg['selected_leagues']),cfg['hours'])
        save_quote_cache()
        _last_result.update(message=f"Bet365: {len(quotes)} partidos leídos automáticamente · 0 peticiones a PulseScore.",warnings=meta.get('failures',[]),stats={'sources':{'bet365':meta},'api_calls':0})
        return home()
    except PulseScoreError as exc:
        return render_home(error=str(exc),coverage=coverage_rows(_last_groups))
    finally:
        _update_lock.release()


@app.get("/")
def home():
    restore_quote_cache()
    if _last_groups:
        cfg = read_config()
        groups = [g for g in _last_groups if g.league_key in cfg["selected_leagues"] and quote_in_window(next(iter(g.quotes.values())), cfg["hours"])]
        _last_result["rows"] = build_crosses(groups, cfg["base_stake"], cfg["max_loss"])
        _last_result["coverage"] = coverage_rows(groups)
        _last_result["stats"].update(groups=len(groups), crosses=len(_last_result["rows"]), with_three=sum(sum(quote_is_fresh(q) for q in g.quotes.values())>=3 for g in groups))
    return render_home(**_last_result)


@app.post("/save-settings")
def save_settings():
    cfg = read_config()
    key = request.form.get("api_key", "").strip()
    if key:
        try:
            storage_message = save_api_key(key)
            _page_cache.clear()
            _last_result.clear()
        except PulseScoreError as exc:
            return render_home(error=str(exc))
    try:
        cfg["base_stake"] = float(str(request.form.get("base_stake", cfg["base_stake"])).replace(",", "."))
        cfg["hours"] = int(request.form.get("hours", cfg["hours"]))
        cfg["max_loss"] = float(str(request.form.get("max_loss", cfg["max_loss"])).replace(",", "."))
        if not math.isfinite(cfg["base_stake"]) or not math.isfinite(cfg["max_loss"]) or not 1 <= cfg["hours"] <= 168 or not .01 <= cfg["base_stake"] <= 10000 or cfg["max_loss"] < 0:
            return render_home(error="Importes o intervalo no válidos.")
        plan = request.form.get("api_plan", cfg["api_plan"])
        if plan in ("UNKNOWN", "BASIC", "STARTER", "PRO", "MAX", "ULTRA"):
            cfg["api_plan"] = plan
        mode = request.form.get("bet365_mode", cfg["bet365_mode"])
        if mode in ("browser_auto", "auto", "web", "pulsescore"):
            cfg["bet365_mode"] = mode
    except Exception:
        return render_home(error="Importes o intervalo no válidos.")
    selected = [x for x in request.form.getlist("leagues") if x in LEAGUES]
    if selected:
        cfg["selected_leagues"] = selected
    write_config(cfg)
    if key:
        return render_home(message=storage_message)
    return redirect(url_for("home"))


@app.post("/check-api")
def check_api():
    key = get_api_key()
    if not key:
        return render_home(error="Primero guarda tu API key de PulseScore.")
    # A single, small request is enough to validate credentials.
    try:
        trace: list[dict[str, Any]] = []
        r = _throttled_get("winamax_es", key, page=1, limit=1, trace=trace)
        if r.status_code != 200:
            return render_home(error=f"PulseScore respondió {r.status_code}: {safe_error(r)}")
        return render_home(message="API de PulseScore correcta. La clave funciona.")
    except PulseScoreError as exc:
        return render_home(error=str(exc))
    except requests.RequestException as exc:
        return render_home(error=connection_error_label(exc))


@app.post("/update")
def update():
    if _scan_status.get('running'):
        return render_home(**_last_result,provider_wait=True)
    if not _update_lock.acquire(blocking=False):
        return render_home(**_last_result, provider_wait=True)
    _update_cancel.clear()
    _update_progress.clear()
    _update_progress.update(source='Preparando consulta',page=0)
    try:
        cfg = read_config()
        if request.form.get('settings_version') == 'simple':
            try:
                new_cfg = dict(cfg)
                new_cfg['base_stake'] = float(request.form.get('base_stake','').replace(',','.'))
                new_cfg['hours'] = int(request.form.get('hours',''))
                new_cfg['max_loss'] = float(request.form.get('max_loss','').replace(',','.'))
                if not math.isfinite(new_cfg['base_stake']) or not math.isfinite(new_cfg['max_loss']) or not .01 <= new_cfg['base_stake'] <= 10000 or not 1 <= new_cfg['hours'] <= 168 or new_cfg['max_loss'] < 0:
                    raise ValueError()
                selected_leagues = [x for x in request.form.getlist('leagues') if x in LEAGUES]
                if not selected_leagues:
                    return render_home(error='Selecciona al menos una competición antes de actualizar.')
                new_cfg.update(selected_leagues=selected_leagues,api_plan='BASIC',bet365_mode='browser_auto')
            except (ValueError,TypeError):
                return render_home(error='Importes o intervalo no válidos.')
            entered_key = request.form.get('api_key','').strip()
            if entered_key:
                try:
                    save_api_key(entered_key)
                except PulseScoreError as exc:
                    return render_home(error=str(exc))
                _page_cache.clear()
            write_config(new_cfg)
            cfg = new_cfg
        if cfg.get('odds_mode') == 'browser_direct':
            restore_quote_cache()
            _browser_results.clear()
            _last_result.setdefault('stats',{})['api_calls']=0
            return render_home(coverage=coverage_rows(_last_groups),automatic_scan=True,
                               automatic_filter={'sources':['winamax_es','betfair_sb','bet365','sportium']},
                               message='Leyendo las casas directamente en el navegador · 0 peticiones a PulseScore.')
        key = get_api_key()
        if not key:
            return render_home(error="Primero guarda tu API key de PulseScore.")
        selected = set(cfg["selected_leagues"])
        all_quotes: dict[str, list[SourceQuote]] = {}
        source_stats: dict[str, Any] = {}
        warnings: list[str] = []
        if cfg["bet365_mode"] == "web" and request.form.get("bet365_reader_result") == "unavailable":
            warnings.append("Bet365: el lector no devolvió cuotas nuevas. Instálalo y actívalo, abre el partido en Bet365 y utiliza la app en ese mismo Chrome o Edge. Solo se conservarán las lecturas anteriores que sigan vigentes.")
        trace: list[dict[str, Any]] = []
        for source in ("winamax_es", "betfair_sb", "bet365"):
            check_update_cancelled()
            try:
                if source=='bet365' and cfg['bet365_mode']=='browser_auto':
                    try: quotes,meta=read_bet365_web(int(cfg['hours']))
                    except PulseScoreError: quotes,meta=[],{'api_calls':0,'with_1x2':0}
                    meta.update(automatic_extension=True,web_snapshot=False)
                elif source=='bet365' and cfg['bet365_mode']=='auto':
                    quotes,meta=fetch_bet365_auto(all_quotes.get('winamax_es',[]),int(cfg['hours']))
                else:
                    quotes, meta = fetch_source(source, key, int(cfg["hours"]), trace)
                all_quotes[source] = quotes
                source_stats[source] = meta
            except PulseScoreError as exc:
                all_quotes[source] = []
                source_stats[source] = {"error": str(exc), "raw_events": 0, "with_1x2": 0}
                warnings.append(str(exc))
        try: all_quotes['sportium'],source_stats['sportium']=read_browser_web('sportium',int(cfg['hours']))
        except PulseScoreError: all_quotes['sportium'],source_stats['sportium']=[],{'api_calls':0,'with_1x2':0}
        source_stats['sportium']['automatic_extension']=True
        check_update_cancelled()
        groups = group_quotes(all_quotes, selected, int(cfg["hours"]))
        _last_groups[:] = groups
        save_quote_cache()
        coverage = coverage_rows(groups)
        rows = build_crosses(groups, float(cfg["base_stake"]), float(cfg["max_loss"]))
        with_three = sum(1 for g in groups if len(g.quotes) >= 3)
        api_calls = sum(1 for t in trace if not t.get("cached"))
        for source, meta in source_stats.items():
            if meta.get('automatic_extension'): continue
            if meta.get('automatic_web'):
                warnings.extend(meta.get('failures',[])[:5])
                if not meta.get('with_1x2'): warnings.append('Bet365 ES: '+meta.get('note','Sin cuotas verificadas.'))
                continue
            if meta.get("web_snapshot"):
                warnings.append("Bet365 ES: lectura directa de partidos abiertos. Actualizar cuotas pide una captura nueva si la extensión está instalada y activa. No busca automáticamente todo el catálogo de Winamax.")
                continue
            if isinstance(meta, dict) and meta.get("coverage_complete") is False:
                warnings.append(
                    f"{SOURCE_DEFS[source]['label']}: se alcanzó el límite de {cfg['max_pages']} páginas antes de cubrir todo el intervalo. "
                    "Puede faltar algún partido; reduce las horas y actualiza de nuevo."
                )
        stats = {
            "groups": len(groups),
            "with_three": with_three,
            "crosses": len(rows),
            "sources": source_stats,
            "api_calls": api_calls,
        }
        msg = f"Actualización completada: {len(groups)} partidos en tus competiciones · {with_three} con las 3 casas · {len(rows)} cruces dentro de la pérdida máxima."
        if not groups:
            available = sum(meta.get('with_1x2',0) for name,meta in source_stats.items() if name in ('winamax_es','betfair_sb'))
            names = ', '.join(LEAGUES[x] for x in cfg['selected_leagues'])
            msg = f"Actualización completada: {available} cuotas de partidos recibidas, pero ninguno coincide con {names} en las próximas {cfg['hours']} horas. Amplía «Próximas horas» o selecciona otras competiciones y vuelve a actualizar."
        if any(meta.get('error') for meta in source_stats.values()):
            msg = f"Actualización parcial: {len(groups)} partidos disponibles. Alguna fuente no pudo actualizar; revisa los avisos de cada casa."
        diagnostic = {
            "version": "4.2",
            "generated_at": datetime.now().astimezone().isoformat(),
            "settings": {"hours": int(cfg["hours"]), "selected_leagues": list(selected)},
            "summary": stats,
            "http_trace": trace,
            "sample_matches": [
                {
                    "home": c["home"], "away": c["away"], "league": c["league"],
                    "start_time": c["start_time"],
                    "time_warning": c["time_warning"],
                    "books": {k: {field: v[field] for field in ("available", "has_quote", "odds", "reason", "source_start", "updated", "received_at", "origin")} for k, v in c["books"].items()},
                }
                for c in coverage[:20]
            ],
            "privacy": "API key is never written to this file.",
        }
        LAST_DIAG_PATH.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2).replace(key, "[REDACTED]"), encoding="utf-8")
        _last_result.update(rows=rows, coverage=coverage, stats=stats, message=msg, warnings=warnings)
        return render_home(**_last_result,automatic_scan=cfg.get('bet365_mode')=='browser_auto' and any('winamax_es' in g.quotes for g in groups))
    except UpdateCancelled:
        _last_result.update(message='Actualización detenida. Se conservan las últimas cuotas completas.')
        return render_home(**_last_result)
    finally:
        _update_lock.release()


@app.get('/update-status')
def update_status():
    progress=dict(_update_progress)
    if _scan_status.get('running') and not _update_lock.locked():
        progress.update(source=_scan_status.get('label','Lector automático')+' · '+str(_scan_status.get('processed',0))+'/'+str(_scan_status.get('total',0)),page=0)
    return dict(progress, running=_update_lock.locked() or bool(_scan_status.get('running')), cancelled=_update_cancel.is_set(),scan=bet365_scan_status())


@app.post('/stop-update')
def stop_update():
    _update_cancel.set()
    _last_result.update(message='Actualización detenida. Se conservan las últimas cuotas completas.')
    return {'ok':True,'running':_update_lock.locked()}


@app.get('/update-result')
def update_result():
    if _update_lock.locked() or _scan_status.get('running'):
        return render_home(**_last_result,provider_wait=True)
    return render_home(**_last_result)


@app.get("/download-diagnostic")
def download_diagnostic():
    if not LAST_DIAG_PATH.exists():
        return render_home(error="Todavía no hay diagnóstico. Haz una actualización primero.")
    return send_file(LAST_DIAG_PATH, as_attachment=True, download_name="diagnostico_cruces_v4.2.json")


@app.get("/demo")
def demo():
    now = datetime.now(timezone.utc) + timedelta(hours=5)
    q1 = SourceQuote("bet365", "Bet365", "d1", "Croacia", "España", "UEFA Nations League", "", now, {"1": 8.0, "X": 6.0, "2": 1.30})
    q2 = SourceQuote("winamax_es", "Winamax ES", "d2", "Croacia", "España", "Liga de Naciones UEFA", "", now, {"1": 8.0, "X": 6.25, "2": 1.27})
    q3 = SourceQuote("betfair_sb", "Betfair Sportsbook", "d3", "Croatia", "Spain", "UEFA Nations League", "", now, {"1": 8.5, "X": 6.2, "2": 1.28})
    g = MatchGroup("Croacia", "España", "Liga de Naciones UEFA", "", now, "internationals", {"bet365": q1, "winamax_es": q2, "betfair_sb": q3})
    cfg = read_config()
    return render_home(
        rows=build_crosses([g], float(cfg["base_stake"]), float(cfg["max_loss"])),
        coverage=coverage_rows([g]),
        stats={"groups": 1, "with_three": 1, "crosses": 1, "api_calls": 0, "sources": {}},
        message="Modo demo: cálculo y unión de tres casas funcionando sin gastar peticiones.",
    )


def open_browser() -> None:
    webbrowser.open_new(f"http://127.0.0.1:{PORT}")


from browser_direct import register as register_direct
register_direct(app)
from freebets import register as register_freebets
register_freebets(app)
from distribution import register as register_distribution
register_distribution(app)
from reader_diagnostics import bp as reader_diagnostics_bp
app.register_blueprint(reader_diagnostics_bp)

if __name__ == "__main__":
    threading.Timer(1.1, open_browser).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
