"""Introspecção segura de tabelas/colunas (MariaDB)."""

from __future__ import annotations

import logging
from typing import Any, Optional, Set

import pandas as pd

logger = logging.getLogger("sgc_api")


def table_exists(dal: Any, table: str) -> bool:
    try:
        df = dal.read("SHOW TABLES LIKE %s", (table,))
        return df is not None and not df.empty
    except Exception as exc:
        logger.warning("Falha ao verificar tabela %s: %s", table, exc)
        return False


def columns_of(dal: Any, table: str) -> Set[str]:
    if not table_exists(dal, table):
        logger.warning("Tabela ausente: %s", table)
        return set()
    try:
        df = dal.read(f"SHOW COLUMNS FROM `{table}`")
        if df is None or df.empty:
            return set()
        # SHOW COLUMNS: Field, Type, Null, Key, Default, Extra
        col_name = "Field" if "Field" in df.columns else df.columns[0]
        return {str(v).strip() for v in df[col_name].tolist()}
    except Exception as exc:
        logger.warning("Falha ao listar colunas de %s: %s", table, exc)
        return set()


def resolve_column(available: Set[str], *candidates: str) -> Optional[str]:
    """Retorna o primeiro nome de coluna existente (case-insensitive)."""
    lower_map = {c.lower(): c for c in available}
    for name in candidates:
        found = lower_map.get(name.lower())
        if found:
            return found
    return None


def safe_read(dal: Any, sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
    try:
        df = dal.read(sql, params)
        if df is None:
            return pd.DataFrame()
        return df
    except Exception as exc:
        logger.warning("Consulta falhou: %s | %s", exc, sql[:120])
        return pd.DataFrame()


def cell_to_python(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    # Datas/horas → ISO 8601 (contrato estável para o frontend)
    if hasattr(value, "isoformat"):
        try:
            if hasattr(value, "hour"):
                return value.strftime("%Y-%m-%dT%H:%M:%S")
            return value.isoformat()  # date → YYYY-MM-DD
        except Exception:
            try:
                return value.isoformat()
            except Exception:
                return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    # numpy / Decimal
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def row_to_dict(row: pd.Series) -> dict:
    return {str(k): cell_to_python(v) for k, v in row.items()}


def normalize_ml_log_row(raw: Optional[dict]) -> Optional[dict]:
    """Converte linha Tb_ML_Log (qualquer casing) para o contrato MlLogEntry."""
    if not raw:
        return None

    lower = {str(k).lower(): v for k, v in raw.items()}

    def pick(*names: str) -> Any:
        for n in names:
            if n.lower() in lower:
                return lower[n.lower()]
        return None

    conf = cell_to_python(pick("Confianca", "confianca"))
    margem = cell_to_python(pick("Margem", "margem"))
    try:
        conf_f = float(conf) if conf is not None else None
    except (TypeError, ValueError):
        conf_f = None
    try:
        margem_f = float(margem) if margem is not None else None
    except (TypeError, ValueError):
        margem_f = None

    idml = cell_to_python(pick("idml"))
    id_glpi = cell_to_python(pick("Id_Glpi", "id_glpi"))
    try:
        idml_i = int(idml) if idml is not None else None
    except (TypeError, ValueError):
        idml_i = None
    try:
        id_glpi_i = int(id_glpi) if id_glpi is not None else None
    except (TypeError, ValueError):
        id_glpi_i = None

    metodo = cell_to_python(pick("Metodo", "metodo"))
    return {
        "idml": idml_i,
        "id_glpi": id_glpi_i,
        "metodo": str(metodo).strip() if metodo is not None else None,
        "equipe_prevista": cell_to_python(pick("Equipe_Prevista", "equipe_prevista")),
        "equipe_ml": cell_to_python(pick("Equipe_ML", "equipe_ml")),
        "equipe_2a": cell_to_python(pick("Equipe_2a", "equipe_2a")),
        "confianca": conf_f,
        "margem": margem_f,
        "motivo_rejeicao": cell_to_python(pick("Motivo_Rejeicao", "motivo_rejeicao")),
        "motivo_atrib": cell_to_python(pick("Motivo_Atrib", "motivo_atrib", "Motivo_atrib")),
        "categoria": cell_to_python(pick("Categoria", "categoria")),
        "localizacao": cell_to_python(pick("Localizacao", "localizacao")),
        "data_registro": cell_to_python(pick("Data_Registro", "data_registro")),
    }
