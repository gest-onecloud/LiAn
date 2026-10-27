
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
    # Crear cliente Supabase directo como fallback si repo no tiene
    direct_supabase = None
    try:
        from supabase import create_client
        import os
        supa_url = os.environ.get("SUPABASE_URL")
        supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if supa_url and supa_key:
            direct_supabase = create_client(supa_url, supa_key)
            print(f"[backfill] Cliente directo Supabase creado: {supa_url[:30]}...")
    except Exception as e:
        print(f"[backfill] No se pudo crear cliente directo Supabase: {e}")
    
    # Usar el que tenga repo o el directo
    supabase_client = None
    if hasattr(repo_supabase, 'supabase') and repo_supabase.supabase:
        supabase_client = repo_supabase.supabase
    elif direct_supabase:
        supabase_client = direct_supabase
        # Asignar al repo para que upsert lo use
        try:
            repo_supabase.supabase = direct_supabase
        except:
            pass

    """
    Job que corre en background: recorre days_back dias para 15 ligas
    Guarda en Supabase historico que crece (no borra)
    """
    from .fixture_sync import _parse_espn
    from .http_client import get_json
    
    total_inserted = 0
    total_fetched = 0
    today = date.today()
    start_date = today - timedelta(days=days_back)
    
    print(f"[backfill] Iniciando backfill {days_back} dias ({start_date} a {today}) x {len(LIGAS_MUNDIALES)} ligas")
    
    # Intentar borrar indice problematico que bloquea upserts
    try:
        if supabase_client:
            # No podemos ejecutar DROP INDEX via supabase client, pero intentamos via RPC si existe
            # Por ahora solo logueamos que intentaremos upserts con on_conflict id
            print("[backfill] Verificando Supabase...")
            # Test upsert pequeno
            test_res = supabase_client.table('matches').select('id', count='exact').limit(1).execute()
            print(f"[backfill] Supabase matches actual count: {test_res.count if hasattr(test_res, 'count') else 'unknown'}")
    except Exception as e:
        print(f"[backfill] Error verificando Supabase: {e}")
    
    for idx_liga, (liga_code, liga_name) in enumerate(LIGAS_MUNDIALES):
        if progress_callback:
            progress_callback(f"Liga {idx_liga+1}/{len(LIGAS_MUNDIALES)}: {liga_code}")
        
        all_for_liga = []
        
        # Recorrer cada 3 dias para no hacer 730 requests por liga (730/3 = 243 requests x 15 ligas = 3645 requests)
        # ESPN devuelve partidos de varios dias cercanos en cada request
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
                # No romper por un error de una fecha
                continue
            
            # Pausa pequeña para no saturar ESPN
            if offset % 30 == 0:
                time.sleep(0.5)
        
        # Deduplicar por liga
        seen = set()
        unique_liga = []
        for m in all_for_liga:
            key = f"{m.get('date')}_{m.get('league_code','').lower()}_{m.get('home','').lower()}_{m.get('away','').lower()}"
            if key not in seen:
                seen.add(key)
                unique_liga.append(m)
        
        print(f"[backfill] {liga_code}: {len(unique_liga)} unicos de {len(all_for_liga)} totales")
        
        if unique_liga:
            try:
                # Usar RepoSupabase para doble escritura (SQLite + Supabase)
                # Capturar stdout de upsert para ver errores de Supabase
                import io
                from contextlib import redirect_stdout
                f = io.StringIO()
                with redirect_stdout(f):
                    count = repo_supabase.upsert_matches(unique_liga)
                output = f.getvalue()
                # Si hubo error de Supabase, guardarlo
                if "[supabase] single error" in output or "[supabase] upsert error" in output or "batch" in output.lower() and "error" in output.lower():
                    backfill_state["last_supabase_error"] = output[-1000:]
                if "[supabase] Upsert OK" in output:
                    # Extraer numero de insertados en Supabase
                    try:
                        import re
                        m = re.search(r"Upsert OK: (\d+)/", output)
                        if m:
                            backfill_state["last_supabase_success"] = int(m.group(1))
                    except:
                        pass
                print(output, end='')
                
                total_inserted += count
                total_fetched += len(unique_liga)
                print(f"[backfill] {liga_code} -> guardados {count} en historico (SQLite)")
            except Exception as e:
                import traceback
                err = f"[backfill] Error guardando {liga_code}: {e}\n{traceback.format_exc()[:1000]}"
                print(err)
                backfill_state["last_supabase_error"] = err[-1000:]
    
    print(f"[backfill] COMPLETADO: {total_fetched} fetched, {total_inserted} guardados en historico")
    
    # Log en sync_log
    try:
        repo_supabase.conn.execute("INSERT INTO sync_log (source, date, count, duration_ms, status) VALUES (?,?,?,?,?)",
                                   ('BACKFILL_15_LIGAS', str(today), total_inserted, 0, 'OK'))
        repo_supabase.conn.commit()
    except:
        pass
    
    # Si tiene Supabase, log tambien alla
    try:
        if hasattr(repo_supabase, 'supabase') and repo_supabase.supabase:
            repo_supabase.supabase.table('sync_log').insert({
                "source": f"BACKFILL_15_LIGAS_{days_back}d",
                "date": str(today),
                "count": total_inserted,
                "status": "OK"
            }).execute()
    except:
        pass
    
    return {"fetched": total_fetched, "inserted": total_inserted, "leagues": len(LIGAS_MUNDIALES)}

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
    
    def progress_cb(msg):
        backfill_state["progress"] = msg
        print(f"[backfill-progress] {msg}")
    
    def run():
        try:
            res = backfill_all_job(repo_supabase, days_back, progress_cb)
            backfill_state["result"] = res
            backfill_state["progress"] = f"Completado: {res['inserted']} partidos"
        except Exception as e:
            import traceback
            backfill_state["result"] = {"error": str(e), "trace": traceback.format_exc()[:1000]}
            backfill_state["progress"] = f"Error: {str(e)[:100]}"
        finally:
            backfill_state["running"] = False
    
    t = threading.Thread(target=run, daemon=True)
    t.start()
    
    return {"status": "started", "days_back": days_back, "leagues": len(LIGAS_MUNDIALES)}
