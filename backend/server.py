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

from backend.data.repo import Repo
from backend.services import fixture_sync, calendar as cal_service
from backend.core.model import Model

repo = Repo(str(REPO_PATH))
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
                "mode":"REAL Poisson Paso7 Temporada Completa V92.2 Ultra Seguro",
                "db_path": str(REPO_PATH),
                "disk_persistent": bool(DB_PATH_ENV)
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
