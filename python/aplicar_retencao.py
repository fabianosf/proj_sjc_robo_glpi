#!/usr/bin/env python3
"""
Aplica política de retenção documental (docs/retencao.md).

Uso:
  python python/aplicar_retencao.py           # dry-run (só lista)
  python python/aplicar_retencao.py --apply   # remove de fato

Não altera conf/, worker de atribuição nem ModeloML.pkl / backup ativo.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "log"
REL_DIR = ROOT / "relatorios"
MODELO_DIR = ROOT / "Modelo"

LOG_DIAS = 90
STDOUT_DIAS = 30
STDOUT_MAX_BYTES = 50 * 1024 * 1024
REL_DIAS = 365
MODELO_KEEP = 20  # alinhado a MAX_VERSOES

_DATE_LOG = re.compile(r"^(\d{2})-(\d{2})-(\d{4})\.log$", re.I)
_MODELO_V = re.compile(r"^ModeloML_v.+\.pkl$", re.I)


def _parse_log_date(name: str):
    m = _DATE_LOG.match(name)
    if not m:
        return None
    d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(y, mth, d)
    except ValueError:
        return None


def _candidates() -> list[Path]:
    agora = datetime.now()
    out: list[Path] = []

    if LOG_DIR.is_dir():
        for p in LOG_DIR.iterdir():
            if not p.is_file():
                continue
            name = p.name
            if name in ("worker_heartbeat.json", "agendador_state.json"):
                continue
            dt = _parse_log_date(name)
            if dt and dt < agora - timedelta(days=LOG_DIAS):
                out.append(p)
                continue
            if name.endswith(("_stdout.log", "_stderr.log")) or name in (
                "worker_stdout.log",
                "worker_stderr.log",
                "api_stdout.log",
                "api_stderr.log",
            ):
                age_ok = (agora - datetime.fromtimestamp(p.stat().st_mtime)) > timedelta(
                    days=STDOUT_DIAS
                )
                size_ok = p.stat().st_size > STDOUT_MAX_BYTES
                if age_ok or size_ok:
                    out.append(p)

    if REL_DIR.is_dir():
        lim = agora - timedelta(days=REL_DIAS)
        for p in REL_DIR.iterdir():
            if p.is_file() and p.suffix.lower() in (".pdf", ".txt"):
                if datetime.fromtimestamp(p.stat().st_mtime) < lim:
                    out.append(p)

    if MODELO_DIR.is_dir():
        versoes = sorted(
            [p for p in MODELO_DIR.iterdir() if p.is_file() and _MODELO_V.match(p.name)],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        for p in versoes[MODELO_KEEP:]:
            out.append(p)
        for extra in ("X.pkl", "ModeloML_test_backup.pkl"):
            ep = MODELO_DIR / extra
            if ep.is_file():
                out.append(ep)

    # únicos, caminhos estáveis
    seen = set()
    uniq: list[Path] = []
    for p in out:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser(description="Retenção SGC (log/relatorios/Modelo)")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Remove arquivos elegíveis (sem isto, apenas lista — dry-run)",
    )
    args = ap.parse_args()
    files = _candidates()
    if not files:
        print("[RETENCAO] Nada a limpar.")
        return 0
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[RETENCAO] {mode}: {len(files)} arquivo(s)")
    for p in files:
        try:
            rel = p.relative_to(ROOT)
        except ValueError:
            rel = p
        print(f"  - {rel}")
        if args.apply:
            p.unlink(missing_ok=True)
    if not args.apply:
        print("[RETENCAO] Rode com --apply para remover.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
