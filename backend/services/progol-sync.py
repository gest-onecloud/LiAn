
import re
import json
from datetime import datetime
from pathlib import Path
import os

# Progol actual cache
CACHE_PATH = Path(__file__).parent.parent / 'data' / 'progol_current.json'

def get_cached_progol():
    try:
        if CACHE_PATH.exists():
            data = json.loads(CACHE_PATH.read_text(encoding='utf-8'))
            return data
    except:
        pass
    # Fallback Progol 30 oct 2026 from TuLotero capture
    return {
        "fecha": "2026-10-30",
        "hasta": "20:55",
        "fuente": "TuLotero - Captura manual",
        "progol": [
            {"n":1, "home":"PUEBLA", "away":"PUMAS"},
            {"n":2, "home":"PACHUCA", "away":"TIGRES"},
            {"n":3, "home":"AGUILAS", "away":"TOLUCA"},
            {"n":4, "home":"ELCHE", "away":"VALENCIA"},
            {"n":5, "home":"ATH. BILBAO", "away":"R. SOCIEDAD"},
            {"n":6, "home":"BOURNEMOUTH", "away":"LEEDS"},
            {"n":7, "home":"LIVERPOOL", "away":"ARSENAL"},
            {"n":8, "home":"MILAN", "away":"INTER MILAN"},
            {"n":9, "home":"JUVENTUS", "away":"NAPOLES"},
            {"n":10, "home":"AUGSBURGO", "away":"FRIBURGO"},
            {"n":11, "home":"LORIENT", "away":"BREST"},
            {"n":12, "home":"GREMIO", "away":"AT. MINEIRO"},
            {"n":13, "home":"BOCA JRS", "away":"RIVER PLATE"},
            {"n":14, "home":"U. CATOLICA", "away":"U. DE CHILE"}
        ],
        "revancha": [
            {"n":1, "home":"MONTERREY", "away":"TIJUANA"},
            {"n":2, "home":"GUADALAJARA", "away":"ATLANTE"},
            {"n":3, "home":"S. LAGUNA", "away":"NECAXA"},
            {"n":4, "home":"C. AZUL", "away":"LEON"},
            {"n":5, "home":"GETAFE", "away":"SEVILLA"},
            {"n":6, "home":"CHELSEA", "away":"MAN. UNITED"},
            {"n":7, "home":"AJAX", "away":"AZ ALKMAAR"}
        ]
    }

def save_progol(data):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data

def scrape_tulotero(html_text):
    """
    Intenta parsear HTML de web.tulotero.mx/jugar/progol-play
    Busca los 14 + 7 partidos con regex simple
    """
    try:
        # Buscar filas con L ... E ... V pattern
        # En TuLotero el HTML tiene <div>PUEBLA</div> etc.
        # Fallback: extraer textos en mayusculas de equipos
        matches = []
        # Regex para filas tipo: 1 L PUEBLA E PUMAS V
        # Como no tenemos HTML exacto ahora, devolver cache
        return None
    except Exception as e:
        print(f"[progol scrape error] {e}")
        return None

def fetch_latest_progol():
    """
    Intenta scrapear TuLotero, si falla devuelve cache
    Automatizable con cron cada 3 dias (Progol sale 2x por semana)
    """
    try:
        # Intentar con requests si está disponible
        try:
            import requests
            url = "https://web.tulotero.mx/jugar/progol-play/32856"
            # TuLotero requiere JS, pero probamos obtener HTML
            r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code==200:
                parsed = scrape_tulotero(r.text)
                if parsed:
                    parsed["fecha"]=datetime.now().strftime("%Y-%m-%d")
                    parsed["fuente"]="TuLotero auto-scrape"
                    save_progol(parsed)
                    return parsed
        except ImportError:
            print("[progol] requests no disponible, usando cache")
        except Exception as e:
            print(f"[progol fetch error] {e}")
    except:
        pass
    return get_cached_progol()

def parse_manual_input(text):
    """
    Permite pegar lista manual:
    1 PUEBLA vs PUMAS
    2 PACHUCA vs TIGRES
    ...
    """
    progol=[]
    revancha=[]
    lines=text.strip().split('\n')
    in_revancha=False
    for line in lines:
        line=line.strip()
        if not line: continue
        if 'revancha' in line.lower():
            in_revancha=True
            continue
        # Buscar patron: numero + home + vs + away
        m=re.match(r'(\d+)\s*[\.-]?\s*(.+?)\s+(?:vs|x|-)\s+(.+)', line, re.I)
        if m:
            n=int(m.group(1))
            home=m.group(2).strip().upper()
            away=m.group(3).strip().upper()
            entry={"n":n, "home":home, "away":away}
            if in_revancha:
                revancha.append(entry)
            else:
                progol.append(entry)
    return {"fecha":datetime.now().strftime("%Y-%m-%d"), "progol":progol[:14], "revancha":revancha[:7], "fuente":"Manual"}
