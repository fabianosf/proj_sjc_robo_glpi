/** Tipos alinhados aos schemas Pydantic da API (`backend/app/schemas.py`). */

export type HealthResponse = {
  status: string
  database: string
  version: string
  worker_updated_at: string | null
  worker_age_seconds: number | null
  worker_alive: boolean | null
  worker_glpi_ok: boolean | null
  worker_last_error: string | null
}

export type DashboardSummary = {
  tickets_total: number | null
  tickets_today: number | null
  technicians_active: number | null
  teams_total: number | null
  ml_log_total: number | null
  corrections_total: number | null
  feedback_total: number | null
  latest_performance: number | null
  latest_performance_date: string | null
  tickets_by_team: Record<string, number>
  tickets_today_by_team: Record<string, number>
  ml_by_method: Record<string, number>
  glpi_novos: number | null
  skips_sem_tecnico_hoje: number | null
  worker_updated_at: string | null
  worker_age_seconds: number | null
  worker_alive: boolean | null
  worker_glpi_ok: boolean | null
  worker_last_error: string | null
  last_assigned_id: number | null
  last_assigned_in_sgc: boolean | null
  last_skip_id: number | null
  last_skip_in_sgc: boolean | null
}

/** Códigos gravados em Tb_ML_Log.Metodo (API). */
export type DecisionMethod =
  | 'DIRETO'
  | 'FALLBACK_PARCIAL'
  | 'ML'
  | 'FALLBACK_CATEGORIA'
  | 'FALLBACK_N1'
  | 'SEM_EQUIPE'
  | string

export type MlLogEntry = {
  idml: number | null
  id_glpi: number | null
  metodo: string | null
  equipe_prevista: string | null
  equipe_ml: string | null
  equipe_2a: string | null
  confianca: number | null
  margem: number | null
  motivo_rejeicao: string | null
  motivo_atrib?: string | null
  categoria: string | null
  localizacao: string | null
  data_registro: string | null
}

export type TicketListItem = {
  id: number | null
  titulo: string | null
  categoria: string | null
  tecnico: string | null
  equipe: string | null
  sit: string | null
  solicitante: string | null
  /** ISO 8601 (`YYYY-MM-DDTHH:mm:ss`) ou null */
  data: string | null
  dat_sol: string | null
  /** Último método de decisão (Tb_ML_Log); null se inexistente */
  metodo: string | null
  status_label: string | null
  data_mod: string | null
  fonte: 'sgc' | 'glpi' | null
}

export type TicketDetail = TicketListItem & {
  descricao: string | null
  ml_log: MlLogEntry | null
  explicacao?: AssignmentExplanation | null
}

export type AssignmentExplanation = {
  metodo: string | null
  metodo_label: string
  equipe: string | null
  tecnico: string | null
  keywords_matched: string[]
  motivo_resumo: string
  motivo_pessoa?: string | null
  equipe_2a: string | null
  confianca: number | null
  motivo_rejeicao: string | null
}

export type TicketGlpiHint = {
  ticket_id: number
  encontrado: boolean
  titulo: string | null
  status: number | null
  status_label: string | null
  tecnico: string | null
  mensagem: string
}

export type TeamGuideItem = {
  equipe: string
  resumo: string
  exemplos: string[]
  tecnicos_ativos: number
  technicians_total: number
  carga_total: number
}

export type PaginatedTickets = {
  page: number
  page_size: number
  total: number
  items: TicketListItem[]
  fonte: 'sgc' | 'glpi' | null
}

export type TeamItem = {
  equipe: string
  technicians_total: number
  technicians_active: number
  carga_total: number
}

export type TechnicianItem = {
  usuario: string
  equipe: string | null
  qtdc: number | null
  sit: string | null
  h1: string | null
  h2: string | null
  empresa: string | null
  matricula: string | null
}

export type TechnicianRedirectResult = {
  de: string
  para: string
  tickets_moved: number
  origem_desativada: boolean
  notification_created: boolean
  glpi_ok_ids?: number[]
  glpi_failed_ids?: number[]
}

export type TicketReassignResult = {
  ticket_id: number
  mode: string
  equipe: string | null
  tecnico: string
  tecnico_anterior?: string | null
  equipe_anterior?: string | null
  glpi_ok: boolean
  sgc_ok?: boolean
  notification_created: boolean
  notification_admin?: boolean
  message: string
}

export type NotificationItem = {
  id: number
  tipo: string
  titulo: string
  mensagem: string
  ref_ids: number[]
  lida: boolean
  criado_por: string | null
  criado_em: string | null
}

export type NotificationList = {
  items: NotificationItem[]
  unread: number
}

export type NotificationUnreadCount = {
  unread: number
}

export type MatriculaSyncResult = {
  updated: number
  skipped: number
  from_oracle: number
  from_glpi: number
  from_ad: number
  from_map: number
  details: string[]
}

export type MatriculaImportResult = {
  updated: number
  not_found: number
  invalid: number
  details: string[]
}

export type RuleItem = {
  equipe: string
  keywords: string[]
  tecnico: string | null
}

export type MlOverview = {
  total_logs: number | null
  by_method: Record<string, number>
  avg_confidence: number | null
  avg_margin: number | null
  recent: MlLogEntry[]
}

export type MlModelVersionItem = {
  arquivo: string
  data: string | null
  f1_macro: number | null
  version: number | null
  train_samples: number | null
}

export type MlModelStatus = {
  model_exists: boolean
  model_mtime: string | null
  model_size: number | null
  ativo: string | null
  f1_macro: number | null
  version: number | null
  train_samples: number | null
  implantado_em: string | null
  versoes: MlModelVersionItem[]
}

export type MlCorrectionItem = {
  idcor: number | null
  id_glpi: number | null
  titulo: string | null
  categoria: string | null
  equipe_sgc: string | null
  equipe_correta: string | null
  tecnico_fechamento: string | null
  data_deteccao: string | null
}

export type PaginatedMlCorrections = {
  page: number
  page_size: number
  total: number
  items: MlCorrectionItem[]
}

export type MethodAccuracyItem = {
  metodo: string
  avaliados: number
  acertos: number
  erros: number
  taxa_pct: number | null
}

export type ErrorPairItem = {
  equipe_sgc: string
  equipe_correta: string
  quantidade: number
}

export type MlAccuracyReport = {
  avaliados: number
  acertos: number
  erros: number
  taxa_pct: number | null
  by_method: MethodAccuracyItem[]
  error_pairs: ErrorPairItem[]
}

export type PaginatedMlLogs = {
  page: number
  page_size: number
  total: number
  items: MlLogEntry[]
}

export type MlSimulateResult = {
  equipe: string | null
  metodo: string | null
  equipe_ml: string | null
  equipe_2a: string | null
  confianca: number | null
  margem: number | null
  motivo_rejeicao: string | null
  tecnico_fixo: string | null
  tecnicos_elegiveis: string[]
  modelo_carregado: boolean
}

export type JobItem = {
  id: string
  name: string
  description: string
  schedule: string
  enabled: boolean
  process_alive?: boolean | null
  agenda_enabled?: boolean | null
  source: string
  last_run_at: string | null
  last_ok: boolean | null
  last_message: string | null
  next_run_at: string | null
}

export type JobsOverview = {
  worker_alive: boolean | null
  scheduler_alive: boolean | null
  scheduler_enabled: boolean
  worker_updated_at: string | null
  scheduler_updated_at: string | null
  jobs: JobItem[]
}

export type WeeklyPersonStats = {
  tecnico: string
  matricula: string | null
  atribuidos: number
  fechados: number
  abertos: number
  tempo_medio_horas: number | null
}

export type WeeklyTeamStats = {
  equipe: string
  atribuidos: number
  fechados: number
  abertos: number
  backlog_ativo: number
  tempo_medio_horas: number | null
  por_tecnico: WeeklyPersonStats[]
}

export type WeeklyTeamReport = {
  week_start: string
  week_end: string
  label: string
  focus_teams: string[]
  teams: WeeklyTeamStats[]
  totals: WeeklyTeamStats
  notes: string[]
}

export type NameCountItem = {
  nome: string
  qtd: number
}

export type RankPersonItem = {
  tecnico: string
  equipe: string
  matricula: string | null
  fechados: number
  atribuidos: number
  tempo_medio_horas: number | null
}

export type OpsPeriod = 'day' | 'week' | 'month' | 'custom'

export type OpsPeriodComparison = {
  period_start: string
  period_end: string
  label: string
  atribuidos: number
  fechados: number
  tempo_medio_horas: number | null
}

export type DailySeriesItem = {
  data: string
  atribuidos: number
  fechados: number
}

export type TempoFaixaItem = {
  faixa: string
  qtd: number
}

export type OpsPeriodReport = {
  period: OpsPeriod
  period_start: string
  period_end: string
  label: string
  focus_teams: string[]
  filtro_tecnico: string | null
  teams: WeeklyTeamStats[]
  totals: WeeklyTeamStats
  rank_fechou_mais: RankPersonItem[]
  rank_fechou_menos: RankPersonItem[]
  top_solicitantes: NameCountItem[]
  top_localizacoes: NameCountItem[]
  notes: string[]
  comparacao: OpsPeriodComparison | null
  serie_diaria: DailySeriesItem[]
  tempo_faixas: TempoFaixaItem[]
  week_start: string | null
  week_end: string | null
}

export type AssertividadePdfItem = {
  filename: string
  size: number
  modified: string | null
}

export type Profile = 'ADMIN' | 'GESTOR' | 'OPERADOR' | 'CONSULTA'

export type UserPublic = {
  id: number
  username: string
  nome: string | null
  perfil: Profile
  ativo: boolean
}

export type TokenResponse = {
  access_token: string
  token_type: string
  expires_in_minutes: number
  user: UserPublic
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}
