
"""
LiAn REAL MODE - Fix 404 + fallback TheSportsDB
"""
import time
from datetime import datetime
from .http_client import get_json

# ESPN endpoints sin fecha = partidos de HOY reales
ESPN_TODAY = [
    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/scoreboard",
]

# Con fecha especifica (para fechas pasadas)
ESPN_WITH_DATE = [
    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates={date}",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard?dates={date}",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard?dates={date}",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/scoreboard?dates={date}",
]

THESPORTSDB = "https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={date}&s=Soccer"

_cache = {"date": None, "data": None, "ts": 0}
CACHE_TTL = 120

def _parse_espn(date_str, raw):
    matches = []
    if not raw:
        return matches
    events = raw.get('events', [])
    for ev in events:
        try:
            comp = ev.get('competitions', [{}])[0]
            competitors = comp.get('competitors', [])
            if len(competitors) < 2:
                continue
            home = next((c for c in competitors if c.get('homeAway') == 'home'), competitors[0])
            away = next((c for c in competitors if c.get('homeAway') == 'away'), competitors[1] if len(competitors)>1 else competitors[0])
            home_name = home.get('team', {}).get('displayName') or 'Local'
            away_name = away.get('team', {}).get('displayName') or 'Visita'
            league = ev.get('league', {}).get('name') or comp.get('league',{}).get('name') or 'Futbol'
            dt_str = ev.get('date') or comp.get('date') or ''
            t = ''
            if dt_str:
                try:
                    dt = datetime.fromisoformat(dt_str.replace('Z','+00:00'))
                    t = dt.strftime('%H:%M')
                except:
                    t = dt_str[11:16] if len(dt_str)>16 else ''
            matches.append({
                "date": date_str,
                "time": t,
                "home": home_name,
                "away": away_name,
                "league": league,
                "competition": league,
                "status": comp.get('status',{}).get('type',{}).get('name','NS')
            })
        except Exception as e:
            print(f"[parse espn] {e}")
            continue
    return matches

def _parse_thesportsdb(date_str, raw):
    matches = []
    if not raw or not raw.get('events'):
        return matches
    for ev in raw.get('events', []):
        try:
            # TheSportsDB format: strHomeTeam, strAwayTeam, strLeague, strTime
            matches.append({
                "date": date_str,
                "time": (ev.get('strTime') or '')[:5],
                "home": ev.get('strHomeTeam') or 'Local',
                "away": ev.get('strAwayTeam') or 'Visita',
                "league": ev.get('strLeague') or 'Futbol',
                "competition": ev.get('strLeague') or 'Futbol',
                "status": ev.get('strStatus') or 'NS'
            })
        except:
            continue
    return matches

def fetch_from_internet(date_str: str):
    global _cache
    now = time.time()
    if _cache['date'] == date_str and (now - _cache['ts']) < CACHE_TTL and _cache['data']:
        print(f"[fixture_sync] cache para {date_str}")
        return _cache['data']

    date_nodash = date_str.replace('-','')
    date_sportsdb = date_str  # TheSportsDB usa YYYY-MM-DD

    print(f"[fixture_sync] REAL -> ESPN hoy para {date_str}")

    # 1. Intentar ESPN HOY sin fecha (siempre trae algo)
    for url in ESPN_TODAY:
        print(f"[fixture_sync] Probando HOY: {url}")
        raw = get_json(url, timeout=8)
        matches = _parse_espn(date_str, raw)
        if matches:
            print(f"[fixture_sync] EXITO HOY {url} -> {len(matches)} partidos")
            _cache = {"date": date_str, "data": matches, "ts": now}
            return matches

    # 2. Intentar ESPN con fecha especifica
    for tmpl in ESPN_WITH_DATE:
        url = tmpl.format(date=date_nodash)
        print(f"[fixture_sync] Probando fecha: {url}")
        raw = get_json(url, timeout=8)
        matches = _parse_espn(date_str, raw)
        if matches:
            print(f"[fixture_sync] EXITO FECHA {url} -> {len(matches)}")
            _cache = {"date": date_str, "data": matches, "ts": now}
            return matches

    # 3. Fallback TheSportsDB (gratis, sin key, funciona con cualquier fecha)
    print(f"[fixture_sync] ESPN vacio, probando TheSportsDB para {date_sportsdb}")
    url = THESPORTSDB.format(date=date_sportsdb)
    print(f"[fixture_sync] TheSportsDB: {url}")
    raw = get_json(url, timeout=8)
    matches = _parse_thesportsdb(date_str, raw)
    if matches:
        print(f"[fixture_sync] EXITO TheSportsDB -> {len(matches)} partidos")
        _cache = {"date": date_str, "data": matches, "ts": now}
        return matches

    print(f"[fixture_sync] TODO vacio para {date_str}")
    return []

def sync_for_date(repo, date_str):
    start = time.time()
    matches = fetch_from_internet(date_str)
    count = repo.upsert_matches(matches) if matches else 0
    duration = int((time.time() - start)*1000)
    repo.log_sync('ESPN+SportsDB', date_str, count, duration, 'OK' if matches else 'EMPTY')
    return matches
