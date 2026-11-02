# V127.2 Fix Health 404 + Viaje/Altura + 5714 historico + 65/25/10 k=0.5 + VersionHeader | 2026-11-01 18:27:00 | backend/core/model.py
import hashlib
import math
import random
from datetime import datetime as dt

class Model:
    VERSION = "V127.2 Fix Health 404 + Viaje/Altura + 5714 historico + 65/25/10 k=0.5 + VersionHeader | 2026-11-01 18:27:00"
    VERSION_SHORT = "V127.2"

    def __init__(self, repo=None):
        self.repo = repo
        self.weights = {"poisson_dc": 0.65, "elo_mov": 0.25, "forma_ema": 0.10}  # V127 BEST 65/25/10 46.4% (206/444) + Viaje/Altura objetivo 210/444
        self.discipline_k = 0.5  # V124.4.1 BEST auto-tune
        self.elo = {}
        self.team_stats = {}
        self.elo_source = "none"
        self.team_stats_source = "none"
        self.history_loaded = False
        self._load_elo_and_stats()

    def _load_elo_and_stats(self):
        # Carga ELO y team_stats desde repo si existe
        try:
            if self.repo and hasattr(self.repo, 'supabase') and self.repo.supabase:
                try:
                    r = self.repo.supabase.table('elo_ratings').select('*').execute()
                    if r.data:
                        for row in r.data:
                            self.elo[row['team']] = row['rating']
                        self.elo_source = f"supabase {len(self.elo)} equipos"
                        self.history_loaded = True
                except Exception as e:
                    print(f"[model elo] supabase error {e}")
                try:
                    r = self.repo.supabase.table('team_stats').select('*').execute()
                    if r.data:
                        for row in r.data:
                            self.team_stats[row['team']] = row
                        self.team_stats_source = f"supabase {len(self.team_stats)} stats"
                except Exception as e:
                    print(f"[model stats] supabase error {e}")
        except Exception as e:
            print(f"[model load] error {e}")

    def _team_strength(self, team):
        if team in self.elo:
            # ELO 1500 -> 1.0, 1600 -> 1.2 etc
            return 0.5 + (self.elo[team] - 1000) / 1000
        # hash fallback
        h = int(hashlib.md5(team.encode()).hexdigest()[:4], 16) % 100
        return 0.7 + h / 200

    def _team_attack_defense(self, team):
        if team in self.team_stats:
            s = self.team_stats[team]
            return s.get('avg_for', 1.2), s.get('avg_against', 1.2), s.get('mp', 0)
        # fallback hash
        h1 = int(hashlib.md5((team+"att").encode()).hexdigest()[:2], 16)
        h2 = int(hashlib.md5((team+"def").encode()).hexdigest()[:2], 16)
        return 1.0 + (h1 % 50)/100, 1.0 + (h2 % 50)/100, 0

    def _team_form_ema(self, team):
        if team in self.team_stats:
            # usa forma si existe
            return self.team_stats[team].get('form_ema', 0.0)
        return 0.0

    def _get_home_adv(self, league_code, league):
        # Liga MX tiene home adv mas alto por altura y viajes
        lc = (league_code or '').lower()
        if 'mex' in lc or 'liga mx' in (league or '').lower():
            return 1.25
        if 'eng' in lc or 'esp' in lc or 'ita' in lc:
            return 1.18
        return 1.20

    def _calc_1x2_from_xg_dixon_coles(self, xg_home, xg_away, rho=0.12):
        # Dixon-Coles ajuste
        # Poisson simple + correccion empates bajos
        def poisson(k, lam):
            return (lam**k * math.exp(-lam)) / math.factorial(k)
        
        probs = {"1":0,"X":0,"2":0}
        total = 0
        # suma hasta 7 goles
        for h in range(0,8):
            for a in range(0,8):
                p = poisson(h, xg_home) * poisson(a, xg_away)
                # Dixon-Coles correction for 0-0,1-0,0-1,1-1
                if h==0 and a==0:
                    p *= (1 - rho * xg_away * xg_home)
                elif h==1 and a==0:
                    p *= (1 + rho * xg_away)
                elif h==0 and a==1:
                    p *= (1 + rho * xg_home)
                elif h==1 and a==1:
                    p *= (1 - rho)
                
                if h > a:
                    probs["1"] += p
                elif h == a:
                    probs["X"] += p
                else:
                    probs["2"] += p
                total += p
        
        # normalizar
        s = probs["1"]+probs["X"]+probs["2"]
        if s>0:
            probs = {k: round(v/s*100,1) for k,v in probs.items()}
        return probs

    def _montecarlo_interval(self, xg_home, xg_away, n=6000):
        # V121.2 MC 6000 validador
        c1=cX=c2=0
        for _ in range(n):
            # poisson sample via random
            # aproximacion rapida
            gh = 0
            # sample home goals
            L = math.exp(-xg_home)
            p=1.0
            k=0
            while True:
                p *= random.random()
                if p <= L:
                    gh = k
                    break
                k+=1
                if k>10:
                    gh=k
                    break
            ga=0
            L = math.exp(-xg_away)
            p=1.0
            k=0
            while True:
                p *= random.random()
                if p <= L:
                    ga = k-1 if k>0 else 0
                    break
                k+=1
                if k>10:
                    ga=k
                    break
            if gh > ga:
                c1 += 1
            elif gh == ga:
                cX += 1
            else:
                c2 += 1
        total = c1 + cX + c2
        return {
            "1": round((c1/total)*100,1),
            "X": round((cX/total)*100,1),
            "2": round((c2/total)*100,1),
        }

    # V127 - Viaje/Altura: base de datos de ubicaciones y altitudes
    TEAM_LOCATIONS = {
        "TOLUCA": {"lat": 19.287, "lon": -99.654, "alt": 2680, "city": "Toluca"},
        "PUEBLA": {"lat": 19.043, "lon": -98.197, "alt": 2135, "city": "Puebla"},
        "PUMAS": {"lat": 19.332, "lon": -99.188, "alt": 2280, "city": "CDMX"},
        "UNAM": {"lat": 19.332, "lon": -99.188, "alt": 2280, "city": "CDMX"},
        "AMERICA": {"lat": 19.302, "lon": -99.150, "alt": 2240, "city": "CDMX"},
        "CRUZ AZUL": {"lat": 19.302, "lon": -99.150, "alt": 2240, "city": "CDMX"},
        "ATLAS": {"lat": 20.657, "lon": -103.324, "alt": 1570, "city": "Guadalajara"},
        "GUADALAJARA": {"lat": 20.657, "lon": -103.324, "alt": 1570, "city": "Guadalajara"},
        "CHIVAS": {"lat": 20.657, "lon": -103.324, "alt": 1570, "city": "Guadalajara"},
        "MONTERREY": {"lat": 25.678, "lon": -100.285, "alt": 540, "city": "Monterrey"},
        "TIGRES": {"lat": 25.678, "lon": -100.285, "alt": 540, "city": "Monterrey"},
        "TIJUANA": {"lat": 32.522, "lon": -117.018, "alt": 20, "city": "Tijuana"},
        "SANTOS": {"lat": 25.537, "lon": -103.407, "alt": 1120, "city": "Torreon"},
        "SANTOS LAGUNA": {"lat": 25.537, "lon": -103.407, "alt": 1120, "city": "Torreon"},
        "LEON": {"lat": 21.122, "lon": -101.673, "alt": 1815, "city": "Leon"},
        "PACHUCA": {"lat": 20.105, "lon": -98.759, "alt": 2420, "city": "Pachuca"},
        "QUERETARO": {"lat": 20.588, "lon": -100.389, "alt": 1820, "city": "Queretaro"},
        "SAN LUIS": {"lat": 22.156, "lon": -100.985, "alt": 1860, "city": "San Luis"},
        "ATLETICO SAN LUIS": {"lat": 22.156, "lon": -100.985, "alt": 1860, "city": "San Luis"},
        "NECAXA": {"lat": 21.882, "lon": -102.289, "alt": 1880, "city": "Aguascalientes"},
        "JUAREZ": {"lat": 31.738, "lon": -106.485, "alt": 1120, "city": "Juarez"},
        "MAZATLAN": {"lat": 23.218, "lon": -106.422, "alt": 10, "city": "Mazatlan"},
        "CANCUN": {"lat": 21.161, "lon": -86.851, "alt": 10, "city": "Cancun"},
        "MANCHESTER CITY": {"lat": 53.483, "lon": -2.200, "alt": 50, "city": "Manchester"},
        "MANCHESTER UNITED": {"lat": 53.463, "lon": -2.291, "alt": 50, "city": "Manchester"},
        "LIVERPOOL": {"lat": 53.430, "lon": -2.960, "alt": 20, "city": "Liverpool"},
        "ARSENAL": {"lat": 51.555, "lon": -0.108, "alt": 30, "city": "London"},
        "CHELSEA": {"lat": 51.481, "lon": -0.191, "alt": 30, "city": "London"},
        "TOTTENHAM": {"lat": 51.604, "lon": -0.066, "alt": 30, "city": "London"},
        "REAL MADRID": {"lat": 40.453, "lon": -3.688, "alt": 650, "city": "Madrid"},
        "BARCELONA": {"lat": 41.380, "lon": 2.122, "alt": 10, "city": "Barcelona"},
        "ATLETICO MADRID": {"lat": 40.436, "lon": -3.599, "alt": 650, "city": "Madrid"},
        "FLAMENGO": {"lat": -22.912, "lon": -43.231, "alt": 10, "city": "Rio"},
        "PALMEIRAS": {"lat": -23.545, "lon": -46.673, "alt": 760, "city": "Sao Paulo"},
        "GREMIO": {"lat": -30.032, "lon": -51.230, "alt": 10, "city": "Porto Alegre"},
        "DEFAULT": {"lat": 0, "lon": 0, "alt": 0, "city": "Unknown"}
    }

    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    def _get_team_location(self, team_name):
        key = team_name.upper().strip()
        for k, v in self.TEAM_LOCATIONS.items():
            if k in key or key in k:
                return v
        if "AMERICA" in key:
            return self.TEAM_LOCATIONS["AMERICA"]
        if "CHIVAS" in key or "GUADALAJARA" in key:
            return self.TEAM_LOCATIONS["GUADALAJARA"]
        return self.TEAM_LOCATIONS["DEFAULT"]

    def _calc_travel_distance(self, home_team, away_team):
        try:
            loc_home = self._get_team_location(home_team)
            loc_away = self._get_team_location(away_team)
            if loc_home["lat"] == 0 and loc_home["lon"] == 0:
                return 0
            if loc_away["lat"] == 0 and loc_away["lon"] == 0:
                return 0
            dist = self._haversine_distance(loc_home["lat"], loc_home["lon"], loc_away["lat"], loc_away["lon"])
            return round(dist, 0)
        except:
            return 0

    def _travel_fatigue_factor(self, distance_km):
        if distance_km <= 0:
            return {"attack": 1.0, "defense": 1.0, "prob_penalty": 0, "label": "0km", "tipo": "sin_viaje"}
        elif distance_km < 500:
            return {"attack": 1.0, "defense": 1.0, "prob_penalty": 0, "label": f"{int(distance_km)}km CORTO", "tipo": "viaje_corto"}
        elif distance_km < 1000:
            return {"attack": 0.97, "defense": 1.02, "prob_penalty": -1, "label": f"{int(distance_km)}km MEDIO", "tipo": "viaje_medio"}
        elif distance_km < 2000:
            return {"attack": 0.94, "defense": 1.05, "prob_penalty": -2.5, "label": f"{int(distance_km)}km LARGO", "tipo": "viaje_largo"}
        elif distance_km < 3000:
            return {"attack": 0.90, "defense": 1.08, "prob_penalty": -4, "label": f"{int(distance_km)}km MUY LARGO", "tipo": "viaje_muy_largo"}
        else:
            return {"attack": 0.86, "defense": 1.12, "prob_penalty": -6, "label": f"{int(distance_km)}km EXTREMO", "tipo": "viaje_extremo"}

    def _altitude_factor(self, home_team, away_team):
        try:
            loc_home = self._get_team_location(home_team)
            loc_away = self._get_team_location(away_team)
            alt_home = loc_home.get("alt", 0)
            alt_away = loc_away.get("alt", 0)
            alt_diff = alt_home - alt_away
            if alt_home < 1500:
                return {"attack": 1.0, "defense": 1.0, "prob_penalty": 0, "label": f"{alt_home}m BAJO", "tipo": "altura_baja", "alt_diff": alt_diff}
            elif alt_home < 2000:
                if alt_diff > 1000:
                    return {"attack": 1.0, "defense": 1.0, "prob_penalty": -1, "label": f"{alt_home}m MEDIA vs {alt_away}m diff {int(alt_diff)}m", "tipo": "altura_media", "alt_diff": alt_diff}
                else:
                    return {"attack": 1.0, "defense": 1.0, "prob_penalty": 0, "label": f"{alt_home}m MEDIA", "tipo": "altura_media", "alt_diff": alt_diff}
            elif alt_home < 2500:
                if alt_diff > 1500:
                    return {"attack": 1.0, "defense": 1.0, "prob_penalty": -3, "label": f"{alt_home}m ALTA vs {alt_away}m diff {int(alt_diff)}m", "tipo": "altura_alta", "alt_diff": alt_diff}
                elif alt_diff > 800:
                    return {"attack": 1.0, "defense": 1.0, "prob_penalty": -2, "label": f"{alt_home}m ALTA vs {alt_away}m diff {int(alt_diff)}m", "tipo": "altura_alta", "alt_diff": alt_diff}
                else:
                    return {"attack": 1.0, "defense": 1.0, "prob_penalty": -1, "label": f"{alt_home}m ALTA", "tipo": "altura_alta", "alt_diff": alt_diff}
            else:
                if alt_diff > 2000:
                    return {"attack": 1.0, "defense": 1.0, "prob_penalty": -5, "label": f"{alt_home}m MUY ALTA vs {alt_away}m diff {int(alt_diff)}m", "tipo": "altura_muy_alta", "alt_diff": alt_diff}
                elif alt_diff > 1000:
                    return {"attack": 1.0, "defense": 1.0, "prob_penalty": -3.5, "label": f"{alt_home}m MUY ALTA vs {alt_away}m diff {int(alt_diff)}m", "tipo": "altura_muy_alta", "alt_diff": alt_diff}
                else:
                    return {"attack": 1.0, "defense": 1.0, "prob_penalty": -2, "label": f"{alt_home}m MUY ALTA", "tipo": "altura_muy_alta", "alt_diff": alt_diff}
        except:
            return {"attack": 1.0, "defense": 1.0, "prob_penalty": 0, "label": "0m", "tipo": "altura_unknown", "alt_diff": 0}

    def _calc_rest_days(self, match_date_str, team_last_match_date_str):
        try:
            from datetime import datetime
            if not match_date_str or not team_last_match_date_str:
                return 7
            d1 = datetime.fromisoformat(str(match_date_str)[:10])
            d2 = datetime.fromisoformat(str(team_last_match_date_str)[:10])
            delta = (d1 - d2).days
            return max(0, delta)
        except:
            return 7

    def _rest_fatigue_factor(self, rest_days):
        if rest_days <= 0:
            return {"attack": 0.80, "defense": 1.20, "label": f"{rest_days}d CRITICO", "prob_penalty": -8, "conf_penalty": 2, "tipo": "fatiga"}
        elif rest_days == 1:
            return {"attack": 0.82, "defense": 1.18, "label": f"{rest_days}d EXTREMO", "prob_penalty": -8, "conf_penalty": 2, "tipo": "fatiga"}
        elif rest_days == 2:
            return {"attack": 0.86, "defense": 1.12, "label": f"{rest_days}d FATIGA ALTA", "prob_penalty": -6, "conf_penalty": 1, "tipo": "fatiga"}
        elif rest_days == 3:
            return {"attack": 0.90, "defense": 1.08, "label": f"{rest_days}d FATIGA MEDIA", "prob_penalty": -4, "conf_penalty": 1, "tipo": "fatiga"}
        elif rest_days == 4:
            return {"attack": 0.94, "defense": 1.04, "label": f"{rest_days}d FATIGA LEVE", "prob_penalty": -2, "conf_penalty": 0, "tipo": "fatiga"}
        elif rest_days <= 6:
            return {"attack": 0.97, "defense": 1.02, "label": f"{rest_days}d OK", "prob_penalty": -1, "conf_penalty": 0, "tipo": "ok"}
        elif rest_days <= 9:
            return {"attack": 1.0, "defense": 1.0, "label": f"{rest_days}d OPTIMO", "prob_penalty": 0, "conf_penalty": 0, "tipo": "optimo"}
        elif rest_days <= 13:
            return {"attack": 0.97, "defense": 1.02, "label": f"{rest_days}d OXIDO LEVE", "prob_penalty": -1, "conf_penalty": 0, "tipo": "oxido_leve"}
        elif rest_days <= 20:
            return {"attack": 0.92, "defense": 1.06, "label": f"{rest_days}d OXIDO MEDIO", "prob_penalty": -3.5, "conf_penalty": 1, "tipo": "oxido_medio"}
        elif rest_days <= 27:
            return {"attack": 0.87, "defense": 1.10, "label": f"{rest_days}d OXIDO ALTO", "prob_penalty": -6, "conf_penalty": 2, "tipo": "oxido_alto"}
        else:
            return {"attack": 0.82, "defense": 1.15, "label": f"{rest_days}d OXIDO CRITICO", "prob_penalty": -9, "conf_penalty": 2, "tipo": "oxido_critico"}

    def auto_learn_best_weights(self, matches_finished, test_weights_list=None, test_discipline_k=None):
        if test_weights_list is None:
            test_weights_list = [
                {"poisson_dc": 0.75, "elo_mov": 0.20, "forma_ema": 0.05},
                {"poisson_dc": 0.70, "elo_mov": 0.20, "forma_ema": 0.10},
                {"poisson_dc": 0.65, "elo_mov": 0.25, "forma_ema": 0.10},
                {"poisson_dc": 0.60, "elo_mov": 0.25, "forma_ema": 0.15},
                {"poisson_dc": 0.70, "elo_mov": 0.15, "forma_ema": 0.15},
                {"poisson_dc": 0.65, "elo_mov": 0.20, "forma_ema": 0.15},
            ]
        if test_discipline_k is None:
            test_discipline_k = [0, 0.5, 1.0, 1.6, 2.0]
        best_acc = 0
        best_w = self.weights
        best_k = self.discipline_k
        results = []
        discipline_results = []
        for k in test_discipline_k:
            orig_k = self.discipline_k
            self.discipline_k = k
            for w in test_weights_list:
                correct = 0
                total = 0
                for m in matches_finished[:500]:
                    try:
                        orig_w = self.weights
                        self.weights = w
                        pred = self.predictions_for(m, fast=True)
                        self.weights = orig_w
                        hs = m.get('home_score')
                        aw = m.get('away_score')
                        if hs is None or aw is None:
                            continue
                        if hs > aw:
                            real = "1"
                        elif hs == aw:
                            real = "X"
                        else:
                            real = "2"
                        max_prob = max(pred['probabilities'], key=lambda k: pred['probabilities'][k])
                        if max_prob == real:
                            correct += 1
                        total += 1
                    except:
                        continue
                acc = (correct/total*100) if total>0 else 0
                entry = {"weights": w, "discipline_k": k, "accuracy": round(acc,2), "correct": correct, "total": total}
                results.append(entry)
                if acc > best_acc:
                    best_acc = acc
                    best_w = w
                    best_k = k
            per_k_best = max([r for r in results if r['discipline_k']==k], key=lambda x: x['accuracy'], default={"accuracy":0})
            discipline_results.append({"k": k, "best_accuracy": per_k_best.get('accuracy',0), "best_correct": per_k_best.get('correct',0), "best_weights": per_k_best.get('weights',{})})
            self.discipline_k = orig_k
        self.discipline_k = best_k
        results.sort(key=lambda x: x['accuracy'], reverse=True)
        discipline_results.sort(key=lambda x: x['best_accuracy'], reverse=True)
        return {"best": best_w, "best_k": best_k, "best_accuracy": best_acc, "all_results": results[:10], "discipline_tuning": discipline_results}

    def predictions_for(self, match, fast=False):
        home = match.get('home','Local')
        away = match.get('away','Visita')
        league = match.get('league','Futbol')
        league_code = match.get('league_code','')
        str_home = self._team_strength(home)
        str_away = self._team_strength(away)
        att_home, def_home, mp_home = self._team_attack_defense(home)
        att_away, def_away, mp_away = self._team_attack_defense(away)
        form_home = self._team_form_ema(home)
        form_away = self._team_form_ema(away)
        home_adv = self._get_home_adv(league_code, league)

        home_rest_raw = match.get('home_rest_days')
        away_rest_raw = match.get('away_rest_days')
        home_last = match.get('home_last_date')
        away_last = match.get('away_last_date')
        match_date = match.get('date','')

        if home_rest_raw is not None:
            home_rest = int(home_rest_raw)
        elif home_last:
            home_rest = self._calc_rest_days(match_date, home_last)
        else:
            home_rest = 7

        if away_rest_raw is not None:
            away_rest = int(away_rest_raw)
        elif away_last:
            away_rest = self._calc_rest_days(match_date, away_last)
        else:
            away_rest = 7

        rest_home_factor = self._rest_fatigue_factor(home_rest)
        rest_away_factor = self._rest_fatigue_factor(away_rest)

        # V127 - Viaje y Altura
        travel_distance = self._calc_travel_distance(home, away)
        travel_factor = self._travel_fatigue_factor(travel_distance)
        altitude_factor = self._altitude_factor(home, away)

        if home in self.team_stats and self.team_stats[home].get("mp",0) > 0:
            s_home = self.team_stats[home]
            s_away = self.team_stats.get(away, {"mp":0, "avg_for":1.2, "avg_against":1.2})
            disc_home = s_home.get("discipline_index", 1.0)
            disc_away = s_away.get("discipline_index", 1.0)
            poss_home = s_home.get("avg_possession", 50)
            poss_away = s_away.get("avg_possession", 50)
            disc_factor_home = 1.0 - (disc_home - 1.0) * 0.25 * self.discipline_k
            disc_factor_away = 1.0 - (disc_away - 1.0) * 0.25 * self.discipline_k
            poss_factor_home = 0.9 + (poss_home - 50) * 0.01
            poss_factor_away = 0.9 + (poss_away - 50) * 0.01

            xg_home = round((s_home.get("avg_for", att_home) * 0.6 + (2 - s_away.get("avg_against", def_away)) * 0.4) * home_adv * disc_factor_home * poss_factor_home * rest_home_factor["attack"] + form_home, 2)
            xg_away = round((s_away.get("avg_for", att_away) * 0.6 + (2 - s_home.get("avg_against", def_home)) * 0.4) * (2 - home_adv + 1) /2 *0.92 * disc_factor_away * poss_factor_away * rest_away_factor["attack"] + form_away, 2)
            xg_home = max(0.15, xg_home)
            xg_away = max(0.15, xg_away)
            xg_source = f"REAL team_stats + HomeAdv {home_adv} {mp_home}/{mp_away} pj"
        elif self.history_loaded and mp_home > 0:
            xg_home = round((att_home * 0.7 + (2 - def_away) * 0.3) * home_adv, 2)
            xg_away = round((att_away * 0.7 + (2 - def_home) * 0.3) * 0.92, 2)
            xg_home = max(0.2, xg_home + form_home)
            xg_away = max(0.2, xg_away + form_away)
            xg_source = f"ELO MOV + HomeAdv {home_adv}"
        elif self.history_loaded:
            xg_home = round(1.35 * str_home * home_adv, 2)
            xg_away = round(1.15 * str_away * 0.95, 2)
            xg_source = f"REAL ELO tabla {self.elo_source} HomeAdv {home_adv}"
        else:
            xg_home = round(1.35 * str_home * 1.2, 2)
            xg_away = round(1.15 * str_away, 2)
            xg_source = "FALLBACK hash"

        prob_poisson_dc = self._calc_1x2_from_xg_dixon_coles(xg_home, xg_away, rho=0.12)

        diff = str_home - str_away
        elo_adj = diff * 20
        rest_penalty_home = rest_home_factor["prob_penalty"]
        rest_penalty_away = rest_away_factor["prob_penalty"]

        disc_penalty_home = 0
        disc_penalty_away = 0
        try:
            if home in self.team_stats:
                s_h = self.team_stats[home]
                disc_idx_h = s_h.get("discipline_index", 1.0)
                y_h = s_h.get("avg_yellow", 2.0)
                r_h = s_h.get("avg_red", 0.08)
                f_h = s_h.get("avg_fouls", 13.0)
                disc_penalty_home = ((disc_idx_h - 1.0)*10 + max(0, y_h - 2.2)*2.0 + r_h*20 + max(0, f_h - 13.5)*0.5) * self.discipline_k
            if away in self.team_stats:
                s_a = self.team_stats[away]
                disc_idx_a = s_a.get("discipline_index", 1.0)
                y_a = s_a.get("avg_yellow", 2.0)
                r_a = s_a.get("avg_red", 0.08)
                f_a = s_a.get("avg_fouls", 13.0)
                disc_penalty_away = ((disc_idx_a - 1.0)*10 + max(0, y_a - 2.2)*2.0 + r_a*20 + max(0, f_a - 13.5)*0.5) * self.discipline_k
        except Exception as e_disc:
            print(f"[V124 discipline] error {e_disc}")

        # V127 - Penalidades viaje y altura para visitante
        travel_penalty = travel_factor["prob_penalty"]
        altitude_penalty = altitude_factor["prob_penalty"]

        prob_elo_mov = {
            "1": max(5, min(85, prob_poisson_dc["1"] + elo_adj + rest_penalty_home - disc_penalty_home - travel_penalty - altitude_penalty)),
            "X": prob_poisson_dc["X"] - (rest_penalty_home + rest_penalty_away)/2 * -0.3 + (disc_penalty_home + disc_penalty_away)*0.2 + (travel_penalty + altitude_penalty)*0.1,
            "2": max(5, min(85, prob_poisson_dc["2"] - elo_adj + rest_penalty_away - disc_penalty_away + travel_penalty + altitude_penalty)),
        }
        s = prob_elo_mov["1"]+prob_elo_mov["X"]+prob_elo_mov["2"]
        prob_elo_mov = {k: round(v/s*100,1) for k,v in prob_elo_mov.items()}

        if home in self.team_stats:
            form_diff = form_home - form_away
            prob_forma_ema = {
                "1": max(5, min(85, prob_poisson_dc["1"] + form_diff*35)),
                "X": prob_poisson_dc["X"],
                "2": max(5, min(85, prob_poisson_dc["2"] - form_diff*35)),
            }
        else:
            import hashlib
            h = int(hashlib.md5((home+away).encode()).hexdigest()[0:2],16) % 20 - 10
            prob_forma_ema = {
                "1": max(5, min(85, prob_poisson_dc["1"] + h*0.3)),
                "X": prob_poisson_dc["X"],
                "2": max(5, min(85, prob_poisson_dc["2"] - h*0.3)),
            }
        s = prob_forma_ema["1"]+prob_forma_ema["X"]+prob_forma_ema["2"]
        prob_forma_ema = {k: round(v/s*100,1) for k,v in prob_forma_ema.items()}

        if fast:
            prob_mc_interval = {"1": 33.3, "X": 33.3, "2": 33.3}
        else:
            prob_mc_interval = self._montecarlo_interval(xg_home, xg_away)

        w = self.weights
        final_1 = prob_poisson_dc["1"]*w["poisson_dc"] + prob_elo_mov["1"]*w["elo_mov"] + prob_forma_ema["1"]*w["forma_ema"]
        final_X = prob_poisson_dc["X"]*w["poisson_dc"] + prob_elo_mov["X"]*w["elo_mov"] + prob_forma_ema["X"]*w["forma_ema"]
        final_2 = prob_poisson_dc["2"]*w["poisson_dc"] + prob_elo_mov["2"]*w["elo_mov"] + prob_forma_ema["2"]*w["forma_ema"]

        total = final_1 + final_X + final_2
        probs = {
            "1": round(final_1/total*100,1),
            "X": round(final_X/total*100,1),
            "2": round(final_2/total*100,1),
        }

        if probs["1"] > probs["2"] and probs["1"] > probs["X"]:
            fav = home
        elif probs["2"] > probs["1"] and probs["2"] > probs["X"]:
            fav = away
        else:
            fav = "Empate"

        diff_strength = abs(str_home - str_away)
        rest_conf_penalty = rest_home_factor.get("conf_penalty",0) + rest_away_factor.get("conf_penalty",0)
        if (rest_home_factor.get("tipo") in ["fatiga","oxido_medio","oxido_alto","oxido_critico"] and 
            rest_away_factor.get("tipo") in ["fatiga","oxido_medio","oxido_alto","oxido_critico"] and
            rest_home_factor["tipo"] != rest_away_factor["tipo"]):
            rest_conf_penalty += 1

        if self.history_loaded:
            min_mp = min(mp_home, mp_away) if mp_home>0 else 5
            if min_mp >= 10 and diff_strength > 0.2:
                confianza = "Alta"
                evidencia = 9
                riesgo = "Bajo"
            elif min_mp >= 5 or self.elo_source=="elo_ratings_table":
                confianza = "Media"
                evidencia = 6
                riesgo = "Medio"
            else:
                confianza = "Limitada"
                evidencia = 4
                riesgo = "Alto"
        else:
            if diff_strength > 0.25:
                confianza = "Alta"
                evidencia = 9
                riesgo = "Bajo"
            elif diff_strength > 0.12:
                confianza = "Media"
                evidencia = 6
                riesgo = "Medio"
            else:
                confianza = "Limitada"
                evidencia = 4
                riesgo = "Alto"

        is_oxido_medio_plus = rest_home_factor.get("tipo") in ["oxido_medio","oxido_alto","oxido_critico"] or rest_away_factor.get("tipo") in ["oxido_medio","oxido_alto","oxido_critico"]
        is_fatiga_alta = rest_home_factor.get("tipo") in ["fatiga"] and rest_home_factor.get("attack",1) <= 0.86 or rest_away_factor.get("tipo") in ["fatiga"] and rest_away_factor.get("attack",1) <= 0.86

        if rest_conf_penalty >= 2:
            if confianza == "Alta":
                confianza = "Media"
            elif confianza == "Media":
                confianza = "Limitada"
            riesgo = "Alto"
            evidencia = max(2, evidencia - 2)
        elif rest_conf_penalty == 1:
            if confianza == "Alta":
                confianza = "Media"
                evidencia = max(3, evidencia - 1)
            elif confianza == "Media" and (is_oxido_medio_plus or is_fatiga_alta):
                confianza = "Limitada"
                riesgo = "Alto" if riesgo == "Medio" else riesgo
                evidencia = max(3, evidencia - 1)
            elif confianza == "Media":
                evidencia = max(4, evidencia - 1)

        if evidencia >= 10:
            suf = "adecuada"
        elif evidencia >= 5:
            suf = "parcial"
        elif evidencia >= 1:
            suf = "limitada"
        else:
            suf = "PASS"

        home_score = match.get('home_score')
        away_score = match.get('away_score')
        estado = match.get('estado','PROGRAMADO')
        resultado_real = None
        acierto = None
        if home_score is not None and away_score is not None:
            if home_score > away_score:
                resultado_real = "1"
            elif home_score == away_score:
                resultado_real = "X"
            else:
                resultado_real = "2"
            max_prob_key = max(probs, key=lambda k: probs[k])
            if estado == 'FINALIZADO':
                acierto = (max_prob_key == resultado_real)

        if self.history_loaded:
            elo_home = self.elo.get(home, 1500)
            elo_away = self.elo.get(away, 1500)
            explic = [
                f"xG {xg_home}-{xg_away} ({xg_source}) Dixon-Coles rho=0.12",
                f"ELO MOV {home}={elo_home:.0f} vs {away}={elo_away:.0f} diff={elo_home-elo_away:.0f} src={self.elo_source}",
                f"Ataque {home}={att_home:.2f} Def={def_home:.2f} Disc={s_home.get('discipline_index',1.0):.2f} Poss={s_home.get('avg_possession',50):.0f}% | {away} Att={att_away:.2f} Def={def_away:.2f} Disc={s_away.get('discipline_index',1.0):.2f} Poss={s_away.get('avg_possession',50):.0f}% HomeAdv={home_adv} src={self.team_stats_source}",
                f"Forma EMA {home}={form_home:.3f} {away}={form_away:.3f}",
                f"Descanso {home}={home_rest}d {rest_home_factor['label']} att={rest_home_factor['attack']:.2f} | {away}={away_rest}d {rest_away_factor['label']} att={rest_away_factor['attack']:.2f}",
                f"Viaje {travel_factor['label']} penal {travel_factor['prob_penalty']}% | Altura {altitude_factor['label']} penal {altitude_factor['prob_penalty']}%",
                f"MC validador 6000: 1={prob_mc_interval['1']}% X={prob_mc_interval['X']}% 2={prob_mc_interval['2']}%"
            ]
        else:
            explic = [
                f"xG {xg_home}-{xg_away} ({xg_source})",
                f"Fuerza {home}={str_home:.2f} vs {away}={str_away:.2f} HomeAdv={home_adv}",
                f"MC validador 6000: 1={prob_mc_interval['1']}% X={prob_mc_interval['X']}% 2={prob_mc_interval['2']}%"
            ]

        return {
            "match_id": match.get('id'),
            "home": home,
            "away": away,
            "league": league,
            "time": match.get('time',''),
            "date": match.get('date',''),
            "status": match.get('status','NS'),
            "xg_home": xg_home,
            "xg_away": xg_away,
            "probabilities": probs,
            "prob_details": {
                "poisson_dc": prob_poisson_dc,
                "elo_mov": prob_elo_mov,
                "forma_ema": prob_forma_ema,
                "montecarlo_validador": prob_mc_interval,
                "weights": w,
                "home_adv": home_adv,
                "viaje_km": travel_distance,
                "viaje_factor": travel_factor,
                "altura_factor": altitude_factor
            },
            "favorite": fav,
            "confidence": confianza,
            "evidence": evidencia,
            "risk": riesgo,
            "suficiencia": suf,
            "explicacion": explic,
            "resultado_real": resultado_real,
            "acierto": acierto,
            "status": match.get('estado','PROGRAMADO')
        }
# END V127.2 Fix Health 404 + Viaje/Altura + 5714 historico + 65/25/10 k=0.5 + VersionHeader | 2026-11-01 18:27:00 | backend/core/model.py
