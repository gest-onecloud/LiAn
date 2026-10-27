
import os
from pathlib import Path
import sqlite3
import re
from datetime import datetime

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except:
    HAS_SUPABASE = False
    print("[supabase] libreria no instalada, solo SQLite")

class RepoSupabase:
    def __init__(self, sqlite_path: str, supabase_url: str = None, supabase_key: str = None):
        # SQLite local (tu repo actual)
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.sqlite_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_sqlite()

        # Supabase
        self.supabase = None
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if HAS_SUPABASE and self.supabase_url and self.supabase_key:
            try:
                self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
                print(f"[supabase] Conectado a {self.supabase_url}")
            except Exception as e:
                print(f"[supabase] Error conexion: {e}")
        else:
            print("[supabase] No configurado, solo SQLite")

    def _init_sqlite(self):
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS matches (id TEXT PRIMARY KEY, date TEXT, time TEXT, home TEXT, away TEXT, league TEXT, competition TEXT, status TEXT, status_detail TEXT, estado TEXT, league_code TEXT, home_score INTEGER, away_score INTEGER, score TEXT)")
        self.conn.commit()

    def upsert_matches(self, matches):
        if not matches:
            return 0
        # 1. SQLite (tu codigo actual)
        cur = self.conn.cursor()
        seen = {}
        for m in matches:
            d = (m.get('date') or '').strip()
            lc = (m.get('league_code') or '').lower().strip()
            h = (m.get('home') or '').lower().strip()
            a = (m.get('away') or '').lower().strip()
            key = f"{d}_{lc}_{h}_{a}"
            if key in seen:
                prev = seen[key]
                if m.get('estado')=='FINALIZADO' and prev.get('estado')!='FINALIZADO':
                    seen[key]=m
            else:
                seen[key]=m
        unique = list(seen.values())
        count = 0
        for m in unique:
            d = m.get('date','').replace(' ','')
            lc = (m.get('league_code') or 'others').lower().replace('.','_')
            h = (m.get('home') or 'local').lower().replace(' ','_')
            aw = (m.get('away') or 'visita').lower().replace(' ','_')
            mid = f"{d}_{lc}_{h}_{aw}"
            mid = re.sub(r'[^a-z0-9_]+', '_', mid)
            cur.execute("INSERT INTO matches (id, date, time, home, away, league, competition, status, status_detail, estado, league_code, home_score, away_score, score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET time=excluded.time, league=excluded.league, status=excluded.status, estado=excluded.estado, league_code=excluded.league_code, home_score=excluded.home_score, away_score=excluded.away_score, score=excluded.score",
                        (mid, m.get('date'), m.get('time',''), m.get('home'), m.get('away'), m.get('league',''), m.get('competition',''), m.get('status','NS'), m.get('status_detail',''), m.get('estado','PROGRAMADO'), m.get('league_code',''), m.get('home_score'), m.get('away_score'), m.get('score')))
            count+=1
        self.conn.commit()

        # 2. Supabase (historico que crece)
        if self.supabase:
            try:
                rows = []
                for m in unique:
                    d = m.get('date','')
                    lc = (m.get('league_code') or 'others').lower()
                    h = (m.get('home') or 'local')
                    aw = (m.get('away') or 'visita')
                    mid = f"{d}_{lc}_{h}_{aw}".lower().replace(' ','_')
                    mid = re.sub(r'[^a-z0-9_]+', '_', mid)
                    rows.append({
                        "id": mid,
                        "date": m.get('date'),
                        "time": m.get('time',''),
                        "home": m.get('home'),
                        "away": m.get('away'),
                        "league": m.get('league',''),
                        "league_code": m.get('league_code',''),
                        "status": m.get('status','NS'),
                        "estado": m.get('estado','PROGRAMADO'),
                        "home_score": m.get('home_score'),
                        "away_score": m.get('away_score'),
                        "score": m.get('score')
                    })
                # upsert en lotes de 100
                for i in range(0, len(rows), 100):
                    batch = rows[i:i+100]
                    self.supabase.table('matches').upsert(batch, on_conflict='id').execute()
                print(f"[supabase] Upsert {len(rows)} partidos historico")
            except Exception as e:
                print(f"[supabase] upsert error: {e}")
        return count

    def get_by_league(self, league_code, limit=500):
        # Primero intenta Supabase si hay conexion
        if self.supabase:
            try:
                res = self.supabase.table('matches').select('*').eq('league_code', league_code).order('date', desc=True).limit(limit).execute()
                if res.data:
                    return res.data
            except Exception as e:
                print(f"[supabase] get_by_league error: {e}")
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM matches WHERE league_code=? ORDER BY date DESC LIMIT ?", (league_code, limit))
        return [dict(r) for r in cur.fetchall()]

    def get_all(self, limit=1000):
        if self.supabase:
            try:
                res = self.supabase.table('matches').select('*').order('date', desc=True).limit(limit).execute()
                if res.data:
                    return res.data
            except Exception as e:
                print(f"[supabase] get_all error: {e}")
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM matches ORDER BY date DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]

    def count_all(self):
        if self.supabase:
            try:
                res = self.supabase.table('matches').select('id', count='exact').limit(1).execute()
                if res.count is not None:
                    return res.count
            except:
                pass
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM matches")
        return cur.fetchone()['c']

    def get_by_league_name(self, name_part, limit=500):
        if self.supabase:
            try:
                res = self.supabase.table('matches').select('*').ilike('league', f'%{name_part}%').order('date', desc=True).limit(limit).execute()
                if res.data:
                    return res.data
            except Exception as e:
                print(f"[supabase] get_by_league_name error: {e}")
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM matches WHERE league LIKE ? OR league_code LIKE ? ORDER BY date DESC LIMIT ?", (f"%{name_part}%", f"%{name_part}%", limit))
        return [dict(r) for r in cur.fetchall()]
