"""Schemas Pydantic — respostas somente leitura (contrato estável com o frontend)."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Códigos gravados pelo worker em Tb_ML_Log.Metodo
DecisionMethod = Literal[
    "DIRETO",
    "FALLBACK_PARCIAL",
    "ML",
    "FALLBACK_CATEGORIA",
    "FALLBACK_N1",
    "SEM_EQUIPE",
]


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
    worker_updated_at: Optional[str] = None
    worker_age_seconds: Optional[int] = None
    worker_alive: Optional[bool] = None
    worker_glpi_ok: Optional[bool] = None
    worker_last_error: Optional[str] = None


class DashboardSummary(BaseModel):
    tickets_total: Optional[int] = None
    tickets_today: Optional[int] = None
    technicians_active: Optional[int] = None
    teams_total: Optional[int] = None
    ml_log_total: Optional[int] = None
    corrections_total: Optional[int] = None
    feedback_total: Optional[int] = None
    latest_performance: Optional[float] = None
    latest_performance_date: Optional[str] = None
    tickets_by_team: Dict[str, int] = Field(default_factory=dict)
    tickets_today_by_team: Dict[str, int] = Field(default_factory=dict)
    ml_by_method: Dict[str, int] = Field(default_factory=dict)
    glpi_novos: Optional[int] = None
    skips_sem_tecnico_hoje: Optional[int] = None
    worker_updated_at: Optional[str] = None
    worker_age_seconds: Optional[int] = None
    worker_alive: Optional[bool] = None
    worker_glpi_ok: Optional[bool] = None
    worker_last_error: Optional[str] = None
    last_assigned_id: Optional[int] = None
    last_assigned_in_sgc: Optional[bool] = None
    last_skip_id: Optional[int] = None
    last_skip_in_sgc: Optional[bool] = None


class MlLogEntry(BaseModel):
    """Contrato normalizado (snake_case) para Tb_ML_Log."""

    idml: Optional[int] = None
    id_glpi: Optional[int] = None
    metodo: Optional[str] = None
    equipe_prevista: Optional[str] = None
    equipe_ml: Optional[str] = None
    equipe_2a: Optional[str] = None
    confianca: Optional[float] = None
    margem: Optional[float] = None
    motivo_rejeicao: Optional[str] = None
    motivo_atrib: Optional[str] = None
    categoria: Optional[str] = None
    localizacao: Optional[str] = None
    data_registro: Optional[str] = None


class TicketListItem(BaseModel):
    id: Optional[int] = None
    titulo: Optional[str] = None
    categoria: Optional[str] = None
    tecnico: Optional[str] = None
    equipe: Optional[str] = None
    sit: Optional[str] = None
    solicitante: Optional[str] = None
    data: Optional[str] = None
    dat_sol: Optional[str] = None
    metodo: Optional[str] = None
    status_label: Optional[str] = None
    data_mod: Optional[str] = None
    fonte: Optional[Literal["sgc", "glpi"]] = None


class TicketDetail(TicketListItem):
    descricao: Optional[str] = None
    ml_log: Optional[MlLogEntry] = None
    explicacao: Optional["AssignmentExplanation"] = None


class AssignmentExplanation(BaseModel):
    """Texto claro: por que este chamado foi para esta equipe/pessoa."""

    metodo: Optional[str] = None
    metodo_label: str = ""
    equipe: Optional[str] = None
    tecnico: Optional[str] = None
    keywords_matched: List[str] = Field(default_factory=list)
    motivo_resumo: str = ""
    motivo_pessoa: Optional[str] = None
    equipe_2a: Optional[str] = None
    confianca: Optional[float] = None
    motivo_rejeicao: Optional[str] = None


class TicketGlpiHint(BaseModel):
    """Quando o chamado não está no SGC: leitura só do GLPI."""

    ticket_id: int
    encontrado: bool = False
    titulo: Optional[str] = None
    status: Optional[int] = None
    status_label: Optional[str] = None
    tecnico: Optional[str] = None
    mensagem: str = ""


class TeamGuideItem(BaseModel):
    equipe: str
    resumo: str
    exemplos: List[str] = Field(default_factory=list)
    tecnicos_ativos: int = 0
    technicians_total: int = 0
    carga_total: int = 0


class PaginatedTickets(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[TicketListItem]
    fonte: Optional[Literal["sgc", "glpi"]] = None


class TeamItem(BaseModel):
    equipe: str
    technicians_total: int
    technicians_active: int
    carga_total: int


class TechnicianItem(BaseModel):
    usuario: str
    equipe: Optional[str] = None
    qtdc: Optional[int] = None
    sit: Optional[str] = None
    h1: Optional[str] = None
    h2: Optional[str] = None
    empresa: Optional[str] = None
    matricula: Optional[str] = None


class TechnicianUpdate(BaseModel):
    """Campos editáveis de Tb_Atrib (ADMIN). Atualiza todas as linhas do mesmo Usuario."""

    equipe: Optional[str] = Field(None, min_length=1, max_length=5)
    sit: Optional[str] = Field(None, pattern=r"^[01]$")
    matricula: Optional[str] = Field(None, max_length=10)
    h1: Optional[str] = Field(None, max_length=10)
    h2: Optional[str] = Field(None, max_length=10)
    empresa: Optional[str] = Field(None, max_length=25)

    model_config = {"extra": "forbid"}


class TechnicianRedirect(BaseModel):
    de: str = Field(..., min_length=1, max_length=20)
    para: str = Field(..., min_length=1, max_length=20)
    desativar_origem: bool = True

    model_config = {"extra": "forbid"}


class MatriculaSyncResult(BaseModel):
    updated: int = 0
    skipped: int = 0
    from_oracle: int = 0
    from_glpi: int = 0
    from_ad: int = 0
    from_map: int = 0
    details: List[str] = Field(default_factory=list)


class MatriculaImportBody(BaseModel):
    """Texto CSV: uma linha por técnico (usuario;matricula ou usuario,matricula)."""

    content: str = Field(..., min_length=1, max_length=500_000)

    model_config = {"extra": "forbid"}


class MatriculaImportResult(BaseModel):
    updated: int = 0
    not_found: int = 0
    invalid: int = 0
    details: List[str] = Field(default_factory=list)


class TechnicianRedirectResult(BaseModel):
    de: str
    para: str
    tickets_moved: int = 0
    origem_desativada: bool = False
    notification_created: bool = False
    glpi_ok_ids: List[int] = Field(default_factory=list)
    glpi_failed_ids: List[int] = Field(default_factory=list)


class TicketReassign(BaseModel):
    """Reatribui um chamado: fila (equipe) ou pessoa específica."""

    mode: Literal["equipe", "pessoa"]
    equipe: Optional[str] = Field(None, min_length=1, max_length=5)
    tecnico: Optional[str] = Field(None, min_length=1, max_length=20)

    model_config = {"extra": "forbid"}


class TicketReassignResult(BaseModel):
    ticket_id: int
    mode: str
    equipe: Optional[str] = None
    tecnico: str
    tecnico_anterior: Optional[str] = None
    equipe_anterior: Optional[str] = None
    glpi_ok: bool = False
    sgc_ok: bool = False
    notification_created: bool = False
    notification_admin: bool = False
    message: str = ""


class NotificationItem(BaseModel):
    id: int
    tipo: str
    titulo: str
    mensagem: str
    ref_ids: List[int] = Field(default_factory=list)
    lida: bool = False
    criado_por: Optional[str] = None
    criado_em: Optional[str] = None


class NotificationList(BaseModel):
    items: List[NotificationItem]
    unread: int = 0


class NotificationUnreadCount(BaseModel):
    unread: int = 0


class RuleItem(BaseModel):
    equipe: str = Field(..., min_length=1, max_length=5)
    keywords: List[str] = Field(..., min_length=1)
    tecnico: Optional[str] = Field(None, max_length=40)

    model_config = {"extra": "forbid"}


class RulesPutBody(BaseModel):
    rules: List[RuleItem]

    model_config = {"extra": "forbid"}


class MlOverview(BaseModel):
    total_logs: Optional[int] = None
    by_method: Dict[str, int] = Field(default_factory=dict)
    avg_confidence: Optional[float] = None
    avg_margin: Optional[float] = None
    recent: List[MlLogEntry] = Field(default_factory=list)


class MlModelVersionItem(BaseModel):
    arquivo: str
    data: Optional[str] = None
    f1_macro: Optional[float] = None
    version: Optional[int] = None
    train_samples: Optional[int] = None


class MlModelStatus(BaseModel):
    """Somente leitura: ModeloML.pkl + metrics.json. Sem treino nem rollback."""

    model_exists: bool = False
    model_mtime: Optional[str] = None
    model_size: Optional[int] = None
    ativo: Optional[str] = None
    f1_macro: Optional[float] = None
    version: Optional[int] = None
    train_samples: Optional[int] = None
    implantado_em: Optional[str] = None
    versoes: List[MlModelVersionItem] = Field(default_factory=list)


class MlCorrectionItem(BaseModel):
    idcor: Optional[int] = None
    id_glpi: Optional[int] = None
    titulo: Optional[str] = None
    categoria: Optional[str] = None
    equipe_sgc: Optional[str] = None
    equipe_correta: Optional[str] = None
    tecnico_fechamento: Optional[str] = None
    data_deteccao: Optional[str] = None


class PaginatedMlCorrections(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[MlCorrectionItem]


class MethodAccuracyItem(BaseModel):
    metodo: str
    avaliados: int = 0
    acertos: int = 0
    erros: int = 0
    taxa_pct: Optional[float] = None


class ErrorPairItem(BaseModel):
    equipe_sgc: str
    equipe_correta: str
    quantidade: int = 0


class MlAccuracyReport(BaseModel):
    avaliados: int = 0
    acertos: int = 0
    erros: int = 0
    taxa_pct: Optional[float] = None
    by_method: List[MethodAccuracyItem] = Field(default_factory=list)
    error_pairs: List[ErrorPairItem] = Field(default_factory=list)


class PaginatedMlLogs(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[MlLogEntry]


class MlSimulateBody(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=500)
    categoria: Optional[str] = Field(None, max_length=500)
    descricao: Optional[str] = Field(None, max_length=4000)
    localizacao: Optional[str] = Field(None, max_length=500)

    model_config = {"extra": "forbid"}


class MlSimulateResult(BaseModel):
    equipe: Optional[str] = None
    metodo: Optional[str] = None
    equipe_ml: Optional[str] = None
    equipe_2a: Optional[str] = None
    confianca: Optional[float] = None
    margem: Optional[float] = None
    motivo_rejeicao: Optional[str] = None
    tecnico_fixo: Optional[str] = None
    tecnicos_elegiveis: List[str] = Field(default_factory=list)
    modelo_carregado: bool = False


class JobItem(BaseModel):
    id: str
    name: str
    description: str
    schedule: str
    enabled: bool  # compat: processo vivo (heartbeat)
    process_alive: Optional[bool] = None
    agenda_enabled: Optional[bool] = None
    source: str = "agendador_sgc"
    last_run_at: Optional[str] = None
    last_ok: Optional[bool] = None
    last_message: Optional[str] = None
    next_run_at: Optional[str] = None


class JobsOverview(BaseModel):
    worker_alive: Optional[bool] = None
    scheduler_alive: Optional[bool] = None
    scheduler_enabled: bool = True
    worker_updated_at: Optional[str] = None
    scheduler_updated_at: Optional[str] = None
    jobs: List[JobItem] = Field(default_factory=list)


class WeeklyPersonStats(BaseModel):
    tecnico: str
    matricula: Optional[str] = None
    atribuidos: int = 0
    fechados: int = 0
    abertos: int = 0
    tempo_medio_horas: Optional[float] = None


class WeeklyTeamStats(BaseModel):
    equipe: str
    atribuidos: int = 0
    fechados: int = 0
    abertos: int = 0
    backlog_ativo: int = 0
    tempo_medio_horas: Optional[float] = None
    por_tecnico: List[WeeklyPersonStats] = Field(default_factory=list)


class NameCountItem(BaseModel):
    nome: str
    qtd: int = 0


class RankPersonItem(BaseModel):
    tecnico: str
    equipe: str
    matricula: Optional[str] = None
    fechados: int = 0
    atribuidos: int = 0
    tempo_medio_horas: Optional[float] = None


class OpsPeriodComparison(BaseModel):
    """Totais do intervalo imediatamente anterior (mesmo número de dias)."""

    period_start: str
    period_end: str
    label: str
    atribuidos: int = 0
    fechados: int = 0
    tempo_medio_horas: Optional[float] = None


class DailySeriesItem(BaseModel):
    data: str
    atribuidos: int = 0
    fechados: int = 0


class TempoFaixaItem(BaseModel):
    faixa: str
    qtd: int = 0


class WeeklyTeamReport(BaseModel):
    """Compatível com o relatório semanal antigo."""

    week_start: str
    week_end: str
    label: str
    focus_teams: List[str] = Field(default_factory=list)
    teams: List[WeeklyTeamStats] = Field(default_factory=list)
    totals: WeeklyTeamStats
    notes: List[str] = Field(default_factory=list)


class OpsPeriodReport(BaseModel):
    period: Literal["day", "week", "month", "custom"]
    period_start: str
    period_end: str
    label: str
    focus_teams: List[str] = Field(default_factory=list)
    filtro_tecnico: Optional[str] = None
    teams: List[WeeklyTeamStats] = Field(default_factory=list)
    totals: WeeklyTeamStats
    rank_fechou_mais: List[RankPersonItem] = Field(default_factory=list)
    rank_fechou_menos: List[RankPersonItem] = Field(default_factory=list)
    top_solicitantes: List[NameCountItem] = Field(default_factory=list)
    top_localizacoes: List[NameCountItem] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    comparacao: Optional[OpsPeriodComparison] = None
    serie_diaria: List[DailySeriesItem] = Field(default_factory=list)
    tempo_faixas: List[TempoFaixaItem] = Field(default_factory=list)
    # aliases úteis na UI / weekly
    week_start: Optional[str] = None
    week_end: Optional[str] = None


class AssertividadePdfItem(BaseModel):
    filename: str
    size: int = 0
    modified: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
