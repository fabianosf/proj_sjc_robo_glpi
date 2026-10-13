#!/usr/bin/env python3
"""
Ponto de entrada SGC na raiz do projeto.

Uso (padrão das demais aplicações):
    python main.py

Se não estiver no venv, reexecuta automaticamente com venv/Scripts/python.exe
(Windows) ou venv/bin/python (Linux).

Com SGC_HEADLESS=1 (Iniciar_SGC.vbs): usa pythonw e redireciona stdout/stderr para log/.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_MAIN = ROOT / "python" / "main.py"


def _headless() -> bool:
    return (os.getenv("SGC_HEADLESS") or "").strip().lower() in ("1", "true", "yes", "on")


def _venv_scripts() -> Path | None:
    if os.name == "nt":
        scripts = ROOT / "venv" / "Scripts"
    else:
        scripts = ROOT / "venv" / "bin"
    return scripts if scripts.is_dir() else None


def _preferred_venv_python() -> Path | None:
    scripts = _venv_scripts()
    if scripts is None:
        return None
    if os.name == "nt":
        if _headless():
            for name in ("pythonw.exe", "python.exe"):
                candidate = scripts / name
                if candidate.is_file():
                    return candidate
        candidate = scripts / "python.exe"
        return candidate if candidate.is_file() else None
    candidate = scripts / "python"
    return candidate if candidate.is_file() else None


def _in_venv(current: str) -> bool:
    scripts = _venv_scripts()
    if scripts is None:
        return False
    try:
        cur = Path(current).resolve()
        if cur.parent.resolve() != scripts.resolve():
            return False
        name = cur.name.lower()
        if os.name == "nt":
            return name in ("python.exe", "pythonw.exe")
        return name == "python"
    except OSError:
        return False


def _redirect_stdio() -> None:
    """Sem janela: manda prints para arquivo (pythonw / headless)."""
    log_dir = ROOT / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "worker_stdout.log"
    # line buffering
    stream = open(path, "a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = stream
    sys.stderr = stream


def _run_app() -> None:
    if not APP_MAIN.is_file():
        print(f"[ERRO] Aplicação não encontrada: {APP_MAIN}", file=sys.stderr)
        sys.exit(1)

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "python"))
    runpy.run_path(str(APP_MAIN), run_name="__main__")


def main() -> None:
    if _headless():
        _redirect_stdio()

    venv_py = _preferred_venv_python()
    if venv_py is None:
        print(
            "[AVISO] Ambiente virtual não encontrado. "
            "Execute setup_env.bat (Windows) ou ./setup_env.sh (Linux).",
            file=sys.stderr,
        )
        _run_app()
        return

    if not _in_venv(sys.executable):
        os.execv(str(venv_py), [str(venv_py), str(Path(__file__).resolve()), *sys.argv[1:]])

    # Se headless pediu pythonw mas ainda estamos em python.exe (console), troca
    if (
        os.name == "nt"
        and _headless()
        and Path(sys.executable).name.lower() == "python.exe"
        and (ROOT / "venv" / "Scripts" / "pythonw.exe").is_file()
    ):
        pyw = ROOT / "venv" / "Scripts" / "pythonw.exe"
        os.execv(str(pyw), [str(pyw), str(Path(__file__).resolve()), *sys.argv[1:]])

    _run_app()


if __name__ == "__main__":
    main()
