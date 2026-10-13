#!/usr/bin/env bash
# Wrapper SGC — sempre usa o Python do venv local.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${ROOT}/venv/bin/python"

if [[ ! -x "${PYTHON}" ]]; then
    echo "[ERRO] Ambiente virtual não encontrado: ${PYTHON}" >&2
    echo "Execute primeiro: ./setup_env.sh" >&2
    exit 1
fi

exec "${PYTHON}" "$@"
