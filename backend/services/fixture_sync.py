
"""
LiAn V64.6.0 - Paso 5.4 FIX FECHA + ESTADO REAL + LIMPIEZA
- Usa fecha REAL de ESPN
- Detecta FINAL con SCORE real, no solo status
- Limpia DB vieja
"""
import time
from datetime import datetime, date as date_obj
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
            status_name = str(status_type.get('name','NS')).upper()
            status_detail = str(status_type.get('detail','')).upper()
            status_state = str(status_type.get('state','pre')).lower()
            
            # DETECCION DE ESTADO ROBUSTA - FIX para STATUS_FINAL_PEN
            estado = 'PROGRAMADO'
            # Si hay marcador y es post, es FINALIZADO
            has_score = hs is not None and as_ is not None
            is_final_keyword = any(k in status_name or k in status_detail for k in ['FINAL', 'FT', 'AET', 'PEN', 'FULL_TIME'])
            is_in_keyword = any(k in status_name or k in status_detail for k in ['IN_PROGRESS', 'LIVE', '1H', '2H', 'HALF', 'HT'])
            
            if status_state == 'post' or is_final_keyword:
                estado = 'FINALIZADO'
            elif status_state == 'in' or is_in_keyword:
                estado = 'EN_JUEGO'
            else:
                # Si tiene marcador y no es pre, probablemente finalizado
                if has_score and status_state != 'pre':
                    estado = 'FINALIZADO'
                else:
                    estado = 'PROGRAMADO'
            
            dt_str = ev.get('date') or comp.get('date') or ''
            t = ''
            fecha_real = requested_date
            if dt_str:
                try:
                    dt = datetime.fromisoformat(dt_str.replace('Z','+00:00'))
                    t = dt.strftime('%H:%M')
                    fecha_real = dt.strftime('%Y-%m-%d')
                except:
                    t = dt_str[11:16] if len(dt_str)>16 else ''
                    try:
                        fecha_real = dt_str[:10]
                    except:
                        pass
            
            matches.append({
                "date": fecha_real,
                "time": t,
                "home": home_name,
                "away": away_name,
                "league": liga_name,
                "league_code": liga_code,
                "competition": liga_name,
                "status": status_type.get('name','NS'),
                "status_detail": status_type.get('detail',''),
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
    print(f"[fixture_sync] MULTI-LIGA FIX -> Trayendo 15 ligas para {requested_date} (hoy es {today_str})")

    all_matches = []

    for liga_code, liga_name in LIGAS_MUNDIALES:
        # Solo pedir fecha específica, no mezclar con hoy
        urls = [
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard?dates={date_nodash}",
        ]
        # Si es hoy, también probar sin fecha como fallback
        if requested_date == today_str:
            urls.append(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard")
        
        for url in urls:
            try:
                raw = get_json(url, timeout=5)
                if raw:
                    matches = _parse_espn(requested_date, raw, liga_code, liga_name)
                    if matches:
                        # Filtrar estrictamente por fecha solicitada
                        filtered = [m for m in matches if m['date'] == requested_date]
                        if filtered:
                            print(f"[fixture_sync] {liga_code} -> {len(filtered)} partidos para {requested_date}")
                            all_matches.extend(filtered)
                        else:
                            # Si no hay para esa fecha en esa liga, no agregar nada
                            if requested_date == today_str:
                                # Para hoy, si ESPN no trae fecha, agregar todo
                                all_matches.extend(matches)
                        break
            except Exception:
                continue

    if not all_matches:
        print(f"[fixture_sync] ESPN vacio para {requested_date}, probando TheSportsDB")
        url = THESPORTSDB.format(date=requested_date)
        raw = get_json(url, timeout=8)
        if raw and raw.get('events'):
            for ev in raw.get('events', []):
                try:
                    fecha_real = ev.get('dateEvent') or requested_date
                    if fecha_real != requested_date:
                        continue
                    hs = None
                    as_ = None
                    try:
                        hs = int(ev.get('intHomeScore')) if ev.get('intHomeScore') else None
                        as_ = int(ev.get('intAwayScore')) if ev.get('intAwayScore') else None
                    except:
                        pass
                    estado = 'PROGRAMADO'
                    st = str(ev.get('strStatus') or '').upper()
                    if any(k in st for k in ['FT', 'FINAL', 'AET', 'PEN']):
                        estado = 'FINALIZADO'
                    elif any(k in st for k in ['LIVE', '1H', '2H']):
                        estado = 'EN_JUEGO'
                    
                    all_matches.append({
                        "date": fecha_real,
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

    # Deduplicar por fecha+equipos+liga
    seen = set()
    unique = []
    for m in all_matches:
        key = f"{m['date']}_{m['home']}_{m['away']}_{m['league']}"
        if key not in seen:
            seen.add(key)
            unique.append(m)

    print(f"[fixture_sync] TOTAL MULTI-LIGA FIX para {requested_date}: {len(unique)} partidos - Fechas: {sorted(set([x['date'] for x in unique]))}")
    if unique:
        estados = {}
        for u in unique:
            estados[u['estado']] = estados.get(u['estado'], 0) + 1
        print(f"[fixture_sync] Estados: {estados}")

    _cache = {"date": requested_date, "data": unique, "ts": now}
    return unique

def sync_for_date(repo, date_str):
    start = time.time()
    # LIMPIEZA: borrar partidos viejos de esa fecha para no dejar basura como Toluca ficticio
    try:
        deleted = repo.delete_by_date(date_str)
        if deleted:
            print(f"[fixture_sync] Limpieza: borrados {deleted} partidos viejos de {date_str}")
    except Exception as e:
        print(f"[fixture_sync] No se pudo limpiar fecha {date_str}: {e}")
    
    matches = fetch_from_internet(date_str)
    count = repo.upsert_matches(matches) if matches else 0
    duration = int((time.time() - start)*1000)
    repo.log_sync('ESPN_MULTI_15LIGAS_FIX_V54', date_str, count, duration, 'OK' if matches else 'EMPTY')
    return matches
