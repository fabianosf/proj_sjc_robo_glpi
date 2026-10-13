"""Garante import do pacote legado `python/` (DAL) sem alterar o worker."""

from __future__ import annotations

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _APP_DIR.parent
PROJECT_ROOT = _BACKEND_DIR.parent
PYTHON_DIR = PROJECT_ROOT / "python"


def ensure_legacy_path() -> Path:
    """Insere `python/` no sys.path (idempotente)."""
    python_str = str(PYTHON_DIR)
    if python_str not in sys.path:
        sys.path.insert(0, python_str)
    return PYTHON_DIR
