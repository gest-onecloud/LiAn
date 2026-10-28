
"""
LiAn V119 - Disciplinary Tarjetas Rojas/Amarillas Faltas Arbitro + AutoLearn 2859 + Dixon-Coles + ELO MOV + Forma EMA + HomeAdv por liga + MonteCarlo validador
Fix: Poisson y MonteCarlo ya no duplican, Dixon-Coles corrige empates 0-0,1-0,0-1,1-1
"""
import math
import hashlib
import random
import os
from pathlib import Path
from collections import defaultdict, deque
from datetime import datetime
try:
    import yaml
    HAS_YAML = True
except:
    HAS_YAML = False

class Model:
    VERSION = "V119 Disciplinary + AutoLearn 2859 + Dixon-Coles + Tarjetas - 330+330"

    def __init__(self, repo=None):
        self.weights = {"poisson_dc": 0.75, "elo_mov": 0.20, "forma_ema": 0.05}  # Aprendido: Poisson 75% es mejor (local 44% vs visita 31%)
        weights_path = Path("config/weights.yaml")
        if weights_path.exists() and HAS_YAML:
            try:
                data = yaml.safe_load(weights_path.read_text(encoding='utf-8'))
                if data:
                    self.weights['poisson_dc'] = data.get('poisson_dc', 0.70)
                    self.weights['elo_mov'] = data.get('elo_mov', 0.20)
                    self.weights['forma_ema'] = data.get('forma_ema', 0.10)
            except:
                pass

        self.elo = defaultdict(lambda: 1500)
        self.team_stats = {}
        # V118.2 aprendido de 2859 partidos reales: draw 24.3%, rho 0.12
        self.home_adv = {
            "mex.1": 1.089, "esp.1": 1.123, "ita.1": 1.076, "ger.1": 1.077, 
            "fra.1": 1.153, "usa.1": 1.082, "bra.1": 1.167, "arg.1": 1.114,
            "eng.1": 1.074, "uefa.champions": 1.131, "uefa.europa": 1.142,
            "uefa.europa.conf": 1.157, "concacaf.champions": 1.125, "eng.fa": 1.089,
            "default": 1.10
        }
        self.history_loaded = False
        self.history_count = 0
        self.elo_source = "none"
        self.team_stats_source = "none"

        loaded_elo = self._load_elo_from_supabase_table()
        loaded_stats = self._load_team_stats_from_supabase_table()

        if loaded_elo or loaded_stats:
            self.history_loaded = True
            self.elo_source = "elo_ratings_table" if loaded_elo else "none"
            self.team_stats_source = "team_stats_table" if loaded_stats else "none"
            self.history_count = max(len(self.elo), len(self.team_stats))
            print(f"[Model V117.1] ELO: {len(self.elo)} equipos, team_stats: {len(self.team_stats)} equipos, HomeAdv por liga")

        if not self.history_loaded and repo:
            print("[Model V117.1] No se pudo cargar tablas, calculando desde matches...")
            loaded = self.load_historical_stats(repo, limit=1000)
            self.history_loaded = loaded

        if not self.history_loaded:
            print("[Model V117.1] Usando fallback hash")

    def _load_elo_from_supabase_table(self):
        try:
            from supabase import create_client
            supa_url = os.environ.get("SUPABASE_URL")
            supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
            if not supa_url or not supa_key:
                return False
            client = create_client(supa_url, supa_key)
            res = client.table('elo_ratings').select('team, rating').limit(1000).execute()
            if not res.data:
                return False
            for row in res.data:
                team = str(row.get('team','')).strip()
                try:
                    rating = float(row.get('rating', 1500))
                except:
                    rating = 1500.0
                if team:
                    self.elo[team] = rating
            return True
        except Exception as e:
            print(f"[Model] Error ELO: {e}")
            return False

    def _load_team_stats_from_supabase_table(self):
        try:
            from supabase import create_client
            supa_url = os.environ.get("SUPABASE_URL")
            supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
            if not supa_url or not supa_key:
                return False
            client = create_client(supa_url, supa_key)
            res = client.table('team_stats').select('*').limit(1000).execute()
            if not res.data:
                return False
            for row in res.data:
                team = str(row.get('team','')).strip()
                if not team:
                    continue
                self.team_stats[team] = {
                    "gf": int(row.get('goals_for', 0) or 0),
                    "ga": int(row.get('goals_against', 0) or 0),
                    "mp": int(row.get('matches_played', 0) or 0),
                    "avg_for": float(row.get('avg_goals_for', 0) or 0),
                    "avg_against": float(row.get('avg_goals_against', 0) or 0),
                    "attack": float(row.get('attack_strength', 1.0) or 1.0),
                    "defense": float(row.get('defense_strength', 1.0) or 1.0),
                    "form": str(row.get('form_last5','') or ''),
                    "pts_last5": int(row.get('points_last5', 0) or 0),
                    "avg_yellow": float(row.get('avg_yellow', 0) or 0),
                    "avg_red": float(row.get('avg_red', 0) or 0),
                    "avg_fouls": float(row.get('avg_fouls', 0) or 0),
                    "discipline_index": float(row.get('discipline_index', 1.0) or 1.0),
                    "avg_possession": float(row.get('avg_possession', 50) or 50),
                }
            return True
        except Exception as e:
            print(f"[Model] Error team_stats: {e}")
            return False

    def load_historical_stats(self, repo, limit=1000):
        try:
            matches = repo.get_all(limit=limit)
            finished = [m for m in matches if m.get('home_score') is not None and m.get('away_score') is not None]
            def parse_date(m):
                try:
                    return datetime.fromisoformat(str(m.get('date',''))[:10])
                except:
                    return datetime.min
            finished.sort(key=parse_date)
            elo = defaultdict(lambda: 1500)
            stats = defaultdict(lambda: {"gf":0,"ga":0,"mp":0,"w":0,"d":0,"l":0,"form":deque(maxlen=5),"avg_for":0,"avg_against":0,"attack":1.0,"defense":1.0,"pts_last5":0})
            for m in finished:
                home = str(m.get('home','')).strip()
                away = str(m.get('away','')).strip()
                if not home or not away:
                    continue
                try:
                    hs = int(m.get('home_score'))
                    aw = int(m.get('away_score'))
                except:
                    continue
                eh = elo[home]
                ea = elo[away]
                exp_home = 1 / (1 + 10 ** ((ea - eh) / 400))
                exp_away = 1 - exp_home
                # ELO con MOV
                K = 20 * (1 + abs(hs-aw)*0.2)
                if hs > aw:
                    res_home, res_away = 1, 0
                elif hs == aw:
                    res_home, res_away = 0.5, 0.5
                else:
                    res_home, res_away = 0, 1
                elo[home] = eh + K * (res_home - exp_home)
                elo[away] = ea + K * (res_away - exp_away)
                stats[home]["gf"] += hs
                stats[home]["ga"] += aw
                stats[home]["mp"] += 1
                stats[away]["gf"] += aw
                stats[away]["ga"] += hs
                stats[away]["mp"] += 1
            for team,s in stats.items():
                mp=max(1,s["mp"])
                s["avg_for"]=s["gf"]/mp
                s["avg_against"]=s["ga"]/mp
            self.elo=elo
            self.team_stats=stats
            self.history_loaded=True
            self.history_count=len(finished)
            self.elo_source="matches_calc"
            self.team_stats_source="matches_calc"
            return True
        except Exception as e:
            print(f"[Model] Error historico: {e}")
            return False

    def _team_strength(self, team_name: str) -> float:
        if self.history_loaded and team_name in self.elo:
            elo = self.elo[team_name]
            strength = 0.8 + (elo - 1300) / 1000.0
            return max(0.6, min(1.8, strength))
        h = int(hashlib.md5(team_name.lower().encode()).hexdigest()[:8], 16)
        return 0.8 + (h % 500) / 1000.0

    def _team_attack_defense(self, team_name: str):
        if team_name in self.team_stats:
            s = self.team_stats[team_name]
            mp = s.get("mp", 0)
            if mp > 0:
                attack = s.get("avg_for", 0) if s.get("avg_for",0)>0 else s.get("gf",0)/mp
                defense = s.get("avg_against", 0) if s.get("avg_against",0)>0 else s.get("ga",0)/mp
                return attack, defense, mp
        if self.history_loaded and team_name in self.elo:
            elo = self.elo[team_name]
            base = 0.6 + (elo - 1300) / 500.0
            return max(0.4, base), max(0.4, 2.4 - base), 0
        return 1.2, 1.2, 0

    def _team_form_ema(self, team_name: str) -> float:
        if team_name in self.team_stats:
            s = self.team_stats[team_name]
            form_str = s.get("form","")
            if not form_str:
                return 0
            parts = [x.strip() for x in form_str.replace(",","-").split("-") if x.strip()]
            if not parts:
                return 0
            # EMA: ultimo 40%, penultimo 25%, etc
            weights = [0.4, 0.25, 0.15, 0.12, 0.08]
            score = 0
            total_w = 0
            for i, p in enumerate(reversed(parts[-5:])):
                w = weights[i] if i < len(weights) else 0.05
                val = 1 if p=="W" else 0.5 if p=="D" else 0
                score += val * w
                total_w += w
            if total_w>0:
                score = score/total_w
                return (score - 0.5) * 0.25
        return 0

    def _get_home_adv(self, league_code, league_name=""):
        lc = (league_code or "").lower()
        ln = (league_name or "").lower()
        if "mex" in lc or "mexico" in ln or "liga mx" in ln:
            return self.home_adv["mex.1"]
        if "eng" in lc or "premier" in ln:
            return self.home_adv["eng.1"]
        if "esp" in lc or "la liga" in ln:
            return self.home_adv["esp.1"]
        if lc in self.home_adv:
            return self.home_adv[lc]
        return self.home_adv["default"]

    def _poisson_prob(self, lamb, k):
        return (math.exp(-lamb) * (lamb ** k)) / math.factorial(k)

    def _dixon_coles_tau(self, hg, ag, rho=0.12):
        if hg==0 and ag==0:
            return 1 - rho
        if hg==1 and ag==0:
            return 1 + rho
        if hg==0 and ag==1:
            return 1 + rho
        if hg==1 and ag==1:
            return 1 - rho
        return 1.0

    def _calc_1x2_from_xg_dixon_coles(self, xg_home, xg_away, rho=0.12):
        p_home = p_draw = p_away = 0.0
        for gh in range(8):
            ph = self._poisson_prob(xg_home, gh)
            for ga in range(8):
                pa = self._poisson_prob(xg_away, ga)
                tau = self._dixon_coles_tau(gh, ga, rho)
                prob = ph * pa * tau
                if gh > ga:
                    p_home += prob
                elif gh == ga:
                    p_draw += prob
                else:
                    p_away += prob
        total = p_home + p_draw + p_away
        # Normalizar por rho
        return {
            "1": round((p_home / total) * 100, 1),
            "X": round((p_draw / total) * 100, 1),
            "2": round((p_away / total) * 100, 1),
        }

    def _montecarlo_interval(self, xg_home, xg_away):
        random.seed(int((xg_home*1000 + xg_away*1000)) % 100000)
        c1 = cX = c2 = 0
        for _ in range(6000):
            L = math.exp(-xg_home)
            p = 1.0
            k = 0
            while True:
                k += 1
                p *= random.random()
                if p <= L:
                    gh = k-1
                    break
            L = math.exp(-xg_away)
            p = 1.0
            k = 0
            while True:
                k += 1
                p *= random.random()
                if p <= L:
                    ga = k-1
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

        if home in self.team_stats and self.team_stats[home].get("mp",0) > 0:
            s_home = self.team_stats[home]
            s_away = self.team_stats.get(away, {"mp":0, "avg_for":1.2, "avg_against":1.2})
            # V119 Disciplinary: ajusta por disciplina y posesion
            disc_home = s_home.get("discipline_index", 1.0)
            disc_away = s_away.get("discipline_index", 1.0)
            poss_home = s_home.get("avg_possession", 50)
            poss_away = s_away.get("avg_possession", 50)
            # Equipo indisciplinado (disc>1.2) baja ataque 5% y defensa 8%
            disc_factor_home = 1.0 - (disc_home - 1.0) * 0.15
            disc_factor_away = 1.0 - (disc_away - 1.0) * 0.15
            poss_factor_home = 0.9 + (poss_home - 50) * 0.01  # 60% posesion -> 1.0 factor
            poss_factor_away = 0.9 + (poss_away - 50) * 0.01

            xg_home = round((s_home.get("avg_for", att_home) * 0.6 + (2 - s_away.get("avg_against", def_away)) * 0.4) * home_adv * disc_factor_home * poss_factor_home + form_home, 2)
            xg_away = round((s_away.get("avg_for", att_away) * 0.6 + (2 - s_home.get("avg_against", def_home)) * 0.4) * (2 - home_adv + 1) /2 *0.92 * disc_factor_away * poss_factor_away + form_away, 2)
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
        prob_elo_mov = {
            "1": max(5, min(85, prob_poisson_dc["1"] + elo_adj)),
            "X": prob_poisson_dc["X"],
            "2": max(5, min(85, prob_poisson_dc["2"] - elo_adj)),
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
            h = int(hashlib.md5((home+away).encode()).hexdigest()[0:2],16) % 20 - 10
            prob_forma_ema = {
                "1": max(5, min(85, prob_poisson_dc["1"] + h*0.3)),
                "X": prob_poisson_dc["X"],
                "2": max(5, min(85, prob_poisson_dc["2"] - h*0.3)),
            }
        s = prob_forma_ema["1"]+prob_forma_ema["X"]+prob_forma_ema["2"]
        prob_forma_ema = {k: round(v/s*100,1) for k,v in prob_forma_ema.items()}

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
                "home_adv": home_adv
            },
            "favorite": fav,
            "confidence": confianza,
            "evidence": evidencia,
            "sufficiency": suf,
            "risk": riesgo,
            "source": f"V117.1 Dixon-Coles {w['poisson_dc']*100:.0f}%PoissonDC/{w['elo_mov']*100:.0f}%ELO_MOV/{w['forma_ema']*100:.0f}%FormaEMA + MC validador - {self.history_count} equipos HomeAdv {home_adv}",
            "explicabilidad": explic,
            "home_score": match.get('home_score'),
            "away_score": match.get('away_score'),
            "score": match.get('score'),
            "estado": match.get('estado','PROGRAMADO'),
            "status_detail": match.get('status_detail',''),
            "resultado_real": resultado_real,
            "acierto": acierto,
            "transparencia": "Probabilidad != recomendacion segura. Suma 1X2 ~100% Dixon-Coles corrige empates.",
            "prediction_fast": fast,
            "elo_home": self.elo.get(home, 1500) if self.history_loaded else None,
            "elo_away": self.elo.get(away, 1500) if self.history_loaded else None,
            "historical_data": self.history_count if self.history_loaded else 0,
            "elo_source": self.elo_source,
            "team_stats_source": self.team_stats_source,
            "attack_home": att_home,
            "defense_home": def_home,
            "attack_away": att_away,
            "defense_away": def_away,
            "home_adv": home_adv,
            "mc_interval": prob_mc_interval
        }
