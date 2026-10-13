# paths.py — caminhos absolutos da raiz do projeto SGC

from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PYTHON_DIR.parent

CONF_DIR = PROJECT_ROOT / "conf"
LOG_DIR = PROJECT_ROOT / "log"
SQL_DIR = PROJECT_ROOT / "sql"
MODEL_DIR = PROJECT_ROOT / "Modelo"
RELATORIOS_DIR = PROJECT_ROOT / "relatorios"
DRIVERS_DIR = PROJECT_ROOT / "drivers"
ARQAUX_FILE = PROJECT_ROOT / "arqaux.txt"
