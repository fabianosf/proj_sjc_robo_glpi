"""Dependências FastAPI — reutiliza DAL legado (conf/sgc.dat via CONFIGURACAO)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from fastapi import HTTPException

from .bootstrap import ensure_legacy_path

logger = logging.getLogger("sgc_api")


@lru_cache(maxsize=1)
def get_dal() -> Any:
    """Instancia única do DAL apontando para sgc.dat (sem expor parâmetros)."""
    ensure_legacy_path()
    try:
        from DAL import DAL  # noqa: WPS433 — pacote legado em python/
    except Exception as exc:
        logger.exception("Falha ao importar DAL")
        raise HTTPException(status_code=503, detail="Camada de dados indisponível.") from exc

    try:
        return DAL(app_name="SGC_API", nome_arquivo_config="sgc.dat")
    except Exception as exc:
        logger.exception("Falha ao inicializar DAL")
        raise HTTPException(status_code=503, detail="Falha na conexão com o banco.") from exc
