
"""
LiAn V114 - Backfill Historico Completo 15 Ligas
Carga 2 años completos en Supabase que crece
"""
import os
import time
from datetime import date, timedelta
import threading

LIGAS_MUNDIALES = [
    ("eng.1", "Premier League - Inglaterra"),
    ("esp.1", "La Liga - España"),
    ("ita.1", "Serie A - Italia"),
    ("ger.1", "Bundesliga - Alemania"),
    ("fra.1", "Ligue 1 - Francia"),
    ("mex.1", "Liga MX - Mexico"),
    ("usa.1", "MLS - USA"),
    ("bra.1", "Brasileirão - Brasil"),
    ("arg.1", "Liga Argentina"),
    ("uefa.champions", "Champions League"),
    ("uefa.europa", "Europa League"),
    ("uefa.europa.conf", "Conference League"),
    ("concacaf.champions", "Concachampions"),
    ("fifa.worldq", "Eliminatorias Mundial"),
    ("eng.fa", "FA Cup"),
]


def backfill_all_job(repo_supabase, days_back=730, progress_callback=None):
    # FORZAR cliente Supabase directo siempre, no depender del repo
    direct_supabase = None
    supa_url = None
    supa_key = None
    try:
        from supabase import create_client
        supa_url = os.environ.get("SUPABASE_URL")
        supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if supa_url and supa_key:
            direct_supabase = create_client(supa_url, supa_key)
            print(f"[backfill] Cliente directo Supabase creado: {supa_url[:30]}... KEY present: {bool(supa_key)}")
        else:
            print(f"[backfill] Faltan env vars: URL={bool(supa_url)} KEY={bool(supa_key)}")
    except Exception as e:
        print(f"[backfill] No se pudo crear cliente directo Supabase: {e}")
        import traceback
        print(traceback.format_exc()[:1000])
    
    # Usar el que tenga repo o el directo
    supabase_client = None
    if hasattr(repo_supabase, 'supabase') and repo_supabase.supabase:
        supabase_client = repo_supabase.supabase
        print("[backfill] Usando cliente de repo_supabase")
    elif direct_supabase:
        supabase_client = direct_supabase
        print("[backfill] Usando cliente directo")
        # Asignar al repo para que upsert lo use si es RepoSupabase
        try:
            repo_supabase.supabase = direct_supabase
        except:
            pass
    else:
        print("[backfill] ADVERTENCIA: No hay cliente Supabase, solo se guardara en SQLite!")

    """
    Job que corre en background: recorre days_back dias para 15 ligas
    Guarda en Supabase historico que crece (no borra)
    """
    from .fixture_sync import _parse_espn
    from .http_client import get_json
    
    total_inserted = 0
    total_fetched = 0
    total_supabase_inserted = 0
    today = date.today()
    start_date = today - timedelta(days=days_back)
    
    print(f"[backfill] Iniciando backfill {days_back} dias ({start_date} a {today}) x {len(LIGAS_MUNDIALES)} ligas")
    
    # Test Supabase
    try:
        if supabase_client:
            test_res = supabase_client.table('matches').select('id', count='exact').limit(1).execute()
            print(f"[backfill] Supabase matches actual count: {test_res.count if hasattr(test_res, 'count') else 'unknown'}")
    except Exception as e:
        print(f"[backfill] Error verificando Supabase: {e}")
    
    for idx_liga, (liga_code, liga_name) in enumerate(LIGAS_MUNDIALES):
        if progress_callback:
            progress_callback(f"Liga {idx_liga+1}/{len(LIGAS_MUNDIALES)}: {liga_code}")
        
        all_for_liga = []
        
        step = 3
        for offset in range(0, days_back, step):
            d = today - timedelta(days=offset)
            date_nodash = d.strftime('%Y%m%d')
            date_iso = d.isoformat()
            
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard?dates={date_nodash}"
            try:
                raw = get_json(url, timeout=8)
                if raw and raw.get('events'):
                    matches = _parse_espn(date_iso, raw, liga_code, liga_name)
                    if matches:
                        all_for_liga.extend(matches)
            except Exception as e:
                continue
            
            if offset % 30 == 0:
                time.sleep(0.5)
        
        # Deduplicar
        seen = set()
        unique_liga = []
        for m in all_for_liga:
            key = f"{m.get('date')}_{m.get('league_code','').lower()}_{m.get('home','').lower()}_{m.get('away','').lower()}"
            if key not in seen:
                seen.add(key)
                unique_liga.append(m)
        
        print(f"[backfill] {liga_code}: {len(unique_liga)} unicos de {len(all_for_liga)} totales")
        
        if unique_liga:
            # 1. Guardar en SQLite via repo (siempre funciona)
            try:
                count_sqlite = repo_supabase.upsert_matches(unique_liga)
                total_inserted += count_sqlite
                total_fetched += len(unique_liga)
                print(f"[backfill] {liga_code} -> SQLite {count_sqlite} partidos")
            except Exception as e:
                print(f"[backfill] Error SQLite {liga_code}: {e}")
            
            # 2. Guardar DIRECTO en Supabase (forzado, no depender de repo)
            if supabase_client:
                try:
                    import re
                    rows = []
                    for m in unique_liga:
                        d_raw = m.get('date','')
                        if not d_raw or not isinstance(d_raw, str):
                            continue
                        d_clean = d_raw.strip()[:10]
                        if len(d_clean) != 10 or d_clean.count('-') != 2:
                            continue
                        lc = (m.get('league_code') or 'others').lower().strip()[:50]
                        h = (m.get('home') or 'local').strip()[:100]
                        aw = (m.get('away') or 'visita').strip()[:100]
                        if not h or not aw:
                            continue
                        mid = f"{d_clean}_{lc}_{h}_{aw}".lower().replace(' ','_')
                        mid = re.sub(r'[^a-z0-9_]+', '_', mid)
                        if len(mid) > 200:
                            mid = mid[:200]
                        rows.append({
                            "id": mid,
                            "date": d_clean,
                            "time": str(m.get('time',''))[:10] if m.get('time') else None,
                            "home": h,
                            "away": aw,
                            "league": str(m.get('league',''))[:100],
                            "league_code": lc,
                            "status": str(m.get('status','NS'))[:20],
                            "estado": str(m.get('estado','PROGRAMADO'))[:20],
                            "home_score": m.get('home_score'),
                            "away_score": m.get('away_score'),
                            "score": str(m.get('score',''))[:20] if m.get('score') else None
                        })
                    
                    # Upsert en lotes de 50
                    supa_ok = 0
                    for i in range(0, len(rows), 50):
                        batch = rows[i:i+50]
                        try:
                            supabase_client.table('matches').upsert(batch, on_conflict='id').execute()
                            supa_ok += len(batch)
                        except Exception as e_batch:
                            print(f"[backfill] Supabase batch {i//50} error: {e_batch}, uno por uno")
                            for single in batch:
                                try:
                                    supabase_client.table('matches').upsert(single, on_conflict='id').execute()
                                    supa_ok += 1
                                except Exception as e_single:
                                    print(f"[backfill] Supabase single id={single.get('id')} error: {e_single}")
                                    backfill_state["last_supabase_error"] = str(e_single)[:1000]
                    
                    total_supabase_inserted += supa_ok
                    backfill_state["last_supabase_success"] = total_supabase_inserted
                    print(f"[backfill] {liga_code} -> Supabase OK {supa_ok}/{len(rows)}")
                    
                except Exception as e:
                    import traceback
                    err = f"[backfill] Error Supabase {liga_code}: {e}\n{traceback.format_exc()[:1000]}"
                    print(err)
                    backfill_state["last_supabase_error"] = err[-1000:]
    
    print(f"[backfill] COMPLETADO: {total_fetched} fetched, {total_inserted} SQLite, {total_supabase_inserted} Supabase")
    
    # Log en sync_log
    try:
        repo_supabase.conn.execute("INSERT INTO sync_log (source, date, count, duration_ms, status) VALUES (?,?,?,?,?)",
                                   ('BACKFILL_15_LIGAS', str(today), total_inserted, 0, 'OK'))
        repo_supabase.conn.commit()
    except:
        pass
    
    # Log en Supabase
    try:
        if supabase_client:
            supabase_client.table('sync_log').insert({
                "source": f"BACKFILL_15_LIGAS_{days_back}d",
                "date": str(today),
                "count": total_supabase_inserted,
                "status": "OK"
            }).execute()
    except:
        pass
    
    return {"fetched": total_fetched, "inserted": total_inserted, "supabase_inserted": total_supabase_inserted, "leagues": len(LIGAS_MUNDIALES)}


# Estado global del backfill
backfill_state = {
    "running": False,
    "progress": "",
    "result": None,
    "started_at": None,
    "last_supabase_error": None,
    "last_supabase_success": 0
}

def start_backfill_thread(repo_supabase, days_back=730):
    if backfill_state["running"]:
        return {"status": "already_running", "progress": backfill_state["progress"]}
    
    backfill_state["running"] = True
    backfill_state["progress"] = "Iniciando..."
    backfill_state["result"] = None
    backfill_state["started_at"] = str(date.today())
    backfill_state["last_supabase_error"] = None
    backfill_state["last_supabase_success"] = 0
    
    def progress_cb(msg):
        backfill_state["progress"] = msg
        print(f"[backfill-progress] {msg}")
    
    def run():
        try:
            res = backfill_all_job(repo_supabase, days_back, progress_cb)
            backfill_state["result"] = res
            backfill_state["progress"] = f"Completado: {res['inserted']} SQLite, {res.get('supabase_inserted',0)} Supabase"
        except Exception as e:
            import traceback
            backfill_state["result"] = {"error": str(e), "trace": traceback.format_exc()[:1000]}
            backfill_state["progress"] = f"Error: {str(e)[:100]}"
        finally:
            backfill_state["running"] = False
    
    t = threading.Thread(target=run, daemon=True)
    t.start()
    
    return {"status": "started", "days_back": days_back, "leagues": len(LIGAS_MUNDIALES)}
