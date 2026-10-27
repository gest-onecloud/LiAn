
import os
import sys
from pathlib import Path

# Ajusta para que encuentre backend
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))

# Cargar env si existe .env local
SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://vndtzfkdaqcjkpofylkh.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""

if not SUPABASE_KEY:
    print("ERROR: Necesitas SUPABASE_SERVICE_ROLE_KEY env var")
    print("Ponlo asi: export SUPABASE_SERVICE_ROLE_KEY=eyJ...")
    sys.exit(1)

from supabase import create_client

# Importar tu repo actual y fixture_sync
from backend.data.repo import Repo
from backend.services import fixture_sync

db_path = ROOT / "data" / "lian.db"
repo_sqlite = Repo(str(db_path))

print(f"[migrate] Leyendo SQLite local: {db_path} -> {repo_sqlite.count_all()} partidos")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. Migrar lo que ya tienes en SQLite
all_matches = repo_sqlite.get_all(limit=1000)
print(f"[migrate] {len(all_matches)} partidos en SQLite para migrar")

rows = []
for m in all_matches:
    # m es dict de SQLite
    rows.append({
        "id": m.get("id"),
        "date": m.get("date"),
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

if rows:
    for i in range(0, len(rows), 100):
        batch = rows[i:i+100]
        res = supabase.table("matches").upsert(batch, on_conflict="id").execute()
        print(f"[migrate] Batch {i//100+1}: {len(batch)} -> ok")
    print(f"[migrate] Migracion SQLite -> Supabase completa: {len(rows)}")

# 2. Sincronizar temporada completa desde ESPN para llenar historico
print("[migrate] Ahora sincronizando desde ESPN (150 dias) para llenar historico...")
try:
    from datetime import datetime, timedelta
    from backend.services.fixture_sync import fetch_all_seasons
    fresh = fetch_all_seasons()
    print(f"[migrate] ESPN devolvio {len(fresh)} partidos frescos")
    if fresh:
        # Usar RepoSupabase si disponible para doble escritura
        try:
            from backend.data.repo_supabase import RepoSupabase
            repo_sup = RepoSupabase(str(db_path), SUPABASE_URL, SUPABASE_KEY)
            c = repo_sup.upsert_matches(fresh)
            print(f"[migrate] Upsert via RepoSupabase: {c} partidos")
        except Exception as e:
            print(f"[migrate] Fallback directo Supabase: {e}")
            rows2 = []
            import re
            for m in fresh:
                d = m.get('date','')
                lc = (m.get('league_code') or 'others').lower()
                h = m.get('home') or 'local'
                a = m.get('away') or 'visita'
                mid = f"{d}_{lc}_{h}_{a}".lower().replace(' ','_')
                mid = re.sub(r'[^a-z0-9_]+', '_', mid)
                rows2.append({
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
            for i in range(0, len(rows2), 100):
                batch = rows2[i:i+100]
                supabase.table("matches").upsert(batch, on_conflict="id").execute()
            print(f"[migrate] Upsert directo {len(rows2)} partidos")
except Exception as e:
    print(f"[migrate] Error sincronizando ESPN: {e}")
    import traceback; traceback.print_exc()

# Contar final
res = supabase.table("matches").select("id", count="exact").limit(1).execute()
print(f"[migrate] TOTAL en Supabase matches: {res.count}")
