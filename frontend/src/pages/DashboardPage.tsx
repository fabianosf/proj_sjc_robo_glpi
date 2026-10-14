import { useQuery } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { fetchDashboardSummary } from '../api/endpoints'
import type { DashboardSummary } from '../api/types'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { displayAgeSeconds, displayNumber } from '../lib/format'

type Level = 'ok' | 'warn' | 'fail'

type Situation = {
  level: Level
  label: string
  text: string
  help?: string
  skipId?: number | null
  actionTo?: string
  actionLabel?: string
}

function situationOf(data: DashboardSummary | undefined): Situation {
  if (!data || data.worker_alive == null) {
    return {
      level: 'fail',
      label: 'Falha',
      text: 'Sem heartbeat do robô',
      actionTo: '/agendamentos',
      actionLabel: 'Ver agendamentos',
    }
  }
  if (data.worker_alive === false) {
    return {
      level: 'warn',
      label: 'Robô parado',
      text: 'O painel está conectado, mas a atribuição automática está pausada.',
      help: data.worker_last_error
        ? `Para retomar no Windows, inicie o Worker com start_worker_hidden.vbs na pasta do SGC. Último erro: ${data.worker_last_error}`
        : 'Chamados novos permanecem no GLPI até o Worker voltar. Para retomar no Windows, execute start_worker_hidden.vbs na pasta do SGC.',
      actionTo: '/agendamentos',
      actionLabel: 'Ver status do robô',
    }
  }
  if (data.worker_glpi_ok === false) {
    return {
      level: 'fail',
      label: 'Falha',
      text: 'GLPI indisponível no último ciclo',
      actionTo: '/agendamentos',
      actionLabel: 'Ver agendamentos',
    }
  }
  const skips = data.skips_sem_tecnico_hoje ?? 0
  if (skips > 0) {
    return {
      level: 'warn',
      label: 'Atenção',
      text:
        skips === 1
          ? '1 chamado ficou Novo hoje: equipe sem técnico elegível'
          : `${skips} chamados ficaram Novo hoje: equipe sem técnico elegível`,
      skipId: data.last_skip_in_sgc ? data.last_skip_id : null,
      actionTo: '/tecnicos',
      actionLabel: 'Ver técnicos',
    }
  }
  const novos = data.glpi_novos ?? 0
  if (novos > 0) {
    return {
      level: 'warn',
      label: 'Atenção',
      text:
        novos === 1 ? 'Fila com 1 Novo no GLPI' : `Fila com ${novos} Novos no GLPI`,
    }
  }
  return {
    level: 'ok',
    label: 'Normal',
    text: 'Em execução · fila vazia',
  }
}

const LEVEL_BAR: Record<Level, string> = {
  ok: 'border-line bg-ok-soft',
  warn: 'border-warn/40 bg-warn-soft',
  fail: 'border-danger/40 bg-danger-soft',
}

const LEVEL_PILL: Record<Level, string> = {
  ok: 'bg-ok text-white',
  warn: 'bg-warn text-white',
  fail: 'bg-danger text-white',
}

export function DashboardPage() {
  const summary = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: ({ signal }) => fetchDashboardSummary(signal),
    refetchInterval: 30_000,
  })

  if (summary.isLoading) return <LoadingState label="Carregando operação…" />
  if (summary.isError) {
    return (
      <ErrorState
        message={summary.error.message}
        onRetry={() => void summary.refetch()}
      />
    )
  }

  const data = summary.data
  const sit = situationOf(data)
  const teams = Object.entries(data?.tickets_today_by_team ?? {}).sort((a, b) => b[1] - a[1])
  const maxTeam = teams.reduce((m, [, n]) => Math.max(m, n), 0) || 1
  const novos = data?.glpi_novos ?? null
  const hoje = data?.tickets_today != null ? displayNumber(data.tickets_today) : '—'
  const filaTxt = novos == null ? '—' : novos === 0 ? 'vazia' : displayNumber(novos)
  const robo =
    data?.worker_alive == null ? '—' : data.worker_alive ? 'Em execução' : 'Parado'
  const roboHint = [
    data?.worker_updated_at ? displayAgeSeconds(data.worker_age_seconds) : null,
    data?.worker_glpi_ok === false
      ? 'GLPI indisponível'
      : data?.worker_glpi_ok === true
        ? 'GLPI ok'
        : null,
  ]
    .filter(Boolean)
    .join(' · ')
  const glpiOff = data?.worker_glpi_ok === false
  const roboAlerta = data?.worker_alive === false || glpiOff

  return (
    <div>
      <PageHeader title="Operação" description="Ciclo atual do robô." />

      <section className={`mb-4 rounded-xl border px-4 py-3 shadow-sm ${LEVEL_BAR[sit.level]}`}>
        <div className="flex flex-wrap items-center gap-3">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-wide ${LEVEL_PILL[sit.level]}`}
          >
            {sit.label}
          </span>
          <p className="min-w-0 flex-1 text-sm font-semibold text-ink">
            {sit.text}
            {sit.skipId != null ? (
              <>
                {' '}
                <Link to={`/chamados/${sit.skipId}`} className="text-accent hover:underline">
                  #{sit.skipId}
                </Link>
              </>
            ) : null}
          </p>
        </div>
        {sit.actionTo && sit.level !== 'ok' ? (
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
            {sit.help ? <p className="text-sm text-muted">{sit.help}</p> : null}
            <Link to={sit.actionTo} className="text-sm font-semibold text-accent hover:underline">
              {sit.actionLabel}
            </Link>
          </div>
        ) : null}
      </section>

      <section className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Hoje" hint="Registrados no SGC">
          {hoje}
        </Metric>
        <Metric
          label="Fila"
          hint="Chamados Novo no GLPI"
          warn={novos != null && novos > 0}
        >
          {filaTxt}
        </Metric>
        <Metric label="Robô" hint={roboHint || 'Heartbeat'} warn={roboAlerta}>
          {robo}
        </Metric>
        <Metric
          label="Último"
          hint={
            data?.last_assigned_id != null && data.last_assigned_in_sgc === false
              ? 'Só no heartbeat / GLPI'
              : 'Última atribuição (heartbeat)'
          }
          warn={data?.last_assigned_id != null && data.last_assigned_in_sgc === false}
        >
          {data?.last_assigned_id != null ? (
            data.last_assigned_in_sgc ? (
              <Link
                to={`/chamados/${data.last_assigned_id}`}
                className="text-accent hover:underline"
              >
                #{data.last_assigned_id}
              </Link>
            ) : (
              <span title="ID no heartbeat, sem linha em Tb_Ticket_new">
                #{data.last_assigned_id}
                <span className="mt-0.5 block text-[10px] font-normal text-amber-800">
                  sem SGC
                </span>
              </span>
            )
          ) : (
            '—'
          )}
        </Metric>
      </section>

      <section className="rounded-xl border border-line bg-panel p-4 shadow-sm">
        <h2 className="mb-3 font-display text-sm font-semibold">Hoje por equipe</h2>
        {!teams.length ? (
          <p className="text-sm text-muted">Nenhum atribuído hoje.</p>
        ) : (
          <ul className="space-y-2.5">
            {teams.map(([equipe, qtd]) => (
              <li key={equipe} className="grid grid-cols-[4rem_1fr_3rem] items-center gap-3 text-sm">
                <span className="font-semibold">{equipe}</span>
                <div className="h-2 overflow-hidden rounded-full bg-canvas">
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{ width: `${Math.max(6, (qtd / maxTeam) * 100)}%` }}
                  />
                </div>
                <span className="text-right tabular-nums text-muted">
                  {qtd.toLocaleString('pt-BR')}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function Metric({
  label,
  hint,
  warn,
  children,
}: {
  label: string
  hint?: string
  warn?: boolean
  children: ReactNode
}) {
  return (
    <article
      className={`rounded-xl border p-4 shadow-sm ${
        warn ? 'border-warn/40 bg-warn-soft' : 'border-line bg-panel'
      }`}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-2 font-display text-2xl font-semibold tabular-nums text-ink">{children}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </article>
  )
}
