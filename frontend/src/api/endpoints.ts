import { apiGet, apiGetBlob, apiPatch, apiPost, apiPut, apiRequest } from './client'
import type {
  DashboardSummary,
  HealthResponse,
  JobsOverview,
  MatriculaImportResult,
  MatriculaSyncResult,
  MlAccuracyReport,
  MlModelStatus,
  MlOverview,
  MlSimulateResult,
  PaginatedMlCorrections,
  PaginatedMlLogs,
  NotificationItem,
  NotificationList,
  NotificationUnreadCount,
  PaginatedTickets,
  RuleItem,
  TeamGuideItem,
  TeamItem,
  TechnicianItem,
  TechnicianRedirectResult,
  TicketDetail,
  TicketGlpiHint,
  TicketReassignResult,
  TokenResponse,
  UserPublic,
  WeeklyTeamReport,
  AssertividadePdfItem,
  OpsPeriod,
  OpsPeriodReport,
} from './types'

export const fetchHealth = (signal?: AbortSignal) =>
  apiRequest<HealthResponse>('/health', { method: 'GET', signal, auth: false })

export const loginRequest = (username: string, password: string, signal?: AbortSignal) =>
  apiPost<TokenResponse>(
    '/api/v1/auth/login',
    { username, password },
    { signal, auth: false },
  )

export const logoutRequest = (signal?: AbortSignal) =>
  apiPost<{ detail: string }>('/api/v1/auth/logout', {}, { signal, auth: true })

export const fetchMe = (signal?: AbortSignal) =>
  apiGet<UserPublic>('/api/v1/auth/me', signal)

export const fetchDashboardSummary = (signal?: AbortSignal) =>
  apiGet<DashboardSummary>('/api/v1/dashboard/summary', signal)

export const fetchTickets = (
  params: { page: number; pageSize: number; search?: string; source?: 'sgc' | 'glpi' },
  signal?: AbortSignal,
) => {
  const qs = new URLSearchParams({
    page: String(params.page),
    page_size: String(params.pageSize),
  })
  if (params.search?.trim()) qs.set('search', params.search.trim())
  const path =
    params.source === 'glpi' ? `/api/v1/tickets/glpi?${qs}` : `/api/v1/tickets?${qs}`
  return apiGet<PaginatedTickets>(path, signal)
}

export const fetchTicket = (id: number, signal?: AbortSignal) =>
  apiGet<TicketDetail>(`/api/v1/tickets/${id}`, signal)

export const fetchTicketGlpiHint = (id: number, signal?: AbortSignal) =>
  apiGet<TicketGlpiHint>(`/api/v1/tickets/${id}/glpi-hint`, signal)

export const reassignTicket = (
  id: number,
  body: { mode: 'equipe' | 'pessoa'; equipe?: string; tecnico?: string },
  signal?: AbortSignal,
) =>
  apiPost<TicketReassignResult>(`/api/v1/tickets/${id}/reassign`, body, { signal })

export const fetchTeams = (signal?: AbortSignal) =>
  apiGet<TeamItem[]>('/api/v1/teams', signal)

export const fetchTeamsGuide = (signal?: AbortSignal) =>
  apiGet<TeamGuideItem[]>('/api/v1/teams/guide', signal)

export const fetchTechnicians = (signal?: AbortSignal) =>
  apiGet<TechnicianItem[]>('/api/v1/technicians', signal)

export const updateTechnician = (
  usuario: string,
  body: {
    equipe?: string
    sit?: string
    matricula?: string
    h1?: string
    h2?: string
    empresa?: string
  },
  signal?: AbortSignal,
) =>
  apiPatch<TechnicianItem>(
    `/api/v1/technicians/${encodeURIComponent(usuario)}`,
    body,
    { signal },
  )

export const redirectTechnician = (
  body: { de: string; para: string; desativar_origem?: boolean },
  signal?: AbortSignal,
) =>
  apiPost<TechnicianRedirectResult>('/api/v1/technicians/redirect', body, { signal })

export const syncMatriculas = (signal?: AbortSignal) =>
  apiPost<MatriculaSyncResult>('/api/v1/technicians/sync-matriculas', {}, { signal })

export const importMatriculasCsv = (content: string, signal?: AbortSignal) =>
  apiPost<MatriculaImportResult>(
    '/api/v1/technicians/import-matriculas',
    { content },
    { signal },
  )

export const fetchRules = (signal?: AbortSignal) =>
  apiGet<RuleItem[]>('/api/v1/rules', signal)

export const saveRules = (rules: RuleItem[], signal?: AbortSignal) =>
  apiPut<RuleItem[]>('/api/v1/rules', { rules }, { signal })

export const fetchMlOverview = (signal?: AbortSignal) =>
  apiGet<MlOverview>('/api/v1/ml/overview', signal)

export const fetchMlModelStatus = (signal?: AbortSignal) =>
  apiGet<MlModelStatus>('/api/v1/ml/model-status', signal)

export const fetchMlCorrections = (
  params: {
    page: number
    pageSize: number
    equipeSgc?: string
    equipeCorreta?: string
  },
  signal?: AbortSignal,
) => {
  const qs = new URLSearchParams({
    page: String(params.page),
    page_size: String(params.pageSize),
  })
  if (params.equipeSgc?.trim()) qs.set('equipe_sgc', params.equipeSgc.trim())
  if (params.equipeCorreta?.trim()) qs.set('equipe_correta', params.equipeCorreta.trim())
  return apiGet<PaginatedMlCorrections>(`/api/v1/ml/corrections?${qs}`, signal)
}

export const fetchMlAccuracy = (signal?: AbortSignal) =>
  apiGet<MlAccuracyReport>('/api/v1/ml/accuracy-by-method', signal)

export const fetchMlLogs = (
  params: {
    page: number
    pageSize: number
    metodo?: string
    equipe?: string
    rejeitados?: boolean
    search?: string
  },
  signal?: AbortSignal,
) => {
  const qs = new URLSearchParams({
    page: String(params.page),
    page_size: String(params.pageSize),
  })
  if (params.metodo?.trim()) qs.set('metodo', params.metodo.trim())
  if (params.equipe?.trim()) qs.set('equipe', params.equipe.trim())
  if (params.rejeitados) qs.set('rejeitados', 'true')
  if (params.search?.trim()) qs.set('search', params.search.trim())
  return apiGet<PaginatedMlLogs>(`/api/v1/ml/logs?${qs}`, signal)
}

export const simulateMl = (
  body: { titulo: string; categoria?: string; descricao?: string; localizacao?: string },
  signal?: AbortSignal,
) => apiPost<MlSimulateResult>('/api/v1/ml/simulate', body, { signal })

export const fetchJobs = (signal?: AbortSignal) =>
  apiGet<JobsOverview>('/api/v1/jobs', signal)

export const fetchWeeklyTeamReport = (
  params?: { weekStart?: string; equipes?: string; tecnico?: string },
  signal?: AbortSignal,
) => {
  const qs = new URLSearchParams()
  if (params?.weekStart) qs.set('week_start', params.weekStart)
  if (params?.equipes) qs.set('equipes', params.equipes)
  if (params?.tecnico) qs.set('tecnico', params.tecnico)
  const q = qs.toString()
  return apiGet<WeeklyTeamReport>(
    `/api/v1/reports/weekly-teams${q ? `?${q}` : ''}`,
    signal,
  )
}

export const fetchOpsPeriodReport = (
  params?: {
    period?: OpsPeriod
    date?: string
    dateFrom?: string
    dateTo?: string
    equipes?: string
    tecnico?: string
  },
  signal?: AbortSignal,
) => {
  const qs = new URLSearchParams()
  if (params?.period) qs.set('period', params.period)
  if (params?.date) qs.set('date', params.date)
  if (params?.dateFrom) qs.set('date_from', params.dateFrom)
  if (params?.dateTo) qs.set('date_to', params.dateTo)
  if (params?.equipes) qs.set('equipes', params.equipes)
  if (params?.tecnico) qs.set('tecnico', params.tecnico)
  const q = qs.toString()
  return apiGet<OpsPeriodReport>(`/api/v1/reports/ops${q ? `?${q}` : ''}`, signal)
}

function opsReportQuery(params?: {
  period?: OpsPeriod
  date?: string
  dateFrom?: string
  dateTo?: string
  equipes?: string
  tecnico?: string
}): string {
  const qs = new URLSearchParams()
  if (params?.period) qs.set('period', params.period)
  if (params?.date) qs.set('date', params.date)
  if (params?.dateFrom) qs.set('date_from', params.dateFrom)
  if (params?.dateTo) qs.set('date_to', params.dateTo)
  if (params?.equipes) qs.set('equipes', params.equipes)
  if (params?.tecnico) qs.set('tecnico', params.tecnico)
  const q = qs.toString()
  return q ? `?${q}` : ''
}

async function triggerBlobDownload(path: string, fallback: string, signal?: AbortSignal) {
  const { blob, filename } = await apiGetBlob(path, fallback, signal)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const downloadOpsPeriodPdf = async (
  params?: {
    period?: OpsPeriod
    date?: string
    dateFrom?: string
    dateTo?: string
    equipes?: string
    tecnico?: string
  },
  signal?: AbortSignal,
) => {
  await triggerBlobDownload(
    `/api/v1/reports/ops.pdf${opsReportQuery(params)}`,
    'Ops_SGC.pdf',
    signal,
  )
}

export const downloadOpsPeriodCsv = async (
  params?: {
    period?: OpsPeriod
    date?: string
    dateFrom?: string
    dateTo?: string
    equipes?: string
    tecnico?: string
  },
  signal?: AbortSignal,
) => {
  await triggerBlobDownload(
    `/api/v1/reports/ops.csv${opsReportQuery(params)}`,
    'Ops_SGC.csv',
    signal,
  )
}

export const fetchAssertividadePdfs = (signal?: AbortSignal) =>
  apiGet<AssertividadePdfItem[]>('/api/v1/reports/assertividade', signal)

export const downloadAssertividadePdf = async (filename: string, signal?: AbortSignal) => {
  await triggerBlobDownload(
    `/api/v1/reports/assertividade/${encodeURIComponent(filename)}`,
    filename,
    signal,
  )
}

export const fetchNotifications = (
  params?: { unreadOnly?: boolean; limit?: number },
  signal?: AbortSignal,
) => {
  const qs = new URLSearchParams()
  if (params?.unreadOnly) qs.set('unread_only', 'true')
  if (params?.limit) qs.set('limit', String(params.limit))
  const q = qs.toString()
  return apiGet<NotificationList>(`/api/v1/notifications${q ? `?${q}` : ''}`, signal)
}

export const fetchNotificationsUnread = (signal?: AbortSignal) =>
  apiGet<NotificationUnreadCount>('/api/v1/notifications/unread-count', signal)

export const markNotificationRead = (id: number, signal?: AbortSignal) =>
  apiPost<NotificationItem>(`/api/v1/notifications/${id}/read`, {}, { signal })

export const markAllNotificationsRead = (signal?: AbortSignal) =>
  apiPost<NotificationUnreadCount>('/api/v1/notifications/read-all', {}, { signal })
