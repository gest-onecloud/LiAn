from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

# PASO 4: Soporte para Disco Persistente en Render
DB_PATH_ENV = os.environ.get("LIAN_DB_PATH", "")
if DB_PATH_ENV:
    REPO_PATH = Path(DB_PATH_ENV)
    REPO_PATH.parent.mkdir(parents=True, exist_ok=True)
else:
    ROOT = Path(__file__).resolve().parent.parent
    REPO_PATH = ROOT / 'backend' / 'data' / 'lian.db'
    REPO_PATH.parent.mkdir(parents=True, exist_ok=True)

from backend.data.repo import Repo
from backend.services import fixture_sync, calendar as cal_service
from backend.core.model import Model

repo = Repo(str(REPO_PATH))
model = Model()

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
                "mode":"REAL Poisson Paso7 Temporada Completa",
                "db_path": str(REPO_PATH),
                "disk_persistent": bool(DB_PATH_ENV)
            }).encode())
            return
        # PASO 8: Temporada completa por liga
        if parsed.path == "/api/calendar/season/league":
            league_code = qs.get('league',[''])[0] or qs.get('league_code',[''])[0]
            limit = int(qs.get('limit',['500'])[0])
            if league_code:
                matches = repo.get_by_league(league_code, limit=limit)
                if not matches:
                    # fallback por nombre
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
            # Trigger background sync de temporada completa
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
            self.wfile.write(json.dumps({"status":"sync_temporada_iniciada","message":"Sincronizando 15 ligas temporada completa, tarda 2-3 min, luego /api/calendar/season"}).encode())
            return
        # PASO 7: Temporada completa - todos los partidos ordenados recientes primero
        if parsed.path == "/api/calendar/season":
            limit = int(qs.get('limit',['500'])[0])
            since = qs.get('since',[None])[0]  # opcional: 2025-08-01
            matches = repo.get_season(since_date=since, limit=limit)
            payload = []
            for m in matches:
                pred = model.predictions_for(m, fast=False)
                payload.append(pred)
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"matches":payload,"count":len(payload),"source":"DB Temporada Completa - recientes primero","dates":repo.get_dates()}).encode())
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
            self.wfile.write(json.dumps({"date":date,"matches":payload,"count":len(payload),"source":"DB REAL + Poisson Paso4","db_path":str(REPO_PATH)}).encode())
            return
        if parsed.path == "/api/calendar":
            date = qs.get('date',[datetime.now().strftime('%Y-%m-%d')])[0]
            refresh = qs.get('refresh',['0'])[0]=='1'
            full = qs.get('full',['0'])[0]=='1'  # Paso7: full season sync
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
                self.wfile.write(json.dumps({"date":date,"status":"sync_started_background","full":full,"message":"Sincronizando ESPN temporada completa, recarga en 10s /api/calendar/season"}).encode())
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
        self.send_response(404)
        _cors(self)
        self.end_headers()
        self.wfile.write(b'{"error":"not found"}')

def auto_warmup():
    try:
        c = repo.count_all()
        if c == 0:
            today = datetime.now().strftime('%Y-%m-%d')
            print(f"[Paso7 Auto-Warmup] BD vacia ({REPO_PATH}), sincronizando {today}...")
            fixture_sync.sync_for_date(repo, today)
            print(f"[Paso7 Auto-Warmup] Listo, ahora records={repo.count_all()}")
        else:
            print(f"[Paso7] BD OK con {c} partidos en {REPO_PATH}")
    except Exception as e:
        print(f"[Paso7 Warmup error] {e}")

def main():
    port = int(os.environ.get("LIAN_PORT", os.environ.get("PORT", "8000")))
    print(f"[server] REAL MODE Paso7 Temporada Completa puerto {port} DB {REPO_PATH} {Model.VERSION}")
    threading.Thread(target=auto_warmup, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()
