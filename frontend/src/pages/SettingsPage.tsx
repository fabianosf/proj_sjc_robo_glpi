import { useQuery } from '@tanstack/react-query'
import { getApiBaseUrl } from '../api/client'
import { fetchDashboardSummary, fetchHealth } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { displayAgeSeconds, displayDate, displayNumber, displayValue } from '../lib/format'

export function SettingsPage() {
  const baseUrl = getApiBaseUrl()
  const { user } = useAuth()
  const health = useQuery({
    queryKey: ['health', 'settings'],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 30_000,
  })
  const worker = useQuery({
    queryKey: ['dashboard-summary', 'settings-worker'],
    queryFn: ({ signal }) => fetchDashboardSummary(signal),
    refetchInterval: 30_000,
  })

  return (
    <div>
      <PageHeader
        title="Configurações"
        description="Parâmetros públicos do painel. Nenhum segredo, token JWT, conf/ ou credencial é exibido."
      />

      <section className="mb-4 max-w-2xl space-y-3 rounded-xl border border-line bg-panel p-5 shadow-sm">
        <h2 className="font-display text-sm font-semibold">Sessão</h2>
        <dl className="grid gap-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs text-muted">Usuário</dt>
            <dd className="font-medium">{displayValue(user?.username)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Nome</dt>
            <dd className="font-medium">{displayValue(user?.nome)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Perfil</dt>
            <dd className="font-medium">{displayValue(user?.perfil)}</dd>
          </div>
        </dl>
      </section>

      <section className="max-w-2xl space-y-4 rounded-xl border border-line bg-panel p-5 shadow-sm">
        <h2 className="font-display text-sm font-semibold">Conexão com a API</h2>
        <dl className="space-y-3 text-sm">
          <div>
            <dt className="text-xs font-semibold uppercase text-muted">VITE_API_BASE_URL</dt>
            <dd className="mt-1 break-all rounded-lg bg-canvas px-3 py-2 font-mono text-ink">
              {baseUrl}
            </dd>
          </div>
        </dl>

        <div className="border-t border-line pt-4">
          <h3 className="text-sm font-semibold">Status atual</h3>
          {health.isLoading ? (
            <div className="mt-3">
              <LoadingState label="Consultando /health…" />
            </div>
          ) : health.isError ? (
            <div className="mt-3">
              <ErrorState message={health.error.message} onRetry={() => void health.refetch()} />
            </div>
          ) : (
            <>
            <dl className="mt-3 grid gap-3 sm:grid-cols-3">
              <div>
                <dt className="text-xs text-muted">Status</dt>
                <dd className="font-medium">{displayValue(health.data?.status)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Banco</dt>
                <dd className="font-medium">{displayValue(health.data?.database)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Versão API</dt>
                <dd className="font-medium">{displayValue(health.data?.version)}</dd>
              </div>
            </dl>
            <h4 className="mt-5 text-sm font-semibold">Worker (robô)</h4>
            <dl className="mt-3 grid gap-3 sm:grid-cols-3">
              <div>
                <dt className="text-xs text-muted">Heartbeat</dt>
                <dd className="font-medium">
                  {health.data?.worker_alive == null
                    ? 'Não disponível'
                    : health.data.worker_alive
                      ? 'Em execução'
                      : 'Parado'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Último sinal</dt>
                <dd className="font-medium">
                  {health.data?.worker_updated_at
                    ? `${displayDate(health.data.worker_updated_at)} (${displayAgeSeconds(health.data.worker_age_seconds)})`
                    : 'Não disponível'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">GLPI</dt>
                <dd className="font-medium">
                  {health.data?.worker_glpi_ok == null
                    ? 'Não disponível'
                    : health.data.worker_glpi_ok
                      ? 'Ok'
                      : 'Indisponível'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Novos na fila</dt>
                <dd className="font-medium">{displayNumber(worker.data?.glpi_novos)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Último atribuído</dt>
                <dd className="font-medium">
                  {worker.data?.last_assigned_id != null
                    ? `#${worker.data.last_assigned_id}`
                    : 'Não disponível'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Sem elegível hoje</dt>
                <dd className="font-medium">
                  {displayNumber(worker.data?.skips_sem_tecnico_hoje)}
                  {worker.data?.last_skip_id != null
                    ? ` (último #${worker.data.last_skip_id})`
                    : ''}
                </dd>
              </div>
            </dl>
            {health.data?.worker_last_error ? (
              <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">
                Último erro: {health.data.worker_last_error}
              </p>
            ) : null}
            </>
          )}
        </div>

        <p className="text-xs text-muted">
          Rotas de dados exigem JWT. Não há acesso direto a GLPI, MariaDB, Telegram, conf/ ou
          modelos ML a partir do navegador.
        </p>
      </section>
    </div>
  )
}
