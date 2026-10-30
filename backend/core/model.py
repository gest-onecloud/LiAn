
class Model:
    VERSION = "V64.6.0 REAL MODE - Paso 1"
    def predictions_for(self, match, fast=False):
        return {
            "match_id": match.get('id'),
            "home": match.get('home'),
            "away": match.get('away'),
            "time": match.get('time'),
            "league": match.get('league'),
            "status": "PROGRAMADO" if not fast else "CARGANDO...",
            "favorite": f"{match.get('home')} vs {match.get('away')}",
            "probabilities": {"1": 0, "X": 0, "2": 0},
            "confidence": 0,
            "evidence": 0,
            "prediction_fast": fast
        }
