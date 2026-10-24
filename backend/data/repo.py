
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

    def init_all(self):
        cur = self.conn.cursor()
        # Tabla matches - unica fuente de verdad
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_unique ON matches(date, home, away)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date)")

        # Tabla predictions - para despues
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

        # Tabla sync_log - para saber cuando se sincronizo
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

    def upsert_matches(self, matches):
        if not matches:
            return 0
        cur = self.conn.cursor()
        count = 0
        for m in matches:
            mid = f"{m['date']}_{m['home']}_{m['away']}".lower().replace(' ', '_')
            cur.execute("""
            INSERT INTO matches (id, date, time, home, away, league, competition, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                time=excluded.time,
                league=excluded.league,
                competition=excluded.competition,
                status=excluded.status
            """, (mid, m.get('date'), m.get('time',''), m.get('home'), m.get('away'), m.get('league',''), m.get('competition',''), m.get('status','NS')))
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

    def log_sync(self, source, date, count, duration_ms, status):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO sync_log (source, date, count, duration_ms, status) VALUES (?,?,?,?,?)",
                    (source, date, count, duration_ms, status))
        self.conn.commit()
