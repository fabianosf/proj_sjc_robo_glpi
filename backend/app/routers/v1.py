"""Rotas /api/v1 — leitura operacional e escritas ADMIN (técnicos, regras, redirect)."""

from __future__ import annotations

import logging
from typing import Annotated, List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from ..auth.deps import require_min_rank, require_profiles
from ..auth.schemas import UserPublic
from ..deps import get_dal
from ..schemas import (
    DashboardSummary,
    JobsOverview,
    MatriculaImportBody,
    MatriculaImportResult,
    MatriculaSyncResult,
    MlAccuracyReport,
    MlModelStatus,
    MlOverview,
    MlSimulateBody,
    MlSimulateResult,
    NotificationItem,
    NotificationList,
    NotificationUnreadCount,
    OpsPeriodReport,
    PaginatedMlCorrections,
    PaginatedMlLogs,
    PaginatedTickets,
    RuleItem,
    RulesPutBody,
    TeamGuideItem,
    TeamItem,
    TechnicianItem,
    TechnicianRedirect,
    TechnicianRedirectResult,
    TechnicianUpdate,
    TicketDetail,
    TicketGlpiHint,
    TicketReassign,
    TicketReassignResult,
    WeeklyTeamReport,
    AssertividadePdfItem,
)
from ..services import notifications as notif_svc
from ..services import queries

logger = logging.getLogger("sgc_api")
router = APIRouter(prefix="/api/v1", tags=["api-v1"])

# CONSULTA+: leitura operacional
ConsultaUser = Annotated[UserPublic, Depends(require_min_rank("CONSULTA"))]
# OPERADOR+: agendamentos
OperadorUser = Annotated[UserPublic, Depends(require_min_rank("OPERADOR"))]
# GESTOR+: visão ML
GestorUser = Annotated[UserPublic, Depends(require_min_rank("GESTOR"))]
# ADMIN: edição de cadastro operacional
AdminUser = Annotated[UserPublic, Depends(require_profiles("ADMIN"))]


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(_user: ConsultaUser) -> DashboardSummary:
    try:
        return queries.get_dashboard_summary(get_dal())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("dashboard/summary")
        raise HTTPException(status_code=500, detail="Erro ao montar o resumo.") from exc


@router.get("/tickets", response_model=PaginatedTickets)
def tickets(
    _user: ConsultaUser,
    page: int = Query(1, ge=1, description="Página (>= 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página (1–100)"),
    search: Optional[str] = Query(None, max_length=100),
) -> PaginatedTickets:
    try:
        return queries.list_tickets(get_dal(), page=page, page_size=page_size, search=search)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("tickets list")
        raise HTTPException(status_code=500, detail="Erro ao listar chamados.") from exc


@router.get("/tickets/glpi", response_model=PaginatedTickets)
def tickets_glpi(
    _user: ConsultaUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100),
) -> PaginatedTickets:
    """Chamados ativos do GLPI (status=notold) — mesma busca do front ticket.php."""
    try:
        return queries.list_glpi_active_tickets(
            page=page, page_size=page_size, search=search
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("tickets glpi")
        raise HTTPException(
            status_code=500, detail="Erro ao listar chamados do GLPI."
        ) from exc


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
def ticket_detail(ticket_id: int, _user: ConsultaUser) -> TicketDetail:
    if ticket_id < 1:
        raise HTTPException(status_code=400, detail="ticket_id deve ser um inteiro >= 1.")
    try:
        item = queries.get_ticket(get_dal(), ticket_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ticket detail %s", ticket_id)
        raise HTTPException(status_code=500, detail="Erro ao buscar chamado.") from exc

    if item is None:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")
    return item


@router.get("/tickets/{ticket_id}/glpi-hint", response_model=TicketGlpiHint)
def ticket_glpi_hint(ticket_id: int, _user: ConsultaUser) -> TicketGlpiHint:
    """Quando o chamado não está no SGC: consulta GLPI (só leitura) para explicar atribuição."""
    if ticket_id < 1:
        raise HTTPException(status_code=400, detail="ticket_id deve ser um inteiro >= 1.")
    try:
        return queries.get_ticket_glpi_hint(ticket_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ticket glpi-hint %s", ticket_id)
        raise HTTPException(status_code=500, detail="Erro ao consultar GLPI.") from exc


@router.post("/tickets/{ticket_id}/reassign", response_model=TicketReassignResult)
def reassign_ticket_route(
    ticket_id: int,
    body: TicketReassign,
    user: AdminUser,
) -> TicketReassignResult:
    """ADMIN: envia um chamado para outra fila (equipe) ou para uma pessoa."""
    if ticket_id < 1:
        raise HTTPException(status_code=400, detail="ticket_id deve ser um inteiro >= 1.")
    try:
        result = queries.reassign_ticket(
            get_dal(),
            ticket_id=ticket_id,
            mode=body.mode,
            equipe=body.equipe,
            tecnico=body.tecnico,
            criado_por=user.username,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ticket reassign %s by %s", ticket_id, user.username)
        raise HTTPException(status_code=500, detail="Erro ao reatribuir chamado.") from exc
    logger.info(
        "TICKET_REASSIGN by=%s id=%s mode=%s equipe=%s tecnico=%s",
        user.username,
        result.ticket_id,
        result.mode,
        result.equipe,
        result.tecnico,
    )
    return result


@router.get("/teams", response_model=List[TeamItem])
def teams(_user: ConsultaUser) -> List[TeamItem]:
    try:
        return queries.list_teams(get_dal())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("teams")
        raise HTTPException(status_code=500, detail="Erro ao listar equipes.") from exc


@router.get("/teams/guide", response_model=List[TeamGuideItem])
def teams_guide(_user: ConsultaUser) -> List[TeamGuideItem]:
    """O que cada fila faz (resumo + exemplos do arqaux) para ajudar no redirect."""
    try:
        return queries.list_teams_guide(get_dal())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("teams guide")
        raise HTTPException(status_code=500, detail="Erro ao montar guia das filas.") from exc


@router.get("/technicians", response_model=List[TechnicianItem])
def technicians(_user: ConsultaUser) -> List[TechnicianItem]:
    try:
        return queries.list_technicians(get_dal())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("technicians")
        raise HTTPException(status_code=500, detail="Erro ao listar técnicos.") from exc


@router.patch("/technicians/{usuario}", response_model=TechnicianItem)
def patch_technician(
    usuario: str,
    body: TechnicianUpdate,
    user: AdminUser,
) -> TechnicianItem:
    """Atualiza equipe/situação/matrícula (e horário/empresa) em Tb_Atrib. Somente ADMIN."""
    login = unquote(usuario or "").strip()
    if not login or len(login) > 20:
        raise HTTPException(status_code=400, detail="Usuário inválido.")
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="Informe ao menos um campo para atualizar.")
    try:
        item = queries.update_technician(get_dal(), login, **payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("technicians patch %s by %s", login, user.username)
        raise HTTPException(status_code=500, detail="Erro ao atualizar técnico.") from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Técnico não encontrado.")
    logger.info(
        "TECH_UPDATE by=%s usuario=%s fields=%s",
        user.username,
        item.usuario,
        sorted(payload.keys()),
    )
    return item


@router.post("/technicians/redirect", response_model=TechnicianRedirectResult)
def redirect_technician_route(body: TechnicianRedirect, user: AdminUser) -> TechnicianRedirectResult:
    """Redireciona login de atribuição: move tickets locais, notifica destino e opcionalmente desativa origem."""
    try:
        result = queries.redirect_technician(
            get_dal(),
            de=body.de.strip(),
            para=body.para.strip(),
            desativar_origem=body.desativar_origem,
            criado_por=user.username,
        )
    except Exception as exc:
        logger.exception("technicians redirect by %s", user.username)
        raise HTTPException(status_code=500, detail="Erro ao redirecionar técnico.") from exc
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Origem/destino inválidos (destino precisa estar ativo em Tb_Atrib).",
        )
    logger.info(
        "TECH_REDIRECT by=%s de=%s para=%s tickets=%s off=%s notif=%s",
        user.username,
        result.de,
        result.para,
        result.tickets_moved,
        result.origem_desativada,
        result.notification_created,
    )
    return result


@router.post("/technicians/sync-matriculas", response_model=MatriculaSyncResult)
def sync_matriculas_route(user: AdminUser) -> MatriculaSyncResult:
    """Sincroniza matrículas: Oracle Globus → GLPI (nome exato) → AD → mapa .env."""
    try:
        result = queries.sync_matriculas_from_map(get_dal())
    except Exception as exc:
        logger.exception("sync matriculas by %s", user.username)
        raise HTTPException(status_code=500, detail="Erro ao sincronizar matrículas.") from exc
    logger.info(
        "MATRICULA_SYNC by=%s updated=%s oracle=%s glpi=%s ad=%s map=%s skipped=%s",
        user.username,
        result.updated,
        result.from_oracle,
        result.from_glpi,
        result.from_ad,
        result.from_map,
        result.skipped,
    )
    return result


@router.post("/technicians/import-matriculas", response_model=MatriculaImportResult)
def import_matriculas_route(body: MatriculaImportBody, user: AdminUser) -> MatriculaImportResult:
    """Importa CSV usuario;matricula (ou vírgula) para Tb_Atrib.Matricula. Somente ADMIN."""
    try:
        result = queries.import_matriculas_from_csv(get_dal(), body.content)
    except Exception as exc:
        logger.exception("import matriculas by %s", user.username)
        raise HTTPException(status_code=500, detail="Erro ao importar matrículas.") from exc
    logger.info(
        "MATRICULA_IMPORT by=%s updated=%s not_found=%s invalid=%s",
        user.username,
        result.updated,
        result.not_found,
        result.invalid,
    )
    return result


@router.get("/rules", response_model=List[RuleItem])
def get_rules(_user: ConsultaUser) -> List[RuleItem]:
    """Lista regras palavra-chave → equipe [@técnico] do arqaux.txt."""
    try:
        return queries.list_assignment_rules()
    except Exception as exc:
        logger.exception("rules get")
        raise HTTPException(status_code=500, detail="Erro ao ler regras.") from exc


@router.put("/rules", response_model=List[RuleItem])
def put_rules(body: RulesPutBody, user: AdminUser) -> List[RuleItem]:
    """Substitui arqaux.txt (com backup .bak). Ordem da lista = prioridade DIRETO."""
    if len(body.rules) > 500:
        raise HTTPException(status_code=400, detail="Máximo de 500 regras.")
    for i, rule in enumerate(body.rules):
        if not rule.keywords or not any(k.strip() for k in rule.keywords):
            raise HTTPException(status_code=400, detail=f"Regra {i + 1}: informe palavras-chave.")
        if len(rule.equipe.strip()) > 5:
            raise HTTPException(status_code=400, detail=f"Regra {i + 1}: equipe inválida.")
    try:
        saved = queries.save_assignment_rules(body.rules)
    except Exception as exc:
        logger.exception("rules put by %s", user.username)
        raise HTTPException(status_code=500, detail="Erro ao gravar regras.") from exc
    logger.info("RULES_SAVE by=%s count=%s", user.username, len(saved))
    return saved


@router.get("/ml/overview", response_model=MlOverview)
def ml_overview(_user: GestorUser) -> MlOverview:
    try:
        return queries.get_ml_overview(get_dal())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ml/overview")
        raise HTTPException(status_code=500, detail="Erro ao montar overview ML.") from exc


@router.get("/ml/model-status", response_model=MlModelStatus)
def ml_model_status(_user: GestorUser) -> MlModelStatus:
    try:
        return queries.get_ml_model_status()
    except Exception as exc:
        logger.exception("ml/model-status")
        raise HTTPException(status_code=500, detail="Erro ao ler status do modelo.") from exc


@router.get("/ml/corrections", response_model=PaginatedMlCorrections)
def ml_corrections(
    _user: GestorUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    equipe_sgc: Optional[str] = Query(None, max_length=5),
    equipe_correta: Optional[str] = Query(None, max_length=5),
) -> PaginatedMlCorrections:
    try:
        return queries.list_ml_corrections(
            get_dal(),
            page=page,
            page_size=page_size,
            equipe_sgc=equipe_sgc,
            equipe_correta=equipe_correta,
        )
    except Exception as exc:
        logger.exception("ml/corrections")
        raise HTTPException(status_code=500, detail="Erro ao listar correções.") from exc


@router.get("/ml/accuracy-by-method", response_model=MlAccuracyReport)
def ml_accuracy(_user: GestorUser) -> MlAccuracyReport:
    try:
        return queries.get_ml_accuracy(get_dal())
    except Exception as exc:
        logger.exception("ml/accuracy")
        raise HTTPException(status_code=500, detail="Erro ao calcular assertividade.") from exc


@router.get("/ml/logs", response_model=PaginatedMlLogs)
def ml_logs(
    _user: GestorUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    metodo: Optional[str] = Query(None, max_length=24),
    equipe: Optional[str] = Query(None, max_length=5),
    rejeitados: bool = Query(False),
    search: Optional[str] = Query(None, max_length=100),
) -> PaginatedMlLogs:
    try:
        return queries.list_ml_logs(
            get_dal(),
            page=page,
            page_size=page_size,
            metodo=metodo,
            equipe=equipe,
            rejeitados=rejeitados,
            search=search,
        )
    except Exception as exc:
        logger.exception("ml/logs")
        raise HTTPException(status_code=500, detail="Erro ao listar log ML.") from exc


@router.post("/ml/simulate", response_model=MlSimulateResult)
def ml_simulate(_user: GestorUser, body: MlSimulateBody) -> MlSimulateResult:
    try:
        return queries.simulate_equipe_chamado(
            titulo=body.titulo,
            categoria=body.categoria,
            descricao=body.descricao,
            localizacao=body.localizacao,
        )
    except Exception as exc:
        logger.exception("ml/simulate")
        raise HTTPException(status_code=500, detail="Erro ao simular classificação.") from exc


@router.get("/jobs", response_model=JobsOverview)
def jobs(_user: OperadorUser) -> JobsOverview:
    try:
        return queries.list_jobs()
    except Exception as exc:
        logger.exception("jobs")
        raise HTTPException(status_code=500, detail="Erro ao listar jobs.") from exc


@router.get("/reports/ops", response_model=OpsPeriodReport)
def ops_period_report(
    _user: ConsultaUser,
    period: str = Query("week", description="day | week | month | custom"),
    date: Optional[str] = Query(
        None,
        description="Data de referência YYYY-MM-DD (dia / qualquer dia da semana / mês).",
    ),
    date_from: Optional[str] = Query(
        None,
        description="Início do intervalo YYYY-MM-DD (com date_to ou period=custom).",
    ),
    date_to: Optional[str] = Query(
        None,
        description="Fim do intervalo YYYY-MM-DD (inclusivo).",
    ),
    equipes: Optional[str] = Query(
        None,
        description="CSV de equipes (ex.: N1,N2,N3,DEV). Vazio = default + outras com movimento.",
    ),
    tecnico: Optional[str] = Query(
        None,
        description="Login do técnico (filtra relatório para uma pessoa).",
        max_length=40,
    ),
) -> OpsPeriodReport:
    p = (period or "week").strip().lower()
    if p not in ("day", "week", "month", "custom"):
        raise HTTPException(
            status_code=400,
            detail="period deve ser day, week, month ou custom.",
        )
    try:
        return queries.get_ops_period_report(
            get_dal(),
            period=p,
            ref_date=date,
            date_from=date_from,
            date_to=date_to,
            equipes=equipes,
            tecnico=tecnico,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("reports/ops")
        raise HTTPException(
            status_code=500, detail="Erro ao montar relatório operacional."
        ) from exc


@router.get("/reports/ops.pdf")
def ops_period_report_pdf(
    _user: ConsultaUser,
    period: str = Query("week", description="day | week | month | custom"),
    date: Optional[str] = Query(
        None,
        description="Data de referência YYYY-MM-DD (dia / qualquer dia da semana / mês).",
    ),
    date_from: Optional[str] = Query(
        None,
        description="Início do intervalo YYYY-MM-DD (com date_to ou period=custom).",
    ),
    date_to: Optional[str] = Query(
        None,
        description="Fim do intervalo YYYY-MM-DD (inclusivo).",
    ),
    equipes: Optional[str] = Query(
        None,
        description="CSV de equipes (ex.: N1,N2,N3,DEV). Vazio = default + outras com movimento.",
    ),
    tecnico: Optional[str] = Query(
        None,
        description="Login do técnico (filtra relatório para uma pessoa).",
        max_length=40,
    ),
):
    p = (period or "week").strip().lower()
    if p not in ("day", "week", "month", "custom"):
        raise HTTPException(
            status_code=400,
            detail="period deve ser day, week, month ou custom.",
        )
    try:
        path = queries.build_ops_period_pdf(
            get_dal(),
            period=p,
            ref_date=date,
            date_from=date_from,
            date_to=date_to,
            equipes=equipes,
            tecnico=tecnico,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("reports/ops.pdf")
        raise HTTPException(
            status_code=500, detail="Erro ao gerar PDF operacional."
        ) from exc
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="attachment",
    )


@router.get("/reports/ops.csv")
def ops_period_report_csv(
    _user: ConsultaUser,
    period: str = Query("week"),
    date: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    equipes: Optional[str] = Query(None),
    tecnico: Optional[str] = Query(None, max_length=40),
):
    p = (period or "week").strip().lower()
    if p not in ("day", "week", "month", "custom"):
        raise HTTPException(
            status_code=400,
            detail="period deve ser day, week, month ou custom.",
        )
    try:
        payload = queries.build_ops_period_csv(
            get_dal(),
            period=p,
            ref_date=date,
            date_from=date_from,
            date_to=date_to,
            equipes=equipes,
            tecnico=tecnico,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("reports/ops.csv")
        raise HTTPException(
            status_code=500, detail="Erro ao gerar CSV operacional."
        ) from exc
    fname = "Ops_SGC.csv"
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/reports/assertividade", response_model=List[AssertividadePdfItem])
def assertividade_pdfs(_user: ConsultaUser) -> List[AssertividadePdfItem]:
    try:
        return queries.list_assertividade_pdfs()
    except Exception as exc:
        logger.exception("reports/assertividade")
        raise HTTPException(
            status_code=500, detail="Erro ao listar PDFs de assertividade."
        ) from exc


@router.get("/reports/assertividade/{filename}")
def assertividade_pdf_download(_user: ConsultaUser, filename: str):
    path = queries.assertividade_pdf_path(unquote(filename))
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="attachment",
    )


@router.get("/reports/weekly-teams", response_model=WeeklyTeamReport)
def weekly_teams_report(
    _user: ConsultaUser,
    week_start: Optional[str] = Query(
        None,
        description="Qualquer data da semana (YYYY-MM-DD); usa a segunda-feira da semana.",
    ),
    equipes: Optional[str] = Query(
        None,
        description="CSV de equipes (ex.: N1,N2,N3,DEV). Default: N1,N2,N3,DEV + outras com movimento.",
    ),
    tecnico: Optional[str] = Query(None, max_length=40),
) -> WeeklyTeamReport:
    try:
        return queries.get_weekly_team_report(
            get_dal(), week_start=week_start, equipes=equipes, tecnico=tecnico
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("reports/weekly-teams")
        raise HTTPException(
            status_code=500, detail="Erro ao montar relatório semanal."
        ) from exc


@router.get("/notifications", response_model=NotificationList)
def notifications_list(
    user: ConsultaUser,
    unread_only: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
) -> NotificationList:
    try:
        return notif_svc.list_notifications(
            get_dal(), user.username, unread_only=unread_only, limit=limit
        )
    except Exception as exc:
        logger.exception("notifications list")
        raise HTTPException(status_code=500, detail="Erro ao listar notificações.") from exc


@router.get("/notifications/unread-count", response_model=NotificationUnreadCount)
def notifications_unread(user: ConsultaUser) -> NotificationUnreadCount:
    try:
        return notif_svc.unread_count(get_dal(), user.username)
    except Exception as exc:
        logger.exception("notifications unread")
        raise HTTPException(status_code=500, detail="Erro ao contar notificações.") from exc


@router.post("/notifications/{notif_id}/read", response_model=NotificationItem)
def notification_mark_read(notif_id: int, user: ConsultaUser) -> NotificationItem:
    try:
        ok = notif_svc.mark_read(get_dal(), user.username, notif_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Notificação não encontrada.")
        items = notif_svc.list_notifications(get_dal(), user.username, limit=100).items
        for it in items:
            if it.id == notif_id:
                return it
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("notification read")
        raise HTTPException(status_code=500, detail="Erro ao marcar notificação.") from exc


@router.post("/notifications/read-all", response_model=NotificationUnreadCount)
def notifications_read_all(user: ConsultaUser) -> NotificationUnreadCount:
    try:
        notif_svc.mark_all_read(get_dal(), user.username)
        return notif_svc.unread_count(get_dal(), user.username)
    except Exception as exc:
        logger.exception("notifications read-all")
        raise HTTPException(status_code=500, detail="Erro ao marcar notificações.") from exc
