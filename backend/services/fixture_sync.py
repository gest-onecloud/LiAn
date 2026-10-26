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



def fetch_season_for_liga(liga_code, liga_name):
    """PASO 8.1 FIX: Trae temporada completa recorriendo últimos 90 días + próximos 60 días por liga (ESPN por fecha)"""
    from datetime import date as date_obj, timedelta
    all_matches = []
    today = date_obj.today()
    
    # Recorrer últimos 90 días + próximos 60 días = 150 días de temporada
    # Esto sí trae toda la temporada real de Liga MX, Premier, etc.
    days_back = 90
    days_future = 60
    dates_to_fetch = []
    for i in range(-days_future, days_back+1):
        d = today - timedelta(days=i)
        dates_to_fetch.append(d)
    
    print(f"[season] {liga_code} - Recorriendo {len(dates_to_fetch)} días para temporada completa")
    
    for d in dates_to_fetch:
        date_str = d.isoformat()
        date_nodash = d.strftime('%Y%m%d')
        # ESPN API por fecha específica para esta liga
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard?dates={date_nodash}"
        try:
            raw = get_json(url, timeout=5)
            if raw and raw.get('events'):
                matches = _parse_espn(date_str, raw, liga_code, liga_name)
                # Solo guardar si la fecha parseada coincide con un rango razonable (no filtrar demasiado)
                if matches:
                    # Filtrar solo para no traer partidos de fechas muy lejanas mal parseadas
                    for m in matches:
                        # Solo agregar si la liga coincide o el partido es de esta liga
                        all_matches.append(m)
        except Exception as e:
            continue
    
    # Deduplicar por fecha+liga+equipos normalizado
    seen=set()
    unique=[]
    for m in all_matches:
        key=f"{m['date']}_{m['league_code'].lower()}_{m['home'].lower()}_{m['away'].lower()}"
        if key not in seen:
            seen.add(key)
            unique.append(m)
    print(f"[season] {liga_code} TOTAL temporada 90+60 días: {len(unique)} partidos únicos")
    # Si no obtuvimos nada, intentar con endpoint sin fecha (día actual)
    if len(unique)==0:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard"
            raw = get_json(url, timeout=8)
            if raw and raw.get('events'):
                matches = _parse_espn(today.isoformat(), raw, liga_code, liga_name)
                unique.extend(matches)
                print(f"[season] {liga_code} fallback sin fecha -> {len(matches)} partidos")
        except:
            pass
    return unique

def fetch_all_seasons():
    """Trae temporada completa de las 15 ligas"""
    all_matches=[]
    for liga_code, liga_name in LIGAS_MUNDIALES:
        try:
            matches=fetch_season_for_liga(liga_code, liga_name)
            all_matches.extend(matches)
            print(f"[all_seasons] {liga_code}: {len(matches)}")
        except Exception as e:
            print(f"[all_seasons] Error {liga_code}: {e}")
    # Deduplicar global
    seen=set()
    unique=[]
    for m in all_matches:
        key=f"{m['date']}_{m['home']}_{m['away']}_{m['league_code']}"
        if key not in seen:
            seen.add(key)
            unique.append(m)
    print(f"[all_seasons] TOTAL 15 ligas: {len(unique)} partidos temporada completa")
    return unique

def sync_all_seasons(repo):
    """Sincroniza temporada completa de todas las ligas a la BD - FIX dedup"""
    print("[sync_all_seasons] Iniciando sincronización temporada completa 15 ligas...")
    # Limpiar duplicados existentes primero
    try:
        cleaned = repo.clean_duplicates()
        print(f"[sync_all_seasons] Limpieza previa: {cleaned} duplicados eliminados")
    except:
        pass
    matches=fetch_all_seasons()
    if matches:
        count=repo.upsert_matches(matches)
        print(f"[sync_all_seasons] Guardados {count} partidos temporada completa")
        # Limpiar de nuevo después de insertar
        try:
            cleaned2 = repo.clean_duplicates()
            print(f"[sync_all_seasons] Limpieza posterior: {cleaned2} duplicados")
        except:
            pass
        repo.log_sync('SEASON_15_LIGAS', '2025-2026', count, 0, 'OK')
        return count
    return 0


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


def sync_season(repo, days_back=90):
    from datetime import date as date_obj, timedelta
    print(f"[fixture_sync] PASO 7 - Sincronizando temporada completa últimos {days_back} días")
    today = date_obj.today()
    total_synced = 0
    for i in range(days_back):
        d = today - timedelta(days=i)
        date_str = d.isoformat()
        try:
            print(f"[fixture_sync] Temporada día {i+1}/{days_back} -> {date_str}")
            matches = fetch_from_internet(date_str)
            if matches:
                count = repo.upsert_matches(matches)
                total_synced += count
                print(f"[fixture_sync] {date_str} -> {count} partidos")
        except Exception as e:
            print(f"[fixture_sync] Error {date_str}: {e}")
            continue
    print(f"[fixture_sync] Temporada completa: {total_synced} partidos sincronizados")
    return total_synced

def sync_range(repo, start_date, end_date):
    from datetime import datetime, timedelta
    try:
        s = datetime.fromisoformat(start_date).date()
        e = datetime.fromisoformat(end_date).date()
        delta = (e - s).days
        for i in range(delta+1):
            d = s + timedelta(days=i)
            sync_for_date(repo, d.isoformat())
    except Exception as ex:
        print(f"[sync_range error] {ex}")


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
