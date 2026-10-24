
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# PASO 4: Soporte para Disco Persistente en Render
# Si existe env var LIAN_DB_PATH=/var/data/lian.db (Render Disk), usa ese
# Si no, usa backend/data/lian.db local
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
                "mode":"REAL Poisson Paso4 Persistente",
                "db_path": str(REPO_PATH),
                "disk_persistent": bool(DB_PATH_ENV)
            }).encode())
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
            if refresh:
                def bg():
                    try:
                        fixture_sync.sync_for_date(repo, date)
                    except Exception as e:
                        print(f"[bg_sync error] {e}")
                threading.Thread(target=bg,daemon=True).start()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(json.dumps({"date":date,"status":"sync_started_background","message":"Sincronizando ESPN, recarga en 5s /api/calendar/fast"}).encode())
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
    """Paso 4: Si BD vacia, sincroniza automaticamente hoy"""
    try:
        c = repo.count_all()
        if c == 0:
            today = datetime.now().strftime('%Y-%m-%d')
            print(f"[Paso4 Auto-Warmup] BD vacia ({REPO_PATH}), sincronizando {today} automaticamente...")
            fixture_sync.sync_for_date(repo, today)
            print(f"[Paso4 Auto-Warmup] Listo, ahora records={repo.count_all()}")
        else:
            print(f"[Paso4] BD OK con {c} partidos en {REPO_PATH}")
    except Exception as e:
        print(f"[Paso4 Warmup error] {e}")

def main():
    port = int(os.environ.get("LIAN_PORT", os.environ.get("PORT", "8000")))
    print(f"[server] REAL MODE Paso4 Persistente puerto {port} DB {REPO_PATH} {Model.VERSION} Disk={bool(DB_PATH_ENV)}")
    # Auto-warmup en background para no bloquear inicio
    threading.Thread(target=auto_warmup, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()
