
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
REPO_PATH = ROOT / 'backend' / 'data' / 'lian.db'

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
            self.wfile.write(json.dumps({"ok":True,"records":records,"version":Model.VERSION,"mode":"REAL ESPN_ALL"}).encode())
            return
        if parsed.path == "/api/calendar/fast":
            date = qs.get('date',[datetime.now().strftime('%Y-%m-%d')])[0]
            matches = cal_service.get_calendar_for_date(repo, date)
            payload = [{"id":m['id'],"date":m['date'],"time":m['time'],"home":m['home'],"away":m['away'],"league":m['league'],"competition":m['competition'],"status":m.get('status','NS')} for m in matches]
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(json.dumps({"date":date,"matches":payload,"count":len(payload),"source":"DB REAL"}).encode())
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
                self.wfile.write(json.dumps({"date":date,"status":"sync_started_background","message":"Sincronizando con ESPN, recarga en 4s /api/calendar/fast"}).encode())
                return
            else:
                matches = cal_service.get_calendar_for_date(repo, date)
                payload = [{"id":m['id'],"date":m['date'],"time":m['time'],"home":m['home'],"away":m['away'],"league":m['league'],"competition":m['competition'],"status":m.get('status','NS')} for m in matches]
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

def main():
    port = int(os.environ.get("LIAN_PORT", os.environ.get("PORT", "8000")))
    print(f"[server] REAL MODE puerto {port} DB {REPO_PATH} {Model.VERSION}")
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()
