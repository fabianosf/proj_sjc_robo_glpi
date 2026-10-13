#!/usr/bin/env bash
# Inicia o monitoramento SGC usando o venv local.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

PYTHON="${ROOT}/venv/bin/python"

if [[ ! -x "${PYTHON}" ]]; then
    echo "[ERRO] Ambiente virtual não encontrado: ${PYTHON}" >&2
    echo "Execute primeiro: ./setup_env.sh" >&2
    exit 1
fi

exec "${PYTHON}" main.py "$@"
