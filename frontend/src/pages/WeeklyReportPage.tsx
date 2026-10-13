import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CheckCircle2, ClipboardList, Clock, Download, FileSpreadsheet, Percent, Ticket, Users } from 'lucide-react'
import {
  downloadAssertividadePdf,
  downloadOpsPeriodCsv,
  downloadOpsPeriodPdf,
  fetchAssertividadePdfs,
  fetchOpsPeriodReport,
  fetchTechnicians,
} from '../api/endpoints'
import { displayBytes, displayDate, displayNumber, displayValue } from '../lib/format'
import type { OpsPeriod } from '../api/types'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { StatCard } from '../components/ui/StatCard'

function todayIso(): string {
  return toIso(new Date())
}

function toIso(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

function parseIso(iso: string): Date {
  return new Date(`${iso}T12:00:00`)
}

const MAX_RANGE_DAYS = 92

function clampRange(from: string, to: string): { from: string; to: string } {
  let a = parseIso(from)
  let b = parseIso(to)
  if (Number.isNaN(a.getTime())) a = new Date()
  if (Number.isNaN(b.getTime())) b = new Date()
  if (a > b) {
    const tmp = a
    a = b
    b = tmp
  }
  const span = Math.round((b.getTime() - a.getTime()) / 86400000)
  if (span > MAX_RANGE_DAYS) {
    b = new Date(a)
    b.setDate(a.getDate() + MAX_RANGE_DAYS)
  }
  return { from: toIso(a), to: toIso(b) }
}

function mondayOf(iso: string): Date {
  const d = parseIso(iso)
  const weekday = d.getDay()
  const diff = weekday === 0 ? -6 : 1 - weekday
  d.setDate(d.getDate() + diff)
  return d
}

type PresetPeriod = 'day' | 'week' | 'month'

function rangeForPreset(period: PresetPeriod, aroundIso: string): { from: string; to: string } {
  const d = parseIso(aroundIso)
  if (period === 'day') {
    const iso = toIso(d)
    return { from: iso, to: iso }
  }
  if (period === 'week') {
    const mon = mondayOf(aroundIso)
    const sun = new Date(mon)
    sun.setDate(mon.getDate() + 6)
    return { from: toIso(mon), to: toIso(sun) }
  }
  const start = new Date(d.getFullYear(), d.getMonth(), 1)
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0)
  return { from: toIso(start), to: toIso(end) }
}

function matchesPreset(period: PresetPeriod, from: string, to: string): boolean {
  const aroundTo = rangeForPreset(period, to)
  const aroundFrom = rangeForPreset(period, from)
  return (
    (from === aroundTo.from && to === aroundTo.to) ||
    (from === aroundFrom.from && to === aroundFrom.to)
  )
}

function shiftRange(
  from: string,
  to: string,
  period: OpsPeriod,
  lastPreset: PresetPeriod,
  delta: number,
): { from: string; to: string } {
  if (period === 'custom') {
    const start = parseIso(from)
    const end = parseIso(to)
    const days = Math.round((end.getTime() - start.getTime()) / 86400000) + 1
    start.setDate(start.getDate() + delta * days)
    end.setDate(end.getDate() + delta * days)
    return clampRange(toIso(start), toIso(end))
  }
  const around = delta >= 0 ? to : from
  const d = parseIso(around)
  if (lastPreset === 'day') d.setDate(d.getDate() + delta)
  else if (lastPreset === 'week') d.setDate(d.getDate() + delta * 7)
  else d.setMonth(d.getMonth() + delta)
  return rangeForPreset(lastPreset, toIso(d))
}

const PERIOD_LABEL: Record<OpsPeriod, string> = {
  day: 'Diário',
  week: 'Semanal',
  month: 'Mensal',
  custom: 'Intervalo',
}

function operationalIndex(fechados: number, atribuidos: number): string {
  if (atribuidos <= 0) return '—'
  return `${((100 * fechados) / atribuidos).toLocaleString('pt-BR', {
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  })}%`
}

type DeltaTone = 'up' | 'down' | 'flat'

function deltaInt(cur: number, prev: number): { text: string; tone: DeltaTone } {
  const d = cur - prev
  if (d > 0) return { text: `+${d.toLocaleString('pt-BR')}`, tone: 'up' }
  if (d < 0) return { text: d.toLocaleString('pt-BR'), tone: 'down' }
  return { text: '0', tone: 'flat' }
}

function deltaHours(
  cur: number | null,
  prev: number | null,
): { text: string; tone: DeltaTone } {
  if (cur == null || prev == null) return { text: '—', tone: 'flat' }
  const d = Math.round((cur - prev) * 100) / 100
  const fmt = d.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (d > 0) return { text: `+${fmt} h`, tone: 'up' }
  if (d < 0) return { text: `${fmt} h`, tone: 'down' }
  return { text: '0,00 h', tone: 'flat' }
}

function toneClass(tone: DeltaTone, invert = false): string {
  if (tone === 'flat') return 'text-muted'
  const good = invert ? tone === 'down' : tone === 'up'
  return good ? 'text-emerald-800' : 'text-rose-800'
}

function shortDay(iso: string): string {
  const parts = iso.split('-')
  if (parts.length !== 3) return iso
  return `${parts[2]}/${parts[1]}`
}

const DEFAULT_EQUIPES = 'N1,N2,N3,DEV'

const PIE_COLORS = [
  '#0d7377',
  '#0384c7',
  '#d69e2e',
  '#9b2c2c',
  '#6b46c1',
  '#2b6cb0',
  '#38a169',
  '#dd6b20',
]

const CHART_TOOLTIP = {
  background: 'var(--sgc-panel)',
  border: '1px solid var(--sgc-line)',
  color: 'var(--sgc-ink)',
}

export function WeeklyReportPage() {
  const [period, setPeriod] = useState<OpsPeriod>('week')
  const [lastPreset, setLastPreset] = useState<PresetPeriod>('week')
  const [dateFrom, setDateFrom] = useState(() => rangeForPreset('week', todayIso()).from)
  const [dateTo, setDateTo] = useState(() => rangeForPreset('week', todayIso()).to)
  const [equipes, setEquipes] = useState(DEFAULT_EQUIPES)
  const [tecnico, setTecnico] = useState('')
  const [pdfBusy, setPdfBusy] = useState(false)
  const [csvBusy, setCsvBusy] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [assertBusy, setAssertBusy] = useState<string | null>(null)

  const techQuery = useQuery({
    queryKey: ['technicians'],
    queryFn: ({ signal }) => fetchTechnicians(signal),
  })

  const assertQuery = useQuery({
    queryKey: ['assertividade-pdfs'],
    queryFn: ({ signal }) => fetchAssertividadePdfs(signal),
  })

  const query = useQuery({
    queryKey: ['ops-report', period, dateFrom, dateTo, equipes, tecnico],
    queryFn: ({ signal }) =>
      fetchOpsPeriodReport(
        {
          period,
          dateFrom,
          dateTo,
          equipes: equipes.trim() || undefined,
          tecnico: tecnico.trim() || undefined,
        },
        signal,
      ),
  })

  function applyPreset(p: PresetPeriod) {
    const range = rangeForPreset(p, dateTo || todayIso())
    setLastPreset(p)
    setPeriod(p)
    setDateFrom(range.from)
    setDateTo(range.to)
  }

  function onDateFromChange(value: string) {
    const next = clampRange(value || todayIso(), dateTo)
    setDateFrom(next.from)
    setDateTo(next.to)
    const hit = (['day', 'week', 'month'] as PresetPeriod[]).find((p) =>
      matchesPreset(p, next.from, next.to),
    )
    setPeriod(hit ?? 'custom')
  }

  function onDateToChange(value: string) {
    const next = clampRange(dateFrom, value || todayIso())
    setDateFrom(next.from)
    setDateTo(next.to)
    const hit = (['day', 'week', 'month'] as PresetPeriod[]).find((p) =>
      matchesPreset(p, next.from, next.to),
    )
    setPeriod(hit ?? 'custom')
  }

  function goToday() {
    const range = rangeForPreset(lastPreset, todayIso())
    setPeriod(lastPreset)
    setDateFrom(range.from)
    setDateTo(range.to)
  }

  function shift(delta: number) {
    const next = shiftRange(dateFrom, dateTo, period, lastPreset, delta)
    setDateFrom(next.from)
    setDateTo(next.to)
    const hit = (['day', 'week', 'month'] as PresetPeriod[]).find((p) =>
      matchesPreset(p, next.from, next.to),
    )
    setPeriod(hit ?? 'custom')
  }

  async function onDownloadPdf() {
    setExportError(null)
    setPdfBusy(true)
    try {
      await downloadOpsPeriodPdf({
        period,
        dateFrom,
        dateTo,
        equipes: equipes.trim() || undefined,
        tecnico: tecnico.trim() || undefined,
      })
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Não foi possível gerar o PDF.')
    } finally {
      setPdfBusy(false)
    }
  }

  async function onDownloadCsv() {
    setExportError(null)
    setCsvBusy(true)
    try {
      await downloadOpsPeriodCsv({
        period,
        dateFrom,
        dateTo,
        equipes: equipes.trim() || undefined,
        tecnico: tecnico.trim() || undefined,
      })
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Não foi possível gerar o Excel.')
    } finally {
      setCsvBusy(false)
    }
  }

  async function onDownloadAssertividade(filename: string) {
    setExportError(null)
    setAssertBusy(filename)
    try {
      await downloadAssertividadePdf(filename)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Não foi possível baixar o PDF de assertividade.')
    } finally {
      setAssertBusy(null)
    }
  }

  function drillEquipe(eq: string) {
    const name = eq.trim().toUpperCase()
    if (!name || name === 'TOTAL') return
    setEquipes(name)
  }

  const activeLogins = useMemo(
    () =>
      (techQuery.data ?? [])
        .filter((t) => t.sit === '1')
        .map((t) => t.usuario)
        .sort((a, b) => a.localeCompare(b)),
    [techQuery.data],
  )

  const chartData = useMemo(() => {
    return (query.data?.teams ?? [])
      .filter((t) => t.equipe !== 'TOTAL')
      .map((t) => ({
        equipe: t.equipe,
        atribuídos: t.atribuidos,
        fechados: t.fechados,
      }))
  }, [query.data])

  const pieData = useMemo(
    () => chartData.filter((t) => t.fechados > 0).map((t) => ({ equipe: t.equipe, value: t.fechados })),
    [chartData],
  )

  const serieData = useMemo(
    () =>
      (query.data?.serie_diaria ?? []).map((d) => ({
        ...d,
        dia: shortDay(d.data),
      })),
    [query.data],
  )

  const rankBars = useMemo(
    () =>
      (query.data?.rank_fechou_mais ?? []).map((r) => ({
        nome: r.tecnico,
        fechados: r.fechados,
      })),
    [query.data],
  )

  const vsAnterior = useMemo(() => {
    const data = query.data
    const cmp = data?.comparacao
    if (!data || !cmp) return null
    return {
      label: cmp.label,
      atribuidos: deltaInt(data.totals.atribuidos, cmp.atribuidos),
      fechados: deltaInt(data.totals.fechados, cmp.fechados),
      tempo: deltaHours(data.totals.tempo_medio_horas, cmp.tempo_medio_horas),
    }
  }, [query.data])

  return (
    <div>
      <PageHeader
        title="Relatórios"
        description="Por intervalo, equipe e pessoa: fechados, tempo médio, ranking e quem mais pede."
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div>
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Período</span>
          <div className="flex gap-1">
            {(['day', 'week', 'month'] as PresetPeriod[]).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => applyPreset(p)}
                className={`rounded-lg border px-3 py-2 text-sm font-semibold ${
                  period === p || matchesPreset(p, dateFrom, dateTo)
                    ? 'border-accent bg-accent text-white'
                    : 'border-line bg-panel text-accent hover:bg-canvas'
                }`}
              >
                {PERIOD_LABEL[p]}
              </button>
            ))}
          </div>
        </div>

        <label className="block">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Data inicial</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => onDateFromChange(e.target.value || todayIso())}
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Data final</span>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-lg border border-line px-3 py-2 text-sm hover:bg-canvas"
              onClick={() => shift(-1)}
            >
              ←
            </button>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => onDateToChange(e.target.value || todayIso())}
              className="rounded-lg border border-line bg-panel px-3 py-2 text-sm"
            />
            <button
              type="button"
              className="rounded-lg border border-line px-3 py-2 text-sm hover:bg-canvas"
              onClick={() => shift(1)}
            >
              →
            </button>
            <button
              type="button"
              className="rounded-lg border border-line px-3 py-2 text-sm hover:bg-canvas"
              onClick={goToday}
            >
              Hoje
            </button>
          </div>
        </label>

        <label className="block min-w-[200px] flex-1">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Equipes</span>
          <div className="flex gap-2">
            <input
              value={equipes}
              onChange={(e) => setEquipes(e.target.value.toUpperCase())}
              className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm"
              placeholder="N1,N2,N3,DEV"
            />
            {equipes.trim().toUpperCase() !== DEFAULT_EQUIPES ? (
              <button
                type="button"
                className="shrink-0 rounded-lg border border-line px-3 py-2 text-xs font-semibold text-accent hover:bg-canvas"
                onClick={() => setEquipes(DEFAULT_EQUIPES)}
              >
                Todas
              </button>
            ) : null}
          </div>
        </label>

        <label className="block min-w-[180px]">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Técnico</span>
          <select
            value={tecnico}
            onChange={(e) => setTecnico(e.target.value)}
            className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm"
          >
            <option value="">Todos</option>
            {tecnico && !activeLogins.includes(tecnico) ? (
              <option value={tecnico}>{tecnico}</option>
            ) : null}
            {activeLogins.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          onClick={() => void onDownloadPdf()}
          disabled={pdfBusy || csvBusy || query.isLoading}
          className="inline-flex items-center gap-2 rounded-lg border border-accent bg-accent px-3 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60"
        >
          <Download className="h-4 w-4" aria-hidden />
          {pdfBusy ? 'Gerando…' : 'Baixar PDF'}
        </button>
        <button
          type="button"
          onClick={() => void onDownloadCsv()}
          disabled={pdfBusy || csvBusy || query.isLoading}
          className="inline-flex items-center gap-2 rounded-lg border border-line bg-panel px-3 py-2 text-sm font-semibold text-accent hover:bg-canvas disabled:opacity-60"
        >
          <FileSpreadsheet className="h-4 w-4" aria-hidden />
          {csvBusy ? 'Gerando…' : 'Baixar Excel'}
        </button>
      </div>
      {exportError ? (
        <p className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">
          {exportError}
        </p>
      ) : null}

      {query.isLoading ? (
        <LoadingState label="Montando relatório…" />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !query.data ? (
        <EmptyState title="Sem dados" description="A API não retornou o relatório." />
      ) : (
        <>
          <p className="mb-4 text-sm text-muted">
            {PERIOD_LABEL[query.data.period]}:{' '}
            <span className="font-medium text-ink">{query.data.label}</span>
            {query.data.filtro_tecnico ? (
              <>
                {' '}
                · técnico{' '}
                <span className="font-mono font-medium text-ink">{query.data.filtro_tecnico}</span>
              </>
            ) : null}
          </p>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <StatCard
              title="Atribuídos (SGC)"
              value={displayNumber(query.data.totals.atribuidos)}
              hint="No período"
              icon={Ticket}
            />
            <StatCard
              title="Fechados (GLPI)"
              value={displayNumber(query.data.totals.fechados)}
              hint="Feedback no período"
              icon={CheckCircle2}
            />
            <StatCard
              title="Índice operacional"
              value={operationalIndex(
                query.data.totals.fechados,
                query.data.totals.atribuidos,
              )}
              hint="Fechados / atribuídos (fontes diferentes)"
              icon={Percent}
            />
            <StatCard
              title="Abertos (GLPI)"
              value={displayNumber(query.data.totals.abertos)}
              hint="Aberturas no período (feedback)"
              icon={ClipboardList}
            />
            <StatCard
              title="Backlog ativo"
              value={displayNumber(query.data.totals.backlog_ativo)}
              hint="Sit=1 agora"
              icon={Users}
            />
            <StatCard
              title="Tempo médio"
              value={
                query.data.totals.tempo_medio_horas != null
                  ? `${displayNumber(query.data.totals.tempo_medio_horas)} h`
                  : '—'
              }
              hint="Abertura → fechamento"
              icon={Clock}
            />
          </div>
          <p className="mt-2 text-[11px] text-muted">
            Índice operacional mistura SGC (atribuídos) e GLPI (fechados). Não é % de resolução da
            semana nem assertividade.
          </p>

          {vsAnterior && query.data.comparacao ? (
            <div className="mt-6 rounded-xl border border-line bg-panel p-4 shadow-sm">
              <h2 className="font-display text-sm font-semibold text-ink">
                Vs período anterior
              </h2>
              <p className="mt-0.5 text-[11px] text-muted">{vsAnterior.label}</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <div>
                  <p className="text-xs font-semibold uppercase text-muted">Atribuídos</p>
                  <p className="mt-1 font-mono text-sm">
                    {displayNumber(query.data.totals.atribuidos)}{' '}
                    <span className={`font-semibold ${toneClass(vsAnterior.atribuidos.tone)}`}>
                      ({vsAnterior.atribuidos.text})
                    </span>
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase text-muted">Fechados</p>
                  <p className="mt-1 font-mono text-sm">
                    {displayNumber(query.data.totals.fechados)}{' '}
                    <span className={`font-semibold ${toneClass(vsAnterior.fechados.tone)}`}>
                      ({vsAnterior.fechados.text})
                    </span>
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase text-muted">Tempo médio</p>
                  <p className="mt-1 font-mono text-sm">
                    {query.data.totals.tempo_medio_horas != null
                      ? `${displayNumber(query.data.totals.tempo_medio_horas)} h`
                      : '—'}{' '}
                    <span className={`font-semibold ${toneClass(vsAnterior.tempo.tone, true)}`}>
                      ({vsAnterior.tempo.text})
                    </span>
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          {serieData.length ? (
            <div className="mt-6 rounded-xl border border-line bg-panel p-4 shadow-sm">
              <h2 className="font-display text-sm font-semibold text-ink">Volume por dia</h2>
              <p className="text-[11px] text-muted">Atribuídos (SGC) vs fechados (GLPI)</p>
              <div className="mt-3 h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={serieData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--sgc-line)" />
                    <XAxis dataKey="dia" tick={{ fontSize: 11, fill: 'var(--sgc-muted)' }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: 'var(--sgc-muted)' }} />
                    <Tooltip contentStyle={CHART_TOOLTIP} />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="atribuidos"
                      name="Atribuídos"
                      stroke="var(--sgc-accent)"
                      fill="var(--sgc-accent)"
                      fillOpacity={0.18}
                    />
                    <Area
                      type="monotone"
                      dataKey="fechados"
                      name="Fechados"
                      stroke="#0384c7"
                      fill="#0384c7"
                      fillOpacity={0.18}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : null}

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-line bg-panel p-4 shadow-sm">
              <h2 className="font-display text-sm font-semibold text-ink">Fechados por equipe</h2>
              <p className="text-[11px] text-muted">Clique na fatia para filtrar a equipe</p>
              <div className="mt-3 h-72">
                {pieData.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        dataKey="value"
                        nameKey="equipe"
                        cx="50%"
                        cy="50%"
                        innerRadius={48}
                        outerRadius={88}
                        onClick={(entry) => {
                          const eq = (entry as { equipe?: string })?.equipe
                          if (eq) drillEquipe(eq)
                        }}
                      >
                        {pieData.map((row, i) => (
                          <Cell key={row.equipe} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={CHART_TOOLTIP} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="flex h-full items-center justify-center text-sm text-muted">
                    Sem fechamentos no recorte.
                  </p>
                )}
              </div>
            </div>

            {chartData.length ? (
              <div className="rounded-xl border border-line bg-panel p-4 shadow-sm">
                <h2 className="font-display text-sm font-semibold text-ink">Comparativo por equipe</h2>
                <p className="text-[11px] text-muted">Clique na barra para filtrar. Backlog fica no card.</p>
                <div className="mt-3 h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--sgc-line)" />
                      <XAxis dataKey="equipe" tick={{ fontSize: 12, fill: 'var(--sgc-muted)' }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: 'var(--sgc-muted)' }} />
                      <Tooltip contentStyle={CHART_TOOLTIP} />
                      <Legend />
                      <Bar
                        dataKey="atribuídos"
                        fill="var(--sgc-accent)"
                        cursor="pointer"
                        onClick={(d) => {
                          const eq = (d as { equipe?: string })?.equipe
                          if (eq) drillEquipe(eq)
                        }}
                      />
                      <Bar
                        dataKey="fechados"
                        fill="#0384c7"
                        cursor="pointer"
                        onClick={(d) => {
                          const eq = (d as { equipe?: string })?.equipe
                          if (eq) drillEquipe(eq)
                        }}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            {rankBars.length ? (
              <div className="rounded-xl border border-line bg-panel p-4 shadow-sm">
                <h2 className="font-display text-sm font-semibold text-ink">Quem mais fechou</h2>
                <div className="mt-3 h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={rankBars} layout="vertical" margin={{ left: 8, right: 12 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--sgc-line)" />
                      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                      <YAxis
                        type="category"
                        dataKey="nome"
                        width={120}
                        tick={{ fontSize: 11, fill: 'var(--sgc-muted)' }}
                      />
                      <Tooltip contentStyle={CHART_TOOLTIP} />
                      <Bar dataKey="fechados" name="Fechados" fill="#0384c7" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}

            {(query.data.tempo_faixas ?? []).some((f) => f.qtd > 0) ? (
              <div className="rounded-xl border border-line bg-panel p-4 shadow-sm">
                <h2 className="font-display text-sm font-semibold text-ink">Tempo até o fechamento</h2>
                <p className="text-[11px] text-muted">Faixas sobre fechados GLPI no período</p>
                <div className="mt-3 h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={query.data.tempo_faixas}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--sgc-line)" />
                      <XAxis dataKey="faixa" tick={{ fontSize: 11, fill: 'var(--sgc-muted)' }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: 'var(--sgc-muted)' }} />
                      <Tooltip contentStyle={CHART_TOOLTIP} />
                      <Bar dataKey="qtd" name="Chamados" fill="#d69e2e" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            {query.data.top_solicitantes.length ? (
              <div className="rounded-xl border border-line bg-panel p-4 shadow-sm">
                <h2 className="font-display text-sm font-semibold text-ink">Quem mais pede</h2>
                <p className="text-[11px] text-muted">Atribuídos SGC no período</p>
                <div className="mt-3 h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={query.data.top_solicitantes.slice(0, 8)}
                      layout="vertical"
                      margin={{ left: 8, right: 12 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--sgc-line)" />
                      <XAxis type="number" allowDecimals={false} />
                      <YAxis type="category" dataKey="nome" width={130} tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={CHART_TOOLTIP} />
                      <Bar dataKey="qtd" name="Chamados" fill="var(--sgc-accent)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}

            {query.data.top_localizacoes.length ? (
              <div className="rounded-xl border border-line bg-panel p-4 shadow-sm">
                <h2 className="font-display text-sm font-semibold text-ink">Onde mais abre</h2>
                <p className="text-[11px] text-muted">Localização nos fechamentos GLPI</p>
                <div className="mt-3 h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={query.data.top_localizacoes.slice(0, 8)}
                      layout="vertical"
                      margin={{ left: 8, right: 12 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--sgc-line)" />
                      <XAxis type="number" allowDecimals={false} />
                      <YAxis type="category" dataKey="nome" width={130} tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={CHART_TOOLTIP} />
                      <Bar dataKey="qtd" name="Chamados" fill="#805ad5" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}
          </div>

          {!query.data.filtro_tecnico && query.data.rank_fechou_menos.length ? (
            <div className="mt-6 rounded-xl border border-line bg-panel p-4 shadow-sm">
              <h2 className="font-display text-sm font-semibold text-ink">Menos fechou</h2>
              <p className="text-[11px] text-muted">Entre quem teve fechamento no período — volume baixo não é ranking de desempenho.</p>
              <ul className="mt-2 space-y-1.5 text-sm">
                {query.data.rank_fechou_menos.map((r, i) => (
                  <li key={`m-${r.equipe}-${r.tecnico}`} className="flex justify-between gap-2">
                    <span>
                      <span className="text-muted">{i + 1}.</span> {r.tecnico}{' '}
                      <span className="text-xs text-muted">({r.equipe})</span>
                    </span>
                    <span className="font-mono font-semibold">{r.fechados}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="mt-6 overflow-x-auto rounded-xl border border-line bg-panel shadow-sm">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-canvas/80 text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-3 font-semibold">Equipe</th>
                  <th className="px-3 py-3 font-semibold">Atribuídos</th>
                  <th className="px-3 py-3 font-semibold">Fechados</th>
                  <th className="px-3 py-3 font-semibold">Abertos</th>
                  <th className="px-3 py-3 font-semibold">Backlog</th>
                  <th className="px-3 py-3 font-semibold">Tempo médio</th>
                </tr>
              </thead>
              <tbody>
                {query.data.teams.map((t) => (
                  <tr key={t.equipe} className="border-t border-line">
                    <td className="px-3 py-2.5 font-semibold">
                      <button
                        type="button"
                        className="text-accent hover:underline"
                        onClick={() => drillEquipe(t.equipe)}
                      >
                        {t.equipe}
                      </button>
                    </td>
                    <td className="px-3 py-2.5">{displayNumber(t.atribuidos)}</td>
                    <td className="px-3 py-2.5">{displayNumber(t.fechados)}</td>
                    <td className="px-3 py-2.5">{displayNumber(t.abertos)}</td>
                    <td className="px-3 py-2.5">{displayNumber(t.backlog_ativo)}</td>
                    <td className="px-3 py-2.5">
                      {t.tempo_medio_horas != null
                        ? `${displayNumber(t.tempo_medio_horas)} h`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {query.data.teams.map((t) =>
            t.por_tecnico.length ? (
              <div key={`p-${t.equipe}`} className="mt-6">
                <h3 className="mb-2 font-display text-sm font-semibold text-ink">
                  {t.equipe} — por técnico
                </h3>
                <div className="overflow-x-auto rounded-xl border border-line bg-panel shadow-sm">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-canvas/80 text-xs uppercase text-muted">
                      <tr>
                        <th className="px-3 py-3 font-semibold">Técnico</th>
                        <th className="px-3 py-3 font-semibold">Matrícula</th>
                        <th className="px-3 py-3 font-semibold">Atribuídos</th>
                        <th className="px-3 py-3 font-semibold">Fechados</th>
                        <th className="px-3 py-3 font-semibold">Abertos*</th>
                        <th className="px-3 py-3 font-semibold">Tempo médio</th>
                      </tr>
                    </thead>
                    <tbody>
                      {t.por_tecnico.map((p) => (
                        <tr key={p.tecnico} className="border-t border-line">
                          <td className="px-3 py-2.5 font-medium">{displayValue(p.tecnico)}</td>
                          <td className="px-3 py-2.5 font-mono text-xs">
                            {p.matricula && p.matricula !== '00000' ? p.matricula : '—'}
                          </td>
                          <td className="px-3 py-2.5">{displayNumber(p.atribuidos)}</td>
                          <td className="px-3 py-2.5">{displayNumber(p.fechados)}</td>
                          <td className="px-3 py-2.5">{displayNumber(p.abertos)}</td>
                          <td className="px-3 py-2.5">
                            {p.tempo_medio_horas != null
                              ? `${displayNumber(p.tempo_medio_horas)} h`
                              : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-1 text-[11px] text-muted">
                  *Abertos = tickets cuja abertura caiu no período (feedback), não necessariamente ainda
                  abertos.
                </p>
              </div>
            ) : null,
          )}

          {query.data.notes.length ? (
            <ul className="mt-6 list-disc space-y-1 rounded-xl border border-line bg-canvas/50 px-5 py-3 text-xs text-muted">
              {query.data.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          ) : null}
        </>
      )}

      <section className="mt-8 rounded-xl border border-line bg-panel p-4 shadow-sm">
        <h2 className="font-display text-sm font-semibold text-ink">PDFs de assertividade</h2>
        <p className="mt-1 text-xs text-muted">
          Relatórios gerados pelo worker às 03:00 (Assertividade_SGC_YYYYMMDD.pdf), separados do PDF
          operacional acima.
        </p>
        {assertQuery.isLoading ? (
          <div className="mt-3">
            <LoadingState label="Listando PDFs…" />
          </div>
        ) : assertQuery.isError ? (
          <div className="mt-3">
            <ErrorState
              message={assertQuery.error.message}
              onRetry={() => void assertQuery.refetch()}
            />
          </div>
        ) : !assertQuery.data?.length ? (
          <div className="mt-3">
            <EmptyState
              title="Nenhum PDF ainda"
              description="Quando o job das 03:00 rodar, os arquivos aparecem aqui."
            />
          </div>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase text-muted">
                <tr>
                  <th className="px-2 py-2 font-semibold">Arquivo</th>
                  <th className="px-2 py-2 font-semibold">Gerado</th>
                  <th className="px-2 py-2 font-semibold">Tamanho</th>
                  <th className="px-2 py-2 font-semibold"> </th>
                </tr>
              </thead>
              <tbody>
                {assertQuery.data.map((item) => (
                  <tr key={item.filename} className="border-b border-line/70">
                    <td className="px-2 py-2 font-mono text-xs">{item.filename}</td>
                    <td className="px-2 py-2 whitespace-nowrap">{displayDate(item.modified)}</td>
                    <td className="px-2 py-2">{displayBytes(item.size)}</td>
                    <td className="px-2 py-2">
                      <button
                        type="button"
                        disabled={assertBusy === item.filename}
                        onClick={() => void onDownloadAssertividade(item.filename)}
                        className="inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-xs font-semibold text-accent hover:bg-canvas disabled:opacity-60"
                      >
                        <Download className="h-3 w-3" aria-hidden />
                        {assertBusy === item.filename ? 'Baixando…' : 'Baixar'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
