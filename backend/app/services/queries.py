"""Consultas e mutações do painel (técnicos, regras, redirect GLPI, relatórios)."""

from __future__ import annotations

import logging
import os
import re
import csv
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from ..db_meta import (
    cell_to_python,
    columns_of,
    normalize_ml_log_row,
    resolve_column,
    row_to_dict,
    safe_read,
    table_exists,
)
from ..schemas import (
    AssertividadePdfItem,
    AssignmentExplanation,
    DashboardSummary,
    ErrorPairItem,
    JobItem,
    JobsOverview,
    MatriculaImportResult,
    MatriculaSyncResult,
    MethodAccuracyItem,
    MlAccuracyReport,
    MlCorrectionItem,
    MlLogEntry,
    MlModelStatus,
    MlModelVersionItem,
    MlOverview,
    MlSimulateResult,
    DailySeriesItem,
    NameCountItem,
    OpsPeriodComparison,
    OpsPeriodReport,
    TempoFaixaItem,
    PaginatedMlCorrections,
    PaginatedMlLogs,
    PaginatedTickets,
    RankPersonItem,
    RuleItem,
    TeamGuideItem,
    TeamItem,
    TechnicianItem,
    TechnicianRedirectResult,
    TicketDetail,
    TicketGlpiHint,
    TicketListItem,
    TicketReassignResult,
    WeeklyPersonStats,
    WeeklyTeamReport,
    WeeklyTeamStats,
)
from ..auth.config import get_ad_user_map
from ..bootstrap import ensure_legacy_path

logger = logging.getLogger("sgc_api")

_SEARCH_SAFE = re.compile(r"[^\w\s.\-@]", re.UNICODE)


def clamp_pagination(page: int, page_size: int) -> Tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    return page, page_size


def _sanitize_search(search: Optional[str]) -> str:
    if not search:
        return ""
    cleaned = _SEARCH_SAFE.sub("", str(search)).strip()
    return cleaned[:100]


def _count(dal: Any, table: str, where: str = "", params: Optional[tuple] = None) -> Optional[int]:
    if not table_exists(dal, table):
        logger.warning("Contagem ignorada — tabela ausente: %s", table)
        return None
    sql = f"SELECT COUNT(*) AS cnt FROM `{table}`"
    if where:
        sql += f" WHERE {where}"
    df = safe_read(dal, sql, params)
    if df.empty:
        return 0
    return int(cell_to_python(df.iloc[0]["cnt"]) or 0)


def get_dashboard_summary(dal: Any) -> DashboardSummary:
    summary = DashboardSummary()

    cols_ticket = columns_of(dal, "Tb_Ticket_new")
    col_data = resolve_column(cols_ticket, "Data")
    col_dat_reg = resolve_column(cols_ticket, "Dat_Reg")
    col_equipe = resolve_column(cols_ticket, "Equipe")
    # Prefer Dat_Reg (instante atribuição SGC); fallback Data (abertura GLPI)
    col_hoje = col_dat_reg or col_data

    summary.tickets_total = _count(dal, "Tb_Ticket_new")

    if col_hoje:
        summary.tickets_today = _count(
            dal, "Tb_Ticket_new", f"DATE(`{col_hoje}`) = CURDATE()"
        )
    else:
        summary.tickets_today = None

    if table_exists(dal, "Tb_Atrib"):
        summary.technicians_active = _count(dal, "Tb_Atrib", "Sit = '1' OR Sit = 1")
        df_teams = safe_read(
            dal,
            "SELECT COUNT(DISTINCT UPPER(TRIM(Equipe))) AS cnt FROM Tb_Atrib "
            "WHERE Equipe IS NOT NULL AND TRIM(Equipe) <> ''",
        )
        summary.teams_total = (
            int(cell_to_python(df_teams.iloc[0]["cnt"]) or 0) if not df_teams.empty else 0
        )
    else:
        summary.technicians_active = None
        summary.teams_total = None

    summary.ml_log_total = _count(dal, "Tb_ML_Log")
    summary.corrections_total = _count(dal, "Tb_Correcao_Feedback")
    summary.feedback_total = _count(dal, "Tb_Ticket_Feedback_Temp")

    if table_exists(dal, "tb_performance"):
        df_perf = safe_read(
            dal,
            "SELECT Performance, Data FROM tb_performance ORDER BY Data DESC LIMIT 1",
        )
        if not df_perf.empty:
            summary.latest_performance = float(
                cell_to_python(df_perf.iloc[0]["Performance"]) or 0
            )
            summary.latest_performance_date = cell_to_python(df_perf.iloc[0]["Data"])
    else:
        logger.warning("Tabela ausente: tb_performance")

    if col_equipe and table_exists(dal, "Tb_Ticket_new"):
        df_eq = safe_read(
            dal,
            f"SELECT UPPER(TRIM(`{col_equipe}`)) AS equipe, COUNT(*) AS total "
            f"FROM Tb_Ticket_new "
            f"WHERE `{col_equipe}` IS NOT NULL AND TRIM(`{col_equipe}`) <> '' "
            f"GROUP BY UPPER(TRIM(`{col_equipe}`)) "
            f"ORDER BY total DESC",
        )
        for _, row in df_eq.iterrows():
            eq = str(cell_to_python(row["equipe"]) or "").strip()
            if eq:
                summary.tickets_by_team[eq] = int(cell_to_python(row["total"]) or 0)

        if col_hoje:
            df_hoje = safe_read(
                dal,
                f"SELECT UPPER(TRIM(`{col_equipe}`)) AS equipe, COUNT(*) AS total "
                f"FROM Tb_Ticket_new "
                f"WHERE `{col_equipe}` IS NOT NULL AND TRIM(`{col_equipe}`) <> '' "
                f"AND DATE(`{col_hoje}`) = CURDATE() "
                f"GROUP BY UPPER(TRIM(`{col_equipe}`)) "
                f"ORDER BY total DESC",
            )
            if df_hoje is not None:
                for _, row in df_hoje.iterrows():
                    eq = str(cell_to_python(row["equipe"]) or "").strip()
                    if eq:
                        summary.tickets_today_by_team[eq] = int(
                            cell_to_python(row["total"]) or 0
                        )

    if table_exists(dal, "Tb_ML_Log"):
        cols_ml = columns_of(dal, "Tb_ML_Log")
        col_metodo = resolve_column(cols_ml, "Metodo")
        if col_metodo:
            df_m = safe_read(
                dal,
                f"SELECT `{col_metodo}` AS metodo, COUNT(*) AS total "
                f"FROM Tb_ML_Log GROUP BY `{col_metodo}`",
            )
            for _, row in df_m.iterrows():
                metodo = str(cell_to_python(row["metodo"]) or "N/A")
                summary.ml_by_method[metodo] = int(cell_to_python(row["total"]) or 0)
        else:
            logger.warning("Coluna Metodo ausente em Tb_ML_Log")

    _apply_worker_snapshot(summary, dal)
    return summary


def get_worker_heartbeat() -> Dict[str, Any]:
    ensure_legacy_path()
    try:
        from WorkerHeartbeat import snapshot_for_api  # noqa: WPS433
    except Exception:
        return {}
    try:
        snap = snapshot_for_api()
        return snap if isinstance(snap, dict) else {}
    except Exception:
        logger.debug("WorkerHeartbeat snapshot indisponível", exc_info=True)
        return {}


def _opt_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ticket_in_sgc(dal: Any, ticket_id: Optional[int]) -> bool:
    if ticket_id is None or ticket_id < 1:
        return False
    if not table_exists(dal, "Tb_Ticket_new"):
        return False
    cols = columns_of(dal, "Tb_Ticket_new")
    col_id = resolve_column(cols, "Id")
    if not col_id:
        return False
    df = safe_read(
        dal,
        f"SELECT 1 AS ok FROM Tb_Ticket_new WHERE `{col_id}` = %s LIMIT 1",
        (int(ticket_id),),
    )
    return df is not None and not df.empty


def _apply_worker_snapshot(summary: DashboardSummary, dal: Any) -> None:
    snap = get_worker_heartbeat()
    if not snap.get("updated_at"):
        return
    summary.worker_updated_at = snap.get("updated_at")
    summary.worker_alive = bool(snap.get("alive"))
    summary.worker_age_seconds = _opt_int(snap.get("age_seconds"))
    glpi_ok = snap.get("glpi_ok")
    summary.worker_glpi_ok = None if glpi_ok is None else bool(glpi_ok)
    err = snap.get("last_error")
    summary.worker_last_error = str(err).strip() if err else None
    summary.glpi_novos = _opt_int(snap.get("novos_na_fila"))
    summary.skips_sem_tecnico_hoje = _opt_int(snap.get("skips_today"))
    assigned = _opt_int(snap.get("last_assigned_id"))
    skip = _opt_int(snap.get("last_skip_id"))
    summary.last_assigned_id = assigned
    summary.last_assigned_in_sgc = _ticket_in_sgc(dal, assigned) if assigned else False
    summary.last_skip_id = skip
    summary.last_skip_in_sgc = _ticket_in_sgc(dal, skip) if skip else False


def list_tickets(
    dal: Any, page: int = 1, page_size: int = 20, search: Optional[str] = None
) -> PaginatedTickets:
    page, page_size = clamp_pagination(page, page_size)
    empty = PaginatedTickets(page=page, page_size=page_size, total=0, items=[])

    if not table_exists(dal, "Tb_Ticket_new"):
        logger.warning("Tabela ausente: Tb_Ticket_new")
        return empty

    cols = columns_of(dal, "Tb_Ticket_new")
    col_id = resolve_column(cols, "Id")
    col_titulo = resolve_column(cols, "Titulo")
    col_cat = resolve_column(cols, "Categoria")
    col_tec = resolve_column(cols, "Tecnico", "tecnico")
    col_eq = resolve_column(cols, "Equipe")
    col_sit = resolve_column(cols, "Sit")
    col_sol = resolve_column(cols, "sol", "Sol")
    col_data = resolve_column(cols, "Data")
    col_dat_sol = resolve_column(cols, "Dat_Sol")

    if not col_id:
        logger.warning("Coluna Id ausente em Tb_Ticket_new")
        return empty

    select_parts = [f"t.`{col_id}` AS id"]
    if col_titulo:
        select_parts.append(f"t.`{col_titulo}` AS titulo")
    if col_cat:
        select_parts.append(f"t.`{col_cat}` AS categoria")
    if col_tec:
        select_parts.append(f"t.`{col_tec}` AS tecnico")
    if col_eq:
        select_parts.append(f"t.`{col_eq}` AS equipe")
    if col_sit:
        select_parts.append(f"t.`{col_sit}` AS sit")
    if col_sol:
        select_parts.append(f"t.`{col_sol}` AS solicitante")
    if col_data:
        select_parts.append(f"t.`{col_data}` AS data")
    if col_dat_sol:
        select_parts.append(f"t.`{col_dat_sol}` AS dat_sol")

    # Último método de decisão (Tb_ML_Log) — contrato para badges no frontend
    ml_cols = columns_of(dal, "Tb_ML_Log") if table_exists(dal, "Tb_ML_Log") else set()
    col_ml_glpi = resolve_column(ml_cols, "Id_Glpi")
    col_ml_metodo = resolve_column(ml_cols, "Metodo")
    col_ml_data = resolve_column(ml_cols, "Data_Registro")
    col_ml_id = resolve_column(ml_cols, "idml")
    if col_ml_glpi and col_ml_metodo:
        order_ml = (
            f"ml.`{col_ml_data}` DESC, ml.`{col_ml_id}` DESC"
            if col_ml_data and col_ml_id
            else (f"ml.`{col_ml_data}` DESC" if col_ml_data else f"ml.`{col_ml_id}` DESC" if col_ml_id else "1")
        )
        select_parts.append(
            f"(SELECT ml.`{col_ml_metodo}` FROM Tb_ML_Log ml "
            f"WHERE ml.`{col_ml_glpi}` = t.`{col_id}` "
            f"ORDER BY {order_ml} LIMIT 1) AS metodo"
        )
    else:
        logger.warning("Método ML indisponível na listagem (Tb_ML_Log ausente ou incompleta)")

    where = "1=1"
    params: list = []
    q = _sanitize_search(search)
    if q:
        likes = []
        for c in (col_titulo, col_cat, col_tec, col_eq, col_sol):
            if c:
                likes.append(f"t.`{c}` LIKE %s")
                params.append(f"%{q}%")
        if col_id and q.isdigit():
            likes.append(f"t.`{col_id}` = %s")
            params.append(int(q))
        if likes:
            where = "(" + " OR ".join(likes) + ")"

    total = _count(dal, "Tb_Ticket_new", where.replace("t.", ""), tuple(params) if params else None) or 0
    offset = (page - 1) * page_size
    order = f"t.`{col_data}` DESC" if col_data else f"t.`{col_id}` DESC"
    sql = (
        f"SELECT {', '.join(select_parts)} FROM Tb_Ticket_new t "
        f"WHERE {where} ORDER BY {order} LIMIT %s OFFSET %s"
    )
    params_page = list(params) + [page_size, offset]
    df = safe_read(dal, sql, tuple(params_page))

    items: List[TicketListItem] = []
    for _, row in df.iterrows():
        metodo_raw = cell_to_python(row.get("metodo")) if "metodo" in row.index else None
        items.append(
            TicketListItem(
                id=cell_to_python(row.get("id")),
                titulo=cell_to_python(row.get("titulo")),
                categoria=cell_to_python(row.get("categoria")),
                tecnico=cell_to_python(row.get("tecnico")),
                equipe=cell_to_python(row.get("equipe")),
                sit=str(cell_to_python(row.get("sit"))) if cell_to_python(row.get("sit")) is not None else None,
                solicitante=cell_to_python(row.get("solicitante")),
                data=cell_to_python(row.get("data")),
                dat_sol=cell_to_python(row.get("dat_sol")),
                metodo=str(metodo_raw).strip() if metodo_raw is not None else None,
            )
        )

    return PaginatedTickets(page=page, page_size=page_size, total=total, items=items, fonte="sgc")


def list_glpi_active_tickets(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
) -> PaginatedTickets:
    """
    Lista chamados ativos do GLPI (status=notold), igual ao front ticket.php.
    """
    from ..bootstrap import PROJECT_ROOT, ensure_legacy_path

    page, page_size = clamp_pagination(page, page_size)
    empty = PaginatedTickets(page=page, page_size=page_size, total=0, items=[], fonte="glpi")

    ensure_legacy_path()
    try:
        from GLPI_API import GLPI_API  # noqa: WPS433
    except Exception as exc:
        logger.exception("Import GLPI_API: %s", exc)
        return empty

    conf_dir = PROJECT_ROOT / "conf"
    api = None
    try:
        api = GLPI_API.from_config(conf_dir if conf_dir.is_dir() else None)
        total, rows = api.search_tickets_ativos(
            offset=(page - 1) * page_size,
            limit=page_size,
            search=search,
        )
    except Exception as exc:
        logger.exception("list_glpi_active_tickets: %s", exc)
        return empty
    finally:
        if api is not None:
            try:
                api.encerrar_sessao()
            except Exception:
                pass

    items: List[TicketListItem] = []
    for row in rows:
        status = row.get("status")
        items.append(
            TicketListItem(
                id=row.get("id"),
                titulo=row.get("titulo"),
                categoria=row.get("categoria"),
                tecnico=row.get("tecnico"),
                equipe=None,
                sit=str(status) if status is not None else None,
                solicitante=row.get("solicitante"),
                data=row.get("data_abertura"),
                dat_sol=None,
                metodo=None,
                status_label=str(status) if status is not None else None,
                data_mod=str(row.get("data_mod")) if row.get("data_mod") is not None else None,
                fonte="glpi",
            )
        )
    return PaginatedTickets(
        page=page, page_size=page_size, total=int(total or 0), items=items, fonte="glpi"
    )


def _glpi_assign_tickets(ticket_ids: List[int], tecnico: str) -> List[int]:
    """Atribui chamados no GLPI ao destino. Devolve IDs que deram certo."""
    from ..bootstrap import PROJECT_ROOT, ensure_legacy_path

    if not ticket_ids or not (tecnico or "").strip():
        return []
    ensure_legacy_path()
    try:
        from GLPI_API import GLPI_API  # noqa: WPS433
    except Exception as exc:
        logger.exception("Import GLPI_API (redirect): %s", exc)
        return []

    conf_dir = PROJECT_ROOT / "conf"
    api = None
    ok_ids: List[int] = []
    try:
        api = GLPI_API.from_config(conf_dir if conf_dir.is_dir() else None)
        for tid in ticket_ids:
            try:
                if api._atribuir_Chamado_Tecnico(tid, tecnico):
                    ok_ids.append(tid)
                else:
                    logger.warning(
                        "redirect GLPI recusou chamado=%s tecnico=%s", tid, tecnico
                    )
            except Exception as exc:
                logger.warning(
                    "redirect GLPI falhou chamado=%s tecnico=%s: %s",
                    tid,
                    tecnico,
                    exc,
                )
    except Exception as exc:
        logger.exception("redirect GLPI sessão: %s", exc)
    finally:
        if api is not None:
            try:
                api.encerrar_sessao()
            except Exception:
                pass
    return ok_ids


def get_ticket(dal: Any, ticket_id: int) -> Optional[TicketDetail]:
    if not table_exists(dal, "Tb_Ticket_new"):
        logger.warning("Tabela ausente: Tb_Ticket_new")
        return None

    cols = columns_of(dal, "Tb_Ticket_new")
    col_id = resolve_column(cols, "Id")
    if not col_id:
        return None

    mapping = {
        "id": col_id,
        "titulo": resolve_column(cols, "Titulo"),
        "categoria": resolve_column(cols, "Categoria"),
        "descricao": resolve_column(cols, "Descricao"),
        "tecnico": resolve_column(cols, "Tecnico", "tecnico"),
        "equipe": resolve_column(cols, "Equipe"),
        "sit": resolve_column(cols, "Sit"),
        "solicitante": resolve_column(cols, "sol", "Sol"),
        "data": resolve_column(cols, "Data"),
        "dat_sol": resolve_column(cols, "Dat_Sol"),
    }
    select_parts = [f"`{db}` AS {alias}" for alias, db in mapping.items() if db]
    sql = f"SELECT {', '.join(select_parts)} FROM Tb_Ticket_new WHERE `{col_id}` = %s LIMIT 1"
    df = safe_read(dal, sql, (int(ticket_id),))
    if df.empty:
        return None

    row = df.iloc[0]
    ml_entry: Optional[MlLogEntry] = None
    if table_exists(dal, "Tb_ML_Log"):
        cols_ml = columns_of(dal, "Tb_ML_Log")
        col_glpi = resolve_column(cols_ml, "Id_Glpi")
        col_data_reg = resolve_column(cols_ml, "Data_Registro")
        col_idml = resolve_column(cols_ml, "idml")
        if col_glpi:
            if col_data_reg and col_idml:
                order = f"`{col_data_reg}` DESC, `{col_idml}` DESC"
            elif col_data_reg:
                order = f"`{col_data_reg}` DESC"
            elif col_idml:
                order = f"`{col_idml}` DESC"
            else:
                order = "1"
            df_ml = safe_read(
                dal,
                f"SELECT * FROM Tb_ML_Log WHERE `{col_glpi}` = %s ORDER BY {order} LIMIT 1",
                (int(ticket_id),),
            )
            if not df_ml.empty:
                normalized = normalize_ml_log_row(row_to_dict(df_ml.iloc[0]))
                ml_entry = MlLogEntry(**normalized) if normalized else None
        else:
            logger.warning("Coluna Id_Glpi ausente em Tb_ML_Log")
    else:
        logger.warning("Tabela ausente: Tb_ML_Log")

    sit_val = cell_to_python(row.get("sit"))
    metodo_val = ml_entry.metodo if ml_entry else None
    titulo_val = cell_to_python(row.get("titulo"))
    cat_val = cell_to_python(row.get("categoria"))
    desc_val = cell_to_python(row.get("descricao"))
    tec_val = cell_to_python(row.get("tecnico"))
    eq_val = cell_to_python(row.get("equipe"))

    explicacao = build_assignment_explanation(
        titulo=str(titulo_val or ""),
        categoria=str(cat_val or ""),
        descricao=str(desc_val or ""),
        equipe=str(eq_val or "") if eq_val else None,
        tecnico=str(tec_val or "") if tec_val else None,
        ml_entry=ml_entry,
    )

    return TicketDetail(
        id=cell_to_python(row.get("id")),
        titulo=titulo_val,
        categoria=cat_val,
        descricao=desc_val,
        tecnico=tec_val,
        equipe=eq_val,
        sit=str(sit_val) if sit_val is not None else None,
        solicitante=cell_to_python(row.get("solicitante")),
        data=cell_to_python(row.get("data")),
        dat_sol=cell_to_python(row.get("dat_sol")),
        metodo=metodo_val,
        ml_log=ml_entry,
        explicacao=explicacao,
    )


_GLPI_STATUS_LABEL = {
    1: "Novo",
    2: "Em atendimento (atribuído)",
    3: "Em atendimento (planejado)",
    4: "Pendente",
    5: "Solucionado",
    6: "Fechado",
}


def get_ticket_glpi_hint(ticket_id: int) -> TicketGlpiHint:
    """Leitura GLPI quando o chamado não está no SGC — explica atribuição externa."""
    from ..bootstrap import PROJECT_ROOT, ensure_legacy_path

    tid = int(ticket_id)
    if tid < 1:
        raise HTTPException(status_code=400, detail="ticket_id inválido.")

    ensure_legacy_path()
    try:
        from GLPI_API import GLPI_API  # noqa: WPS433
    except Exception as exc:
        logger.exception("Import GLPI_API (glpi-hint): %s", exc)
        return TicketGlpiHint(
            ticket_id=tid,
            encontrado=False,
            mensagem="Não foi possível carregar a API do GLPI neste ambiente.",
        )

    conf_dir = PROJECT_ROOT / "conf"
    api = None
    try:
        api = GLPI_API.from_config(conf_dir if conf_dir.is_dir() else None)
        raw = api._obter_ticket(tid)
        if not isinstance(raw, dict) or not raw.get("id"):
            return TicketGlpiHint(
                ticket_id=tid,
                encontrado=False,
                mensagem=f"Chamado #{tid} não encontrado no GLPI.",
            )
        titulo = raw.get("name")
        try:
            status_i = int(raw.get("status")) if raw.get("status") is not None else None
        except (TypeError, ValueError):
            status_i = None
        tecnico = api._obter_tecnico_atribuido_chamado(tid)
        status_label = _GLPI_STATUS_LABEL.get(status_i or -1)
        if tecnico:
            msg = (
                f"Este chamado não passou pelo robô SGC (não está em Tb_Ticket_new). "
                f"No GLPI está atribuído a {tecnico}. "
                "A atribuição veio do GLPI / processo externo."
            )
        else:
            msg = (
                f"Este chamado não passou pelo robô SGC (não está em Tb_Ticket_new). "
                "No GLPI não há técnico assigned — atribuição externa ou ainda Novo."
            )
        return TicketGlpiHint(
            ticket_id=tid,
            encontrado=True,
            titulo=str(titulo) if titulo else None,
            status=status_i,
            status_label=status_label,
            tecnico=str(tecnico).strip() if tecnico else None,
            mensagem=msg,
        )
    except Exception as exc:
        logger.exception("glpi-hint %s", tid)
        return TicketGlpiHint(
            ticket_id=tid,
            encontrado=False,
            mensagem=f"Falha ao consultar GLPI: {exc}",
        )
    finally:
        if api is not None:
            try:
                api.encerrar_sessao()
            except Exception:
                pass


_EQUIPE_RESUMO: Dict[str, str] = {
    "N1": "Hardware / desktop (impressora, teclado, toner, formatação…)",
    "N2": "Celular e infra física (cabeamento, nobreak, câmera, GPS…)",
    "N3": "Acesso, senha e sistemas (remoto, Globus, backup…)",
    "N4": "Sistemas / desenvolvimento (SGC, homologação, site, código…)",
    "N5": "Comunicação interna e mídia (guias, TVs, atualização de mídia…)",
    "N6": "Treinamentos e compliance corporativo",
    "N7": "Segurança do trabalho / documentação (PPP, DDS, perícia…)",
    "N8": "Facilities / predial (ar-condicionado, elétrica, hidráulica…)",
    "N9": "Meio ambiente e limpeza (resíduos, água/óleo…)",
    "NE": "Atendimento médico / SAT",
    "NA": "Transportes / contratação",
    "NB": "Pagamentos",
    "NC": "Controle de peças / estoque / mapas NF",
    "ND": "Cadastros, tags, boletos e programações",
}

_METODO_LABELS: Dict[str, str] = {
    "DIRETO": "Regra direta (palavra-chave no arqaux)",
    "REGRA_DIRETA": "Regra direta (palavra-chave no arqaux)",
    "FALLBACK_PARCIAL": "Regra parcial (várias palavras; uma equipe venceu)",
    "ML": "Modelo de inteligência artificial",
    "FALLBACK_CATEGORIA": "Pela categoria do chamado no GLPI",
    "FALLBACK_N1": "Padrão N1 (nenhuma regra/ML/categoria casou)",
    "SEM_EQUIPE": "Sem equipe definida",
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").replace("\xa0", " ")


def _keyword_in_text(keyword: str, texto: str) -> bool:
    kw = (keyword or "").strip()
    if not kw or not texto:
        return False
    pattern = rf"(?<!\w){re.escape(kw)}(?!\w)"
    return bool(re.search(pattern, texto, re.IGNORECASE))


def _match_keywords_for_equipe(
    equipe: str,
    titulo: str,
    categoria: str,
    descricao: str,
) -> List[str]:
    eq = (equipe or "").strip().upper()
    if not eq:
        return []
    texto = f"{titulo or ''} {categoria or ''} {_strip_html(descricao or '')}"
    matched: List[str] = []
    seen = set()
    try:
        for rule in list_assignment_rules():
            if (rule.equipe or "").strip().upper() != eq:
                continue
            for kw in rule.keywords or []:
                k = (kw or "").strip()
                if not k:
                    continue
                key = k.upper()
                if key in seen:
                    continue
                if _keyword_in_text(k, texto):
                    seen.add(key)
                    matched.append(k)
                    if len(matched) >= 12:
                        return matched
    except Exception as exc:
        logger.warning("match keywords equipe=%s: %s", eq, exc)
    return matched


def build_assignment_explanation(
    *,
    titulo: str,
    categoria: str,
    descricao: str,
    equipe: Optional[str],
    tecnico: Optional[str],
    ml_entry: Optional[MlLogEntry],
) -> AssignmentExplanation:
    metodo_raw = (ml_entry.metodo if ml_entry else None) or None
    metodo = str(metodo_raw).strip().upper() if metodo_raw else ""
    metodo_label = _METODO_LABELS.get(metodo, metodo or "Sem registro de classificação")
    eq = (equipe or "").strip().upper() or None
    tec = (tecnico or "").strip() or None
    matched = _match_keywords_for_equipe(eq or "", titulo, categoria, descricao) if eq else []
    motivo_pessoa = None
    if ml_entry and ml_entry.motivo_atrib:
        motivo_pessoa = str(ml_entry.motivo_atrib).strip() or None

    parts: List[str] = []
    if motivo_pessoa:
        parts.append(motivo_pessoa)
    if metodo:
        parts.append(f"Classificado por: {metodo_label}.")
    else:
        parts.append("Não há log de classificação (Tb_ML_Log) para este chamado.")

    if eq:
        resumo = _EQUIPE_RESUMO.get(eq, f"Equipe {eq}")
        parts.append(f"Fila atual: {eq} — {resumo}.")
    if matched:
        parts.append("Palavras do chamado que batem com a regra: " + ", ".join(matched) + ".")
    elif eq and metodo in ("DIRETO", "REGRA_DIRETA", "FALLBACK_PARCIAL") and not motivo_pessoa:
        parts.append(
            "Nenhuma palavra-chave da regra foi encontrada agora no título/categoria "
            "(pode ter mudado o texto ou a regra)."
        )

    if tec and not motivo_pessoa:
        if metodo in ("DIRETO", "REGRA_DIRETA"):
            pinned = False
            try:
                for rule in list_assignment_rules():
                    if (rule.equipe or "").upper() != (eq or ""):
                        continue
                    if (rule.tecnico or "").strip().upper() == tec.upper():
                        if any(
                            _keyword_in_text(
                                k, f"{titulo} {categoria} {_strip_html(descricao)}"
                            )
                            for k in (rule.keywords or [])
                        ):
                            pinned = True
                            break
            except Exception:
                pinned = False
            if pinned:
                parts.append(
                    f"Técnico {tec}: indicado pela regra DIRETO (técnico fixo na palavra-chave)."
                )
            else:
                parts.append(
                    f"Técnico {tec}: escolhido entre os ativos da equipe {eq or '?'} "
                    "(no horário, menor carga QtdC)."
                )
        else:
            parts.append(
                f"Técnico {tec}: escolhido entre os ativos da equipe {eq or '?'} "
                "(no horário, menor carga QtdC)."
            )
    elif tec and motivo_pessoa:
        parts.append(f"Técnico atual no SGC: {tec}.")

    if ml_entry and ml_entry.equipe_2a:
        parts.append(f"2ª opção do modelo: {ml_entry.equipe_2a}.")
    if ml_entry and ml_entry.motivo_rejeicao:
        parts.append(f"Motivo de rejeição ML: {ml_entry.motivo_rejeicao}.")

    return AssignmentExplanation(
        metodo=metodo or None,
        metodo_label=metodo_label,
        equipe=eq,
        tecnico=tec,
        keywords_matched=matched,
        motivo_resumo=" ".join(parts),
        motivo_pessoa=motivo_pessoa,
        equipe_2a=ml_entry.equipe_2a if ml_entry else None,
        confianca=ml_entry.confianca if ml_entry else None,
        motivo_rejeicao=ml_entry.motivo_rejeicao if ml_entry else None,
    )


def list_teams(dal: Any) -> List[TeamItem]:
    if not table_exists(dal, "Tb_Atrib"):
        logger.warning("Tabela ausente: Tb_Atrib")
        return []

    df = safe_read(
        dal,
        """
        SELECT
            UPPER(TRIM(Equipe)) AS equipe,
            COUNT(*) AS technicians_total,
            SUM(CASE WHEN Sit = '1' OR Sit = 1 THEN 1 ELSE 0 END) AS technicians_active,
            COALESCE(SUM(QtdC), 0) AS carga_total
        FROM Tb_Atrib
        WHERE Equipe IS NOT NULL AND TRIM(Equipe) <> ''
        GROUP BY UPPER(TRIM(Equipe))
        ORDER BY equipe
        """,
    )
    items: List[TeamItem] = []
    for _, row in df.iterrows():
        items.append(
            TeamItem(
                equipe=str(cell_to_python(row["equipe"]) or ""),
                technicians_total=int(cell_to_python(row["technicians_total"]) or 0),
                technicians_active=int(cell_to_python(row["technicians_active"]) or 0),
                carga_total=int(cell_to_python(row["carga_total"]) or 0),
            )
        )
    return items


def list_teams_guide(dal: Any) -> List[TeamGuideItem]:
    """Guia das filas: resumo + exemplos do arqaux + contagens Tb_Atrib."""
    stats = {t.equipe.upper(): t for t in list_teams(dal) if t.equipe}
    keywords_by_eq: Dict[str, List[str]] = {}
    try:
        for rule in list_assignment_rules():
            eq = (rule.equipe or "").strip().upper()
            if not eq:
                continue
            bucket = keywords_by_eq.setdefault(eq, [])
            for kw in rule.keywords or []:
                k = (kw or "").strip()
                if k and k.upper() not in {x.upper() for x in bucket}:
                    bucket.append(k)
    except Exception as exc:
        logger.warning("list_teams_guide rules: %s", exc)

    equipes = sorted(set(stats.keys()) | set(keywords_by_eq.keys()) | set(_EQUIPE_RESUMO.keys()))
    items: List[TeamGuideItem] = []
    for eq in equipes:
        st = stats.get(eq)
        exemplos = (keywords_by_eq.get(eq) or [])[:8]
        resumo = _EQUIPE_RESUMO.get(eq)
        if not resumo:
            if exemplos:
                resumo = f"Equipe {eq} — exemplos: " + ", ".join(exemplos[:4])
            else:
                resumo = f"Equipe {eq} (sem regras no arqaux)"
        items.append(
            TeamGuideItem(
                equipe=eq,
                resumo=resumo,
                exemplos=exemplos,
                tecnicos_ativos=st.technicians_active if st else 0,
                technicians_total=st.technicians_total if st else 0,
                carga_total=st.carga_total if st else 0,
            )
        )
    return items


def list_technicians(dal: Any) -> List[TechnicianItem]:
    if not table_exists(dal, "Tb_Atrib"):
        logger.warning("Tabela ausente: Tb_Atrib")
        return []

    cols = columns_of(dal, "Tb_Atrib")
    col_user = resolve_column(cols, "Usuario")
    if not col_user:
        logger.warning("Coluna Usuario ausente em Tb_Atrib")
        return []

    col_eq = resolve_column(cols, "Equipe")
    col_qtd = resolve_column(cols, "QtdC")
    col_sit = resolve_column(cols, "Sit")
    col_h1 = resolve_column(cols, "H1")
    col_h2 = resolve_column(cols, "H2")
    col_emp = resolve_column(cols, "Empresa")
    col_mat = resolve_column(cols, "Matricula", "matricula", "MATRICULA")
    col_id = resolve_column(cols, "idatr")

    def _norm_matricula(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        try:
            if isinstance(raw, float):
                if raw != raw:  # NaN
                    return None
                if raw == int(raw):
                    raw = int(raw)
        except (TypeError, ValueError, OverflowError):
            pass
        s = str(raw).strip()
        if s.endswith(".0") and s.replace(".", "", 1).isdigit():
            s = s[:-2]
        if s in ("", "0", "00000", "None", "nan", "NaN"):
            return None
        return s[:10]

    parts = [f"TRIM(`{col_user}`) AS usuario"]
    if col_eq:
        parts.append(f"`{col_eq}` AS equipe")
    if col_qtd:
        parts.append(f"`{col_qtd}` AS qtdc")
    if col_sit:
        parts.append(f"`{col_sit}` AS sit")
    if col_h1:
        parts.append(f"`{col_h1}` AS h1")
    if col_h2:
        parts.append(f"`{col_h2}` AS h2")
    if col_emp:
        parts.append(f"`{col_emp}` AS empresa")
    if col_mat:
        parts.append(f"TRIM(`{col_mat}`) AS matricula")

    parts_full = list(parts)
    if col_id:
        parts_full.insert(0, f"`{col_id}` AS _idatr")
    df = safe_read(
        dal,
        f"SELECT {', '.join(parts_full)} FROM Tb_Atrib ORDER BY "
        + (f"`{col_id}` DESC" if col_id else f"`{col_user}`"),
    )
    best: Dict[str, TechnicianItem] = {}
    best_score: Dict[str, Tuple[int, int, int]] = {}

    for _, row in df.iterrows():
        usuario = str(cell_to_python(row.get("usuario")) or "").strip()
        if not usuario:
            continue
        key = usuario.upper()
        sit_val = cell_to_python(row.get("sit"))
        sit_s = str(sit_val).strip() if sit_val is not None else ""
        qtdc_val = cell_to_python(row.get("qtdc"))
        try:
            qtdc_i = int(qtdc_val) if qtdc_val is not None else None
        except (TypeError, ValueError):
            qtdc_i = None
        mat_s = _norm_matricula(cell_to_python(row.get("matricula"))) if col_mat else None
        idatr_raw = cell_to_python(row.get("_idatr"))
        try:
            idatr_i = int(idatr_raw) if idatr_raw is not None else 0
        except (TypeError, ValueError):
            idatr_i = 0

        candidate = TechnicianItem(
            usuario=usuario,
            equipe=cell_to_python(row.get("equipe")),
            qtdc=qtdc_i,
            sit=sit_s or None,
            h1=cell_to_python(row.get("h1")),
            h2=cell_to_python(row.get("h2")),
            empresa=cell_to_python(row.get("empresa")),
            matricula=mat_s,
        )
        # Preferir: tem matrícula > ativo > id mais novo
        score = (
            1 if mat_s else 0,
            1 if sit_s == "1" else 0,
            idatr_i,
        )
        prev = best.get(key)
        if prev is None or score > best_score.get(key, (-1, -1, -1)):
            if prev is not None and not candidate.matricula and prev.matricula:
                candidate.matricula = prev.matricula
            best[key] = candidate
            best_score[key] = score
        elif prev is not None and not prev.matricula and mat_s:
            prev.matricula = mat_s

    items = list(best.values())
    items.sort(key=lambda x: x.usuario.lower())
    return items


def update_technician(
    dal: Any,
    usuario: str,
    *,
    equipe: Optional[str] = None,
    sit: Optional[str] = None,
    matricula: Optional[str] = None,
    h1: Optional[str] = None,
    h2: Optional[str] = None,
    empresa: Optional[str] = None,
) -> Optional[TechnicianItem]:
    """
    Atualiza Equipe/Sit/Matricula/H1/H2/Empresa em todas as linhas de Tb_Atrib
    com o mesmo Usuario. Não altera token nem QtdC.
    """
    user = (usuario or "").strip()
    if not user:
        return None
    if not table_exists(dal, "Tb_Atrib"):
        return None

    cols = columns_of(dal, "Tb_Atrib")
    col_user = resolve_column(cols, "Usuario")
    if not col_user:
        return None

    existing = safe_read(
        dal,
        f"SELECT 1 AS ok FROM Tb_Atrib WHERE UPPER(TRIM(`{col_user}`)) = %s LIMIT 1",
        (user.upper(),),
    )
    if existing is None or existing.empty:
        return None

    sets: List[str] = []
    values: List[Any] = []

    def _add(col_name: str, value: Optional[str], allow_empty: bool = False) -> None:
        col = resolve_column(cols, col_name)
        if not col or value is None:
            return
        cleaned = value.strip()
        if not cleaned and not allow_empty:
            return
        sets.append(f"`{col}` = %s")
        values.append(cleaned)

    _add("Equipe", equipe)
    _add("Sit", sit)
    if matricula is not None:
        col_mat = resolve_column(cols, "Matricula")
        if col_mat:
            sets.append(f"`{col_mat}` = %s")
            values.append(matricula.strip())
    _add("H1", h1, allow_empty=True)
    _add("H2", h2, allow_empty=True)
    _add("Empresa", empresa, allow_empty=True)

    if not sets:
        # Nada a alterar — devolve estado atual
        for item in list_technicians(dal):
            if item.usuario.upper() == user.upper():
                return item
        return None

    values.append(user.upper())
    sql = (
        f"UPDATE Tb_Atrib SET {', '.join(sets)} "
        f"WHERE UPPER(TRIM(`{col_user}`)) = %s"
    )
    ok = dal.update(sql, tuple(values))
    if not ok:
        logger.warning("update_technician falhou para usuario=%s", user)
        return None

    for item in list_technicians(dal):
        if item.usuario.upper() == user.upper():
            return item
    return None


def redirect_technician(
    dal: Any,
    *,
    de: str,
    para: str,
    desativar_origem: bool = True,
    criado_por: Optional[str] = None,
) -> Optional[TechnicianRedirectResult]:
    """Move tickets no GLPI e na base local; notifica o destino; opcionalmente desativa origem."""
    from .notifications import notify_tickets_redirected

    src = (de or "").strip()
    dst = (para or "").strip()
    if not src or not dst or src.upper() == dst.upper():
        return None
    if not table_exists(dal, "Tb_Atrib"):
        return None

    cols_a = columns_of(dal, "Tb_Atrib")
    col_user = resolve_column(cols_a, "Usuario")
    col_sit = resolve_column(cols_a, "Sit")
    if not col_user:
        return None

    df_src = safe_read(
        dal,
        f"SELECT 1 AS ok FROM Tb_Atrib WHERE UPPER(TRIM(`{col_user}`)) = %s LIMIT 1",
        (src.upper(),),
    )
    df_dst = safe_read(
        dal,
        f"""
        SELECT 1 AS ok FROM Tb_Atrib
        WHERE UPPER(TRIM(`{col_user}`)) = %s
          AND (Sit = 1 OR Sit = '1')
        LIMIT 1
        """,
        (dst.upper(),),
    )
    if df_src is None or df_src.empty or df_dst is None or df_dst.empty:
        return None

    tickets_moved = 0
    ticket_ids: List[int] = []
    col_tec = None
    col_id = None
    if table_exists(dal, "Tb_Ticket_new"):
        cols_t = columns_of(dal, "Tb_Ticket_new")
        col_tec = resolve_column(cols_t, "tecnico") or resolve_column(cols_t, "Tecnico")
        col_id = resolve_column(cols_t, "Id")
        if col_tec and col_id:
            df_ids = safe_read(
                dal,
                f"""
                SELECT `{col_id}` AS id
                FROM Tb_Ticket_new
                WHERE UPPER(TRIM(`{col_tec}`)) = %s
                ORDER BY `{col_id}` DESC
                """,
                (src.upper(),),
            )
            if df_ids is not None and not df_ids.empty:
                for _, row in df_ids.iterrows():
                    raw = cell_to_python(row.get("id"))
                    try:
                        ticket_ids.append(int(raw))
                    except (TypeError, ValueError):
                        pass

    glpi_ok = _glpi_assign_tickets(ticket_ids, dst) if ticket_ids else []
    if ticket_ids and not glpi_ok:
        logger.warning(
            "redirect %s→%s: nenhum chamado atribuído no GLPI (%s ids)",
            src,
            dst,
            len(ticket_ids),
        )
        failed_all = list(ticket_ids)
        return TechnicianRedirectResult(
            de=src,
            para=dst,
            tickets_moved=0,
            origem_desativada=False,
            notification_created=False,
            glpi_ok_ids=[],
            glpi_failed_ids=failed_all,
        )

    ids_to_move = glpi_ok if ticket_ids else []
    glpi_failed = [t for t in ticket_ids if t not in set(glpi_ok)] if ticket_ids else []
    if ids_to_move and col_tec and col_id:
        placeholders = ", ".join(["%s"] * len(ids_to_move))
        dal.update(
            f"UPDATE Tb_Ticket_new SET `{col_tec}` = %s "
            f"WHERE `{col_id}` IN ({placeholders})",
            (dst[:20], *ids_to_move),
        )
        tickets_moved = len(ids_to_move)

    origem_off = False
    can_deactivate = desativar_origem and (
        not ticket_ids or len(glpi_ok) == len(ticket_ids)
    )
    if can_deactivate and col_sit:
        ok = dal.update(
            f"UPDATE Tb_Atrib SET `{col_sit}` = %s WHERE UPPER(TRIM(`{col_user}`)) = %s",
            ("0", src.upper()),
        )
        origem_off = bool(ok)

    notif_ok = False
    try:
        notif_ok = notify_tickets_redirected(
            dal,
            de=src,
            para=dst,
            ticket_ids=ids_to_move if ids_to_move else [],
            criado_por=criado_por,
        )
    except Exception as exc:
        logger.warning("Falha ao notificar redirecionamento %s→%s: %s", src, dst, exc)

    return TechnicianRedirectResult(
        de=src,
        para=dst,
        tickets_moved=tickets_moved,
        origem_desativada=origem_off,
        notification_created=notif_ok,
        glpi_ok_ids=list(ids_to_move),
        glpi_failed_ids=glpi_failed,
    )


def _parse_hhmm(value: Any) -> Optional[Any]:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None


def _hora_no_expediente(hora_atual: Any, h1: Any, h2: Any) -> bool:
    if h1 is None or h2 is None:
        return False
    if h1 <= h2:
        return h1 <= hora_atual <= h2
    return hora_atual >= h1 or hora_atual <= h2


def pick_eligible_technician(dal: Any, equipe: str) -> Optional[str]:
    """Login ativo da equipe, no horário, menor QtdC (mesma ideia do worker)."""
    eq = (equipe or "").strip().upper()
    if not eq or not table_exists(dal, "Tb_Atrib"):
        return None
    df = safe_read(
        dal,
        """
        SELECT TRIM(Usuario) AS usuario, H1 AS h1, H2 AS h2, QtdC AS qtdc
        FROM Tb_Atrib
        WHERE UPPER(TRIM(Equipe)) = %s
          AND (Sit = 1 OR Sit = '1')
        """,
        (eq,),
    )
    if df is None or df.empty:
        return None

    agora = datetime.now().time()
    best_user: Optional[str] = None
    best_carga: Optional[int] = None
    for _, row in df.iterrows():
        usuario = str(cell_to_python(row.get("usuario")) or "").strip()
        if not usuario:
            continue
        h1 = _parse_hhmm(cell_to_python(row.get("h1")))
        h2 = _parse_hhmm(cell_to_python(row.get("h2")))
        if not _hora_no_expediente(agora, h1, h2):
            continue
        raw_q = cell_to_python(row.get("qtdc"))
        try:
            carga = int(raw_q) if raw_q is not None else 0
        except (TypeError, ValueError):
            carga = 0
        if best_carga is None or carga < best_carga:
            best_carga = carga
            best_user = usuario
    return best_user


def _active_technician_login(dal: Any, tecnico: str) -> Optional[str]:
    login = (tecnico or "").strip()
    if not login or not table_exists(dal, "Tb_Atrib"):
        return None
    df = safe_read(
        dal,
        """
        SELECT TRIM(Usuario) AS usuario
        FROM Tb_Atrib
        WHERE UPPER(TRIM(Usuario)) = %s
          AND (Sit = 1 OR Sit = '1')
        LIMIT 1
        """,
        (login.upper(),),
    )
    if df is None or df.empty:
        return None
    return str(cell_to_python(df.iloc[0].get("usuario")) or "").strip() or None


def reassign_ticket(
    dal: Any,
    *,
    ticket_id: int,
    mode: str,
    equipe: Optional[str] = None,
    tecnico: Optional[str] = None,
    criado_por: Optional[str] = None,
) -> TicketReassignResult:
    """Reatribui um chamado do SGC para fila (equipe) ou pessoa; atualiza GLPI + SGC."""
    from .notifications import notify_reassign_actor, notify_tickets_redirected

    tid = int(ticket_id)
    if tid < 1:
        raise HTTPException(status_code=400, detail="ticket_id inválido.")

    detail = get_ticket(dal, tid)
    if detail is None:
        raise HTTPException(status_code=404, detail="Chamado não encontrado no SGC.")

    prev_tec = (detail.tecnico or "").strip() or None
    prev_eq = (detail.equipe or "").strip() or None

    mode_norm = (mode or "").strip().lower()
    dest_equipe: Optional[str] = None
    dest_tec: Optional[str] = None

    if mode_norm == "equipe":
        dest_equipe = (equipe or "").strip().upper()
        if not dest_equipe:
            raise HTTPException(status_code=400, detail="Informe a equipe (fila).")
        dest_tec = pick_eligible_technician(dal, dest_equipe)
        if not dest_tec:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Nenhum técnico disponível na fila {dest_equipe} "
                    "(ativo e no horário de expediente)."
                ),
            )
    elif mode_norm == "pessoa":
        dest_tec = _active_technician_login(dal, tecnico or "")
        if not dest_tec:
            raise HTTPException(
                status_code=400,
                detail="Técnico destino inválido ou inativo (Sit≠1).",
            )
        df_eq = safe_read(
            dal,
            """
            SELECT UPPER(TRIM(Equipe)) AS equipe
            FROM Tb_Atrib
            WHERE UPPER(TRIM(Usuario)) = %s
              AND (Sit = 1 OR Sit = '1')
            LIMIT 1
            """,
            (dest_tec.upper(),),
        )
        if df_eq is not None and not df_eq.empty:
            dest_equipe = str(cell_to_python(df_eq.iloc[0].get("equipe")) or "").strip() or None
    else:
        raise HTTPException(status_code=400, detail="mode deve ser 'equipe' ou 'pessoa'.")

    glpi_ok_ids = _glpi_assign_tickets([tid], dest_tec)
    if tid not in glpi_ok_ids:
        raise HTTPException(
            status_code=502,
            detail=f"GLPI recusou a atribuição do chamado #{tid} para {dest_tec}.",
        )

    cols = columns_of(dal, "Tb_Ticket_new")
    col_id = resolve_column(cols, "Id")
    col_tec = resolve_column(cols, "tecnico") or resolve_column(cols, "Tecnico")
    col_eq = resolve_column(cols, "Equipe")
    if not col_id or not col_tec:
        raise HTTPException(status_code=500, detail="Colunas de Tb_Ticket_new incompletas.")

    if dest_equipe and col_eq:
        sgc_ok = bool(
            dal.update(
                f"UPDATE Tb_Ticket_new SET `{col_tec}` = %s, `{col_eq}` = %s "
                f"WHERE `{col_id}` = %s",
                (dest_tec[:20], dest_equipe[:5], tid),
            )
        )
    else:
        sgc_ok = bool(
            dal.update(
                f"UPDATE Tb_Ticket_new SET `{col_tec}` = %s WHERE `{col_id}` = %s",
                (dest_tec[:20], tid),
            )
        )

    de_label = prev_tec or "SGC"
    notif_ok = False
    try:
        notif_ok = notify_tickets_redirected(
            dal,
            de=de_label,
            para=dest_tec,
            ticket_ids=[tid],
            criado_por=criado_por,
        )
    except Exception as exc:
        logger.warning("Falha ao notificar reassign #%s→%s: %s", tid, dest_tec, exc)

    notif_admin = False
    actor = (criado_por or "").strip()
    if actor:
        try:
            notif_admin = notify_reassign_actor(
                dal,
                actor=actor,
                ticket_id=tid,
                mode=mode_norm,
                equipe=dest_equipe,
                tecnico=dest_tec,
                criado_por=criado_por,
            )
        except Exception as exc:
            logger.warning("Falha ao notificar ADMIN reassign #%s: %s", tid, exc)

    if mode_norm == "equipe":
        msg = (
            f"Chamado #{tid} enviado para a fila {dest_equipe} "
            f"(técnico: {dest_tec})."
        )
    else:
        fila = f" · equipe {dest_equipe}" if dest_equipe else ""
        msg = f"Chamado #{tid} enviado para {dest_tec}{fila}."

    return TicketReassignResult(
        ticket_id=tid,
        mode=mode_norm,
        equipe=dest_equipe,
        tecnico=dest_tec,
        tecnico_anterior=prev_tec,
        equipe_anterior=prev_eq,
        glpi_ok=True,
        sgc_ok=sgc_ok,
        notification_created=notif_ok,
        notification_admin=notif_admin,
        message=msg,
    )


def sync_matriculas_from_map(dal: Any) -> MatriculaSyncResult:
    """
    Sincroniza Tb_Atrib.Matricula:

    1. Oracle Globus FLP_FUNCIONARIOS.CHAPAFUNC (login + e-mail AD)
    2. GLPI User.registration_number (nome exato)
    3. AD employeeNumber / employeeID
    4. SGC_AUTH_AD_USER_MAP (.env)
    """
    result = MatriculaSyncResult()
    if not table_exists(dal, "Tb_Atrib"):
        result.details.append("Tb_Atrib ausente")
        return result

    cols = columns_of(dal, "Tb_Atrib")
    col_user = resolve_column(cols, "Usuario")
    col_mat = resolve_column(cols, "Matricula")
    if not col_user or not col_mat:
        result.details.append("Colunas Usuario/Matricula ausentes")
        return result

    df_users = safe_read(
        dal,
        f"""
        SELECT TRIM(`{col_user}`) AS usuario,
               TRIM(COALESCE(`{col_mat}`, '')) AS matricula
        FROM Tb_Atrib
        WHERE TRIM(COALESCE(`{col_user}`, '')) <> ''
        ORDER BY 1
        """,
    )
    if df_users is None or df_users.empty:
        result.details.append("Nenhum usuário em Tb_Atrib")
        return result

    def _mat_vazia(raw: Any) -> bool:
        s = str(raw or "").strip()
        if s.endswith(".0") and s.replace(".", "", 1).isdigit():
            s = s[:-2]
        return s in ("", "0", "00000", "None", "nan", "NaN")

    # Um usuário pode ter várias linhas em Tb_Atrib; só sync se TODAS estão vazias
    mat_por_user: Dict[str, str] = {}
    for _, r in df_users.iterrows():
        u = str(cell_to_python(r["usuario"]) or "").strip()
        if not u:
            continue
        m = str(cell_to_python(r.get("matricula")) or "").strip()
        prev = mat_por_user.get(u)
        if prev is None or _mat_vazia(prev):
            mat_por_user[u] = m

    usuarios = list(mat_por_user.keys())
    ja_preenchidos = [u for u, m in mat_por_user.items() if not _mat_vazia(m)]
    if ja_preenchidos:
        result.details.append(
            f"Ignorados com matrícula já preenchida: {len(ja_preenchidos)}"
        )
    usuarios = [u for u in usuarios if _mat_vazia(mat_por_user.get(u, ""))]
    if not usuarios:
        result.details.append("Nenhuma matrícula vazia para sincronizar")
        return result

    extra_emails: Dict[str, str] = {}
    extra_names: Dict[str, str] = {}
    ad_regs: Dict[str, str] = {}
    try:
        from .ad_matricula import fetch_ad_identities

        identities = fetch_ad_identities(usuarios)
        for sam, ident in identities.items():
            if ident.mail:
                extra_emails[sam] = ident.mail
            if ident.person_name:
                extra_names[sam] = ident.person_name
            if ident.matricula:
                ad_regs[sam] = ident.matricula
    except Exception as exc:
        logger.warning("AD identity lookup: %s", exc)

    try:
        from .oracle_matricula import fetch_matriculas_from_oracle

        oracle_regs = fetch_matriculas_from_oracle(
            usuarios, extra_emails=extra_emails, extra_names=extra_names
        )
    except Exception as exc:
        logger.warning("Oracle matricula lookup: %s", exc)
        oracle_regs = {}

    glpi_regs = _fetch_glpi_registration_numbers(usuarios)

    user_map = get_ad_user_map()  # matricula -> ad_user
    map_by_user = {
        (ad or "").strip().lower(): (mat or "").strip()
        for mat, ad in user_map.items()
        if (ad or "").strip() and (mat or "").strip()
    }

    result.details.append(
        f"Fontes: Oracle={len(oracle_regs)} GLPI={len(glpi_regs)} "
        f"AD={len(ad_regs)} mapa={len(map_by_user)} e-mails AD={len(extra_emails)} "
        f"nomes AD={len(extra_names)}"
    )

    def _lookup_ci(store: dict, usuario: str) -> Optional[str]:
        v = store.get(usuario) or store.get(usuario.lower())
        if v:
            return v
        for k, val in store.items():
            if str(k).lower() == usuario.lower():
                return val
        return None

    unmatched: List[str] = []
    for usuario in usuarios:
        mat: Optional[str] = None
        fonte = ""
        o = _lookup_ci(oracle_regs, usuario)
        if o:
            mat, fonte = o, "oracle"
        if not mat:
            g = glpi_regs.get(usuario.lower()) or glpi_regs.get(usuario)
            if g:
                mat, fonte = g, "glpi"
        if not mat:
            a = _lookup_ci(ad_regs, usuario)
            if a:
                mat, fonte = a, "ad"
        if not mat:
            m = map_by_user.get(usuario.lower())
            if m:
                mat, fonte = m, "mapa"
        if not mat:
            result.skipped += 1
            unmatched.append(usuario)
            continue

        mat_s = mat.strip()[:10]
        # Só preenche células vazias / placeholder — nunca sobrescreve matrícula real
        ok = dal.update(
            f"UPDATE Tb_Atrib SET `{col_mat}` = %s "
            f"WHERE UPPER(TRIM(`{col_user}`)) = %s "
            f"AND ("
            f"TRIM(COALESCE(`{col_mat}`, '')) = '' "
            f"OR TRIM(COALESCE(`{col_mat}`, '')) IN ('0', '00000')"
            f")",
            (mat_s, usuario.upper()),
        )
        if ok:
            result.updated += 1
            if fonte == "oracle":
                result.from_oracle += 1
            elif fonte == "glpi":
                result.from_glpi += 1
            elif fonte == "ad":
                result.from_ad += 1
            else:
                result.from_map += 1
            if len(result.details) < 40:
                result.details.append(f"{usuario} = {mat_s} ({fonte})")
        else:
            result.skipped += 1
            unmatched.append(usuario)
            result.details.append(f"{usuario}: falha no update")

    if unmatched:
        shown = unmatched[:30]
        extra = f"…" if len(unmatched) > 30 else ""
        result.details.append(
            f"Sem fonte ({len(unmatched)}): {', '.join(shown)}{extra}"
        )

    if result.updated == 0:
        result.details.append(
            "Nenhuma matrícula encontrada no Oracle/GLPI/AD. "
            "Importe CSV, edite manualmente ou use o mapa .env."
        )

    return result


def _glpi_search_cell(row: dict, field: str) -> str:
    raw = row.get(field)
    if raw is None:
        try:
            raw = row.get(int(field))
        except (TypeError, ValueError):
            raw = None
    if raw is None:
        return ""
    return str(raw).strip()


def _fetch_glpi_registration_numbers(usuarios: list[str]) -> Dict[str, str]:
    """User.registration_number do GLPI (campo 22) — só nome exatamente igual."""
    from urllib.parse import urlencode

    from ..bootstrap import PROJECT_ROOT, ensure_legacy_path

    ensure_legacy_path()
    out: Dict[str, str] = {}
    wanted = {u.strip().lower(): u.strip() for u in usuarios if (u or "").strip()}
    if not wanted:
        return out
    try:
        from GLPI_API import GLPI_API  # noqa: WPS433
    except Exception as exc:
        logger.warning("Import GLPI_API para matrículas: %s", exc)
        return out

    conf_dir = PROJECT_ROOT / "conf"
    api = None
    try:
        api = GLPI_API.from_config(conf_dir if conf_dir.is_dir() else None)
        name_to_id: Dict[str, str] = {}
        name_to_reg: Dict[str, str] = {}
        page_size = 200

        def _search_pages(with_reg: bool) -> None:
            name_to_id.clear()
            name_to_reg.clear()
            total: Optional[int] = None
            page = 0
            while page < 50:
                start = page * page_size
                end = start + page_size - 1
                params = [
                    ("criteria[0][field]", "2"),
                    ("criteria[0][searchtype]", "morethan"),
                    ("criteria[0][value]", "0"),
                    ("forcedisplay[0]", "1"),
                    ("forcedisplay[1]", "2"),
                    ("range", f"{start}-{end}"),
                ]
                if with_reg:
                    params.insert(-1, ("forcedisplay[2]", "22"))
                url = f"{api._api_url}/search/User?{urlencode(params)}"
                resposta = api._requisicao_url_completa(url, method="GET")
                if not isinstance(resposta, dict):
                    break
                dados = resposta.get("data") or []
                if total is None:
                    try:
                        total = int(resposta.get("totalcount") or 0)
                    except (TypeError, ValueError):
                        total = 0
                for row in dados:
                    if not isinstance(row, dict):
                        continue
                    name = _glpi_search_cell(row, "1")
                    uid = _glpi_search_cell(row, "2")
                    reg = _glpi_search_cell(row, "22") if with_reg else ""
                    if not name:
                        continue
                    key = name.lower()
                    if uid:
                        name_to_id[key] = uid
                    if reg and reg not in ("0", "00000"):
                        name_to_reg[key] = reg[:10]
                if not dados:
                    break
                if total and end >= total - 1:
                    break
                if len(dados) < page_size:
                    break
                page += 1

        try:
            _search_pages(True)
        except Exception as exc:
            logger.info("GLPI search User com campo 22 falhou (%s); repetindo sem matrícula", exc)
            _search_pages(False)

        missing_ids: List[str] = []
        for key in wanted:
            if key in name_to_reg:
                out[key] = name_to_reg[key]
            elif key in name_to_id:
                missing_ids.append(name_to_id[key])

        for uid in missing_ids:
            try:
                user = api._requisicao(f"/User/{uid}", method="GET")
                if isinstance(user, list):
                    user = user[0] if user else {}
                if not isinstance(user, dict):
                    continue
                name = str(user.get("name") or "").strip().lower()
                if name not in wanted:
                    continue
                reg = str(user.get("registration_number") or "").strip()
                if reg and reg not in ("0", "00000"):
                    out[name] = reg[:10]
            except Exception as exc:
                logger.debug("GLPI matricula id %s: %s", uid, exc)

        logger.info(
            "GLPI matrículas (nome exato): %s / %s",
            len(out),
            len(wanted),
        )
    except Exception as exc:
        logger.warning("GLPI registration_number sync: %s", exc)
    finally:
        if api is not None:
            try:
                api.encerrar_sessao()
            except Exception:
                pass
    return out


def _parse_matricula_csv_line(line: str) -> Optional[Tuple[str, str]]:
    raw = (line or "").strip()
    if not raw or raw.startswith("#"):
        return None
    # Cabeçalho comum
    low = raw.lower().replace(" ", "")
    if low in ("usuario;matricula", "usuario,matricula", "login;matricula"):
        return None
    if ";" in raw:
        parts = raw.split(";", 1)
    elif "," in raw:
        parts = raw.split(",", 1)
    elif "\t" in raw:
        parts = raw.split("\t", 1)
    else:
        parts = raw.split(None, 1)
    if len(parts) != 2:
        return None
    usuario = parts[0].strip().strip('"').strip("'")
    matricula = parts[1].strip().strip('"').strip("'")
    if not usuario or not matricula:
        return None
    if len(usuario) > 20 or len(matricula) > 10:
        return None
    return usuario, matricula


def import_matriculas_from_csv(dal: Any, content: str) -> MatriculaImportResult:
    """Atualiza Tb_Atrib.Matricula a partir de texto CSV (usuario;matricula)."""
    result = MatriculaImportResult()
    if not table_exists(dal, "Tb_Atrib"):
        result.details.append("Tb_Atrib ausente")
        return result

    cols = columns_of(dal, "Tb_Atrib")
    col_user = resolve_column(cols, "Usuario")
    col_mat = resolve_column(cols, "Matricula")
    if not col_user or not col_mat:
        result.details.append("Colunas Usuario/Matricula ausentes")
        return result

    seen: set[str] = set()
    for lineno, line in enumerate((content or "").splitlines(), start=1):
        parsed = _parse_matricula_csv_line(line)
        if parsed is None:
            stripped = (line or "").strip()
            if stripped and not stripped.startswith("#"):
                low = stripped.lower().replace(" ", "")
                if low not in ("usuario;matricula", "usuario,matricula", "login;matricula"):
                    result.invalid += 1
                    result.details.append(f"L{lineno}: inválida")
            continue
        usuario, matricula = parsed
        key = usuario.upper()
        if key in seen:
            result.invalid += 1
            result.details.append(f"L{lineno}: duplicado {usuario}")
            continue
        seen.add(key)

        df = safe_read(
            dal,
            f"SELECT 1 AS ok FROM Tb_Atrib WHERE UPPER(TRIM(`{col_user}`)) = %s LIMIT 1",
            (key,),
        )
        if df is None or df.empty:
            result.not_found += 1
            result.details.append(f"{usuario}: não encontrado")
            continue
        ok = dal.update(
            f"UPDATE Tb_Atrib SET `{col_mat}` = %s WHERE UPPER(TRIM(`{col_user}`)) = %s",
            (matricula[:10], key),
        )
        if ok:
            result.updated += 1
            result.details.append(f"{usuario} = {matricula}")
        else:
            result.invalid += 1
            result.details.append(f"{usuario}: falha no update")

    if not seen and result.invalid == 0 and result.not_found == 0:
        result.details.append("Nenhuma linha válida no CSV")
    return result


def list_assignment_rules() -> List[RuleItem]:
    """Lê arqaux.txt (mesmo arquivo do worker)."""
    ensure_legacy_path()
    from arqaux_rules import load_rules  # noqa: WPS433
    from paths import ARQAUX_FILE  # noqa: WPS433

    return [
        RuleItem(equipe=r.equipe, keywords=list(r.keywords), tecnico=r.tecnico)
        for r in load_rules(ARQAUX_FILE)
    ]


def save_assignment_rules(items: List[RuleItem]) -> List[RuleItem]:
    """Grava arqaux.txt com backup .bak (worker relê a cada classificação)."""
    ensure_legacy_path()
    from arqaux_rules import Rule, save_rules  # noqa: WPS433
    from paths import ARQAUX_FILE  # noqa: WPS433

    rules = [
        Rule(
            equipe=(it.equipe or "").strip().upper(),
            keywords=[k.strip().upper() for k in it.keywords if k and k.strip()],
            tecnico=(it.tecnico or "").strip() or None,
        )
        for it in items
    ]
    rules = [r for r in rules if r.equipe and r.keywords]
    save_rules(ARQAUX_FILE, rules, backup=True)
    return [
        RuleItem(equipe=r.equipe, keywords=list(r.keywords), tecnico=r.tecnico)
        for r in rules
    ]


def get_ml_overview(dal: Any) -> MlOverview:
    overview = MlOverview()
    if not table_exists(dal, "Tb_ML_Log"):
        logger.warning("Tabela ausente: Tb_ML_Log")
        return overview

    cols = columns_of(dal, "Tb_ML_Log")
    col_metodo = resolve_column(cols, "Metodo")
    col_conf = resolve_column(cols, "Confianca")
    col_margem = resolve_column(cols, "Margem")
    col_data = resolve_column(cols, "Data_Registro")

    overview.total_logs = _count(dal, "Tb_ML_Log")

    if col_metodo:
        df_m = safe_read(
            dal,
            f"SELECT `{col_metodo}` AS metodo, COUNT(*) AS total "
            f"FROM Tb_ML_Log GROUP BY `{col_metodo}`",
        )
        for _, row in df_m.iterrows():
            overview.by_method[str(cell_to_python(row["metodo"]) or "N/A")] = int(
                cell_to_python(row["total"]) or 0
            )
    else:
        logger.warning("Coluna Metodo ausente em Tb_ML_Log")

    if col_conf:
        df_c = safe_read(
            dal, f"SELECT AVG(`{col_conf}`) AS avg_c FROM Tb_ML_Log WHERE `{col_conf}` IS NOT NULL"
        )
        if not df_c.empty and cell_to_python(df_c.iloc[0]["avg_c"]) is not None:
            overview.avg_confidence = round(float(cell_to_python(df_c.iloc[0]["avg_c"])), 2)

    if col_margem:
        df_g = safe_read(
            dal,
            f"SELECT AVG(`{col_margem}`) AS avg_m FROM Tb_ML_Log WHERE `{col_margem}` IS NOT NULL",
        )
        if not df_g.empty and cell_to_python(df_g.iloc[0]["avg_m"]) is not None:
            overview.avg_margin = round(float(cell_to_python(df_g.iloc[0]["avg_m"])), 2)

    order = f"`{col_data}` DESC" if col_data else "1 DESC"
    # Seleciona campos úteis sem wildcard sensível (não há segredos nessa tabela)
    select_cols = []
    for name in (
        "idml",
        "Id_Glpi",
        "Metodo",
        "Equipe_Prevista",
        "Equipe_ML",
        "Equipe_2a",
        "Confianca",
        "Margem",
        "Motivo_Rejeicao",
        "Categoria",
        "Localizacao",
        "Data_Registro",
    ):
        resolved = resolve_column(cols, name)
        if resolved:
            select_cols.append(f"`{resolved}`")
    if select_cols:
        df_r = safe_read(
            dal, f"SELECT {', '.join(select_cols)} FROM Tb_ML_Log ORDER BY {order} LIMIT 20"
        )
        recent: List[MlLogEntry] = []
        for _, row in df_r.iterrows():
            normalized = normalize_ml_log_row(row_to_dict(row))
            if normalized:
                recent.append(MlLogEntry(**normalized))
        overview.recent = recent

    return overview


def get_ml_model_status() -> MlModelStatus:
    """Lê ModeloML.pkl e metrics.json. Não treina nem restaura versões."""
    ensure_legacy_path()
    from paths import MODEL_DIR  # noqa: WPS433

    status = MlModelStatus()
    pkl = MODEL_DIR / "ModeloML.pkl"
    status.model_exists = pkl.is_file()
    if pkl.is_file():
        st = pkl.stat()
        status.model_size = int(st.st_size)
        status.model_mtime = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")

    metrics_path = MODEL_DIR / "metrics.json"
    if not metrics_path.is_file():
        return status
    try:
        raw = json.loads(metrics_path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("metrics.json ilegível", exc_info=True)
        return status
    if not isinstance(raw, dict):
        return status
    ativo = str(raw.get("ativo") or "").strip() or None
    status.ativo = ativo
    versoes = raw.get("versoes") if isinstance(raw.get("versoes"), list) else []
    entry: Dict[str, Any] = {}
    for item in versoes:
        if isinstance(item, dict) and ativo and item.get("arquivo") == ativo:
            entry = item
            break
    if not entry and versoes and isinstance(versoes[0], dict):
        entry = versoes[0]
    f1 = entry.get("f1_macro")
    try:
        status.f1_macro = float(f1) if f1 is not None else None
    except (TypeError, ValueError):
        status.f1_macro = None
    ver = entry.get("version")
    try:
        status.version = int(ver) if ver is not None else None
    except (TypeError, ValueError):
        status.version = None
    samples = entry.get("train_samples")
    try:
        status.train_samples = int(samples) if samples is not None else None
    except (TypeError, ValueError):
        status.train_samples = None
    data_imp = entry.get("data")
    status.implantado_em = str(data_imp).strip() if data_imp else None
    items: List[MlModelVersionItem] = []
    for item in versoes[:8]:
        if not isinstance(item, dict):
            continue
        nome = str(item.get("arquivo") or "").strip()
        if not nome:
            continue
        f1v = item.get("f1_macro")
        try:
            f1_f = float(f1v) if f1v is not None else None
        except (TypeError, ValueError):
            f1_f = None
        verv = item.get("version")
        try:
            ver_i = int(verv) if verv is not None else None
        except (TypeError, ValueError):
            ver_i = None
        samp = item.get("train_samples")
        try:
            samp_i = int(samp) if samp is not None else None
        except (TypeError, ValueError):
            samp_i = None
        data_v = item.get("data")
        items.append(
            MlModelVersionItem(
                arquivo=nome[:160],
                data=str(data_v).strip() if data_v else None,
                f1_macro=f1_f,
                version=ver_i,
                train_samples=samp_i,
            )
        )
    status.versoes = items
    return status


def list_ml_corrections(
    dal: Any,
    page: int = 1,
    page_size: int = 20,
    *,
    equipe_sgc: Optional[str] = None,
    equipe_correta: Optional[str] = None,
) -> PaginatedMlCorrections:
    page, page_size = clamp_pagination(page, page_size)
    empty = PaginatedMlCorrections(page=page, page_size=page_size, total=0, items=[])
    if not table_exists(dal, "Tb_Correcao_Feedback"):
        logger.warning("Tabela ausente: Tb_Correcao_Feedback")
        return empty

    cols = columns_of(dal, "Tb_Correcao_Feedback")
    col_id = resolve_column(cols, "idcor")
    col_glpi = resolve_column(cols, "Id_Glpi")
    col_titulo = resolve_column(cols, "Titulo")
    col_cat = resolve_column(cols, "Categoria")
    col_sgc = resolve_column(cols, "Equipe_SGC")
    col_ok = resolve_column(cols, "Equipe_Correta")
    col_tec = resolve_column(cols, "Tecnico_Fechamento")
    col_data = resolve_column(cols, "Data_Deteccao")
    if not col_glpi:
        return empty

    parts = [f"`{col_glpi}` AS id_glpi"]
    if col_id:
        parts.append(f"`{col_id}` AS idcor")
    if col_titulo:
        parts.append(f"`{col_titulo}` AS titulo")
    if col_cat:
        parts.append(f"`{col_cat}` AS categoria")
    if col_sgc:
        parts.append(f"`{col_sgc}` AS equipe_sgc")
    if col_ok:
        parts.append(f"`{col_ok}` AS equipe_correta")
    if col_tec:
        parts.append(f"`{col_tec}` AS tecnico_fechamento")
    if col_data:
        parts.append(f"`{col_data}` AS data_deteccao")

    where = ["1=1"]
    params: list = []
    sgc = (equipe_sgc or "").strip().upper()[:5]
    if sgc and col_sgc:
        where.append(f"UPPER(TRIM(`{col_sgc}`)) = %s")
        params.append(sgc)
    ok_eq = (equipe_correta or "").strip().upper()[:5]
    if ok_eq and col_ok:
        where.append(f"UPPER(TRIM(`{col_ok}`)) = %s")
        params.append(ok_eq)
    where_sql = " AND ".join(where)

    total = _count(dal, "Tb_Correcao_Feedback", where_sql, tuple(params) if params else None) or 0
    offset = (page - 1) * page_size
    order = f"`{col_data}` DESC" if col_data else (f"`{col_id}` DESC" if col_id else "1 DESC")
    df = safe_read(
        dal,
        f"SELECT {', '.join(parts)} FROM Tb_Correcao_Feedback "
        f"WHERE {where_sql} ORDER BY {order} LIMIT %s OFFSET %s",
        tuple(params + [page_size, offset]),
    )
    items: List[MlCorrectionItem] = []
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            raw_id = cell_to_python(row.get("idcor")) if "idcor" in row.index else None
            raw_glpi = cell_to_python(row.get("id_glpi"))
            try:
                idcor = int(raw_id) if raw_id is not None else None
            except (TypeError, ValueError):
                idcor = None
            try:
                id_glpi = int(raw_glpi) if raw_glpi is not None else None
            except (TypeError, ValueError):
                id_glpi = None
            items.append(
                MlCorrectionItem(
                    idcor=idcor,
                    id_glpi=id_glpi,
                    titulo=cell_to_python(row.get("titulo")) if "titulo" in row.index else None,
                    categoria=cell_to_python(row.get("categoria")) if "categoria" in row.index else None,
                    equipe_sgc=cell_to_python(row.get("equipe_sgc")) if "equipe_sgc" in row.index else None,
                    equipe_correta=(
                        cell_to_python(row.get("equipe_correta")) if "equipe_correta" in row.index else None
                    ),
                    tecnico_fechamento=(
                        cell_to_python(row.get("tecnico_fechamento"))
                        if "tecnico_fechamento" in row.index
                        else None
                    ),
                    data_deteccao=(
                        cell_to_python(row.get("data_deteccao")) if "data_deteccao" in row.index else None
                    ),
                )
            )
    return PaginatedMlCorrections(page=page, page_size=page_size, total=total, items=items)


def get_ml_accuracy(dal: Any) -> MlAccuracyReport:
    """
    Avalia último log ML por chamado contra fechamento (feedback) e correções.
    Correção em Tb_Correcao_Feedback = erro; fechado sem correção = acerto.
    """
    report = MlAccuracyReport()
    if not table_exists(dal, "Tb_ML_Log") or not table_exists(dal, "Tb_Ticket_Feedback_Temp"):
        return report

    cols_ml = columns_of(dal, "Tb_ML_Log")
    col_ml_id = resolve_column(cols_ml, "idml")
    col_ml_glpi = resolve_column(cols_ml, "Id_Glpi")
    col_ml_metodo = resolve_column(cols_ml, "Metodo")
    if not col_ml_id or not col_ml_glpi:
        return report

    has_corr = table_exists(dal, "Tb_Correcao_Feedback")
    cols_c = columns_of(dal, "Tb_Correcao_Feedback") if has_corr else set()
    col_c_glpi = resolve_column(cols_c, "Id_Glpi") if has_corr else None
    col_c_sgc = resolve_column(cols_c, "Equipe_SGC") if has_corr else None
    col_c_ok = resolve_column(cols_c, "Equipe_Correta") if has_corr else None

    metodo_sel = f"ml.`{col_ml_metodo}`" if col_ml_metodo else "NULL"
    corr_join = (
        f"LEFT JOIN Tb_Correcao_Feedback cf ON cf.`{col_c_glpi}` = last.`id_glpi`"
        if col_c_glpi
        else ""
    )
    erro_expr = f"cf.`{col_c_glpi}` IS NOT NULL" if col_c_glpi else "0"
    df = safe_read(
        dal,
        f"""
        SELECT last.metodo AS metodo,
               COUNT(*) AS avaliados,
               SUM(CASE WHEN {erro_expr} THEN 1 ELSE 0 END) AS erros
        FROM (
            SELECT ml.`{col_ml_glpi}` AS id_glpi,
                   {metodo_sel} AS metodo
            FROM Tb_ML_Log ml
            INNER JOIN (
                SELECT `{col_ml_glpi}` AS id_glpi, MAX(`{col_ml_id}`) AS max_id
                FROM Tb_ML_Log
                GROUP BY `{col_ml_glpi}`
            ) x ON ml.`{col_ml_id}` = x.max_id
        ) last
        INNER JOIN Tb_Ticket_Feedback_Temp fb ON fb.Id_Glpi = last.id_glpi
        {corr_join}
        GROUP BY last.metodo
        """,
    )
    by_method: List[MethodAccuracyItem] = []
    total_av = total_er = 0
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            av = int(cell_to_python(row.get("avaliados")) or 0)
            er = int(cell_to_python(row.get("erros")) or 0)
            ac = max(0, av - er)
            metodo = str(cell_to_python(row.get("metodo")) or "N/A")
            total_av += av
            total_er += er
            by_method.append(
                MethodAccuracyItem(
                    metodo=metodo,
                    avaliados=av,
                    acertos=ac,
                    erros=er,
                    taxa_pct=round(ac / av * 100, 1) if av else None,
                )
            )
    by_method.sort(key=lambda x: x.avaliados, reverse=True)
    report.avaliados = total_av
    report.erros = total_er
    report.acertos = max(0, total_av - total_er)
    report.taxa_pct = round(report.acertos / total_av * 100, 1) if total_av else None
    report.by_method = by_method

    if col_c_sgc and col_c_ok:
        df_p = safe_read(
            dal,
            f"""
            SELECT TRIM(`{col_c_sgc}`) AS equipe_sgc,
                   TRIM(`{col_c_ok}`) AS equipe_correta,
                   COUNT(*) AS quantidade
            FROM Tb_Correcao_Feedback
            WHERE TRIM(COALESCE(`{col_c_sgc}`, '')) <> ''
              AND TRIM(COALESCE(`{col_c_ok}`, '')) <> ''
            GROUP BY TRIM(`{col_c_sgc}`), TRIM(`{col_c_ok}`)
            ORDER BY quantidade DESC
            LIMIT 15
            """,
        )
        if df_p is not None and not df_p.empty:
            for _, row in df_p.iterrows():
                report.error_pairs.append(
                    ErrorPairItem(
                        equipe_sgc=str(cell_to_python(row.get("equipe_sgc")) or ""),
                        equipe_correta=str(cell_to_python(row.get("equipe_correta")) or ""),
                        quantidade=int(cell_to_python(row.get("quantidade")) or 0),
                    )
                )
    return report


def list_ml_logs(
    dal: Any,
    *,
    page: int = 1,
    page_size: int = 20,
    metodo: Optional[str] = None,
    equipe: Optional[str] = None,
    rejeitados: bool = False,
    search: Optional[str] = None,
) -> PaginatedMlLogs:
    page, page_size = clamp_pagination(page, page_size)
    empty = PaginatedMlLogs(page=page, page_size=page_size, total=0, items=[])
    if not table_exists(dal, "Tb_ML_Log"):
        logger.warning("Tabela ausente: Tb_ML_Log")
        return empty

    cols = columns_of(dal, "Tb_ML_Log")
    col_metodo = resolve_column(cols, "Metodo")
    col_eq = resolve_column(cols, "Equipe_Prevista")
    col_rej = resolve_column(cols, "Motivo_Rejeicao")
    col_data = resolve_column(cols, "Data_Registro")
    col_glpi = resolve_column(cols, "Id_Glpi")
    col_id = resolve_column(cols, "idml")

    select_cols = []
    for name in (
        "idml",
        "Id_Glpi",
        "Metodo",
        "Equipe_Prevista",
        "Equipe_ML",
        "Equipe_2a",
        "Confianca",
        "Margem",
        "Motivo_Rejeicao",
        "Categoria",
        "Localizacao",
        "Data_Registro",
    ):
        resolved = resolve_column(cols, name)
        if resolved:
            select_cols.append(f"`{resolved}`")
    if not select_cols:
        return empty

    where = ["1=1"]
    params: list = []
    m = (metodo or "").strip()
    if m and col_metodo:
        where.append(f"`{col_metodo}` = %s")
        params.append(m[:24])
    eq = (equipe or "").strip()
    if eq and col_eq:
        where.append(f"UPPER(TRIM(`{col_eq}`)) = %s")
        params.append(eq.upper()[:5])
    if rejeitados and col_rej:
        where.append(f"TRIM(COALESCE(`{col_rej}`, '')) <> ''")
    q = _sanitize_search(search)
    if q:
        likes = []
        if col_glpi and q.isdigit():
            likes.append(f"`{col_glpi}` = %s")
            params.append(int(q))
        col_cat = resolve_column(cols, "Categoria")
        if col_cat:
            likes.append(f"`{col_cat}` LIKE %s")
            params.append(f"%{q}%")
        if likes:
            where.append("(" + " OR ".join(likes) + ")")

    where_sql = " AND ".join(where)
    total = _count(dal, "Tb_ML_Log", where_sql, tuple(params) if params else None) or 0
    offset = (page - 1) * page_size
    order = f"`{col_data}` DESC" if col_data else (f"`{col_id}` DESC" if col_id else "1 DESC")
    df = safe_read(
        dal,
        f"SELECT {', '.join(select_cols)} FROM Tb_ML_Log "
        f"WHERE {where_sql} ORDER BY {order} LIMIT %s OFFSET %s",
        tuple(params + [page_size, offset]),
    )
    items: List[MlLogEntry] = []
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            normalized = normalize_ml_log_row(row_to_dict(row))
            if normalized:
                items.append(MlLogEntry(**normalized))
    return PaginatedMlLogs(page=page, page_size=page_size, total=total, items=items)


def simulate_equipe_chamado(
    titulo: str,
    categoria: Optional[str] = None,
    descricao: Optional[str] = None,
    localizacao: Optional[str] = None,
) -> MlSimulateResult:
    """Dry-run do pipeline híbrido — não grava GLPI nem Tb_ML_Log."""
    ensure_legacy_path()
    result = MlSimulateResult()
    try:
        from ML import ClML  # noqa: WPS433
        from MetodosGenericos import ClMetodosGenericos  # noqa: WPS433
    except Exception as exc:
        logger.exception("simulate import: %s", exc)
        result.motivo_rejeicao = "Falha ao carregar o classificador."
        return result

    class _DummyTrade:
        """Evita sessão GLPI — simulate só usa arqaux + modelo + Tb_Atrib."""

    try:
        ml = ClML()
        modelo = ml.le_modelo_ml()
        result.modelo_carregado = bool(modelo and modelo[0] is not None)
        met = ClMetodosGenericos(_DummyTrade())  # type: ignore[arg-type]
        res = met.resolver_equipe_chamado(
            ml,
            modelo,
            (titulo or "").strip(),
            (categoria or "").strip(),
            (descricao or "").strip(),
            (localizacao or "").strip(),
        )
        result.equipe = (res.get("equipe") or "") or None
        result.metodo = (res.get("metodo") or "") or None
        result.equipe_ml = (res.get("equipe_ml") or "") or None
        result.equipe_2a = (res.get("equipe_2a") or "") or None
        try:
            result.confianca = float(res.get("confianca") or 0) or None
        except (TypeError, ValueError):
            result.confianca = None
        try:
            result.margem = float(res.get("margem") or 0) or None
        except (TypeError, ValueError):
            result.margem = None
        result.motivo_rejeicao = (res.get("motivo_rejeicao") or "") or None
        result.tecnico_fixo = (res.get("tecnico_fixo") or "") or None
        equipe = result.equipe or ""
        if equipe:
            try:
                cands = met.listar_tecnicos_elegiveis_equipe(
                    equipe,
                    (titulo or "").strip(),
                    (localizacao or "").strip(),
                    categoria=(categoria or "").strip(),
                )
                result.tecnicos_elegiveis = [str(x) for x in (cands or [])[:12]]
            except Exception as exc:
                logger.warning("simulate candidatos: %s", exc)
    except Exception as exc:
        logger.exception("simulate_equipe_chamado: %s", exc)
        result.motivo_rejeicao = "Erro ao simular classificação."
    return result


def list_jobs() -> JobsOverview:
    """
    Catálogo do AgendadorSGC + heartbeat (somente leitura).
    Não inicia o agendador nem importa o worker como processo.
    """
    ensure_legacy_path()
    retrain_h = int(os.getenv("ML_RETRAIN_HOUR", "2"))
    report_h = int(os.getenv("ML_REPORT_HOUR", "3"))
    feedback_wday = int(os.getenv("ML_FEEDBACK_REPORT_WDAY", "6"))
    feedback_h = int(os.getenv("ML_FEEDBACK_REPORT_HOUR", "4"))
    dias = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
    wday_label = dias[feedback_wday] if 0 <= feedback_wday <= 6 else str(feedback_wday)
    intervalo = int(os.getenv("SGC_INTERVALO_VARREDURA", "30") or 30)

    worker: Dict[str, Any] = {}
    sched: Dict[str, Any] = {}
    try:
        from WorkerHeartbeat import snapshot_for_api as _worker_snap  # noqa: WPS433

        worker = _worker_snap() or {}
    except Exception:
        worker = {}
    try:
        from SchedulerHeartbeat import snapshot_for_api as _sched_snap  # noqa: WPS433

        sched = _sched_snap() or {}
    except Exception:
        sched = {}
    jobs_snap = sched.get("jobs") if isinstance(sched.get("jobs"), dict) else {}

    # Preferência: flag gravada pelo worker; fallback env da API
    env_auto = os.getenv("SGC_AGENDADOR_AUTO", "1").lower() in ("1", "true", "yes")
    hb_auto = worker.get("agendador_auto")
    if hb_auto is None:
        agendador_auto = env_auto
    else:
        agendador_auto = bool(hb_auto)

    worker_alive = bool(worker.get("alive")) if worker.get("updated_at") else False
    sched_alive = bool(sched.get("alive")) if sched.get("updated_at") else False

    def _parse_iso(raw: Any) -> Optional[datetime]:
        s = str(raw or "").strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None

    def _fill(job: JobItem) -> JobItem:
        raw = jobs_snap.get(job.id)
        if isinstance(raw, dict):
            at = str(raw.get("at") or "").strip() or None
            job.last_run_at = at
            ok = raw.get("ok")
            job.last_ok = None if ok is None else bool(ok)
            msg = str(raw.get("message") or "").strip() or None
            job.last_message = msg
        return job

    def _next_from_last(last_iso: Optional[str], delta: timedelta) -> Optional[str]:
        ts = _parse_iso(last_iso)
        if ts is None:
            return None
        nxt = ts + delta
        if nxt.tzinfo is not None:
            nxt = nxt.astimezone().replace(tzinfo=None)
        return _iso_local(nxt)

    catalog = [
        JobItem(
            id="retreino_diario",
            name="Re-treino ML diário",
            description=(
                "Sincroniza feedback GLPI, detecta correções e re-treina o modelo "
                "(executado pelo AgendadorSGC do worker)."
            ),
            schedule=f"Diário às {retrain_h:02d}:00",
            enabled=bool(agendador_auto and sched_alive),
            process_alive=sched_alive if agendador_auto else False,
            agenda_enabled=agendador_auto,
            source="agendador_sgc",
            next_run_at=(
                _iso_local(_next_daily_hour(retrain_h))
                if (agendador_auto and sched_alive)
                else None
            ),
        ),
        JobItem(
            id="relatorio_assertividade",
            name="PDF de assertividade",
            description="Gera relatório PDF diário de assertividade do SGC.",
            schedule=f"Diário às {report_h:02d}:00",
            enabled=bool(agendador_auto and sched_alive),
            process_alive=sched_alive if agendador_auto else False,
            agenda_enabled=agendador_auto,
            source="agendador_sgc",
            next_run_at=(
                _iso_local(_next_daily_hour(report_h))
                if (agendador_auto and sched_alive)
                else None
            ),
        ),
        JobItem(
            id="relatorio_feedback",
            name="Relatório de cobertura de feedback",
            description="Gera relatório semanal de cobertura/gaps do feedback ML.",
            schedule=f"{wday_label} às {feedback_h:02d}:00",
            enabled=bool(agendador_auto and sched_alive),
            process_alive=sched_alive if agendador_auto else False,
            agenda_enabled=agendador_auto,
            source="agendador_sgc",
            next_run_at=(
                _iso_local(_next_weekly_hour(feedback_wday, feedback_h))
                if (agendador_auto and sched_alive)
                else None
            ),
        ),
        JobItem(
            id="monitor_chamados",
            name="Monitoramento de chamados Novos",
            description=(
                f"Loop principal do worker (intervalo "
                f"{intervalo}s)."
            ),
            schedule="Contínuo (processo main.py)",
            enabled=worker_alive,
            process_alive=worker_alive,
            agenda_enabled=True,
            source="main.py",
            next_run_at=(
                _next_from_last(worker.get("updated_at"), timedelta(seconds=max(5, intervalo)))
                if worker_alive
                else None
            ),
        ),
        JobItem(
            id="verifica_atribuicoes",
            name="Sincronização técnico GLPI ↔ base",
            description="A cada 15 minutos no loop do main.py.",
            schedule="A cada 15 minutos",
            enabled=worker_alive,
            process_alive=worker_alive,
            agenda_enabled=True,
            source="main.py",
            next_run_at=(
                (
                    _next_from_last(
                        (jobs_snap.get("verifica_atribuicoes") or {}).get("at")
                        if isinstance(jobs_snap.get("verifica_atribuicoes"), dict)
                        else None,
                        timedelta(minutes=15),
                    )
                    or (
                        _iso_local(datetime.now() + timedelta(minutes=15))
                        if worker_alive
                        else None
                    )
                )
                if worker_alive
                else None
            ),
        ),
    ]
    return JobsOverview(
        worker_alive=worker.get("alive") if worker.get("updated_at") else None,
        scheduler_alive=(
            False
            if not agendador_auto
            else (bool(sched.get("alive")) if sched.get("updated_at") else None)
        ),
        scheduler_enabled=agendador_auto,
        worker_updated_at=worker.get("updated_at"),
        scheduler_updated_at=sched.get("updated_at"),
        jobs=[_fill(j) for j in catalog],
    )


def _iso_local(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat(timespec="seconds")


def _next_daily_hour(hour: int) -> datetime:
    now = datetime.now()
    hour = max(0, min(23, int(hour)))
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if now >= candidate:
        candidate += timedelta(days=1)
    return candidate


def _next_weekly_hour(wday: int, hour: int) -> datetime:
    now = datetime.now()
    hour = max(0, min(23, int(hour)))
    wday = int(wday) % 7
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    days = (wday - now.weekday()) % 7
    if days == 0 and now >= candidate:
        days = 7
    return candidate + timedelta(days=days)


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _parse_ref_date(raw: Optional[str]) -> date:
    if raw:
        try:
            return date.fromisoformat(raw.strip()[:10])
        except ValueError:
            pass
    return date.today()


def _period_window(period: str, ref: date) -> Tuple[date, date, str]:
    """Retorna (start, end_inclusive, label)."""
    p = (period or "week").strip().lower()
    if p == "day":
        return ref, ref, ref.strftime("%d/%m/%Y")
    if p == "month":
        start = ref.replace(day=1)
        if start.month == 12:
            end = date(start.year, 12, 31)
        else:
            end = date(start.year, start.month + 1, 1) - timedelta(days=1)
        return start, end, start.strftime("%m/%Y")
    start = _monday_of(ref)
    end = start + timedelta(days=6)
    label = f"{start.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}"
    return start, end, label


MAX_OPS_RANGE_DAYS = 92

_TEMPO_FAIXAS_LABELS = ("Até 4 h", "4–8 h", "8–24 h", "Acima de 24 h")
_TEMPO_FAIXAS_KEYS = ("ate_4h", "4_8h", "8_24h", "acima_24h")


def _iso_day(value: Any) -> Optional[str]:
    py = cell_to_python(value)
    if py is None:
        return None
    if isinstance(py, datetime):
        return py.date().isoformat()
    if isinstance(py, date):
        return py.isoformat()
    raw = str(py).strip()[:10]
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw
    return None


def _empty_daily_series(start: date, end: date) -> Dict[str, DailySeriesItem]:
    out: Dict[str, DailySeriesItem] = {}
    cursor = start
    while cursor <= end:
        key = cursor.isoformat()
        out[key] = DailySeriesItem(data=key)
        cursor += timedelta(days=1)
    return out


def _empty_tempo_faixas() -> List[TempoFaixaItem]:
    return [TempoFaixaItem(faixa=label, qtd=0) for label in _TEMPO_FAIXAS_LABELS]


def _custom_window(date_from: Optional[str], date_to: Optional[str]) -> Tuple[date, date, str]:
    """Janela inclusiva a partir de date_from/date_to. Troca se invertido; teto 92 dias."""
    start = _parse_ref_date(date_from)
    end = _parse_ref_date(date_to)
    if start > end:
        start, end = end, start
    span_days = (end - start).days
    if span_days > MAX_OPS_RANGE_DAYS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Intervalo máximo de {MAX_OPS_RANGE_DAYS} dias "
                f"(recebido {span_days + 1} dias)."
            ),
        )
    if start == end:
        label = start.strftime("%d/%m/%Y")
    else:
        label = f"{start.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}"
    return start, end, label


def get_ops_period_report(
    dal: Any,
    *,
    period: str = "week",
    ref_date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    equipes: Optional[str] = None,
    tecnico: Optional[str] = None,
    include_comparacao: bool = True,
) -> OpsPeriodReport:
    """
    Relatório operacional diário / semanal / mensal / intervalo livre por equipe
    (e opcionalmente 1 técnico).

    Fontes:
      - Tb_Ticket_new.Data → atribuídos + top solicitantes (sol)
      - Tb_Ticket_Feedback_Temp → fechados, abertos, tempo, top localizações
      - Tb_Ticket_new Sit=1 → backlog ativo (snapshot)
    """
    p = (period or "week").strip().lower()
    has_range = bool((date_from or "").strip() or (date_to or "").strip())
    if p not in ("day", "week", "month", "custom"):
        p = "week"
    if p == "custom" and not has_range:
        raise HTTPException(
            status_code=400,
            detail="Informe date_from e date_to para period=custom.",
        )
    if has_range:
        start, end, label = _custom_window(date_from or date_to, date_to or date_from)
        if p != "custom":
            # Datas explícitas: mantém o atalho só como rótulo; a janela é o intervalo.
            pass
        else:
            p = "custom"
    else:
        ref = _parse_ref_date(ref_date)
        start, end, label = _period_window(p, ref)
    start_dt = datetime.combine(start, datetime.min.time())
    end_exclusive = datetime.combine(end + timedelta(days=1), datetime.min.time())

    focus_default = ["N1", "N2", "N3", "DEV"]
    strict_focus = bool(equipes and equipes.strip())
    if strict_focus:
        focus = [e.strip().upper() for e in equipes.split(",") if e.strip()]
    else:
        focus = list(focus_default)

    tec_filter = (tecnico or "").strip()
    tec_filter_u = tec_filter.upper() if tec_filter else ""

    notes = [
        "Fechados/abertos/tempo vêm do feedback GLPI (Tb_Ticket_Feedback_Temp).",
        "Atribuídos e solicitantes vêm da base local SGC (Tb_Ticket_new) no período.",
        "Backlog ativo = chamados locais com Sit=1 no momento da consulta.",
        "Localização = onde o chamado foi aberto (proxy de demanda).",
    ]
    if tec_filter:
        notes.append(f"Filtro de técnico ativo: {tec_filter}.")

    serie_map = _empty_daily_series(start, end)
    tempo_faixas = _empty_tempo_faixas()
    faixa_index = {k: i for i, k in enumerate(_TEMPO_FAIXAS_KEYS)}

    teams: Dict[str, WeeklyTeamStats] = {}
    people: Dict[str, Dict[str, WeeklyPersonStats]] = {}
    person_close_minutes: Dict[Tuple[str, str], List[float]] = {}
    team_close_minutes: Dict[str, List[float]] = {}

    def _team(eq: str) -> WeeklyTeamStats:
        key = (eq or "SEM_EQUIPE").strip().upper() or "SEM_EQUIPE"
        if key not in teams:
            teams[key] = WeeklyTeamStats(equipe=key)
            people[key] = {}
        return teams[key]

    def _person(eq: str, tec: str) -> WeeklyPersonStats:
        key = (eq or "SEM_EQUIPE").strip().upper() or "SEM_EQUIPE"
        _team(key)
        tkey = (tec or "SEM_TECNICO").strip() or "SEM_TECNICO"
        bucket = people[key]
        if tkey not in bucket:
            bucket[tkey] = WeeklyPersonStats(tecnico=tkey)
        return bucket[tkey]

    def _tec_ok(tec: str) -> bool:
        if not tec_filter_u:
            return True
        return (tec or "").strip().upper() == tec_filter_u

    top_solicitantes: List[NameCountItem] = []
    if table_exists(dal, "Tb_Ticket_new"):
        cols = columns_of(dal, "Tb_Ticket_new")
        col_data = resolve_column(cols, "Data")
        col_eq = resolve_column(cols, "Equipe")
        col_tec = resolve_column(cols, "tecnico") or resolve_column(cols, "Tecnico")
        col_sol = resolve_column(cols, "sol", "Sol", "Solicitante")
        if col_data and col_eq:
            tec_sel = f"TRIM(`{col_tec}`) AS tecnico" if col_tec else "'SEM_TECNICO' AS tecnico"
            where_extra = ""
            params: List[Any] = [start_dt, end_exclusive]
            if tec_filter_u and col_tec:
                where_extra = f" AND UPPER(TRIM(`{col_tec}`)) = %s"
                params.append(tec_filter_u)
            df = safe_read(
                dal,
                f"""
                SELECT
                    UPPER(TRIM(COALESCE(`{col_eq}`, 'SEM_EQUIPE'))) AS equipe,
                    {tec_sel},
                    COUNT(*) AS total
                FROM Tb_Ticket_new
                WHERE `{col_data}` >= %s AND `{col_data}` < %s
                {where_extra}
                GROUP BY UPPER(TRIM(COALESCE(`{col_eq}`, 'SEM_EQUIPE'))),
                         {f'TRIM(`{col_tec}`)' if col_tec else "1"}
                """,
                tuple(params),
            )
            for _, row in df.iterrows():
                eq = str(cell_to_python(row["equipe"]) or "SEM_EQUIPE")
                tec = str(cell_to_python(row.get("tecnico")) or "SEM_TECNICO")
                if not _tec_ok(tec):
                    continue
                n = int(cell_to_python(row["total"]) or 0)
                _team(eq).atribuidos += n
                _person(eq, tec).atribuidos += n

            if col_sol:
                params_s: List[Any] = [start_dt, end_exclusive]
                where_s = ""
                if tec_filter_u and col_tec:
                    where_s = f" AND UPPER(TRIM(`{col_tec}`)) = %s"
                    params_s.append(tec_filter_u)
                df_s = safe_read(
                    dal,
                    f"""
                    SELECT
                        TRIM(`{col_sol}`) AS nome,
                        COUNT(*) AS total
                    FROM Tb_Ticket_new
                    WHERE `{col_data}` >= %s AND `{col_data}` < %s
                      AND TRIM(COALESCE(`{col_sol}`, '')) <> ''
                    {where_s}
                    GROUP BY TRIM(`{col_sol}`)
                    ORDER BY total DESC
                    LIMIT 10
                    """,
                    tuple(params_s),
                )
                for _, row in df_s.iterrows():
                    nome = str(cell_to_python(row.get("nome")) or "").strip()
                    if nome:
                        top_solicitantes.append(
                            NameCountItem(
                                nome=nome, qtd=int(cell_to_python(row["total"]) or 0)
                            )
                        )

            params_day: List[Any] = [start_dt, end_exclusive]
            where_day = ""
            if tec_filter_u and col_tec:
                where_day = f" AND UPPER(TRIM(`{col_tec}`)) = %s"
                params_day.append(tec_filter_u)
            df_day_a = safe_read(
                dal,
                f"""
                SELECT DATE(`{col_data}`) AS dia, COUNT(*) AS total
                FROM Tb_Ticket_new
                WHERE `{col_data}` >= %s AND `{col_data}` < %s
                {where_day}
                GROUP BY DATE(`{col_data}`)
                """,
                tuple(params_day),
            )
            if df_day_a is not None and not df_day_a.empty:
                for _, row in df_day_a.iterrows():
                    dia = _iso_day(row.get("dia"))
                    if dia and dia in serie_map:
                        serie_map[dia].atribuidos = int(cell_to_python(row["total"]) or 0)

        col_sit = resolve_column(cols, "Sit")
        if col_eq and col_sit:
            where_b = ""
            params_b: List[Any] = []
            if tec_filter_u and col_tec:
                where_b = f" AND UPPER(TRIM(`{col_tec}`)) = %s"
                params_b.append(tec_filter_u)
            df_b = safe_read(
                dal,
                f"""
                SELECT
                    UPPER(TRIM(COALESCE(`{col_eq}`, 'SEM_EQUIPE'))) AS equipe,
                    COUNT(*) AS total
                FROM Tb_Ticket_new
                WHERE (`{col_sit}` = '1' OR `{col_sit}` = 1)
                {where_b}
                GROUP BY UPPER(TRIM(COALESCE(`{col_eq}`, 'SEM_EQUIPE')))
                """,
                tuple(params_b) if params_b else None,
            )
            for _, row in df_b.iterrows():
                eq = str(cell_to_python(row["equipe"]) or "SEM_EQUIPE")
                _team(eq).backlog_ativo = int(cell_to_python(row["total"]) or 0)
    else:
        notes.append("Tb_Ticket_new ausente — atribuídos/backlog/solicitantes não disponíveis.")

    top_localizacoes: List[NameCountItem] = []
    if table_exists(dal, "Tb_Ticket_Feedback_Temp"):
        cols_f = columns_of(dal, "Tb_Ticket_Feedback_Temp")
        col_fech = resolve_column(cols_f, "Data_Fechamento")
        col_aber = resolve_column(cols_f, "Data_Abertura")
        col_eq_f = resolve_column(cols_f, "Equipe")
        col_tec_f = resolve_column(cols_f, "Tecnico")
        col_loc = resolve_column(cols_f, "Localizacao", "Localização")
        if col_fech and col_eq_f:
            tec_sel = (
                f"TRIM(`{col_tec_f}`) AS tecnico" if col_tec_f else "'SEM_TECNICO' AS tecnico"
            )
            where_extra = ""
            params_f: List[Any] = [start_dt, end_exclusive]
            if tec_filter_u and col_tec_f:
                where_extra = f" AND UPPER(TRIM(`{col_tec_f}`)) = %s"
                params_f.append(tec_filter_u)
            df_f = safe_read(
                dal,
                f"""
                SELECT
                    UPPER(TRIM(COALESCE(`{col_eq_f}`, 'SEM_EQUIPE'))) AS equipe,
                    {tec_sel},
                    COUNT(*) AS total,
                    AVG(TIMESTAMPDIFF(MINUTE, `{col_aber}`, `{col_fech}`)) AS avg_min
                FROM Tb_Ticket_Feedback_Temp
                WHERE `{col_fech}` >= %s AND `{col_fech}` < %s
                {where_extra}
                GROUP BY UPPER(TRIM(COALESCE(`{col_eq_f}`, 'SEM_EQUIPE'))),
                         {f'TRIM(`{col_tec_f}`)' if col_tec_f else "1"}
                """,
                tuple(params_f),
            )
            for _, row in df_f.iterrows():
                eq = str(cell_to_python(row["equipe"]) or "SEM_EQUIPE")
                tec = str(cell_to_python(row.get("tecnico")) or "SEM_TECNICO")
                if not _tec_ok(tec):
                    continue
                n = int(cell_to_python(row["total"]) or 0)
                _team(eq).fechados += n
                _person(eq, tec).fechados += n
                avg_min = cell_to_python(row.get("avg_min"))
                if avg_min is not None and n > 0:
                    weighted = float(avg_min) * n
                    team_close_minutes.setdefault(eq, []).append(weighted)
                    person_close_minutes.setdefault((eq, tec), []).append(weighted)

            for eq, weighted in team_close_minutes.items():
                t = teams[eq]
                if t.fechados > 0 and weighted:
                    t.tempo_medio_horas = round(sum(weighted) / t.fechados / 60.0, 2)
            for (eq, tec), weighted in person_close_minutes.items():
                pstats = _person(eq, tec)
                if pstats.fechados > 0 and weighted:
                    pstats.tempo_medio_horas = round(
                        sum(weighted) / pstats.fechados / 60.0, 2
                    )

            params_day_f: List[Any] = [start_dt, end_exclusive]
            where_day_f = ""
            if tec_filter_u and col_tec_f:
                where_day_f = f" AND UPPER(TRIM(`{col_tec_f}`)) = %s"
                params_day_f.append(tec_filter_u)
            df_day_f = safe_read(
                dal,
                f"""
                SELECT DATE(`{col_fech}`) AS dia, COUNT(*) AS total
                FROM Tb_Ticket_Feedback_Temp
                WHERE `{col_fech}` >= %s AND `{col_fech}` < %s
                {where_day_f}
                GROUP BY DATE(`{col_fech}`)
                """,
                tuple(params_day_f),
            )
            if df_day_f is not None and not df_day_f.empty:
                for _, row in df_day_f.iterrows():
                    dia = _iso_day(row.get("dia"))
                    if dia and dia in serie_map:
                        serie_map[dia].fechados = int(cell_to_python(row["total"]) or 0)

            if col_aber:
                params_fx: List[Any] = [start_dt, end_exclusive]
                where_fx = ""
                if tec_filter_u and col_tec_f:
                    where_fx = f" AND UPPER(TRIM(`{col_tec_f}`)) = %s"
                    params_fx.append(tec_filter_u)
                df_fx = safe_read(
                    dal,
                    f"""
                    SELECT
                        CASE
                            WHEN TIMESTAMPDIFF(MINUTE, `{col_aber}`, `{col_fech}`) < 240
                                THEN 'ate_4h'
                            WHEN TIMESTAMPDIFF(MINUTE, `{col_aber}`, `{col_fech}`) < 480
                                THEN '4_8h'
                            WHEN TIMESTAMPDIFF(MINUTE, `{col_aber}`, `{col_fech}`) < 1440
                                THEN '8_24h'
                            ELSE 'acima_24h'
                        END AS faixa,
                        COUNT(*) AS total
                    FROM Tb_Ticket_Feedback_Temp
                    WHERE `{col_fech}` >= %s AND `{col_fech}` < %s
                      AND `{col_aber}` IS NOT NULL
                    {where_fx}
                    GROUP BY faixa
                    """,
                    tuple(params_fx),
                )
                if df_fx is not None and not df_fx.empty:
                    for _, row in df_fx.iterrows():
                        key = str(cell_to_python(row.get("faixa")) or "").strip()
                        idx = faixa_index.get(key)
                        if idx is not None:
                            tempo_faixas[idx].qtd = int(cell_to_python(row["total"]) or 0)

        if col_aber and col_eq_f:
            tec_sel = (
                f"TRIM(`{col_tec_f}`) AS tecnico" if col_tec_f else "'SEM_TECNICO' AS tecnico"
            )
            where_extra = ""
            params_a: List[Any] = [start_dt, end_exclusive]
            if tec_filter_u and col_tec_f:
                where_extra = f" AND UPPER(TRIM(`{col_tec_f}`)) = %s"
                params_a.append(tec_filter_u)
            df_a = safe_read(
                dal,
                f"""
                SELECT
                    UPPER(TRIM(COALESCE(`{col_eq_f}`, 'SEM_EQUIPE'))) AS equipe,
                    {tec_sel},
                    COUNT(*) AS total
                FROM Tb_Ticket_Feedback_Temp
                WHERE `{col_aber}` >= %s AND `{col_aber}` < %s
                {where_extra}
                GROUP BY UPPER(TRIM(COALESCE(`{col_eq_f}`, 'SEM_EQUIPE'))),
                         {f'TRIM(`{col_tec_f}`)' if col_tec_f else "1"}
                """,
                tuple(params_a),
            )
            for _, row in df_a.iterrows():
                eq = str(cell_to_python(row["equipe"]) or "SEM_EQUIPE")
                tec = str(cell_to_python(row.get("tecnico")) or "SEM_TECNICO")
                if not _tec_ok(tec):
                    continue
                n = int(cell_to_python(row["total"]) or 0)
                _team(eq).abertos += n
                _person(eq, tec).abertos += n

        if col_loc and col_fech:
            where_l = ""
            params_l: List[Any] = [start_dt, end_exclusive]
            if tec_filter_u and col_tec_f:
                where_l = f" AND UPPER(TRIM(`{col_tec_f}`)) = %s"
                params_l.append(tec_filter_u)
            df_l = safe_read(
                dal,
                f"""
                SELECT
                    TRIM(`{col_loc}`) AS nome,
                    COUNT(*) AS total
                FROM Tb_Ticket_Feedback_Temp
                WHERE `{col_fech}` >= %s AND `{col_fech}` < %s
                  AND TRIM(COALESCE(`{col_loc}`, '')) <> ''
                {where_l}
                GROUP BY TRIM(`{col_loc}`)
                ORDER BY total DESC
                LIMIT 10
                """,
                tuple(params_l),
            )
            for _, row in df_l.iterrows():
                nome = str(cell_to_python(row.get("nome")) or "").strip()
                if nome:
                    top_localizacoes.append(
                        NameCountItem(
                            nome=nome, qtd=int(cell_to_python(row["total"]) or 0)
                        )
                    )
    else:
        notes.append(
            "Tb_Ticket_Feedback_Temp ausente — fechados/abertos GLPI não disponíveis."
        )

    for eq in focus:
        _team(eq)

    mat_by_user: Dict[str, str] = {}
    if table_exists(dal, "Tb_Atrib"):
        df_m = safe_read(
            dal,
            """
            SELECT TRIM(Usuario) AS usuario, TRIM(Matricula) AS matricula
            FROM Tb_Atrib
            WHERE TRIM(COALESCE(Matricula, '')) <> ''
              AND TRIM(COALESCE(Matricula, '')) NOT IN ('0', '00000')
            """,
        )
        for _, row in df_m.iterrows():
            u = str(cell_to_python(row.get("usuario")) or "").strip().upper()
            m = str(cell_to_python(row.get("matricula")) or "").strip()
            if u and m:
                mat_by_user[u] = m

    rank_candidates: List[RankPersonItem] = []
    for eq, stats in teams.items():
        plist = list(people.get(eq, {}).values())
        for pstats in plist:
            pstats.matricula = mat_by_user.get(pstats.tecnico.strip().upper())
            if pstats.fechados > 0 or pstats.atribuidos > 0:
                rank_candidates.append(
                    RankPersonItem(
                        tecnico=pstats.tecnico,
                        equipe=eq,
                        matricula=pstats.matricula,
                        fechados=pstats.fechados,
                        atribuidos=pstats.atribuidos,
                        tempo_medio_horas=pstats.tempo_medio_horas,
                    )
                )
        plist.sort(key=lambda x: (-(x.fechados + x.atribuidos), x.tecnico.lower()))
        stats.por_tecnico = plist[:50]

    def _sort_key(t: WeeklyTeamStats) -> Tuple[int, int, str]:
        in_focus = 0 if t.equipe in focus else 1
        vol = -(t.fechados + t.atribuidos + t.abertos)
        return (in_focus, vol, t.equipe)

    ordered = sorted(teams.values(), key=_sort_key)
    if strict_focus:
        visible = [t for t in ordered if t.equipe in focus]
    else:
        visible = [
            t
            for t in ordered
            if t.equipe in focus or (t.fechados + t.atribuidos + t.abertos) > 0
        ]

    if tec_filter_u:
        visible = [
            t
            for t in visible
            if (t.atribuidos + t.fechados + t.abertos + t.backlog_ativo) > 0
            or any(ps.tecnico.upper() == tec_filter_u for ps in t.por_tecnico)
        ]

    totals = WeeklyTeamStats(equipe="TOTAL")
    weighted_total: List[float] = []
    for t in visible:
        totals.atribuidos += t.atribuidos
        totals.fechados += t.fechados
        totals.abertos += t.abertos
        totals.backlog_ativo += t.backlog_ativo
        if t.tempo_medio_horas is not None and t.fechados > 0:
            weighted_total.append(t.tempo_medio_horas * t.fechados)
    if totals.fechados > 0 and weighted_total:
        totals.tempo_medio_horas = round(sum(weighted_total) / totals.fechados, 2)

    by_fechados = sorted(
        rank_candidates,
        key=lambda r: (-r.fechados, -r.atribuidos, r.tecnico.lower()),
    )
    closed_only = [r for r in by_fechados if r.fechados > 0]
    rank_mais = closed_only[:5] if not tec_filter_u else []
    rank_menos = (
        sorted(closed_only, key=lambda r: (r.fechados, r.atribuidos, r.tecnico.lower()))[
            :5
        ]
        if not tec_filter_u
        else []
    )

    report = OpsPeriodReport(
        period=p,  # type: ignore[arg-type]
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        label=label,
        focus_teams=focus,
        filtro_tecnico=tec_filter or None,
        teams=visible,
        totals=totals,
        rank_fechou_mais=rank_mais,
        rank_fechou_menos=rank_menos,
        top_solicitantes=top_solicitantes,
        top_localizacoes=top_localizacoes,
        notes=notes,
        serie_diaria=list(serie_map.values()),
        tempo_faixas=tempo_faixas,
        week_start=start.isoformat() if p in ("week", "custom") else None,
        week_end=end.isoformat() if p in ("week", "custom") else None,
    )
    if include_comparacao:
        report.comparacao = _ops_period_comparison(
            dal, report, equipes=equipes, tecnico=tecnico
        )
    return report


def previous_ops_window(period_start: str, period_end: str) -> Tuple[str, str]:
    """Mesmo número de dias imediatamente anterior (fim inclusivo)."""
    start = date.fromisoformat(period_start)
    end = date.fromisoformat(period_end)
    span = (end - start).days
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span)
    return prev_start.isoformat(), prev_end.isoformat()


def _ops_period_comparison(
    dal: Any,
    current: OpsPeriodReport,
    *,
    equipes: Optional[str],
    tecnico: Optional[str],
) -> OpsPeriodComparison:
    prev_from, prev_to = previous_ops_window(current.period_start, current.period_end)
    previous = get_ops_period_report(
        dal,
        period="custom",
        date_from=prev_from,
        date_to=prev_to,
        equipes=equipes,
        tecnico=tecnico,
        include_comparacao=False,
    )
    return OpsPeriodComparison(
        period_start=previous.period_start,
        period_end=previous.period_end,
        label=previous.label,
        atribuidos=previous.totals.atribuidos,
        fechados=previous.totals.fechados,
        tempo_medio_horas=previous.totals.tempo_medio_horas,
    )


def build_ops_period_pdf(
    dal: Any,
    *,
    period: str = "week",
    ref_date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    equipes: Optional[str] = None,
    tecnico: Optional[str] = None,
) -> Path:
    """PDF 2–3 páginas a partir do mesmo recorte de get_ops_period_report (com comparação)."""
    current = get_ops_period_report(
        dal,
        period=period,
        ref_date=ref_date,
        date_from=date_from,
        date_to=date_to,
        equipes=equipes,
        tecnico=tecnico,
    )
    from RelatorioOpsPdf import gerar_relatorio_ops_pdf  # noqa: WPS433 — python/

    return gerar_relatorio_ops_pdf(current)


def build_ops_period_csv(
    dal: Any,
    *,
    period: str = "week",
    ref_date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    equipes: Optional[str] = None,
    tecnico: Optional[str] = None,
) -> bytes:
    """CSV (Excel) do mesmo recorte de GET /reports/ops."""
    report = get_ops_period_report(
        dal,
        period=period,
        ref_date=ref_date,
        date_from=date_from,
        date_to=date_to,
        equipes=equipes,
        tecnico=tecnico,
    )
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(["SGC Relatorio operacional", report.label])
    w.writerow(["Periodo", report.period_start, report.period_end])
    if report.filtro_tecnico:
        w.writerow(["Tecnico", report.filtro_tecnico])
    w.writerow([])
    w.writerow(["KPI", "Valor"])
    w.writerow(["Atribuidos", report.totals.atribuidos])
    w.writerow(["Fechados", report.totals.fechados])
    w.writerow(["Abertos", report.totals.abertos])
    w.writerow(["Backlog", report.totals.backlog_ativo])
    w.writerow(["Tempo medio horas", report.totals.tempo_medio_horas or ""])
    if report.comparacao:
        w.writerow([])
        w.writerow(["Vs periodo anterior", report.comparacao.label])
        w.writerow(["Atribuidos anterior", report.comparacao.atribuidos])
        w.writerow(["Fechados anterior", report.comparacao.fechados])
        w.writerow(["Tempo medio anterior", report.comparacao.tempo_medio_horas or ""])
    w.writerow([])
    w.writerow(["Equipe", "Atribuidos", "Fechados", "Abertos", "Backlog", "Tempo medio horas"])
    for t in report.teams:
        w.writerow(
            [
                t.equipe,
                t.atribuidos,
                t.fechados,
                t.abertos,
                t.backlog_ativo,
                t.tempo_medio_horas if t.tempo_medio_horas is not None else "",
            ]
        )
    w.writerow([])
    w.writerow(["Dia", "Atribuidos", "Fechados"])
    for d in report.serie_diaria:
        w.writerow([d.data, d.atribuidos, d.fechados])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


_ASSERT_PDF = re.compile(r"^Assertividade_SGC_\d{8}\.pdf$")


def list_assertividade_pdfs() -> List[AssertividadePdfItem]:
    from paths import RELATORIOS_DIR  # noqa: WPS433

    RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)
    items: List[AssertividadePdfItem] = []
    for path in sorted(RELATORIOS_DIR.glob("Assertividade_SGC_*.pdf"), reverse=True):
        if not _ASSERT_PDF.match(path.name):
            continue
        stat = path.stat()
        items.append(
            AssertividadePdfItem(
                filename=path.name,
                size=int(stat.st_size),
                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            )
        )
    return items[:60]


def assertividade_pdf_path(filename: str) -> Path:
    from paths import RELATORIOS_DIR  # noqa: WPS433

    name = (filename or "").strip()
    if not _ASSERT_PDF.match(name):
        raise HTTPException(status_code=400, detail="Arquivo de assertividade inválido.")
    root = RELATORIOS_DIR.resolve()
    path = (root / name).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Arquivo fora da pasta de relatórios.")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="PDF de assertividade não encontrado.")
    return path


def get_weekly_team_report(
    dal: Any,
    *,
    week_start: Optional[str] = None,
    equipes: Optional[str] = None,
    tecnico: Optional[str] = None,
) -> WeeklyTeamReport:
    """Alias semanal do relatório operacional."""
    ops = get_ops_period_report(
        dal,
        period="week",
        ref_date=week_start,
        equipes=equipes,
        tecnico=tecnico,
        include_comparacao=False,
    )
    return WeeklyTeamReport(
        week_start=ops.period_start,
        week_end=ops.period_end,
        label=ops.label,
        focus_teams=ops.focus_teams,
        teams=ops.teams,
        totals=ops.totals,
        notes=ops.notes,
    )
