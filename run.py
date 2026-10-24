from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent
REPO_PATH = ROOT / 'backend' / 'data' / 'lian.db'

# Asegurar que backend/data exista
(REPO_PATH.parent / 'public_priors.json').parent.mkdir(parents=True, exist_ok=True)
if not (REPO_PATH.parent / 'public_priors.json').exists():
    (REPO_PATH.parent / 'public_priors.json').write_text('{}', encoding='utf-8')

# Inicializar BD con tablas
sys.path.insert(0, str(ROOT))
from backend.data.repo import Repo

repo = Repo(str(REPO_PATH))
if hasattr(repo, 'init_all'):
    repo.init_all()
else:
    # fallback para repo.py antiguo
    if hasattr(repo, 'init'):
        repo.init()

print(f"[run.py] DB lista en {REPO_PATH}")

# Arrancar servidor
from backend.server import main as server_main
if __name__ == "__main__":
    server_main()
