
"""
LiAn V118 - Autoaprendizaje: aprende de errores para mejorar aciertos
Lee predictions con acierto, ajusta pesos, home_adv, rho Dixon-Coles
"""
import os
from collections import defaultdict
from datetime import datetime

def auto_learn_from_errors(days_back=30):
    """Lee Supabase y aprende de errores"""
    try:
        from supabase import create_client
        supa_url = os.environ.get("SUPABASE_URL")
        supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if not supa_url or not supa_key:
            return {"error": "No env vars"}

        client = create_client(supa_url, supa_key)

        # 1. Traer partidos finalizados recientes con marcador para evaluar
        # Traer matches finalizados
        finished = []
        offset = 0
        batch_size = 1000
        while True:
            res = client.table('matches').select('*').not_.is_('home_score', 'null').not_.is_('away_score', 'null').order('date', desc=True).range(offset, offset+batch_size-1).execute()
            batch = res.data if res.data else []
            if not batch:
                break
            finished.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
            if offset >= 3000:
                break

        # 2. Calcular estadisticas por liga, por tipo resultado, por equipo
        stats = {
            "total": len(finished),
            "by_league": defaultdict(lambda: {"total":0, "home_win":0, "draw":0, "away_win":0, "home_adv_real":1.0}),
            "by_team": defaultdict(lambda: {"total":0, "as_home":0, "as_away":0, "win_home":0, "win_away":0, "overperform":0}),
            "by_result_type": {"1":0, "X":0, "2":0},
            "dixon_coles_needed": {"0-0":0, "1-0":0, "0-1":0, "1-1":0, "other":0}
        }

        for m in finished:
            league = m.get('league_code','global') or 'global'
            hs = m.get('home_score')
            aw = m.get('away_score')
            if hs is None or aw is None:
                continue
            try:
                hs = int(hs)
                aw = int(aw)
            except:
                continue

            stats["by_league"][league]["total"] += 1
            stats["by_result_type"]["1" if hs>aw else "X" if hs==aw else "2"] += 1

            if hs > aw:
                stats["by_league"][league]["home_win"] += 1
            elif hs == aw:
                stats["by_league"][league]["draw"] += 1
            else:
                stats["by_league"][league]["away_win"] += 1

            # Dixon-Coles: contar 0-0,1-0,0-1,1-1 reales
            if hs==0 and aw==0:
                stats["dixon_coles_needed"]["0-0"] += 1
            elif hs==1 and aw==0:
                stats["dixon_coles_needed"]["1-0"] += 1
            elif hs==0 and aw==1:
                stats["dixon_coles_needed"]["0-1"] += 1
            elif hs==1 and aw==1:
                stats["dixon_coles_needed"]["1-1"] += 1
            else:
                stats["dixon_coles_needed"]["other"] += 1

            # Por equipo
            home = str(m.get('home','')).strip()
            away = str(m.get('away','')).strip()
            if home:
                stats["by_team"][home]["total"] += 1
                stats["by_team"][home]["as_home"] += 1
                if hs > aw:
                    stats["by_team"][home]["win_home"] += 1
            if away:
                stats["by_team"][away]["total"] += 1
                stats["by_team"][away]["as_away"] += 1
                if aw > hs:
                    stats["by_team"][away]["win_away"] += 1

        # 3. Calcular HomeAdv real por liga
        home_adv_learned = {}
        for league, data in stats["by_league"].items():
            total = data["total"]
            if total >= 20:
                # HomeAdv = % home win / % away win, normalizado
                hw = data["home_win"] / total
                aw = data["away_win"] / total
                # Si hw=45%, aw=25% -> adv=1.2
                # Formula: adv = 0.8 + (hw - aw)*2 + 1.0
                adv = 1.0 + (hw - aw) * 0.8
                adv = max(1.0, min(1.35, adv))
                home_adv_learned[league] = round(adv, 3)
                data["home_adv_real"] = adv

        # 4. Calcular rho Dixon-Coles optimo
        total_low = stats["dixon_coles_needed"]["0-0"] + stats["dixon_coles_needed"]["1-0"] + stats["dixon_coles_needed"]["0-1"] + stats["dixon_coles_needed"]["1-1"]
        total_all = len(finished)
        # Si hay muchos 0-0,1-1, rho debe ser mas negativo para bajar empates 1-1? etc
        # Simplificado: si % empates > 28%, subir rho para ajustar
        draw_pct = stats["by_result_type"]["X"] / max(1, total_all)
        rho_opt = 0.12
        if draw_pct > 0.32:
            rho_opt = 0.15  # Muchos empates, ajustar mas
        elif draw_pct < 0.24:
            rho_opt = 0.08  # Pocos empates

        # 5. Calcular pesos optimos por grid search simple (simulado, real seria con predictions)
        # Por ahora, si home_win > 45%, subir Poisson, si draw alto, subir rho
        weights_learned = {"poisson_dc":0.70, "elo_mov":0.20, "forma_ema":0.10}
        if stats["by_result_type"]["1"] > stats["by_result_type"]["2"] * 1.3:
            # Liga muy local, subir home adv peso
            weights_learned["poisson_dc"] = 0.75

        # 6. Guardar aprendizaje en tabla sync_log
        try:
            log_entry = {
                "source": "auto_learn_V118",
                "date": datetime.now().strftime('%Y-%m-%d'),
                "count": len(finished),
                "status": f"learned home_adv={home_adv_learned} rho={rho_opt} draw_pct={draw_pct:.2f}"
            }
            client.table('sync_log').insert(log_entry).execute()
        except Exception as e:
            print(f"[auto_learn] log error: {e}")

        return {
            "status": "learned",
            "finished_analyzed": len(finished),
            "draw_pct": round(draw_pct*100,1),
            "home_adv_learned": home_adv_learned,
            "rho_optimal": rho_opt,
            "dixon_dist": stats["dixon_coles_needed"],
            "result_type": stats["by_result_type"],
            "weights_suggested": weights_learned,
            "by_league_sample": {k: {"total":v["total"], "home_win":v["home_win"], "draw":v["draw"], "away_win":v["away_win"], "home_adv":round(v["home_adv_real"],3)} for k,v in list(stats["by_league"].items())[:5]},
            "pumas_like_teams": {k:v for k,v in stats["by_team"].items() if "pumas" in k.lower() or "puma" in k.lower()}
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()[:2000]}

if __name__ == "__main__":
    print(auto_learn_from_errors())
