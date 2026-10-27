
"""
LiAn V114.7 REAL ELO - Paso 5: ELO real + ataque/defensa desde historico Supabase
Ya no usa hash, usa historial real de 555+ partidos
Poisson 58%, ELO 16%, Forma 10%, MonteCarlo 16% - 6000 sims
"""
import math
import hashlib
import random
from pathlib import Path
from collections import defaultdict, deque
from datetime import datetime
try:
    import yaml
    HAS_YAML = True
except:
    HAS_YAML = False

class Model:
    VERSION = "V114.7 REAL ELO - Historico Supabase"

    def __init__(self, repo=None):
        # Cargar pesos
        self.weights = {"poisson": 0.58, "elo_fuerza": 0.16, "forma": 0.10, "montecarlo": 0.16}
        weights_path = Path("config/weights.yaml")
        if weights_path.exists() and HAS_YAML:
            try:
                data = yaml.safe_load(weights_path.read_text(encoding='utf-8'))
                if data:
                    self.weights['poisson'] = data.get('poisson', 0.58)
                    self.weights['elo_fuerza'] = data.get('elo_fuerza', 0.16)
                    self.weights['forma'] = data.get('forma', 0.10)
                    self.weights['montecarlo'] = data.get('montecarlo', 0.16)
            except:
                pass

        # Stats reales desde historico
        self.elo = defaultdict(lambda: 1500)  # ELO rating
        self.team_stats = {}  # ataque, defensa, partidos, forma
        self.history_loaded = False
        self.history_count = 0
        
        if repo:
            self.load_historical_stats(repo)

    def load_historical_stats(self, repo, limit=5000):
        """Carga historial real desde Supabase/SQLite y calcula ELO + ataque/defensa"""
        try:
            matches = repo.get_all(limit=limit)
            # Filtrar solo FINALIZADOS con marcador
            finished = [m for m in matches if m.get('home_score') is not None and m.get('away_score') is not None and m.get('estado') in ('FINALIZADO', 'FINALIZADO', None, '')]
            # Ordenar por fecha ascendente para calcular ELO cronologicamente
            def parse_date(m):
                try:
                    return datetime.fromisoformat(str(m.get('date',''))[:10])
                except:
                    return datetime.min
            finished.sort(key=parse_date)
            
            # Inicializar
            elo = defaultdict(lambda: 1500)
            stats = defaultdict(lambda: {"gf": 0, "ga": 0, "mp": 0, "w": 0, "d": 0, "l": 0, "form": deque(maxlen=5)})
            
            K = 20  # Factor K para ELO
            
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
                
                # ELO
                eh = elo[home]
                ea = elo[away]
                # Expected score
                exp_home = 1 / (1 + 10 ** ((ea - eh) / 400))
                exp_away = 1 - exp_home
                
                # Actual result
                if hs > aw:
                    res_home, res_away = 1, 0
                elif hs == aw:
                    res_home, res_away = 0.5, 0.5
                else:
                    res_home, res_away = 0, 1
                
                # Update ELO
                elo[home] = eh + K * (res_home - exp_home)
                elo[away] = ea + K * (res_away - exp_away)
                
                # Stats ataque/defensa
                stats[home]["gf"] += hs
                stats[home]["ga"] += aw
                stats[home]["mp"] += 1
                stats[away]["gf"] += aw
                stats[away]["ga"] += hs
                stats[away]["mp"] += 1
                
                if hs > aw:
                    stats[home]["w"] += 1
                    stats[away]["l"] += 1
                    stats[home]["form"].append("W")
                    stats[away]["form"].append("L")
                elif hs == aw:
                    stats[home]["d"] += 1
                    stats[away]["d"] += 1
                    stats[home]["form"].append("D")
                    stats[away]["form"].append("D")
                else:
                    stats[home]["l"] += 1
                    stats[away]["w"] += 1
                    stats[home]["form"].append("L")
                    stats[away]["form"].append("W")
            
            self.elo = elo
            self.team_stats = stats
            self.history_loaded = True
            self.history_count = len(finished)
            print(f"[Model V114.7] Historico cargado: {len(finished)} partidos finalizados, {len(elo)} equipos con ELO real")
            
        except Exception as e:
            import traceback
            print(f"[Model] Error cargando historico: {e}")
            print(traceback.format_exc()[:1000])
            self.history_loaded = False

    def _team_strength(self, team_name: str) -> float:
        """Ahora usa ELO real, no hash"""
        if self.history_loaded and team_name in self.elo:
            # Normalizar ELO 1500 -> 1.0, con rango 0.8 a 1.5
            elo = self.elo[team_name]
            # ELO 1300 = 0.8, 1500 = 1.0, 1700 = 1.2, 1900 = 1.4
            strength = 0.8 + (elo - 1300) / 1000.0
            return max(0.6, min(1.8, strength))
        # Fallback hash si no hay historico (equipo nuevo)
        h = int(hashlib.md5(team_name.lower().encode()).hexdigest()[:8], 16)
        return 0.8 + (h % 500) / 1000.0

    def _team_attack_defense(self, team_name: str):
        """Devuelve ataque y defensa reales"""
        if self.history_loaded and team_name in self.team_stats:
            s = self.team_stats[team_name]
            mp = max(1, s["mp"])
            attack = s["gf"] / mp  # Goles a favor por partido
            defense = s["ga"] / mp  # Goles en contra por partido
            return attack, defense, s["mp"]
        return 1.2, 1.2, 0  # Fallback promedio

    def _team_form(self, team_name: str) -> float:
        """Forma basada en ultimos 5: W=1, D=0.5, L=0"""
        if self.history_loaded and team_name in self.team_stats:
            form = self.team_stats[team_name]["form"]
            if not form:
                return 0
            score = sum(1 if x=="W" else 0.5 if x=="D" else 0 for x in form) / len(form)
            # Convertir a ajuste -0.1 a +0.1
            return (score - 0.5) * 0.2
        return 0

    def _poisson_prob(self, lamb, k):
        return (math.exp(-lamb) * (lamb ** k)) / math.factorial(k)

    def _calc_1x2_from_xg(self, xg_home, xg_away):
        p_home = p_draw = p_away = 0.0
        for gh in range(8):
            ph = self._poisson_prob(xg_home, gh)
            for ga in range(8):
                pa = self._poisson_prob(xg_away, ga)
                prob = ph * pa
                if gh > ga:
                    p_home += prob
                elif gh == ga:
                    p_draw += prob
                else:
                    p_away += prob
        total = p_home + p_draw + p_away
        return {
            "1": round((p_home / total) * 100, 1),
            "X": round((p_draw / total) * 100, 1),
            "2": round((p_away / total) * 100, 1),
        }

    def _montecarlo_6000(self, xg_home, xg_away):
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

        str_home = self._team_strength(home)
        str_away = self._team_strength(away)
        
        att_home, def_home, mp_home = self._team_attack_defense(home)
        att_away, def_away, mp_away = self._team_attack_defense(away)
        
        form_home = self._team_form(home)
        form_away = self._team_form(away)

        # xG REAL con ataque/defensa
        if self.history_loaded and mp_home > 3 and mp_away > 3:
            # Formula real: xG_home = ataque_home * (2 - defensa_away) * ventaja_local
            xg_home = round((att_home * 0.7 + (2 - def_away) * 0.3) * 1.15, 2)
            xg_away = round((att_away * 0.7 + (2 - def_home) * 0.3) * 0.95, 2)
            # Ajuste por forma
            xg_home = max(0.2, xg_home + form_home)
            xg_away = max(0.2, xg_away + form_away)
            xg_source = f"REAL {mp_home}/{mp_away} partidos"
        else:
            xg_home = round(1.35 * str_home * 1.2, 2)
            xg_away = round(1.15 * str_away, 2)
            xg_source = "FALLBACK hash (pocos datos)"

        # 1. Poisson 58%
        prob_poisson = self._calc_1x2_from_xg(xg_home, xg_away)

        # 2. ELO Fuerza 16%
        diff = str_home - str_away
        elo_adj = diff * 18  # Mas peso a ELO real
        prob_elo = {
            "1": max(5, min(85, prob_poisson["1"] + elo_adj)),
            "X": prob_poisson["X"],
            "2": max(5, min(85, prob_poisson["2"] - elo_adj)),
        }
        s = prob_elo["1"]+prob_elo["X"]+prob_elo["2"]
        prob_elo = {k: round(v/s*100,1) for k,v in prob_elo.items()}

        # 3. Forma 10% (real, no hash)
        if self.history_loaded:
            form_diff = form_home - form_away
            prob_forma = {
                "1": max(5, min(85, prob_poisson["1"] + form_diff*30)),
                "X": prob_poisson["X"],
                "2": max(5, min(85, prob_poisson["2"] - form_diff*30)),
            }
        else:
            h = int(hashlib.md5((home+away).encode()).hexdigest()[0:2],16) % 20 - 10
            prob_forma = {
                "1": max(5, min(85, prob_poisson["1"] + h*0.3)),
                "X": prob_poisson["X"],
                "2": max(5, min(85, prob_poisson["2"] - h*0.3)),
            }
        s = prob_forma["1"]+prob_forma["X"]+prob_forma["2"]
        prob_forma = {k: round(v/s*100,1) for k,v in prob_forma.items()}

        # 4. MonteCarlo 16%
        prob_mc = self._montecarlo_6000(xg_home, xg_away)

        # Ensemble
        w = self.weights
        final_1 = prob_poisson["1"]*w["poisson"] + prob_elo["1"]*w["elo_fuerza"] + prob_forma["1"]*w["forma"] + prob_mc["1"]*w["montecarlo"]
        final_X = prob_poisson["X"]*w["poisson"] + prob_elo["X"]*w["elo_fuerza"] + prob_forma["X"]*w["forma"] + prob_mc["X"]*w["montecarlo"]
        final_2 = prob_poisson["2"]*w["poisson"] + prob_elo["2"]*w["elo_fuerza"] + prob_forma["2"]*w["forma"] + prob_mc["2"]*w["montecarlo"]

        total = final_1 + final_X + final_2
        probs = {
            "1": round(final_1/total*100,1),
            "X": round(final_X/total*100,1),
            "2": round(final_2/total*100,1),
        }

        # Favorito
        if probs["1"] > probs["2"] and probs["1"] > probs["X"]:
            fav = home
        elif probs["2"] > probs["1"] and probs["2"] > probs["X"]:
            fav = away
        else:
            fav = "Empate"

        # Confianza basada en datos reales
        diff_strength = abs(str_home - str_away)
        if self.history_loaded:
            # Si tenemos muchos partidos, confianza mas precisa
            min_mp = min(mp_home, mp_away)
            if min_mp >= 10 and diff_strength > 0.2:
                confianza = "Alta"
                evidencia = 9
                riesgo = "Bajo"
            elif min_mp >= 5 and diff_strength > 0.1:
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

        # Explicabilidad mejorada
        if self.history_loaded and mp_home > 0:
            elo_home = self.elo.get(home, 1500)
            elo_away = self.elo.get(away, 1500)
            explic = [
                f"xG {xg_home}-{xg_away} ({xg_source})",
                f"ELO REAL {home}={elo_home:.0f} vs {away}={elo_away:.0f} diff={elo_home-elo_away:.0f}",
                f"Ataque {home}={att_home:.2f} Def={def_home:.2f} ({mp_home} pj) | {away} Att={att_away:.2f} Def={def_away:.2f} ({mp_away} pj)",
                f"Forma {home}={form_home:+.2f} {away}={form_away:+.2f}",
                f"MonteCarlo 6000 sims: 1={prob_mc['1']}% X={prob_mc['X']}% 2={prob_mc['2']}%"
            ]
        else:
            explic = [
                f"xG {xg_home}-{xg_away} con ventaja local 20% ({xg_source})",
                f"Fuerza {home}={str_home:.2f} vs {away}={str_away:.2f} diff={diff_strength:.2f}",
                f"MonteCarlo 6000 sims: 1={prob_mc['1']}% X={prob_mc['X']}% 2={prob_mc['2']}%"
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
                "poisson": prob_poisson,
                "elo": prob_elo,
                "forma": prob_forma,
                "montecarlo": prob_mc,
                "weights": w
            },
            "favorite": fav,
            "confidence": confianza,
            "evidence": evidencia,
            "sufficiency": suf,
            "risk": riesgo,
            "source": f"Ensemble REAL {w['poisson']*100:.0f}%Poisson/{w['elo_fuerza']*100:.0f}%ELO/{w['forma']*100:.0f}%Forma/{w['montecarlo']*100:.0f}%MC6000 - {self.history_count} partidos historicos" if self.history_loaded else f"Ensemble {w['poisson']*100:.0f}%Poisson/{w['elo_fuerza']*100:.0f}%ELO/{w['forma']*100:.0f}%Forma/{w['montecarlo']*100:.0f}%MC6000",
            "explicabilidad": explic,
            "home_score": match.get('home_score'),
            "away_score": match.get('away_score'),
            "score": match.get('score'),
            "estado": match.get('estado','PROGRAMADO'),
            "status_detail": match.get('status_detail',''),
            "resultado_real": resultado_real,
            "acierto": acierto,
            "transparencia": "Probabilidad != recomendacion segura. Suma 1X2 ~100%. Revisar datos faltantes.",
            "prediction_fast": fast,
            "elo_home": self.elo.get(home, 1500) if self.history_loaded else None,
            "elo_away": self.elo.get(away, 1500) if self.history_loaded else None,
            "historical_data": self.history_count if self.history_loaded else 0
        }
