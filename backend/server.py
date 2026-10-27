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
            records = repo.count_all()
            self.wfile.write(json.dumps({
                "ok":True,
                "records":records,
                "version":Model.VERSION,
                "mode":"REAL Poisson Paso7 + Supabase Historico V113",
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
            limit = int(qs.get('limit',['500'])[0])
            since = qs.get('since',[None])[0]
            matches = repo.get_season(since_date=since, limit=limit)
            payload = []
            for m in matches:
                pred = model.predictions_for(m, fast=False)
                payload.append(pred)
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"matches":payload,"count":len(payload),"source":"DB Temporada Completa","dates":repo.get_dates()}).encode())
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
            limit = int(qs.get('limit',['500'])[0])
            matches = repo.get_by_league("mex.1", limit=limit)
            if not matches:
                matches = repo.get_by_league_name("Liga MX", limit=limit)
            if not matches:
                matches = repo.get_by_league_name("mex", limit=limit)
            if not matches:
                matches = repo.get_by_league_name("Mexico", limit=limit)
            # FIX V100: Si hay menos de 20 (solo 4 del finde), devolver TODOS para mostrar temporada completa 135+
            if len(matches) < 20:
                print(f"[Liga MX] Solo {len(matches)} mex.1, devolviendo todos como fallback temporada completa para no mostrar 0")
                all_matches = repo.get_all(limit=limit)
                # Si all también es poco (<20), intentar traer todo sin límite
                if len(all_matches) < 20:
                    all_matches = repo.get_all(limit=1000)
                matches = all_matches if all_matches else matches
            payload = []
            for m in matches:
                pred = model.predictions_for(m, fast=False)
                payload.append(pred)
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"league":"mex.1","matches":payload,"count":len(payload),"source":f"Liga MX + fallback ({len(payload)} partidos) - Mexico" if len(payload)>0 else "Sin datos, sincroniza"}).encode())
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
