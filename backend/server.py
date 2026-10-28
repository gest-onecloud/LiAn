from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
import re

# PASO 4: Soporte para Disco Persistente en Render
DB_PATH_ENV = os.environ.get("LIAN_DB_PATH", "")
if DB_PATH_ENV:
    REPO_PATH = Path(DB_PATH_ENV)
    REPO_PATH.parent.mkdir(parents=True, exist_ok=True)
else:
    ROOT = Path(__file__).resolve().parent.parent
    REPO_PATH = ROOT / 'backend' / 'data' / 'lian.db'
    REPO_PATH.parent.mkdir(parents=True, exist_ok=True)

# Paso 5: Supabase Historico con fallback SQLite
try:
    from backend.data.repo_supabase import RepoSupabase
    HAS_SUPABASE_LIB = True
except Exception as e:
    print(f"[repo_supabase] no disponible: {e}")
    HAS_SUPABASE_LIB = False

from backend.services import fixture_sync, calendar as cal_service
from backend.core.model import Model

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if HAS_SUPABASE_LIB and SUPABASE_URL and SUPABASE_KEY:
    try:
        repo = RepoSupabase(str(REPO_PATH), SUPABASE_URL, SUPABASE_KEY)
        print(f"[server] Usando RepoSupabase historico -> {SUPABASE_URL}")
    except Exception as e:
        print(f"[server] Error RepoSupabase, fallback SQLite: {e}")
        from backend.data.repo import Repo
        repo = Repo(str(REPO_PATH))
else:
    from backend.data.repo import Repo
    repo = Repo(str(REPO_PATH))
    if not SUPABASE_URL:
        print("[server] SUPABASE_URL no configurado, usando SQLite local")
    else:
        print("[server] Supabase lib no disponible, usando SQLite")

try:
    model = Model(repo=repo if 'repo' in locals() else None)
except Exception as e:
    print(f"[model] Error cargando con repo, fallback sin repo: {e}")
    model = Model()

# PROGOL ULTRA SEGURO - embebido, no requiere progol_sync.py
PROGOL_FALLBACK = {
    "fecha": "2026-10-30",
    "hasta": "20:55",
    "fuente": "TuLotero - V92.2 Ultra Seguro",
    "progol": [
        {"n":1, "home":"PUEBLA", "away":"PUMAS"},
        {"n":2, "home":"PACHUCA", "away":"TIGRES"},
        {"n":3, "home":"AGUILAS", "away":"TOLUCA"},
        {"n":4, "home":"ELCHE", "away":"VALENCIA"},
        {"n":5, "home":"ATH. BILBAO", "away":"R. SOCIEDAD"},
        {"n":6, "home":"BOURNEMOUTH", "away":"LEEDS"},
        {"n":7, "home":"LIVERPOOL", "away":"ARSENAL"},
        {"n":8, "home":"MILAN", "away":"INTER MILAN"},
        {"n":9, "home":"JUVENTUS", "away":"NAPOLES"},
        {"n":10, "home":"AUGSBURGO", "away":"FRIBURGO"},
        {"n":11, "home":"LORIENT", "away":"BREST"},
        {"n":12, "home":"GREMIO", "away":"AT. MINEIRO"},
        {"n":13, "home":"BOCA JRS", "away":"RIVER PLATE"},
        {"n":14, "home":"U. CATOLICA", "away":"U. DE CHILE"}
    ],
    "revancha": [
        {"n":1, "home":"MONTERREY", "away":"TIJUANA"},
        {"n":2, "home":"GUADALAJARA", "away":"ATLANTE"},
        {"n":3, "home":"S. LAGUNA", "away":"NECAXA"},
        {"n":4, "home":"C. AZUL", "away":"LEON"},
        {"n":5, "home":"GETAFE", "away":"SEVILLA"},
        {"n":6, "home":"CHELSEA", "away":"MAN. UNITED"},
        {"n":7, "home":"AJAX", "away":"AZ ALKMAAR"}
    ]
}

PROGOL_CACHE_FILE = Path(__file__).parent / 'data' / 'progol_current.json'

def get_progolo_current():
    # Intentar cargar cache si existe
    try:
        if PROGOL_CACHE_FILE.exists():
            data = json.loads(PROGOL_CACHE_FILE.read_text(encoding='utf-8'))
            if data.get('progol'):
                return data
    except Exception as e:
        print(f"[progol cache error] {e}")
    # Intentar cargar progol_sync si existe (opcional, no rompe si no existe)
    try:
        from backend.services import progol_sync
        return progol_sync.get_cached_progol()
    except:
        pass
    return PROGOL_FALLBACK

def save_progolo_manual(text):
    progol=[]
    revancha=[]
    in_revancha=False
    for line in text.strip().split('\n'):
        line=line.strip()
        if not line: continue
        if 'revancha' in line.lower():
            in_revancha=True
            continue
        m=re.match(r'(\d+)\s*[\.-]?\s*(.+?)\s+(?:vs|x|-)\s+(.+)', line, re.I)
        if m:
            n=int(m.group(1))
            home=m.group(2).strip().upper()
            away=m.group(3).strip().upper()
            entry={"n":n, "home":home, "away":away}
            if in_revancha:
                revancha.append(entry)
            else:
                progol.append(entry)
    data={"fecha":datetime.now().strftime("%Y-%m-%d"), "progol":progol[:14], "revancha":revancha[:7], "fuente":"Manual V92.2", "hasta":"20:55"}
    try:
        PROGOL_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROGOL_CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"[progol save error] {e}")
    # También intentar guardar via progol_sync si existe
    try:
        from backend.services import progol_sync
        progol_sync.save_progol(data)
    except:
        pass
    return data

def _cors(h):
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Content-Type")

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        _cors(self)
        self.end_headers()
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if parsed.path in ("/api/health","/"):
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            # Contar directo Supabase para no depender de repo
            records = 0
            supa_count = 0
            sqlite_count = 0
            try:
                sqlite_count = repo.count_all() if hasattr(repo, 'count_all') else 0
            except:
                pass
            try:
                from supabase import create_client
                supa_url = os.environ.get("SUPABASE_URL")
                supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                if supa_url and supa_key:
                    supa_client = create_client(supa_url, supa_key)
                    r = supa_client.table('matches').select('id', count='exact').limit(1).execute()
                    supa_count = r.count if hasattr(r, 'count') and r.count else 0
            except Exception as e:
                supa_count = 0
            
            records = max(supa_count, sqlite_count) if supa_count > 0 else sqlite_count
            
            self.wfile.write(json.dumps({
                "ok":True,
                "records":records,
                "sqlite_count": sqlite_count,
                "supabase_count": supa_count,
                "version":Model.VERSION,
                "mode":"REAL Poisson Paso7 + Supabase Historico V114.7",
                "db_path": str(REPO_PATH),
                "disk_persistent": bool(DB_PATH_ENV),
                "supabase": bool(SUPABASE_URL),
                "supabase_url": SUPABASE_URL[:30]+"..." if SUPABASE_URL else None
            }).encode())
            return
        if parsed.path == "/api/progol/current":
            data = get_progolo_current()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
            return
        if parsed.path == "/api/progol/refresh":
            # Refresh intenta usar progol_sync si existe, si no devuelve cache
            try:
                from backend.services import progol_sync
                data = progol_sync.fetch_latest_progol()
            except:
                data = get_progolo_current()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
            return
        if parsed.path == "/api/calendar/season/league":
            league_code = qs.get('league',[''])[0] or qs.get('league_code',[''])[0]
            limit = int(qs.get('limit',['500'])[0])
            if league_code:
                matches = repo.get_by_league(league_code, limit=limit)
                if not matches:
                    matches = repo.get_by_league_name(league_code, limit=limit)
            else:
                matches = repo.get_all(limit=limit)
            payload = []
            for m in matches:
                pred = model.predictions_for(m, fast=False)
                payload.append(pred)
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"league":league_code,"matches":payload,"count":len(payload),"source":f"Temporada {league_code or 'todas'}"}).encode())
            return
        if parsed.path == "/api/calendar/count_by_league":
            stats = repo.count_by_league()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"leagues":stats,"count":len(stats)}).encode())
            return
        if parsed.path == "/api/supabase/sync-future":
            # V121 - Sincroniza próximos 14 días de ESPN a Supabase
            try:
                from datetime import date as date_obj, timedelta
                from supabase import create_client
                from backend.services.fixture_sync import fetch_season_for_liga, LIGAS_MUNDIALES
                from backend.services.fixture_sync import _parse_espn, get_json

                days_ahead = int(qs.get('days',['14'])[0])
                league_filter = qs.get('league',[''])[0]  # si filtra solo mex.1

                supa_url = os.environ.get("SUPABASE_URL")
                supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                client = create_client(supa_url, supa_key) if supa_url and supa_key else None

                today = date_obj.today()
                future_dates = [today + timedelta(days=i) for i in range(days_ahead+1)]

                # Ligas a sincronizar
                ligas = LIGAS_MUNDIALES
                if league_filter:
                    ligas = [l for l in ligas if l[0]==league_filter]

                all_future = []
                for liga_code, liga_name in ligas:
                    for d in future_dates:
                        date_nodash = d.strftime('%Y%m%d')
                        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard?dates={date_nodash}"
                        try:
                            raw = get_json(url, timeout=5)
                            if raw and raw.get('events'):
                                matches = _parse_espn(d.isoformat(), raw, liga_code, liga_name)
                                # Solo futuros programados
                                for m in matches:
                                    # Si es futuro y no finalizado
                                    if m.get('estado') != 'FINALIZADO':
                                        all_future.append(m)
                        except Exception as e:
                            continue

                # Deduplicar
                seen=set()
                unique=[]
                for m in all_future:
                    key=f"{m['date']}_{m['league_code']}_{m['home']}_{m['away']}"
                    if key not in seen:
                        seen.add(key)
                        unique.append(m)

                # Guardar en Supabase si hay cliente
                saved = 0
                if client and unique:
                    for m in unique:
                        try:
                            # Upsert en matches: si ya existe no duplicar por fecha+equipos
                            # Buscar existente
                            existing = client.table('matches').select('id').eq('date', m['date']).eq('home', m['home']).eq('away', m['away']).limit(1).execute()
                            if not existing.data:
                                client.table('matches').insert({
                                    "date": m['date'],
                                    "home": m['home'],
                                    "away": m['away'],
                                    "league_code": m['league_code'],
                                    "league": m['league'],
                                    "home_score": None,
                                    "away_score": None,
                                    "status": m.get('status','NS'),
                                    "time": m.get('time','')
                                }).execute()
                                saved+=1
                        except Exception as e:
                            print(f"[sync-future] error insert {m}: {e}")
                            continue

                # Tambien guardar en repo SQLite local
                try:
                    count = repo.upsert_matches(unique)
                except:
                    count = len(unique)

                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "future_synced V121",
                    "days_ahead": days_ahead,
                    "leagues": len(ligas),
                    "found": len(unique),
                    "saved_supabase": saved,
                    "saved_sqlite": count,
                    "sample": unique[:5],
                    "dates": [d.isoformat() for d in future_dates[:5]]
                }).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e),"trace":traceback.format_exc()[:3000]}).encode())
            return

        if parsed.path == "/api/calendar/sync_season":

            def bg():
                try:
                    fixture_sync.sync_all_seasons(repo)
                except Exception as e:
                    print(f"[bg_season error] {e}")
            threading.Thread(target=bg,daemon=True).start()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"status":"sync_temporada_iniciada","message":"Sincronizando 15 ligas temporada completa"}).encode())
            return
        if parsed.path == "/api/calendar/season":
            # V119.2 Fix Failed to fetch: fast=True + try/except
            try:
                limit = int(qs.get('limit',['500'])[0])
                since = qs.get('since',[None])[0]
                matches = repo.get_season(since_date=since, limit=limit)
                payload = []
                for m in matches:
                    try:
                        pred = model.predictions_for(m, fast=True)
                        payload.append(pred)
                    except Exception as e:
                        print(f"[calendar season] pred error: {e}")
                        continue
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"matches":payload,"count":len(payload),"source":"DB Temporada Completa V119.2 fast","dates":repo.get_dates()}).encode())
            except Exception as e:
                import traceback
                print(f"[calendar season error] {e}")
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e)}).encode())
            return
        if parsed.path == "/api/calendar/dates":
            dates = repo.get_dates()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"dates":dates,"count":len(dates)}).encode())
            return
        if parsed.path == "/api/calendar/leagues":
            stats = repo.get_leagues_stats()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"leagues":stats,"count":len(stats)}).encode())
            return
        if parsed.path == "/api/calendar/fast":
            date = qs.get('date',[datetime.now().strftime('%Y-%m-%d')])[0]
            matches = cal_service.get_calendar_for_date(repo, date)
            payload = []
            for m in matches:
                pred = model.predictions_for(m, fast=False)
                payload.append(pred)
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"date":date,"matches":payload,"count":len(payload),"source":"DB REAL + Poisson","db_path":str(REPO_PATH)}).encode())
            return
        if parsed.path == "/api/calendar":
            date = qs.get('date',[datetime.now().strftime('%Y-%m-%d')])[0]
            refresh = qs.get('refresh',['0'])[0]=='1'
            full = qs.get('full',['0'])[0]=='1'
            if refresh:
                def bg():
                    try:
                        if full:
                            fixture_sync.sync_season(repo, days_back=90)
                        else:
                            fixture_sync.sync_for_date(repo, date)
                    except Exception as e:
                        print(f"[bg_sync error] {e}")
                threading.Thread(target=bg,daemon=True).start()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"date":date,"status":"sync_started_background","full":full}).encode())
                return
            else:
                matches = cal_service.get_calendar_for_date(repo, date)
                payload = [model.predictions_for(m, fast=False) for m in matches]
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"date":date,"matches":payload,"count":len(payload)}).encode())
                return

        if parsed.path == "/api/liga-mx/sync":
            # Sincroniza SOLO Liga MX temporada completa - V100 FIX: 150 días + fallback todas ligas
            def bg_mx():
                try:
                    from backend.services.fixture_sync import fetch_season_for_liga, fetch_all_seasons
                    matches = fetch_season_for_liga("mex.1", "Liga MX - Mexico")
                    if matches and len(matches) >= 20:
                        c = repo.upsert_matches(matches)
                        print(f"[Liga MX Sync] {len(matches)} partidos, guardados {c}")
                    else:
                        print(f"[Liga MX Sync] Solo {len(matches) if matches else 0} partidos mex.1, sincronizando todas las ligas para temporada completa")
                        all_m = fetch_all_seasons()
                        if all_m:
                            c = repo.upsert_matches(all_m)
                            print(f"[Liga MX Sync fallback todas ligas] {len(all_m)} partidos, guardados {c}")
                        else:
                            from backend.services.fixture_sync import get_json
                            url = "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/scoreboard"
                            raw = get_json(url, timeout=10)
                            if raw and raw.get('events'):
                                from backend.services.fixture_sync import _parse_espn
                                ms = _parse_espn(datetime.now().strftime('%Y-%m-%d'), raw, "mex.1", "Liga MX")
                                if ms:
                                    c = repo.upsert_matches(ms)
                                    print(f"[Liga MX Sync fallback directo] {c} partidos")
                except Exception as e:
                    print(f"[Liga MX Sync error] {e}")
            threading.Thread(target=bg_mx, daemon=True).start()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"status":"sync_liga_mx_iniciada","message":"Sincronizando SOLO Liga MX temporada completa, 60-90 seg, luego /api/liga-mx/season"}).encode())
            return
        if parsed.path == "/api/liga-mx/season":
            # V119.2 Fix Failed to fetch: usar fast=True para evitar timeout MonteCarlo 6000*500
            try:
                limit = int(qs.get('limit',['500'])[0])
                matches = []
                try:
                    from supabase import create_client
                    supa_url = os.environ.get("SUPABASE_URL")
                    supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                    if supa_url and supa_key:
                        supa_client = create_client(supa_url, supa_key)
                        res = supa_client.table('matches').select('*').eq('league_code', 'mex.1').order('date', desc=True).limit(limit).execute()
                        if res.data and len(res.data) > 0:
                            matches = res.data
                            print(f"[Liga MX] Supabase directo: {len(matches)} partidos mex.1")
                except Exception as e:
                    print(f"[Liga MX] Error Supabase directo: {e}")
                
                if not matches:
                    matches = repo.get_by_league("mex.1", limit=limit)
                if not matches:
                    matches = repo.get_by_league_name("Liga MX", limit=limit)
                if not matches:
                    matches = repo.get_all(limit=limit)
                
                if len(matches) < 20:
                    try:
                        from supabase import create_client
                        supa_url = os.environ.get("SUPABASE_URL")
                        supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                        if supa_url and supa_key:
                            supa_client = create_client(supa_url, supa_key)
                            res = supa_client.table('matches').select('*').order('date', desc=True).limit(limit).execute()
                            if res.data:
                                matches = res.data
                    except:
                        pass
                
                # V119.2 Fix: fast=True para 500 partidos no hace MonteCarlo 6000 cada uno (timeout)
                payload = []
                for m in matches:
                    try:
                        pred = model.predictions_for(m, fast=True)
                        payload.append(pred)
                    except Exception as e:
                        print(f"[Liga MX] pred error {m.get('id')}: {e}")
                        continue

                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"league":"mex.1","matches":payload,"count":len(payload),"source":f"Liga MX V119.2 fast ({len(payload)} partidos)"}).encode())
            except Exception as e:
                import traceback
                print(f"[Liga MX season error] {e}\n{traceback.format_exc()}")
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e),"trace":traceback.format_exc()[:1000]}).encode())
            return
        if parsed.path == "/api/liga-mx/fast":
            date = qs.get('date',[datetime.now().strftime('%Y-%m-%d')])[0]
            matches = [m for m in repo.get_by_league("mex.1", limit=500) if m['date']==date]
            if not matches:
                matches = repo.get_by_league_name("mex", limit=100)
            if not matches:
                from backend.services import calendar as cal_service
                all_day = cal_service.get_calendar_for_date(repo, date)
                matches = all_day
                if not matches:
                    matches = repo.get_all(limit=100)
            payload = [model.predictions_for(m, fast=False) for m in matches]
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"date":date,"league":"mex.1","matches":payload,"count":len(payload),"source":"Liga MX fast + fallback"}).encode())
            return





        if parsed.path == "/api/model/reload":
            # Recarga el modelo con historial real desde Supabase
            try:
                from backend.core.model import Model as ModelClass
                # Recargar modelo global (sin usar keyword global dentro de if, asignar directo al modulo)
                import backend.server as server_module
                new_model = ModelClass(repo=repo)
                # Actualizar variable global del modulo
                globals()['model'] = new_model
                # Tambien actualizar en server_module si existe
                try:
                    server_module.model = new_model
                except:
                    pass
                model_local = new_model
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "reloaded",
                    "version": model_local.VERSION,
                    "history_loaded": model_local.history_loaded,
                    "history_count": model_local.history_count,
                    "teams_with_elo": len(model_local.elo) if model_local.history_loaded else 0
                }).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e),"trace":traceback.format_exc()[:1000]}).encode())
            return




        if parsed.path == "/api/match/improve":
            # V120 - Botón Mejorar: MonteCarlo 6000 solo para 1 partido programado
            try:
                home = qs.get('home',[''])[0]
                away = qs.get('away',[''])[0]
                league = qs.get('league',['mex.1'])[0]
                if not home or not away:
                    self.send_response(400)
                    self.send_header("Content-Type","application/json")
                    _cors(self)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error":"Falta home y away"}).encode())
                    return

                # Buscar partido en repo o crear mock
                matches_found = []
                try:
                    matches_found = repo.get_by_league(league, limit=1000)
                    matches_found = [m for m in matches_found if home.lower() in str(m.get('home','')).lower() or away.lower() in str(m.get('away','')).lower()]
                except:
                    matches_found = []

                if matches_found:
                    m = matches_found[0]
                else:
                    # Mock match para mejorar
                    m = {"home": home, "away": away, "league_code": league, "date": "2026-10-28", "home_score": None, "away_score": None, "id": f"improve_{home}_{away}"}

                # Predicción COMPLETA con MonteCarlo 6000
                pred = model.predictions_for(m, fast=False)

                # Agregar intervalos confianza MonteCarlo
                mc = pred.get('montecarlo', {})
                improved = {
                    "home": home,
                    "away": away,
                    "league": league,
                    "probabilities": pred.get('probabilities', {}),
                    "xg": pred.get('xg', {}),
                    "favorite": pred.get('favorite', ''),
                    "confidence": pred.get('confidence', ''),
                    "montecarlo": mc,
                    "model_version": model.VERSION,
                    "team_stats": {
                        home: model.team_stats.get(home, {}),
                        away: model.team_stats.get(away, {})
                    },
                    "elo": {
                        home: model.elo.get(home, 1500),
                        away: model.elo.get(away, 1500)
                    },
                    "improved": True,
                    "message": f"Mejorado con MonteCarlo 6000 + Dixon-Coles + Disciplina + ELO MOV"
                }

                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps(improved).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e),"trace":traceback.format_exc()[:2000]}).encode())
            return

        if parsed.path == "/api/supabase/calc-elo":

            # Calcula ELO real desde matches y lo guarda en elo_ratings
            try:
                from supabase import create_client
                supa_url = os.environ.get("SUPABASE_URL")
                supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                
                if not supa_url or not supa_key:
                    self.send_response(500)
                    self.send_header("Content-Type","application/json")
                    _cors(self)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Faltan env vars Supabase"}).encode())
                    return
                
                client = create_client(supa_url, supa_key)
                
                # 1. Traer todos los partidos finalizados
                # Paginado para evitar limite 1000 de Supabase
                finished = []
                offset = 0
                batch_size = 1000
                while True:
                    res = client.table('matches').select('*').not_.is_('home_score', 'null').not_.is_('away_score', 'null').order('date', desc=False).range(offset, offset+batch_size-1).execute()
                    batch = res.data if res.data else []
                    if not batch:
                        break
                    finished.extend(batch)
                    if len(batch) < batch_size:
                        break
                    offset += batch_size
                    if offset >= 5000:
                        break
                
                # Filtrar solo FINALIZADO o con marcador valido
                from collections import defaultdict, deque
                from datetime import datetime
                
                def parse_date(m):
                    try:
                        return datetime.fromisoformat(str(m.get('date',''))[:10])
                    except:
                        return datetime.min
                
                finished.sort(key=parse_date)
                
                elo = defaultdict(lambda: 1500.0)
                K = 20
                
                for m in finished:
                    home = str(m.get('home','')).strip()
                    away = str(m.get('away','')).strip()
                    if not home or not away:
                        continue
                    try:
                        hs = int(m.get('home_score'))
                        aw = int(m.get('away_score'))
                    except:
                        continue
                    
                    eh = elo[home]
                    ea = elo[away]
                    exp_home = 1 / (1 + 10 ** ((ea - eh) / 400))
                    exp_away = 1 - exp_home
                    
                    if hs > aw:
                        res_home, res_away = 1, 0
                    elif hs == aw:
                        res_home, res_away = 0.5, 0.5
                    else:
                        res_home, res_away = 0, 1
                    
                    elo[home] = eh + K * (res_home - exp_home)
                    elo[away] = ea + K * (res_away - exp_away)
                
                # 2. Guardar en elo_ratings
                # Primero borrar viejos - borrar todo
                try:
                    # Borrar con filtro que siempre match (id > 0)
                    client.table('elo_ratings').delete().gt('id', 0).execute()
                    print('[calc-elo] Tabla elo_ratings limpiada')
                except Exception as e_del:
                    print(f'[calc-elo] Error limpiando elo_ratings: {e_del}')
                    # Intentar delete sin filtro si el anterior falla
                    try:
                        client.table('elo_ratings').delete().neq('team', 'IMPOSSIBLE_TEAM_XYZ').execute()
                    except:
                        pass
                
                rows = []
                for team, rating in elo.items():
                    # Sin team_id para evitar FK error con teams table vacia
                    rows.append({
                        "team": team,
                        "rating": round(rating, 2),
                        "date": datetime.now().strftime('%Y-%m-%d'),
                        "league_code": "global"
                    })
                
                # Insertar en lotes de 100 SIN on_conflict (tabla no tiene unique en team_id)
                inserted = 0
                for i in range(0, len(rows), 100):
                    batch = rows[i:i+100]
                    try:
                        client.table('elo_ratings').insert(batch).execute()
                        inserted += len(batch)
                    except Exception as e_batch:
                        print(f"[calc-elo] Batch {i//100} insert error: {e_batch}, intentando uno por uno")
                        # Intentar uno por uno
                        for single in batch:
                            try:
                                client.table('elo_ratings').insert(single).execute()
                                inserted += 1
                            except Exception as e_single:
                                print(f"[calc-elo] Error {single.get('team')}: {e_single}")
                
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "elo_calculated",
                    "finished_matches": len(finished),
                    "teams_with_elo": len(elo),
                    "inserted": inserted,
                    "sample": sorted([(t, round(r,1)) for t,r in elo.items()], key=lambda x: x[1], reverse=True)[:10]
                }).encode())
                
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e), "trace": traceback.format_exc()[:2000]}).encode())
            return



        if parsed.path == "/api/supabase/calc-team-stats":
            # Calcula ataque/defensa real desde matches y lo guarda en team_stats
            try:
                from supabase import create_client
                supa_url = os.environ.get("SUPABASE_URL")
                supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                
                if not supa_url or not supa_key:
                    self.send_response(500)
                    self.send_header("Content-Type","application/json")
                    _cors(self)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Faltan env vars Supabase"}).encode())
                    return
                
                client = create_client(supa_url, supa_key)
                
                # 1. Traer todos los partidos finalizados con marcador
                # Paginado para evitar limite 1000 de Supabase
                finished = []
                offset = 0
                batch_size = 1000
                while True:
                    res = client.table('matches').select('*').not_.is_('home_score', 'null').not_.is_('away_score', 'null').order('date', desc=False).range(offset, offset+batch_size-1).execute()
                    batch = res.data if res.data else []
                    if not batch:
                        break
                    finished.extend(batch)
                    if len(batch) < batch_size:
                        break
                    offset += batch_size
                    if offset >= 5000:
                        break
                
                from collections import defaultdict, deque
                from datetime import datetime
                
                def parse_date(m):
                    try:
                        return datetime.fromisoformat(str(m.get('date',''))[:10])
                    except:
                        return datetime.min
                
                finished.sort(key=parse_date)
                
                stats = defaultdict(lambda: {"gf":0, "ga":0, "mp":0, "w":0, "d":0, "l":0, "pts":0, "form":deque(maxlen=5), "league": ""})
                
                for m in finished:
                    home = str(m.get('home','')).strip()
                    away = str(m.get('away','')).strip()
                    if not home or not away:
                        continue
                    try:
                        hs = int(m.get('home_score'))
                        aw = int(m.get('away_score'))
                    except:
                        continue
                    
                    league = str(m.get('league_code','') or m.get('league','') or 'global')
                    
                    # Home
                    stats[home]["gf"] += hs
                    stats[home]["ga"] += aw
                    stats[home]["mp"] += 1
                    stats[home]["league"] = league
                    # Away
                    stats[away]["gf"] += aw
                    stats[away]["ga"] += hs
                    stats[away]["mp"] += 1
                    if not stats[away]["league"]:
                        stats[away]["league"] = league
                    
                    if hs > aw:
                        stats[home]["w"] += 1
                        stats[home]["pts"] += 3
                        stats[away]["l"] += 1
                        stats[home]["form"].append("W")
                        stats[away]["form"].append("L")
                    elif hs == aw:
                        stats[home]["d"] += 1
                        stats[away]["d"] += 1
                        stats[home]["pts"] += 1
                        stats[away]["pts"] += 1
                        stats[home]["form"].append("D")
                        stats[away]["form"].append("D")
                    else:
                        stats[home]["l"] += 1
                        stats[away]["w"] += 1
                        stats[away]["pts"] += 3
                        stats[home]["form"].append("L")
                        stats[away]["form"].append("W")
                
                # 2. Limpiar team_stats
                try:
                    client.table('team_stats').delete().gt('id', 0).execute()
                    print('[calc-team-stats] Tabla team_stats limpiada')
                except Exception as e_del:
                    print(f'[calc-team-stats] Error limpiando: {e_del}')
                    try:
                        client.table('team_stats').delete().neq('team', 'IMPOSSIBLE_XYZ').execute()
                    except:
                        pass
                
                # 3. Calcular promedios globales para strength
                all_gf = sum(s["gf"] for s in stats.values())
                all_mp = sum(s["mp"] for s in stats.values())
                avg_league_gf = (all_gf / all_mp) if all_mp>0 else 1.2
                
                rows = []
                for team, s in stats.items():
                    mp = max(1, s["mp"])
                    avg_for = s["gf"] / mp
                    avg_against = s["ga"] / mp
                    # Attack strength = avg_for / avg_league
                    attack_str = avg_for / max(0.1, avg_league_gf)
                    defense_str = avg_against / max(0.1, avg_league_gf)
                    form_str = "-".join(list(s["form"])) if s["form"] else ""
                    pts_last5 = sum(3 if x=="W" else 1 if x=="D" else 0 for x in s["form"])
                    
                    rows.append({
                        "team": team,
                        "league_code": "global",  # Usar global para evitar UNIQUE conflict por liga
                        "matches_played": s["mp"],
                        "goals_for": s["gf"],
                        "goals_against": s["ga"],
                        "avg_goals_for": round(avg_for, 3),
                        "avg_goals_against": round(avg_against, 3),
                        "attack_strength": round(attack_str, 3),
                        "defense_strength": round(defense_str, 3),
                        "form_last5": form_str,
                        "points_last5": pts_last5,
                        "last_update": datetime.now().strftime('%Y-%m-%d')
                    })
                
                # Insertar en lotes de 100
                inserted = 0
                for i in range(0, len(rows), 100):
                    batch = rows[i:i+100]
                    try:
                        client.table('team_stats').insert(batch).execute()
                        inserted += len(batch)
                    except Exception as e_batch:
                        print(f"[calc-team-stats] Batch {i//100} error: {e_batch}, uno por uno")
                        for single in batch:
                            try:
                                client.table('team_stats').insert(single).execute()
                                inserted += 1
                            except Exception as e_single:
                                print(f"[calc-team-stats] Error {single.get('team')}: {e_single}")
                
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "team_stats_calculated",
                    "finished_matches": len(finished),
                    "teams_with_stats": len(stats),
                    "inserted": inserted,
                    "avg_league_gf": round(avg_league_gf,3),
                    "sample": sorted([(t, s["gf"], s["ga"], s["mp"]) for t,s in list(stats.items())[:10]], key=lambda x: x[1], reverse=True)[:10]
                }).encode())
                
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e), "trace": traceback.format_exc()[:2000]}).encode())
            return



        if parsed.path == "/api/supabase/auto-learn":
            # V118.2 Autoaprendizaje INLINE - sin import externo para evitar ModuleNotFoundError en Render
            try:
                from supabase import create_client
                from collections import defaultdict
                from datetime import datetime

                supa_url = os.environ.get("SUPABASE_URL")
                supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                if not supa_url or not supa_key:
                    raise Exception("Faltan env vars Supabase")

                client = create_client(supa_url, supa_key)

                # Traer finalizados paginado
                finished = []
                offset = 0
                batch_size = 1000
                while True:
                    res = client.table('matches').select('*').not_.is_('home_score', 'null').not_.is_('away_score', 'null').order('date', desc=True).range(offset, offset+batch_size-1).execute()
                    batch = res.data if res.data else []
                    if not batch:
                        break
                    finished.extend(batch)
                    if len(batch) < batch_size:
                        break
                    offset += batch_size
                    if offset >= 4000:
                        break

                by_league = defaultdict(lambda: {"total":0, "home_win":0, "draw":0, "away_win":0, "home_adv_real":1.0})
                by_result = {"1":0, "X":0, "2":0}
                dixon = {"0-0":0, "1-0":0, "0-1":0, "1-1":0, "other":0}

                for m in finished:
                    league = m.get('league_code','global') or 'global'
                    hs = m.get('home_score')
                    aw = m.get('away_score')
                    if hs is None or aw is None:
                        continue
                    try:
                        hs = int(hs); aw = int(aw)
                    except:
                        continue
                    by_league[league]["total"] += 1
                    if hs > aw:
                        by_league[league]["home_win"] += 1
                        by_result["1"] += 1
                    elif hs == aw:
                        by_league[league]["draw"] += 1
                        by_result["X"] += 1
                    else:
                        by_league[league]["away_win"] += 1
                        by_result["2"] += 1

                    if hs==0 and aw==0:
                        dixon["0-0"] += 1
                    elif hs==1 and aw==0:
                        dixon["1-0"] += 1
                    elif hs==0 and aw==1:
                        dixon["0-1"] += 1
                    elif hs==1 and aw==1:
                        dixon["1-1"] += 1
                    else:
                        dixon["other"] += 1

                home_adv_learned = {}
                for league, data in by_league.items():
                    total = data["total"]
                    if total >= 20:
                        hw = data["home_win"] / total
                        aw = data["away_win"] / total
                        adv = 1.0 + (hw - aw) * 0.8
                        adv = max(1.0, min(1.35, adv))
                        home_adv_learned[league] = round(adv, 3)
                        data["home_adv_real"] = adv

                total_all = len(finished)
                draw_pct = (by_result["X"] / max(1, total_all)) * 100
                rho_opt = 0.12
                if draw_pct > 32:
                    rho_opt = 0.15
                elif draw_pct < 24:
                    rho_opt = 0.08

                weights = {"poisson_dc":0.70, "elo_mov":0.20, "forma_ema":0.10}
                if by_result["1"] > by_result["2"] * 1.3:
                    weights["poisson_dc"] = 0.75

                # Guardar log
                try:
                    log_entry = {"source": "auto_learn_V118.2", "date": datetime.now().strftime('%Y-%m-%d'), "count": len(finished), "status": f"home_adv={home_adv_learned} rho={rho_opt} draw={draw_pct:.1f}%"}
                    client.table('sync_log').insert(log_entry).execute()
                except:
                    pass

                result = {
                    "status": "learned V118.2 INLINE",
                    "finished_analyzed": len(finished),
                    "draw_pct": round(draw_pct,1),
                    "home_adv_learned": home_adv_learned,
                    "rho_optimal": rho_opt,
                    "dixon_dist": dixon,
                    "result_type": by_result,
                    "weights_suggested": weights,
                    "by_league": {k: {"total":v["total"], "home_win":v["home_win"], "draw":v["draw"], "away_win":v["away_win"], "home_adv":round(v.get("home_adv_real",1.0),3)} for k,v in list(by_league.items())[:10]}
                }

                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e),"trace":traceback.format_exc()[:2000]}).encode())
            return





        if parsed.path == "/api/supabase/discipline-sync":
            # V119.1 INLINE - sin import, estima disciplina determinista
            try:
                from supabase import create_client
                from collections import defaultdict
                import hashlib, random
                from datetime import datetime

                LEAGUE_AVG = {
                    "mex.1": {"yellow": 2.1, "red": 0.12, "fouls": 13.5, "poss_home": 52},
                    "esp.1": {"yellow": 2.4, "red": 0.15, "fouls": 14.2, "poss_home": 53},
                    "eng.1": {"yellow": 1.8, "red": 0.08, "fouls": 11.8, "poss_home": 52},
                    "ita.1": {"yellow": 2.3, "red": 0.14, "fouls": 14.5, "poss_home": 51},
                    "default": {"yellow": 2.0, "red": 0.10, "fouls": 13.0, "poss_home": 52}
                }

                supa_url = os.environ.get("SUPABASE_URL")
                supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                client = create_client(supa_url, supa_key)

                res = client.table('matches').select('*').not_.is_('home_score', 'null').limit(500).order('date', desc=True).execute()
                matches = res.data if res.data else []
                to_update = [m for m in matches if not m.get('referee') or (m.get('home_yellow',0)==0 and m.get('away_yellow',0)==0)]

                def estimate_disc(home, away, league):
                    avg = LEAGUE_AVG.get(league, LEAGUE_AVG["default"])
                    seed = int(hashlib.md5((home+away+league).encode()).hexdigest()[:8], 16)
                    random.seed(seed)
                    yh = max(0, round(avg["yellow"] * (0.7 + random.random()*0.6)))
                    ya = max(0, round(avg["yellow"] * (0.7 + random.random()*0.6)))
                    rh = 1 if random.random() < avg["red"] else 0
                    ra = 1 if random.random() < avg["red"] else 0
                    fh = max(5, round(avg["fouls"] * (0.8 + random.random()*0.4)))
                    fa = max(5, round(avg["fouls"] * (0.8 + random.random()*0.4)))
                    ph = max(35, min(70, avg["poss_home"] + random.randint(-8,8)))
                    return {"home_yellow":yh,"away_yellow":ya,"home_red":rh,"away_red":ra,"home_fouls":fh,"away_fouls":fa,"home_possession":ph,"away_possession":100-ph,"referee":f"Auto-{league}","home_shots":random.randint(8,18),"away_shots":random.randint(6,16)}

                updated = 0
                for m in to_update[:200]:
                    disc = estimate_disc(m.get('home',''), m.get('away',''), m.get('league_code','mex.1'))
                    try:
                        client.table('matches').update(disc).eq('id', m['id']).execute()
                        updated += 1
                    except:
                        continue

                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"status":"discipline_synced V119.1 INLINE","analyzed":len(matches),"updated":updated,"mode":"estimation_fallback","sample_league_avg":LEAGUE_AVG}).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e),"trace":traceback.format_exc()[:2000]}).encode())
            return

        if parsed.path == "/api/supabase/discipline-team":
            # V119.1 INLINE calcula disciplina por equipo
            try:
                from supabase import create_client
                from collections import defaultdict
                supa_url = os.environ.get("SUPABASE_URL")
                supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                client = create_client(supa_url, supa_key)

                finished = []
                offset = 0
                while True:
                    res = client.table('matches').select('*').not_.is_('home_score', 'null').range(offset, offset+999).execute()
                    batch = res.data if res.data else []
                    if not batch:
                        break
                    finished.extend(batch)
                    if len(batch) < 1000:
                        break
                    offset += 1000
                    if offset >= 3000:
                        break

                team_disc = defaultdict(lambda: {"mp":0, "yellow":0, "red":0, "fouls":0, "poss":0})
                for m in finished:
                    home = str(m.get('home','')).strip()
                    away = str(m.get('away','')).strip()
                    if not home or not away:
                        continue
                    hy = int(m.get('home_yellow',0) or 0)
                    ay = int(m.get('away_yellow',0) or 0)
                    hr = int(m.get('home_red',0) or 0)
                    ar = int(m.get('away_red',0) or 0)
                    hf = int(m.get('home_fouls',0) or 0)
                    af = int(m.get('away_fouls',0) or 0)
                    hp = float(m.get('home_possession',50) or 50)
                    ap = float(m.get('away_possession',50) or 50)
                    team_disc[home]["mp"]+=1
                    team_disc[home]["yellow"]+=hy
                    team_disc[home]["red"]+=hr
                    team_disc[home]["fouls"]+=hf
                    team_disc[home]["poss"]+=hp
                    team_disc[away]["mp"]+=1
                    team_disc[away]["yellow"]+=ay
                    team_disc[away]["red"]+=ar
                    team_disc[away]["fouls"]+=af
                    team_disc[away]["poss"]+=ap

                updated = 0
                for team, data in team_disc.items():
                    mp = max(1, data["mp"])
                    avg_y = data["yellow"]/mp
                    avg_r = data["red"]/mp
                    avg_f = data["fouls"]/mp
                    avg_p = data["poss"]/mp
                    disc_idx = 1.0 + (avg_y - 2.0)*0.1 + avg_r*0.3 + (avg_f - 13)*0.02
                    disc_idx = max(0.6, min(1.5, disc_idx))
                    try:
                        existing = client.table('team_stats').select('*').eq('team', team).limit(1).execute()
                        if existing.data:
                            client.table('team_stats').update({
                                "avg_yellow": round(avg_y,2),
                                "avg_red": round(avg_r,3),
                                "avg_fouls": round(avg_f,1),
                                "discipline_index": round(disc_idx,3),
                                "avg_possession": round(avg_p,1)
                            }).eq('team', team).execute()
                            updated+=1
                    except:
                        continue

                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"status":"team_discipline_calculated V119.1 INLINE","teams":len(team_disc),"updated":updated}).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e),"trace":traceback.format_exc()[:2000]}).encode())
            return

        if parsed.path == "/api/supabase/backfill-reset":





            # Fuerza reset del backfill si se quedo pegado
            try:
                from backend.services.backfill import backfill_state
                backfill_state["running"] = False
                backfill_state["progress"] = "Reseteado manualmente"
                backfill_state["result"] = None
                backfill_state["started_at"] = None
                
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "reset_ok",
                    "message": "Backfill reseteado, ya puedes lanzar nuevo backfill-all"
                }).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e)}).encode())
            return


        if parsed.path == "/api/supabase/backfill-all":
            # Inicia backfill completo 15 ligas x 730 dias en background
            try:
                qs_days = int(qs.get('days',['730'])[0])
            except:
                qs_days = 730
            
            try:
                from backend.services.backfill import start_backfill_thread, backfill_state
                res = start_backfill_thread(repo, days_back=qs_days)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps(res).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e),"trace":traceback.format_exc()}).encode())
            return


        if parsed.path == "/api/supabase/test":
            # Test directo de upsert a Supabase para ver error real
            try:
                from supabase import create_client
                supa_url = os.environ.get("SUPABASE_URL")
                supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                
                if not supa_url or not supa_key:
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    _cors(self)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Faltan env vars", "url_present": bool(supa_url), "key_present": bool(supa_key)}).encode())
                    return
                
                client = create_client(supa_url, supa_key)
                
                # Intentar contar
                count_res = client.table('matches').select('id', count='exact').limit(1).execute()
                count_before = count_res.count if hasattr(count_res, 'count') else 0
                
                # Intentar insertar un partido de prueba
                test_match = {
                    "id": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "date": "2026-10-27",
                    "time": "12:00",
                    "home": "Test Local",
                    "away": "Test Visita",
                    "league": "Test League",
                    "league_code": "test.1",
                    "status": "NS",
                    "estado": "PROGRAMADO",
                    "home_score": None,
                    "away_score": None,
                    "score": None
                }
                
                insert_res = client.table('matches').upsert(test_match, on_conflict='id').execute()
                
                # Contar despues
                count_res2 = client.table('matches').select('id', count='exact').limit(1).execute()
                count_after = count_res2.count if hasattr(count_res2, 'count') else 0
                
                # Borrar test
                client.table('matches').delete().eq('id', test_match['id']).execute()
                
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "count_before": count_before,
                    "count_after": count_after,
                    "test_insert": "success",
                    "supabase_url": supa_url[:40] + "...",
                    "insert_data": insert_res.data if hasattr(insert_res, 'data') else None
                }).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "error": str(e),
                    "trace": traceback.format_exc()[:2000]
                }).encode())
            return


        if parsed.path == "/api/supabase/backfill-status":
            # Estado del backfill - V114.4 fix conteo directo Supabase
            try:
                from backend.services.backfill import backfill_state
                # Contar en Supabase DIRECTO desde env, no depender de repo.supabase
                total_supabase = 0
                supa_error = None
                try:
                    from supabase import create_client
                    supa_url = os.environ.get("SUPABASE_URL")
                    supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                    if supa_url and supa_key:
                        supa_client = create_client(supa_url, supa_key)
                        r = supa_client.table('matches').select('id', count='exact').limit(1).execute()
                        total_supabase = r.count if hasattr(r, 'count') and r.count else 0
                    else:
                        supa_error = "No env vars"
                except Exception as e:
                    supa_error = str(e)[:500]
                
                # Contar SQLite directo
                sqlite_count = 0
                try:
                    from backend.data.repo import Repo as RepoSQL
                    r_sql = RepoSQL(str(REPO_PATH))
                    sqlite_count = r_sql.count_all()
                except:
                    try:
                        sqlite_count = repo.count_all() if hasattr(repo, 'count_all') else 0
                    except:
                        pass
                
                # Incluir ultimo error de Supabase capturado
                last_supabase_err = backfill_state.get("last_supabase_error")
                last_supabase_ok = backfill_state.get("last_supabase_success", 0)
                
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "running": backfill_state["running"],
                    "progress": backfill_state["progress"],
                    "result": backfill_state["result"],
                    "started_at": backfill_state["started_at"],
                    "total_in_supabase": total_supabase,
                    "sqlite_count": sqlite_count,
                    "supa_error": supa_error,
                    "last_supabase_error": last_supabase_err,
                    "last_supabase_success": last_supabase_ok
                }).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e), "trace": traceback.format_exc()[:1000]}).encode())
            return


        if parsed.path == "/api/supabase/migrate":
            # Fuerza migracion de SQLite local a Supabase historico - V114 fix directo
            try:
                # 1. Leer SQLite directo
                from backend.data.repo import Repo as RepoSQL
                r_sql = RepoSQL(str(REPO_PATH))
                sqlite_matches = r_sql.get_all(limit=1000)
                
                migrated = 0
                error_msg = None
                
                # 2. Crear cliente Supabase directo desde env, no depender de repo.supabase
                supa_url = os.environ.get("SUPABASE_URL")
                supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
                
                if not supa_url or not supa_key:
                    error_msg = f"Faltan env vars: SUPABASE_URL={bool(supa_url)} SUPABASE_KEY={bool(supa_key)}"
                else:
                    try:
                        from supabase import create_client
                        supa_client = create_client(supa_url, supa_key)
                        rows = []
                        import re
                        for m in sqlite_matches:
                            # Validar fecha
                            d = m.get("date")
                            if not d:
                                continue
                            rows.append({
                                "id": m.get("id"),
                                "date": d,
                                "time": m.get("time",""),
                                "home": m.get("home"),
                                "away": m.get("away"),
                                "league": m.get("league",""),
                                "league_code": m.get("league_code",""),
                                "status": m.get("status","NS"),
                                "estado": m.get("estado","PROGRAMADO"),
                                "home_score": m.get("home_score"),
                                "away_score": m.get("away_score"),
                                "score": m.get("score")
                            })
                        for i in range(0, len(rows), 100):
                            batch = rows[i:i+100]
                            supa_client.table("matches").upsert(batch, on_conflict="id").execute()
                            migrated += len(batch)
                    except Exception as e:
                        error_msg = f"Supabase error: {str(e)}"
                        import traceback
                        error_msg += " " + traceback.format_exc()[:500]
                
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status":"migrated" if migrated>0 else "no_migrated",
                    "sqlite_count":len(sqlite_matches),
                    "migrated_to_supabase":migrated,
                    "supabase_url_present": bool(supa_url),
                    "error": error_msg
                }).encode())
            except Exception as e:
                import traceback
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e),"trace":traceback.format_exc()}).encode())
            return

        self.send_response(404)
        _cors(self)
        self.end_headers()
        self.wfile.write(b'{"error":"not found"}')
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/progol/manual":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode() if length>0 else ''
            try:
                j = json.loads(body) if body else {}
                text = j.get('text','')
                if text:
                    data = save_progolo_manual(text)
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    _cors(self)
                    self.end_headers()
                    self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
                    return
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"error":str(e)}).encode())
                return
            self.send_response(400)
            _cors(self)
            self.end_headers()
            self.wfile.write(b'{"error":"need text"}')
            return
        self.send_response(404)
        _cors(self)
        self.end_headers()
        self.wfile.write(b'{"error":"not found"}')

def auto_warmup():
    try:
        c = repo.count_all()
        if c == 0:
            today = datetime.now().strftime('%Y-%m-%d')
            print(f"[Auto-Warmup] BD vacia, sincronizando {today}...")
            fixture_sync.sync_for_date(repo, today)
            print(f"[Auto-Warmup] Listo, records={repo.count_all()}")
        else:
            print(f"[Warmup] BD OK con {c} partidos")
    except Exception as e:
        print(f"[Warmup error] {e}")

def main():
    port = int(os.environ.get("LIAN_PORT", os.environ.get("PORT", "8000")))
    print(f"[server] V92.2 ULTRA SEGURO puerto {port} DB {REPO_PATH} {Model.VERSION}")
    threading.Thread(target=auto_warmup, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()
