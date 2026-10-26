"""
LiAn V64.6.0 - Paso 5.5 FIX FINAL - Zona horaria + Marcador + Todos los partidos
"""
import time
from datetime import datetime, date as date_obj, timedelta
from .http_client import get_json

LIGAS_MUNDIALES = [
    ("eng.1", "Premier League - Inglaterra"),
    ("esp.1", "La Liga - España"),
    ("ita.1", "Serie A - Italia"),
    ("ger.1", "Bundesliga - Alemania"),
    ("fra.1", "Ligue 1 - Francia"),
    ("mex.1", "Liga MX - Mexico"),
    ("usa.1", "MLS - USA"),
    ("bra.1", "Brasileirão - Brasil"),
    ("arg.1", "Liga Argentina"),
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


def _parse_espn(requested_date, raw, liga_code, liga_name):
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
            home_score_raw = home.get('score')
            away_score_raw = away.get('score')
            try:
                hs = int(home_score_raw) if home_score_raw not in (None,'','None') else None
            except:
                hs = None
            try:
                as_ = int(away_score_raw) if away_score_raw not in (None,'','None') else None
            except:
                as_ = None
            
            status_type = comp.get('status',{}).get('type',{})
            status_name = str(status_type.get('name','NS'))
            status_detail = str(status_type.get('detail',''))
            status_state = str(status_type.get('state','pre')).lower()
            
            upper_name = status_name.upper()
            upper_detail = status_detail.upper()
            
            # DETERMINAR ESTADO REAL ESPN
            # STATUS_SCHEDULED, STATUS_IN_PROGRESS, STATUS_HALFTIME, STATUS_FULL_TIME, STATUS_FINAL, etc
            if any(k in upper_name for k in ['STATUS_FINAL', 'STATUS_FULL_TIME', 'STATUS_AET', 'FINAL']):
                estado = 'FINALIZADO'
            elif 'STATUS_HALFTIME' in upper_name or 'HALF' in upper_name or 'HALF_TIME' in upper_name:
                estado = 'EN_JUEGO'
            elif 'STATUS_IN_PROGRESS' in upper_name or status_state == 'in' or 'LIVE' in upper_name or '1H' in upper_detail or '2H' in upper_detail:
                estado = 'EN_JUEGO'
            elif 'STATUS_SCHEDULED' in upper_name or 'SCHEDULED' in upper_name or status_state == 'pre':
                estado = 'PROGRAMADO'
            else:
                # Fallback por status_state
                if status_state == 'post':
                    estado = 'FINALIZADO'
                elif status_state == 'in':
                    estado = 'EN_JUEGO'
                else:
                    estado = 'PROGRAMADO'
            
            # REGLA CLAVE: Si es PROGRAMADO, NO guardar marcador (ESPN manda 0-0 placeholder)
            if estado == 'PROGRAMADO':
                hs = None
                as_ = None
            
            dt_str = ev.get('date') or comp.get('date') or ''
            t = ''
            fecha_real = requested_date
            fecha_real_utc = requested_date
            if dt_str:
                try:
                    dt = datetime.fromisoformat(dt_str.replace('Z','+00:00'))
                    dt_mex = dt - timedelta(hours=6)
                    t = dt_mex.strftime('%H:%M')
                    fecha_real = dt_mex.strftime('%Y-%m-%d')
                    fecha_real_utc = dt.strftime('%Y-%m-%d')
                except:
                    t = dt_str[11:16] if len(dt_str)>16 else ''
                    try:
                        fecha_real = dt_str[:10]
                        fecha_real_utc = dt_str[:10]
                    except:
                        pass
            
            matches.append({
                "date": fecha_real,
                "date_utc": fecha_real_utc,
                "time": t,
                "home": home_name,
                "away": away_name,
                "league": liga_name,
                "league_code": liga_code,
                "competition": liga_name,
                "status": status_name,
                "status_detail": status_detail,
                "estado": estado,
                "home_score": hs,
                "away_score": as_,
                "score": f"{hs}-{as_}" if hs is not None and as_ is not None else None
            })
        except Exception:
            continue
    return matches

# old replaced
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
            home_score = home.get('score')
            away_score = away.get('score')
            try:
                hs = int(home_score) if home_score not in (None,'','None') else None
            except:
                hs = None
            try:
                as_ = int(away_score) if away_score not in (None,'','None') else None
            except:
                as_ = None
            
            status_type = comp.get('status',{}).get('type',{})
            status_name = str(status_type.get('name','NS'))
            status_detail = str(status_type.get('detail',''))
            status_state = str(status_type.get('state','pre')).lower()
            
            upper_name = status_name.upper()
            upper_detail = status_detail.upper()
            has_score = hs is not None and as_ is not None
            
            # Si tiene marcador, siempre FINALIZADO (más confiable que status)
            if has_score:
                estado = 'FINALIZADO'
            elif status_state == 'post':
                estado = 'FINALIZADO'
            elif any(k in upper_name for k in ['STATUS_FINAL', 'STATUS_FULL_TIME', 'FINAL', 'FT', 'FULL_TIME', 'AET', 'PEN']):
                estado = 'FINALIZADO'
            elif any(k in upper_detail for k in ['FINAL', 'FT', 'FULL-TIME', 'FULL TIME', 'FINAL -']):
                estado = 'FINALIZADO'
            elif status_state == 'post':
                estado = 'FINALIZADO'
            elif status_state == 'in' or any(k in upper_name or k in upper_detail for k in ['IN_PROGRESS', 'LIVE', '1H', '2H', 'HALF']):
                estado = 'EN_JUEGO'
            else:
                estado = 'PROGRAMADO'
            # REGLA DEFINITIVA: si tiene marcador, siempre es FINALIZADO
            if has_score:
                estado = 'FINALIZADO'
            
            dt_str = ev.get('date') or comp.get('date') or ''
            t = ''
            fecha_real = requested_date
            fecha_real_utc = requested_date
            if dt_str:
                try:
                    dt = datetime.fromisoformat(dt_str.replace('Z','+00:00'))
                    dt_mex = dt - timedelta(hours=6)
                    t = dt_mex.strftime('%H:%M')
                    fecha_real = dt_mex.strftime('%Y-%m-%d')
                    fecha_real_utc = dt.strftime('%Y-%m-%d')
                except:
                    t = dt_str[11:16] if len(dt_str)>16 else ''
                    try:
                        fecha_real = dt_str[:10]
                        fecha_real_utc = dt_str[:10]
                    except:
                        pass
            
            matches.append({
                "date": fecha_real,
                "date_utc": fecha_real_utc,
                "time": t,
                "home": home_name,
                "away": away_name,
                "league": liga_name,
                "league_code": liga_code,
                "competition": liga_name,
                "status": status_name,
                "status_detail": status_detail,
                "estado": estado,
                "home_score": hs,
                "away_score": as_,
                "score": f"{hs}-{as_}" if hs is not None and as_ is not None else None
            })
        except Exception:
            continue
    return matches

def fetch_from_internet(requested_date: str):
    global _cache
    now = time.time()
    if _cache['date'] == requested_date and (now - _cache['ts']) < CACHE_TTL and _cache['data']:
        print(f"[fixture_sync] cache para {requested_date} -> {len(_cache['data'])} partidos")
        return _cache['data']

    date_nodash = requested_date.replace('-','')
    today_str = date_obj.today().isoformat()
    yesterday_str = (date_obj.today() - timedelta(days=1)).isoformat()
    tomorrow_str = (date_obj.today() + timedelta(days=1)).isoformat()
    
    print(f"[fixture_sync] FIX 5.5 -> {requested_date} (hoy {today_str})")

    all_matches = []

    for liga_code, liga_name in LIGAS_MUNDIALES:
        if requested_date == today_str:
            dates_to_try = [date_nodash, 
                           (date_obj.today() - timedelta(days=1)).strftime('%Y%m%d'),
                           (date_obj.today() + timedelta(days=1)).strftime('%Y%m%d')]
        else:
            dates_to_try = [date_nodash]
        
        found_for_liga = []
        for d_nodash in dates_to_try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard?dates={d_nodash}"
            try:
                raw = get_json(url, timeout=5)
                if raw:
                    matches = _parse_espn(requested_date, raw, liga_code, liga_name)
                    if matches:
                        found_for_liga.extend(matches)
            except:
                continue
        
        if not found_for_liga and requested_date == today_str:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard"
            try:
                raw = get_json(url, timeout=5)
                if raw:
                    matches = _parse_espn(requested_date, raw, liga_code, liga_name)
                    found_for_liga.extend(matches)
            except:
                pass
        
        if found_for_liga:
            if requested_date == today_str:
                close_dates = {today_str, yesterday_str, tomorrow_str}
                filtered_close = [m for m in found_for_liga if m['date'] in close_dates or m.get('date_utc') in close_dates]
                if filtered_close:
                    print(f"[fixture_sync] {liga_code} -> {len(filtered_close)} partidos MX")
                    all_matches.extend(filtered_close)
                else:
                    all_matches.extend(found_for_liga)
            else:
                filtered = [m for m in found_for_liga if m['date'] == requested_date]
                if filtered:
                    print(f"[fixture_sync] {liga_code} -> {len(filtered)} para {requested_date}")
                    all_matches.extend(filtered)

    if not all_matches:
        print(f"[fixture_sync] ESPN vacio para {requested_date}, TheSportsDB")
        url = THESPORTSDB.format(date=requested_date)
        raw = get_json(url, timeout=8)
        if raw and raw.get('events'):
            for ev in raw.get('events', []):
                try:
                    fecha_real = ev.get('dateEvent') or requested_date
                    hs = None
                    as_ = None
                    try:
                        hs = int(ev.get('intHomeScore')) if ev.get('intHomeScore') else None
                        as_ = int(ev.get('intAwayScore')) if ev.get('intAwayScore') else None
                    except:
                        pass
                    estado = 'PROGRAMADO'
                    st = str(ev.get('strStatus') or '').upper()
                    if any(k in st for k in ['FT', 'FINAL', 'AET', 'PEN', 'FULL_TIME']):
                        estado = 'FINALIZADO'
                    elif any(k in st for k in ['LIVE', '1H', '2H']):
                        estado = 'EN_JUEGO'
                    elif hs is not None:
                        estado = 'FINALIZADO'
                    
                    all_matches.append({
                        "date": fecha_real,
                        "date_utc": fecha_real,
                        "time": (ev.get('strTime') or '')[:5],
                        "home": ev.get('strHomeTeam') or 'Local',
                        "away": ev.get('strAwayTeam') or 'Visita',
                        "league": ev.get('strLeague') or 'Futbol',
                        "league_code": "others",
                        "competition": ev.get('strLeague') or 'Futbol',
                        "status": ev.get('strStatus') or 'NS',
                        "status_detail": ev.get('strStatus') or '',
                        "estado": estado,
                        "home_score": hs,
                        "away_score": as_,
                        "score": f"{hs}-{as_}" if hs is not None and as_ is not None else None
                    })
                except:
                    continue

    seen = set()
    unique = []
    for m in all_matches:
        key = f"{m['date']}_{m['home']}_{m['away']}_{m['league']}"
        if key not in seen:
            seen.add(key)
            unique.append(m)

    print(f"[fixture_sync] TOTAL FIX 5.5 para {requested_date}: {len(unique)} partidos")
    if unique:
        estados = {}
        for u in unique:
            estados[u['estado']] = estados.get(u['estado'], 0) + 1
        print(f"[fixture_sync] Estados: {estados}")

    _cache = {"date": requested_date, "data": unique, "ts": now}
    return unique

def sync_for_date(repo, date_str):
    start = time.time()
    try:
        deleted = repo.delete_by_date(date_str)
        if deleted:
            print(f"[fixture_sync] Limpieza: {deleted} de {date_str}")
    except Exception as e:
        print(f"[fixture_sync] Limpieza error: {e}")
    
    matches = fetch_from_internet(date_str)
    count = repo.upsert_matches(matches) if matches else 0
    duration = int((time.time() - start)*1000)
    repo.log_sync('ESPN_FIX_55', date_str, count, duration, 'OK' if matches else 'EMPTY')
    return matches
