import { useQuery } from '@tanstack/react-query'
import { fetchTeamsGuide } from '../api/endpoints'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { displayNumber, displayValue } from '../lib/format'

export function TeamsPage() {
  const query = useQuery({
    queryKey: ['teams-guide'],
    queryFn: ({ signal }) => fetchTeamsGuide(signal),
  })

  return (
    <div>
      <PageHeader
        title="Equipes"
        description="O que cada fila faz (resumo + exemplos das regras) e carga em Tb_Atrib. Use isto na hora de redirecionar."
      />
      {query.isLoading ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !query.data?.length ? (
        <EmptyState title="Sem equipes" description="A API não retornou o guia das filas." />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-panel shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-canvas/80 text-xs uppercase text-muted">
              <tr>
                <th className="px-3 py-3 font-semibold">Fila</th>
                <th className="px-3 py-3 font-semibold">O que faz</th>
                <th className="px-3 py-3 font-semibold">Exemplos</th>
                <th className="px-3 py-3 font-semibold">Ativos</th>
                <th className="px-3 py-3 font-semibold">Carga</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((t) => (
                <tr key={t.equipe} className="border-t border-line align-top">
                  <td className="px-3 py-2.5 font-semibold">{displayValue(t.equipe)}</td>
                  <td className="px-3 py-2.5 max-w-xs text-ink">{displayValue(t.resumo)}</td>
                  <td className="px-3 py-2.5 max-w-sm text-muted">
                    {(t.exemplos ?? []).slice(0, 8).join(', ') || '—'}
                  </td>
                  <td className="px-3 py-2.5">
                    {displayNumber(t.tecnicos_ativos)}
                    <span className="text-xs text-muted">
                      {' '}
                      / {displayNumber(t.technicians_total)}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">{displayNumber(t.carga_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
