import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { Search } from 'lucide-react'
import { fetchTickets } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/ui/button'
import { MethodBadge } from '../components/MethodBadge'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { useDebounce } from '../hooks/useDebounce'
import { displayDate, displayValue } from '../lib/format'

type TicketSource = 'glpi' | 'sgc'

const FONTE_STORAGE_KEY = 'sgc_tickets_fonte'

function resolveTicketSource(params: URLSearchParams): TicketSource {
  const fromUrl = params.get('fonte')
  if (fromUrl === 'glpi' || fromUrl === 'sgc') return fromUrl
  try {
    const stored = localStorage.getItem(FONTE_STORAGE_KEY)
    if (stored === 'glpi' || stored === 'sgc') return stored
  } catch {
    /* ignore */
  }
  return 'sgc'
}

export function TicketsPage() {
  const { hasMinProfile } = useAuth()
  const canReassign = hasMinProfile('ADMIN')
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') || 1) || 1)
  const pageSize = Math.min(100, Math.max(1, Number(params.get('page_size') || 20) || 20))
  const source = resolveTicketSource(params)
  const [searchInput, setSearchInput] = useState(params.get('search') ?? '')
  const debouncedSearch = useDebounce(searchInput, 400)

  const query = useQuery({
    queryKey: ['tickets', source, page, pageSize, debouncedSearch],
    queryFn: ({ signal }) =>
      fetchTickets(
        { page, pageSize, search: debouncedSearch, source },
        signal,
      ),
    placeholderData: (prev) => prev,
  })

  const totalPages = useMemo(() => {
    const total = query.data?.total ?? 0
    return Math.max(1, Math.ceil(total / pageSize))
  }, [query.data?.total, pageSize])

  const updateParams = (next: {
    page?: number
    page_size?: number
    search?: string
    fonte?: TicketSource
  }) => {
    const sp = new URLSearchParams(params)
    if (next.page != null) sp.set('page', String(next.page))
    if (next.page_size != null) sp.set('page_size', String(next.page_size))
    if (next.fonte != null) {
      sp.set('fonte', next.fonte)
      try {
        localStorage.setItem(FONTE_STORAGE_KEY, next.fonte)
      } catch {
        /* ignore */
      }
    }
    if (next.search !== undefined) {
      if (next.search.trim()) sp.set('search', next.search.trim())
      else sp.delete('search')
    }
    setParams(sp)
  }

  const isGlpi = source === 'glpi'

  return (
    <div>
      <PageHeader
        title="Chamados"
        description={
          isGlpi
            ? 'Ao vivo do GLPI — mesmos critérios do front (status = ativos / notold), ordenados pela última alteração.'
            : 'Base local SGC (Tb_Ticket_new) — chamados atribuídos pelo robô.'
        }
      />

      {isGlpi ? (
        <p className="mb-4 rounded-lg border border-line bg-panel px-3 py-2 text-sm text-muted">
          Esta lista é para consulta. Chamados novos continuam sendo tratados pelo robô;
          para alterar o destino de um chamado já processado, selecione <strong className="text-ink">SGC (robô)</strong>.
        </p>
      ) : null}

      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => updateParams({ page: 1, fonte: 'glpi' })}
          className={`rounded-lg border px-3 py-2 text-sm font-semibold ${
            isGlpi
              ? 'border-accent bg-accent text-white'
              : 'border-line bg-panel text-accent hover:bg-canvas'
          }`}
        >
          GLPI (ativos)
        </button>
        <button
          type="button"
          onClick={() => updateParams({ page: 1, fonte: 'sgc' })}
          className={`rounded-lg border px-3 py-2 text-sm font-semibold ${
            !isGlpi
              ? 'border-accent bg-accent text-white'
              : 'border-line bg-panel text-accent hover:bg-canvas'
          }`}
        >
          SGC (robô)
        </button>
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <label className="block min-w-0 flex-1">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Buscar</span>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
              aria-hidden
            />
            <input
              type="search"
              value={searchInput}
              onChange={(e) => {
                setSearchInput(e.target.value)
                updateParams({ page: 1, search: e.target.value })
              }}
              placeholder={
                isGlpi
                  ? 'ID ou título no GLPI…'
                  : 'ID, título, categoria, técnico…'
              }
              className="w-full rounded-lg border border-line bg-panel py-2.5 pl-10 pr-3 text-sm outline-none focus:border-accent"
              aria-label="Buscar chamados"
            />
          </div>
        </label>
        <label className="block w-full sm:w-40">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Por página</span>
          <select
            className="w-full rounded-lg border border-line bg-panel px-3 py-2.5 text-sm"
            value={pageSize}
            onChange={(e) => updateParams({ page: 1, page_size: Number(e.target.value) })}
            aria-label="Itens por página"
          >
            {[10, 20, 50, 100].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      {query.isLoading ? (
        <LoadingState label="Carregando chamados…" />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !query.data?.items.length ? (
        <EmptyState title="Nenhum chamado" description="A busca não retornou resultados." />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-panel shadow-sm">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-canvas/80 text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-3 font-semibold">ID</th>
                  <th className="px-3 py-3 font-semibold">Título</th>
                  <th className="px-3 py-3 font-semibold">Categoria</th>
                  {isGlpi ? (
                    <th className="px-3 py-3 font-semibold">Solicitante</th>
                  ) : (
                    <th className="px-3 py-3 font-semibold">Equipe</th>
                  )}
                  <th className="px-3 py-3 font-semibold">Técnico</th>
                  <th className="px-3 py-3 font-semibold">Status</th>
                  <th className="px-3 py-3 font-semibold">
                    {isGlpi ? 'Abertura' : 'Data'}
                  </th>
                  {isGlpi ? (
                    <th className="px-3 py-3 font-semibold">Última alt.</th>
                  ) : (
                    <th className="px-3 py-3 font-semibold">Método</th>
                  )}
                  {canReassign && !isGlpi ? (
                    <th className="px-3 py-3 font-semibold">Ação</th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((t, idx) => (
                  <tr
                    key={`${t.fonte ?? source}-${t.id ?? 'x'}-${t.data_mod ?? t.data ?? ''}-${idx}`}
                    className="border-t border-line"
                  >
                    <td className="px-3 py-2.5">
                      {t.id != null && !isGlpi ? (
                        <Link
                          to={`/chamados/${t.id}`}
                          className="font-semibold text-accent hover:underline"
                        >
                          {t.id}
                        </Link>
                      ) : t.id != null ? (
                        <a
                          href={`http://10.1.1.28/glpi/front/ticket.form.php?id=${t.id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="font-semibold text-accent hover:underline"
                        >
                          {t.id}
                        </a>
                      ) : (
                        'Não disponível'
                      )}
                    </td>
                    {canReassign && !isGlpi ? (
                      <td className="px-3 py-2.5">
                        {t.id != null ? (
                          <Button asChild variant="outline" size="sm">
                            <Link to={`/chamados/${t.id}?direcionar=1`}>
                              Direcionar
                            </Link>
                          </Button>
                        ) : (
                          '—'
                        )}
                      </td>
                    ) : null}
                    <td className="max-w-[14rem] truncate px-3 py-2.5" title={t.titulo ?? undefined}>
                      {displayValue(t.titulo)}
                    </td>
                    <td className="px-3 py-2.5">{displayValue(t.categoria)}</td>
                    <td className="px-3 py-2.5">
                      {displayValue(isGlpi ? t.solicitante : t.equipe)}
                    </td>
                    <td className="px-3 py-2.5">{displayValue(t.tecnico)}</td>
                    <td className="px-3 py-2.5">
                      {displayValue(t.status_label ?? t.sit)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">{displayDate(t.data)}</td>
                    <td className="px-3 py-2.5">
                      {isGlpi ? (
                        displayDate(t.data_mod)
                      ) : (
                        <MethodBadge method={t.metodo} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
            <p className="text-muted">
              Total: <strong className="text-ink">{query.data.total.toLocaleString('pt-BR')}</strong>
              {' · '}
              Página {page} de {totalPages}
              {isGlpi ? ' · fonte GLPI' : ' · fonte SGC'}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => updateParams({ page: page - 1 })}
                className="rounded-lg border border-line bg-panel px-3 py-1.5 font-medium disabled:opacity-40"
              >
                Anterior
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => updateParams({ page: page + 1 })}
                className="rounded-lg border border-line bg-panel px-3 py-1.5 font-medium disabled:opacity-40"
              >
                Próxima
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
