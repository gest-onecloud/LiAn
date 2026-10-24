
"""
LiAn V64.6.0 - Paso 5 MULTI-LIGA MUNDIAL
15 ligas principales incluyendo Liga MX, MLS, Champions, etc.
"""
import time
from datetime import datetime
from .http_client import get_json

# 15 Ligas principales mundiales - Codigos ESPN oficiales
LIGAS_MUNDIALES = [
    # Top 5 Europa
    ("eng.1", "Premier League - Inglaterra"),
    ("esp.1", "La Liga - España"),
    ("ita.1", "Serie A - Italia"),
    ("ger.1", "Bundesliga - Alemania"),
    ("fra.1", "Ligue 1 - Francia"),
    # America
    ("mex.1", "Liga MX - Mexico"),
    ("usa.1", "MLS - USA"),
    ("bra.1", "Brasileirão - Brasil"),
    ("arg.1", "Liga Argentina"),
    # Competencias Internacionales
    ("uefa.champions", "Champions League"),
    ("uefa.europa", "Europa League"),
    ("uefa.europa.conf", "Conference League"),
    ("concacaf.champions", "Concachampions"),
    ("fifa.worldq", "Eliminatorias Mundial"),
    ("eng.fa", "FA Cup"),
]

THESPORTSDB = "https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={date}&s=Soccer"

_cache = {"date": None, "data": None, "ts": 0}
CACHE_TTL = 180

def _parse_espn(date_str, raw, liga_code, liga_name):
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
            home_name = home.get('team', {}).get('displayName') or home.get('team',{}).get('shortDisplayName') or 'Local'
            away_name = away.get('team', {}).get('displayName') or away.get('team',{}).get('shortDisplayName') or 'Visita'
            league = liga_name
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
                "league_code": liga_code,
                "competition": league,
                "status": comp.get('status',{}).get('type',{}).get('name','NS')
            })
        except Exception as e:
            continue
    return matches

def _parse_thesportsdb(date_str, raw):
    matches = []
    if not raw or not raw.get('events'):
        return matches
    for ev in raw.get('events', []):
        try:
            matches.append({
                "date": date_str,
                "time": (ev.get('strTime') or '')[:5],
                "home": ev.get('strHomeTeam') or 'Local',
                "away": ev.get('strAwayTeam') or 'Visita',
                "league": ev.get('strLeague') or 'Futbol',
                "league_code": "others",
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
        print(f"[fixture_sync] cache para {date_str} -> {len(_cache['data'])} partidos")
        return _cache['data']

    date_nodash = date_str.replace('-','')
    print(f"[fixture_sync] MULTI-LIGA -> Trayendo {len(LIGAS_MUNDIALES)} ligas para {date_str}")

    all_matches = []

    # 1. Intentar todas las ligas con fecha y sin fecha
    for liga_code, liga_name in LIGAS_MUNDIALES:
        # Sin fecha = partidos de HOY en esa liga
        urls = [
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard",
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard?dates={date_nodash}",
        ]
        for url in urls:
            try:
                raw = get_json(url, timeout=5)
                if raw:
                    matches = _parse_espn(date_str, raw, liga_code, liga_name)
                    if matches:
                        print(f"[fixture_sync] {liga_code} -> {len(matches)} partidos")
                        all_matches.extend(matches)
                        break  # Si encontro con esta liga, no probar segunda URL
            except Exception as e:
                continue

    # 2. Si aun no hay nada, TheSportsDB
    if not all_matches:
        print(f"[fixture_sync] ESPN vacio, probando TheSportsDB")
        url = THESPORTSDB.format(date=date_str)
        raw = get_json(url, timeout=8)
        matches = _parse_thesportsdb(date_str, raw)
        if matches:
            print(f"[fixture_sync] TheSportsDB -> {len(matches)} partidos")
            all_matches = matches

    # Deduplicar por home+away
    seen = set()
    unique = []
    for m in all_matches:
        key = f"{m['home']}_{m['away']}_{m['league']}"
        if key not in seen:
            seen.add(key)
            unique.append(m)

    print(f"[fixture_sync] TOTAL MULTI-LIGA para {date_str}: {len(unique)} partidos de {len(set([x['league'] for x in unique]))} ligas")

    _cache = {"date": date_str, "data": unique, "ts": now}
    return unique

def sync_for_date(repo, date_str):
    start = time.time()
    matches = fetch_from_internet(date_str)
    count = repo.upsert_matches(matches) if matches else 0
    duration = int((time.time() - start)*1000)
    repo.log_sync('ESPN_MULTI_15LIGAS', date_str, count, duration, 'OK' if matches else 'EMPTY')
    return matches
