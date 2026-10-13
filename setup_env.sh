#!/usr/bin/env bash
# Cria ou atualiza o venv Linux e instala requirements.txt

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

echo "============================================================"
echo "SGC — criação/atualização do ambiente virtual (Linux)"
echo "============================================================"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERRO] python3 não encontrado. Instale Python 3.10+ (ex.: apt install python3 python3-venv python3-pip)." >&2
    exit 1
fi

if [[ ! -x "venv/bin/python" ]]; then
    echo
    echo "[1/3] Criando venv..."
    python3 -m venv venv
else
    echo
    echo "[1/3] venv já existe — reutilizando."
fi

PYTHON="venv/bin/python"

echo
echo "[2/3] Atualizando pip..."
"${PYTHON}" -m pip install --upgrade pip

echo
echo "[3/3] Instalando dependências (requirements.txt)..."
"${PYTHON}" -m pip install -r requirements.txt

echo
echo "[OK] Ambiente pronto. Inicie com: ./run.sh"
echo "     Ou execute scripts: ./sgc_python.sh python/VerificarFase2Local.py"
echo "============================================================"
