import { useEffect, useState, type ReactNode } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  fetchMlAccuracy,
  fetchMlCorrections,
  fetchMlLogs,
  fetchMlModelStatus,
  fetchMlOverview,
  fetchTicket,
  simulateMl,
} from '../api/endpoints'
import type { MlLogEntry } from '../api/types'
import { MethodBadge } from '../components/MethodBadge'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { displayDate, displayValue } from '../lib/format'
import { resolveMethodBadge } from '../lib/methodLabels'

type TabId = 'correcoes' | 'qualidade' | 'log' | 'simular'

const TABS: { id: TabId; label: string }[] = [
  { id: 'correcoes', label: 'Correções' },
  { id: 'qualidade', label: 'Qualidade' },
  { id: 'log', label: 'Log' },
  { id: 'simular', label: 'Simular' },
]

const METHOD_FILTERS = [
  '',
  'DIRETO',
  'FALLBACK_PARCIAL',
  'ML',
  'FALLBACK_CATEGORIA',
  'FALLBACK_N1',
  'SEM_EQUIPE',
]

function fmtScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString('pt-BR', { maximumFractionDigits: 3 })
}

export function MlPage() {
  const [tab, setTab] = useState<TabId>('correcoes')
  const [simulateTicketId, setSimulateTicketId] = useState<number | null>(null)

  function goSimulate(id: number) {
    setSimulateTicketId(id)
    setTab('simular')
  }

  return (
    <div>
      <PageHeader
        title="Inteligência artificial"
        description="Decisão do robô e simulação (não grava GLPI)."
      />

      <MlStrip />

      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`rounded-lg border px-3 py-2 text-sm font-semibold ${
              tab === t.id
                ? 'border-accent bg-accent text-white'
                : 'border-line bg-panel text-accent hover:bg-canvas'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'correcoes' ? <CorrectionsTab onSimulate={goSimulate} /> : null}
      {tab === 'qualidade' ? <QualityTab /> : null}
      {tab === 'log' ? <LogsTab /> : null}
      {tab === 'simular' ? <SimulateTab initialTicketId={simulateTicketId} /> : null}
    </div>
  )
}

function MlStrip() {
  const overview = useQuery({
    queryKey: ['ml-overview'],
    queryFn: ({ signal }) => fetchMlOverview(signal),
  })
  const model = useQuery({
    queryKey: ['ml-model-status'],
    queryFn: ({ signal }) => fetchMlModelStatus(signal),
  })
  const acc = useQuery({
    queryKey: ['ml-accuracy'],
    queryFn: ({ signal }) => fetchMlAccuracy(signal),
  })

  const f1 = model.data?.f1_macro
  const ver = model.data?.version
  const modeloTxt = !model.data
    ? '…'
    : model.data.model_exists
      ? `Modelo F1 ${fmtScore(f1)}${ver != null ? ` · v${ver}` : ''}`
      : 'Modelo ausente'
  const taxa =
    acc.data?.taxa_pct != null
      ? `${acc.data.taxa_pct.toLocaleString('pt-BR')}%`
      : '—'

  return (
    <section className="mb-4 rounded-xl border border-line bg-panel px-4 py-3 text-sm shadow-sm">
      <dl className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <div>
          <dt className="sr-only">Modelo</dt>
          <dd className={`font-semibold ${model.data && !model.data.model_exists ? 'text-amber-800' : 'text-ink'}`}>
            {modeloTxt}
          </dd>
        </div>
        <div>
          <dt className="inline text-xs text-muted">Confiança </dt>
          <dd className="inline font-semibold">{fmtScore(overview.data?.avg_confidence)}</dd>
        </div>
        <div>
          <dt className="inline text-xs text-muted">Margem </dt>
          <dd className="inline font-semibold">{fmtScore(overview.data?.avg_margin)}</dd>
        </div>
        <div>
          <dt className="inline text-xs text-muted">Assertividade </dt>
          <dd className="inline font-semibold">{taxa}</dd>
        </div>
      </dl>
    </section>
  )
}

function CorrectionsTab({ onSimulate }: { onSimulate: (id: number) => void }) {
  const [page, setPage] = useState(1)
  const [equipeSgc, setEquipeSgc] = useState('')
  const [equipeCorreta, setEquipeCorreta] = useState('')
  const pageSize = 20
  const query = useQuery({
    queryKey: ['ml-corrections', page, pageSize, equipeSgc, equipeCorreta],
    queryFn: ({ signal }) =>
      fetchMlCorrections(
        {
          page,
          pageSize,
          equipeSgc: equipeSgc.trim() || undefined,
          equipeCorreta: equipeCorreta.trim() || undefined,
        },
        signal,
      ),
    placeholderData: (prev) => prev,
  })
  const totalPages = Math.max(1, Math.ceil((query.data?.total ?? 0) / pageSize))

  return (
    <>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <label className="block min-w-[7rem] text-sm">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">SGC</span>
          <input
            className="w-full rounded-lg border border-line bg-panel px-3 py-2"
            value={equipeSgc}
            maxLength={5}
            placeholder="N1"
            onChange={(e) => {
              setEquipeSgc(e.target.value)
              setPage(1)
            }}
          />
        </label>
        <label className="block min-w-[7rem] text-sm">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Fechou</span>
          <input
            className="w-full rounded-lg border border-line bg-panel px-3 py-2"
            value={equipeCorreta}
            maxLength={5}
            placeholder="N3"
            onChange={(e) => {
              setEquipeCorreta(e.target.value)
              setPage(1)
            }}
          />
        </label>
        {query.data?.total != null ? (
          <p className="pb-2 text-sm text-muted">{query.data.total.toLocaleString('pt-BR')} divergências</p>
        ) : null}
      </div>

      {query.isLoading ? (
        <LoadingState label="Carregando correções…" />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !query.data?.items.length ? (
        <EmptyState title="Nenhuma correção" description="Equipe SGC = equipe no fechamento." />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-panel shadow-sm">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-canvas/80 text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-2 font-semibold">GLPI</th>
                  <th className="px-3 py-2 font-semibold">SGC</th>
                  <th className="px-3 py-2 font-semibold">Fechamento</th>
                  <th className="px-3 py-2 font-semibold">Data</th>
                  <th className="px-3 py-2 font-semibold"> </th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((c) => (
                  <tr key={c.idcor ?? c.id_glpi} className="border-t border-line">
                    <td className="px-3 py-2" title={c.titulo ?? c.categoria ?? undefined}>
                      {c.id_glpi != null ? (
                        <Link
                          to={`/chamados/${c.id_glpi}`}
                          className="font-semibold text-accent hover:underline"
                        >
                          {c.id_glpi}
                        </Link>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-3 py-2 font-semibold">{displayValue(c.equipe_sgc)}</td>
                    <td className="px-3 py-2 font-semibold">{displayValue(c.equipe_correta)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{displayDate(c.data_deteccao)}</td>
                    <td className="px-3 py-2">
                      {c.id_glpi != null ? (
                        <button
                          type="button"
                          className="text-xs font-semibold text-accent hover:underline"
                          onClick={() => onSimulate(c.id_glpi as number)}
                        >
                          Simular
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} totalPages={totalPages} onPage={setPage} />
        </>
      )}
    </>
  )
}

function QualityTab() {
  const acc = useQuery({
    queryKey: ['ml-accuracy'],
    queryFn: ({ signal }) => fetchMlAccuracy(signal),
  })

  if (acc.isLoading) return <LoadingState label="Carregando qualidade…" />
  if (acc.isError) {
    return <ErrorState message={acc.error.message} onRetry={() => void acc.refetch()} />
  }

  const a = acc.data
  const emptyAccuracy = !a || a.avaliados === 0

  return (
    <>
      {emptyAccuracy ? (
        <p className="mb-3 text-sm text-muted">
          Sem fechamentos cruzados com o log.{' '}
          <Link to="/agendamentos" className="font-semibold text-accent hover:underline">
            Agendamentos
          </Link>
        </p>
      ) : null}

      <section className="overflow-x-auto rounded-xl border border-line bg-panel p-4 shadow-sm">
        <h2 className="mb-2 font-display text-sm font-semibold">Por método</h2>
        {!a?.by_method.length ? (
          <EmptyState description="Sem dados." />
        ) : (
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase text-muted">
              <tr>
                <th className="px-2 py-2">Método</th>
                <th className="px-2 py-2">Avaliados</th>
                <th className="px-2 py-2">Acertos</th>
                <th className="px-2 py-2">Erros</th>
                <th className="px-2 py-2">Taxa</th>
              </tr>
            </thead>
            <tbody>
              {a.by_method.map((row) => (
                <tr key={row.metodo} className="border-t border-line">
                  <td className="px-2 py-2">
                    <MethodBadge method={row.metodo} />
                  </td>
                  <td className="px-2 py-2">{row.avaliados}</td>
                  <td className="px-2 py-2">{row.acertos}</td>
                  <td className="px-2 py-2">{row.erros}</td>
                  <td className="px-2 py-2">
                    {row.taxa_pct != null ? `${row.taxa_pct.toLocaleString('pt-BR')}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="mt-4 overflow-x-auto rounded-xl border border-line bg-panel p-4 shadow-sm">
        <h2 className="mb-2 font-display text-sm font-semibold">SGC → fechamento</h2>
        {!a?.error_pairs.length ? (
          <EmptyState description="Nenhum par." />
        ) : (
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase text-muted">
              <tr>
                <th className="px-2 py-2">Previu</th>
                <th className="px-2 py-2">Fechou</th>
                <th className="px-2 py-2">Qtd</th>
              </tr>
            </thead>
            <tbody>
              {a.error_pairs.map((p) => (
                <tr key={`${p.equipe_sgc}-${p.equipe_correta}`} className="border-t border-line">
                  <td className="px-2 py-2 font-semibold">{p.equipe_sgc}</td>
                  <td className="px-2 py-2 font-semibold">{p.equipe_correta}</td>
                  <td className="px-2 py-2">{p.quantidade}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}

function LogsTab() {
  const [page, setPage] = useState(1)
  const [metodo, setMetodo] = useState('')
  const [equipe, setEquipe] = useState('')
  const [rejeitados, setRejeitados] = useState(false)
  const [search, setSearch] = useState('')
  const pageSize = 20

  const query = useQuery({
    queryKey: ['ml-logs', page, pageSize, metodo, equipe, rejeitados, search],
    queryFn: ({ signal }) =>
      fetchMlLogs({ page, pageSize, metodo, equipe, rejeitados, search }, signal),
    placeholderData: (prev) => prev,
  })
  const totalPages = Math.max(1, Math.ceil((query.data?.total ?? 0) / pageSize))

  return (
    <>
      <div className="mb-3 grid gap-3 sm:grid-cols-4">
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Método</span>
          <select
            className="w-full rounded-lg border border-line bg-panel px-3 py-2"
            value={metodo}
            onChange={(e) => {
              setMetodo(e.target.value)
              setPage(1)
            }}
          >
            {METHOD_FILTERS.map((m) => (
              <option key={m || 'all'} value={m}>
                {m ? (resolveMethodBadge(m)?.label ?? m) : 'Todos'}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Equipe</span>
          <input
            className="w-full rounded-lg border border-line bg-panel px-3 py-2"
            value={equipe}
            onChange={(e) => {
              setEquipe(e.target.value)
              setPage(1)
            }}
            placeholder="N1"
            maxLength={5}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Busca</span>
          <input
            className="w-full rounded-lg border border-line bg-panel px-3 py-2"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            placeholder="ID ou categoria"
          />
        </label>
        <label className="flex items-end gap-2 pb-2 text-sm">
          <input
            type="checkbox"
            checked={rejeitados}
            onChange={(e) => {
              setRejeitados(e.target.checked)
              setPage(1)
            }}
          />
          Rejeitados
        </label>
      </div>

      {query.isLoading ? (
        <LoadingState label="Carregando log…" />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !query.data?.items.length ? (
        <EmptyState title="Nenhum log" description="Ajuste os filtros." />
      ) : (
        <>
          <p className="mb-2 text-sm text-muted">{query.data.total.toLocaleString('pt-BR')} registros</p>
          <div className="overflow-x-auto rounded-xl border border-line bg-panel shadow-sm">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-canvas/80 text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-2 font-semibold">GLPI</th>
                  <th className="px-3 py-2 font-semibold">Método</th>
                  <th className="px-3 py-2 font-semibold">Equipe</th>
                  <th className="px-3 py-2 font-semibold">Conf. / margem</th>
                  <th className="px-3 py-2 font-semibold">Rejeição</th>
                  <th className="px-3 py-2 font-semibold">Data</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((row) => (
                  <tr
                    key={row.idml ?? `${row.id_glpi}-${row.data_registro}`}
                    className="border-t border-line"
                  >
                    <td className="px-3 py-2" title={row.categoria ?? undefined}>
                      {row.id_glpi != null ? (
                        <Link
                          to={`/chamados/${row.id_glpi}`}
                          className="font-semibold text-accent hover:underline"
                        >
                          {row.id_glpi}
                        </Link>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <MethodBadge method={row.metodo} />
                    </td>
                    <td className="px-3 py-2">{displayValue(row.equipe_prevista)}</td>
                    <td className="px-3 py-2">
                      {fmtScore(row.confianca)} / {fmtScore(row.margem)}
                    </td>
                    <td
                      className="max-w-[14rem] truncate px-3 py-2"
                      title={row.motivo_rejeicao ?? undefined}
                    >
                      {row.motivo_rejeicao ? displayValue(row.motivo_rejeicao) : '—'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">{displayDate(row.data_registro)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} totalPages={totalPages} onPage={setPage} />
        </>
      )}
    </>
  )
}

function SimulateTab({ initialTicketId }: { initialTicketId: number | null }) {
  const [ticketId, setTicketId] = useState(
    initialTicketId != null ? String(initialTicketId) : '',
  )
  const [titulo, setTitulo] = useState('')
  const [categoria, setCategoria] = useState('')
  const [descricao, setDescricao] = useState('')
  const [localizacao, setLocalizacao] = useState('')
  const [loadedLog, setLoadedLog] = useState<MlLogEntry | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadBusy, setLoadBusy] = useState(false)

  async function loadFromTicket(id: number) {
    setLoadError(null)
    setLoadBusy(true)
    try {
      const ticket = await fetchTicket(id)
      setTitulo(ticket.titulo ?? '')
      setCategoria(ticket.categoria ?? '')
      setDescricao(ticket.descricao ?? '')
      setLocalizacao(ticket.ml_log?.localizacao ?? '')
      setLoadedLog(ticket.ml_log)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Chamado não encontrado.')
      setLoadedLog(null)
    } finally {
      setLoadBusy(false)
    }
  }

  useEffect(() => {
    if (initialTicketId == null) return
    setTicketId(String(initialTicketId))
    void loadFromTicket(initialTicketId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialTicketId])

  const mut = useMutation({
    mutationFn: () =>
      simulateMl({
        titulo: titulo.trim(),
        categoria: categoria.trim() || undefined,
        descricao: descricao.trim() || undefined,
        localizacao: localizacao.trim() || undefined,
      }),
  })

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <form
        className="space-y-3 rounded-xl border border-line bg-panel p-4 shadow-sm"
        onSubmit={(e) => {
          e.preventDefault()
          if (titulo.trim()) mut.mutate()
        }}
      >
        <div className="flex flex-wrap items-end gap-2">
          <label className="block min-w-[8rem] flex-1 text-sm">
            <span className="mb-1 block text-xs font-semibold uppercase text-muted">ID GLPI</span>
            <input
              className="w-full rounded-lg border border-line bg-canvas px-3 py-2"
              value={ticketId}
              inputMode="numeric"
              onChange={(e) => setTicketId(e.target.value.replace(/[^\d]/g, ''))}
            />
          </label>
          <button
            type="button"
            disabled={loadBusy || !ticketId}
            className="rounded-lg border border-line px-3 py-2 text-sm font-semibold text-accent hover:bg-canvas disabled:opacity-50"
            onClick={() => void loadFromTicket(Number(ticketId))}
          >
            {loadBusy ? '…' : 'Carregar'}
          </button>
        </div>
        {loadError ? <p className="text-sm text-danger">{loadError}</p> : null}
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Título</span>
          <input
            required
            className="w-full rounded-lg border border-line bg-canvas px-3 py-2"
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
          />
        </label>
        <button
          type="submit"
          disabled={mut.isPending || !titulo.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {mut.isPending ? 'Simulando…' : 'Simular'}
        </button>
        {mut.isError ? <p className="text-sm text-danger">{mut.error.message}</p> : null}
      </form>

      <div className="space-y-4">
        <div className="rounded-xl border border-line bg-panel p-4 shadow-sm">
          <h2 className="font-display text-sm font-semibold">Simulação</h2>
          {!mut.data ? (
            <p className="mt-2 text-sm text-muted">Informe o título e simule.</p>
          ) : (
            <dl className="mt-2 grid gap-1 text-sm">
              <Row label="Método">
                <MethodBadge method={mut.data.metodo} />
              </Row>
              <Row label="Equipe">{displayValue(mut.data.equipe)}</Row>
              <Row label="Conf. / margem">
                {fmtScore(mut.data.confianca)} / {fmtScore(mut.data.margem)}
              </Row>
              <Row label="Rejeição">{displayValue(mut.data.motivo_rejeicao)}</Row>
              <Row label="Candidatos">
                {mut.data.tecnicos_elegiveis.length
                  ? mut.data.tecnicos_elegiveis.join(', ')
                  : 'nenhum'}
              </Row>
            </dl>
          )}
        </div>

        {loadedLog ? (
          <div className="rounded-xl border border-line bg-panel p-4 shadow-sm">
            <h2 className="font-display text-sm font-semibold">Log do chamado</h2>
            <dl className="mt-2 grid gap-1 text-sm">
              <Row label="Método">
                <MethodBadge method={loadedLog.metodo} />
              </Row>
              <Row label="Equipe">{displayValue(loadedLog.equipe_prevista)}</Row>
              <Row label="Conf. / margem">
                {fmtScore(loadedLog.confianca)} / {fmtScore(loadedLog.margem)}
              </Row>
              <Row label="Rejeição">{displayValue(loadedLog.motivo_rejeicao)}</Row>
              <Row label="Quando">{displayDate(loadedLog.data_registro)}</Row>
            </dl>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-2 border-t border-line py-1.5 first:border-t-0">
      <dt className="text-xs font-semibold uppercase text-muted">{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function Pager({
  page,
  totalPages,
  onPage,
}: {
  page: number
  totalPages: number
  onPage: (p: number) => void
}) {
  return (
    <div className="mt-3 flex gap-2">
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
        className="rounded-lg border border-line bg-panel px-3 py-1.5 text-sm font-medium disabled:opacity-40"
      >
        Anterior
      </button>
      <span className="self-center text-sm text-muted">
        {page}/{totalPages}
      </span>
      <button
        type="button"
        disabled={page >= totalPages}
        onClick={() => onPage(page + 1)}
        className="rounded-lg border border-line bg-panel px-3 py-1.5 text-sm font-medium disabled:opacity-40"
      >
        Próxima
      </button>
    </div>
  )
}
