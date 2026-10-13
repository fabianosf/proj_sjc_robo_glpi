import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchJobs } from '../api/endpoints'
import type { JobItem } from '../api/types'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { displayDate, displayValue } from '../lib/format'

function aliveLabel(value: boolean | null | undefined, enabled = true): string {
  if (!enabled) return 'Desligado'
  if (value === true) return 'Em execução'
  if (value === false) return 'Parado'
  return 'Não disponível'
}

function jobTone(job: JobItem): string {
  if (!job.enabled) return 'border-line bg-panel'
  if (job.last_ok === false) return 'border-amber-300 bg-amber-50'
  return 'border-line bg-panel'
}

export function JobsPage() {
  const query = useQuery({
    queryKey: ['jobs'],
    queryFn: ({ signal }) => fetchJobs(signal),
    refetchInterval: 30_000,
  })

  const data = query.data
  const jobs = data?.jobs ?? []

  return (
    <div>
      <PageHeader
        title="Agendamentos"
        description="Status do worker e do AgendadorSGC. O painel não dispara jobs — só o processo run.bat."
      />

      {query.isLoading ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !jobs.length ? (
        <EmptyState title="Sem agendamentos" description="A API não retornou jobs." />
      ) : (
        <>
          <section className="mb-4 rounded-xl border border-line bg-panel p-4 shadow-sm">
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted">Worker (main.py)</dt>
                <dd className="font-semibold">{aliveLabel(data?.worker_alive)}</dd>
                <dd className="text-xs text-muted">
                  {data?.worker_updated_at
                    ? `Último sinal ${displayDate(data.worker_updated_at)}`
                    : 'Sem heartbeat em log/'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">AgendadorSGC</dt>
                <dd className="font-semibold">
                  {aliveLabel(data?.scheduler_alive, data?.scheduler_enabled !== false)}
                </dd>
                <dd className="text-xs text-muted">
                  {data?.scheduler_enabled === false
                    ? 'SGC_AGENDADOR_AUTO=0'
                    : data?.scheduler_updated_at
                      ? `Último ciclo ${displayDate(data.scheduler_updated_at)}`
                      : 'Aguardando o worker iniciar o agendador'}
                </dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-muted">
              PDF das 03:00 em{' '}
              <Link to="/relatorios" className="font-semibold text-accent hover:underline">
                Relatórios
              </Link>
              {' · '}
              modelo em{' '}
              <Link to="/ia" className="font-semibold text-accent hover:underline">
                Inteligência artificial
              </Link>
              .
            </p>
          </section>

          <ul className="grid gap-4 md:grid-cols-2">
            {jobs.map((job) => (
              <li key={job.id} className={`rounded-xl border p-5 shadow-sm ${jobTone(job)}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-display text-base font-semibold text-ink">
                      {displayValue(job.name)}
                    </h2>
                    <p className="mt-1 text-xs text-muted">{displayValue(job.id)}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                        (job.process_alive ?? job.enabled)
                          ? 'bg-emerald-100 text-emerald-900'
                          : 'bg-canvas text-muted'
                      }`}
                      title="Heartbeat do processo (worker/agendador)"
                    >
                      {(job.process_alive ?? job.enabled) ? 'Processo vivo' : 'Processo parado'}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                        job.agenda_enabled !== false
                          ? 'bg-sky-100 text-sky-900'
                          : 'bg-canvas text-muted'
                      }`}
                      title="SGC_AGENDADOR_AUTO / agenda configurada"
                    >
                      {job.agenda_enabled === false ? 'Agenda off' : 'Agenda on'}
                    </span>
                  </div>
                </div>
                <p className="mt-3 text-sm text-ink">{displayValue(job.description)}</p>
                <dl className="mt-4 grid gap-2 text-sm">
                  <div className="flex justify-between gap-2 border-t border-line pt-2">
                    <dt className="text-muted">Agenda</dt>
                    <dd className="font-medium">{displayValue(job.schedule)}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-muted">Última execução</dt>
                    <dd className="font-medium text-right">
                      {job.last_run_at ? displayDate(job.last_run_at) : 'Ainda não rodou'}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-muted">Resultado</dt>
                    <dd className="font-medium">
                      {job.last_ok === true ? 'OK' : job.last_ok === false ? 'Falhou' : '—'}
                    </dd>
                  </div>
                  {job.last_message ? (
                    <div className="flex justify-between gap-2">
                      <dt className="text-muted">Detalhe</dt>
                      <dd className="max-w-[16rem] truncate text-right font-medium" title={job.last_message}>
                        {job.last_message}
                      </dd>
                    </div>
                  ) : null}
                  <div className="flex justify-between gap-2">
                    <dt className="text-muted">Próxima</dt>
                    <dd className="font-medium">
                      {job.next_run_at ? displayDate(job.next_run_at) : 'Não disponível'}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-muted">Origem</dt>
                    <dd className="font-medium">{displayValue(job.source)}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
