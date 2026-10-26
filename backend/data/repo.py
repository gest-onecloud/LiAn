import sqlite3
import re
from pathlib import Path
from datetime import datetime

class Repo:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_all()
        self.migrate()

    def init_all(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            time TEXT,
            home TEXT NOT NULL,
            away TEXT NOT NULL,
            league TEXT,
            competition TEXT,
            status TEXT DEFAULT 'NS',
            status_detail TEXT DEFAULT '',
            estado TEXT DEFAULT 'PROGRAMADO',
            league_code TEXT DEFAULT '',
            home_score INTEGER,
            away_score INTEGER,
            score TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_unique ON matches(date, home, away)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date)")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            match_id TEXT PRIMARY KEY,
            date TEXT,
            prob_1 REAL,
            prob_x REAL,
            prob_2 REAL,
            confidence REAL,
            evidence INTEGER,
            favorite TEXT,
            xg_home REAL,
            xg_away REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            date TEXT,
            count INTEGER,
            duration_ms INTEGER,
            status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.conn.commit()

    def migrate(self):
        """Migración para DBs viejas sin columnas nuevas"""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(matches)")
            cols = [r['name'] for r in cur.fetchall()]
            to_add = []
            if 'status_detail' not in cols:
                to_add.append("ALTER TABLE matches ADD COLUMN status_detail TEXT DEFAULT ''")
            if 'estado' not in cols:
                to_add.append("ALTER TABLE matches ADD COLUMN estado TEXT DEFAULT 'PROGRAMADO'")
            if 'league_code' not in cols:
                to_add.append("ALTER TABLE matches ADD COLUMN league_code TEXT DEFAULT ''")
            if 'home_score' not in cols:
                to_add.append("ALTER TABLE matches ADD COLUMN home_score INTEGER")
            if 'away_score' not in cols:
                to_add.append("ALTER TABLE matches ADD COLUMN away_score INTEGER")
            if 'score' not in cols:
                to_add.append("ALTER TABLE matches ADD COLUMN score TEXT")
            for sql in to_add:
                print(f"[repo] Migrando: {sql}")
                cur.execute(sql)
            if to_add:
                self.conn.commit()
        except Exception as e:
            print(f"[repo] migrate error: {e}")

    def upsert_matches(self, matches):
        if not matches:
            return 0
        cur = self.conn.cursor()
        count = 0
        # Deduplicar en memoria antes de insertar: fecha+liga+home+away normalizado
        seen_local = {}
        for m in matches:
            # Normalizar clave para dedup: fecha + liga + home + away en minúsculas sin acentos
            d = (m.get('date') or '').strip()
            lc = (m.get('league_code') or '').lower().strip()
            h = (m.get('home') or '').lower().strip()
            a = (m.get('away') or '').lower().strip()
            key = f"{d}_{lc}_{h}_{a}"
            # Si ya vimos esta clave, quedarse con el que tiene marcador (FINALIZADO)
            if key in seen_local:
                prev = seen_local[key]
                # Preferir el que tiene score y estado FINALIZADO
                if m.get('estado')=='FINALIZADO' and prev.get('estado')!='FINALIZADO':
                    seen_local[key]=m
                elif m.get('home_score') is not None and prev.get('home_score') is None:
                    seen_local[key]=m
                # else keep prev
            else:
                seen_local[key]=m
        
        unique_matches = list(seen_local.values())
        
        for m in unique_matches:
            # ID incluye liga_code para evitar colisión entre ligas
            d = m.get('date','').replace(' ','')
            lc = (m.get('league_code') or 'others').lower().replace('.','_')
            h = (m.get('home') or 'local').lower().replace(' ','_')
            aw = (m.get('away') or 'visita').lower().replace(' ','_')
            mid = f"{d}_{lc}_{h}_{aw}"
            mid = re.sub(r'[^a-z0-9_]+', '_', mid)
            cur.execute("""
            INSERT INTO matches (id, date, time, home, away, league, competition, status, status_detail, estado, league_code, home_score, away_score, score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                time=excluded.time,
                league=excluded.league,
                competition=excluded.competition,
                status=excluded.status,
                status_detail=excluded.status_detail,
                estado=excluded.estado,
                league_code=excluded.league_code,
                home_score=excluded.home_score,
                away_score=excluded.away_score,
                score=excluded.score
            """, (
                mid,
                m.get('date'),
                m.get('time',''),
                m.get('home'),
                m.get('away'),
                m.get('league',''),
                m.get('competition',''),
                m.get('status','NS'),
                m.get('status_detail',''),
                m.get('estado','PROGRAMADO'),
                m.get('league_code',''),
                m.get('home_score'),
                m.get('away_score'),
                m.get('score')
            ))
            count += 1
        self.conn.commit()
        return count

    def get_by_date(self, date_str):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM matches WHERE date=? ORDER BY time ASC, league ASC", (date_str,))
        return [dict(r) for r in cur.fetchall()]

    def count_all(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM matches")
        return cur.fetchone()['c']

    def delete_by_date(self, date_str):
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM matches WHERE date=?", (date_str,))
            self.conn.commit()
            return cur.rowcount
        except Exception as e:
            print(f"[repo] delete_by_date error: {e}")
            return 0


    def get_all(self, limit=1000):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM matches ORDER BY date DESC, time DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]

    def get_season(self, since_date=None, limit=1000):
        cur = self.conn.cursor()
        if since_date:
            cur.execute("SELECT * FROM matches WHERE date >= ? ORDER BY date DESC, time DESC LIMIT ?", (since_date, limit))
        else:
            cur.execute("SELECT * FROM matches ORDER BY date DESC, time DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]

    def get_dates(self):
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT date FROM matches ORDER BY date DESC")
        return [r['date'] for r in cur.fetchall()]

    def get_leagues_stats(self):
        cur = self.conn.cursor()
        cur.execute("SELECT league_code, league, COUNT(*) as c FROM matches GROUP BY league_code, league ORDER BY c DESC")
        return [dict(r) for r in cur.fetchall()]


    def get_by_league(self, league_code, limit=500):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM matches WHERE league_code=? ORDER BY date DESC, time DESC LIMIT ?", (league_code, limit))
        return [dict(r) for r in cur.fetchall()]

    def get_by_league_name(self, league_name_part, limit=500):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM matches WHERE league LIKE ? OR league_code LIKE ? ORDER BY date DESC, time DESC LIMIT ?", (f"%{league_name_part}%", f"%{league_name_part}%", limit))
        return [dict(r) for r in cur.fetchall()]

    def clean_duplicates(self):
        """Elimina duplicados reales dejando solo 1 por fecha+liga+equipos"""
        cur = self.conn.cursor()
        cur.execute("SELECT id, date, league_code, home, away FROM matches")
        rows = cur.fetchall()
        seen = {}
        to_delete = []
        for r in rows:
            key = f"{r['date']}_{(r['league_code'] or '').lower()}_{(r['home'] or '').lower()}_{(r['away'] or '').lower()}"
            if key in seen:
                to_delete.append(r['id'])
            else:
                seen[key]=r['id']
        if to_delete:
            print(f"[repo] Limpiando {len(to_delete)} duplicados")
            for did in to_delete:
                cur.execute("DELETE FROM matches WHERE id=?", (did,))
            self.conn.commit()
        return len(to_delete)

    def count_by_league(self):
        cur = self.conn.cursor()
        cur.execute("SELECT league_code, league, COUNT(*) as c, MIN(date) as desde, MAX(date) as hasta FROM matches GROUP BY league_code, league ORDER BY c DESC")
        return [dict(r) for r in cur.fetchall()]

    def log_sync(self, source, date, count, duration_ms, status):
        try:
            cur = self.conn.cursor()
            cur.execute("INSERT INTO sync_log (source, date, count, duration_ms, status) VALUES (?,?,?,?,?)",
                        (source, date, count, duration_ms, status))
            self.conn.commit()
        except Exception as e:
            print(f"[repo] log_sync error: {e}")
