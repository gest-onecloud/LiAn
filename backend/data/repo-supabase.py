
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

        # 2. Supabase (historico que crece) - FIX con validacion y logs detallados
        supabase_inserted = 0
        if self.supabase:
            try:
                rows = []
                for m in unique:
                    # Validar fecha - si no hay fecha, saltar para no romper batch
                    d_raw = m.get('date','')
                    if not d_raw or not isinstance(d_raw, str):
                        continue
                    # Limpiar fecha: solo YYYY-MM-DD
                    d_clean = d_raw.strip()[:10]
                    if len(d_clean) != 10 or d_clean.count('-') != 2:
                        continue
                    
                    lc = (m.get('league_code') or 'others').lower().strip()
                    h = (m.get('home') or 'local').strip()
                    aw = (m.get('away') or 'visita').strip()
                    if not h or not aw:
                        continue
                    
                    mid = f"{d_clean}_{lc}_{h}_{aw}".lower().replace(' ','_')
                    mid = re.sub(r'[^a-z0-9_]+', '_', mid)
                    # Limitar id a 200 chars max
                    if len(mid) > 200:
                        mid = mid[:200]
                    
                    rows.append({
                        "id": mid,
                        "date": d_clean,
                        "time": str(m.get('time',''))[:10],
                        "home": h[:100],
                        "away": aw[:100],
                        "league": str(m.get('league',''))[:100],
                        "league_code": lc[:50],
                        "status": str(m.get('status','NS'))[:20],
                        "estado": str(m.get('estado','PROGRAMADO'))[:20],
                        "home_score": m.get('home_score'),
                        "away_score": m.get('away_score'),
                        "score": str(m.get('score',''))[:20] if m.get('score') else None
                    })
                
                # upsert en lotes de 50 (mas seguro)
                for i in range(0, len(rows), 50):
                    batch = rows[i:i+50]
                    try:
                        res = self.supabase.table('matches').upsert(batch, on_conflict='id').execute()
                        supabase_inserted += len(batch)
                    except Exception as e_batch:
                        # Si falla batch, intentar uno por uno para identificar malos
                        print(f"[supabase] batch {i//50} error: {e_batch}, intentando uno por uno")
                        for single in batch:
                            try:
                                self.supabase.table('matches').upsert(single, on_conflict='id').execute()
                                supabase_inserted += 1
                            except Exception as e_single:
                                print(f"[supabase] single error id={single.get('id')}: {e_single}")
                
                print(f"[supabase] Upsert OK: {supabase_inserted}/{len(rows)} partidos historico")
            except Exception as e:
                import traceback
                print(f"[supabase] upsert error general: {e}")
                print(traceback.format_exc()[:1000])
        else:
            print("[supabase] No hay cliente supabase, solo SQLite")
        
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
        sqlite_count = 0
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) as c FROM matches")
            sqlite_count = cur.fetchone()['c']
        except:
            pass
        
        if self.supabase:
            try:
                res = self.supabase.table('matches').select('id', count='exact').limit(1).execute()
                if res.count is not None:
                    # Devolver el maximo entre ambos, para no ocultar datos
                    supa_count = res.count
                    if supa_count == 0 and sqlite_count > 0:
                        print(f"[supabase] count_all: Supabase=0 pero SQLite={sqlite_count}, devolviendo SQLite para no ocultar")
                        return sqlite_count
                    return max(supa_count, sqlite_count) if supa_count > 0 else sqlite_count
            except Exception as e:
                print(f"[supabase] count_all error: {e}, devolviendo SQLite {sqlite_count}")
        
        return sqlite_count

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
