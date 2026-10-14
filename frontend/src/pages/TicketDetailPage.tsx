import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import {
  fetchTeamsGuide,
  fetchTechnicians,
  fetchTicket,
  fetchTicketGlpiHint,
  reassignTicket,
} from '../api/endpoints'
import { ApiError, type TicketReassignResult } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { MethodBadge } from '../components/MethodBadge'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { Button } from '../components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
import { displayDate, displayValue } from '../lib/format'
import { cn } from '../lib/utils'

function Field({
  label,
  value,
  highlight,
  hint,
}: {
  label: string
  value: string
  highlight?: boolean
  hint?: string
}) {
  return (
    <div
      className={
        highlight
          ? 'rounded-lg border border-emerald-300 bg-emerald-50/80 px-2 py-1.5'
          : undefined
      }
    >
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
        {label}
        {hint ? (
          <span className="ml-2 font-medium normal-case tracking-normal text-emerald-800">
            {hint}
          </span>
        ) : null}
      </dt>
      <dd className="mt-1 text-sm text-ink">{value}</dd>
    </div>
  )
}

function CheckRow({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-center gap-2 text-sm">
      <span
        className={
          'inline-flex h-5 min-w-5 items-center justify-center rounded-full text-xs font-bold ' +
          (ok ? 'bg-emerald-600 text-white' : 'bg-amber-200 text-amber-950')
        }
        aria-hidden
      >
        {ok ? '✓' : '!'}
      </span>
      <span>
        {label}: <strong>{ok ? 'sim' : 'não'}</strong>
      </span>
    </li>
  )
}

function MissingInSgcPanel({ ticketId }: { ticketId: number }) {
  const [asked, setAsked] = useState(false)
  const hintQuery = useQuery({
    queryKey: ['ticket-glpi-hint', ticketId],
    queryFn: ({ signal }) => fetchTicketGlpiHint(ticketId, signal),
    enabled: asked && Number.isFinite(ticketId) && ticketId >= 1,
    retry: 1,
  })

  return (
    <div>
      <EmptyState
        title={`Chamado #${ticketId} não está no SGC`}
        description="Esse ID não existe em Tb_Ticket_new. Pode ter sido atribuído só no GLPI (fora do robô)."
      />
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
          disabled={asked && hintQuery.isFetching}
          onClick={() => setAsked(true)}
        >
          {hintQuery.isFetching ? 'Consultando GLPI…' : 'Consultar no GLPI'}
        </button>
      </div>
      {hintQuery.isError ? (
        <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">
          {hintQuery.error instanceof ApiError
            ? hintQuery.error.message
            : 'Falha ao consultar GLPI.'}
        </p>
      ) : null}
      {hintQuery.data ? (
        <section className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-4 shadow-sm">
          <h2 className="font-display text-sm font-semibold text-amber-950">
            Por que Fulano? (consulta GLPI)
          </h2>
          <p className="mt-2 text-sm text-amber-950">{hintQuery.data.mensagem}</p>
          {hintQuery.data.encontrado ? (
            <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs font-semibold uppercase text-muted">Título</dt>
                <dd>{displayValue(hintQuery.data.titulo)}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase text-muted">Técnico no GLPI</dt>
                <dd className="font-semibold">{displayValue(hintQuery.data.tecnico)}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase text-muted">Status</dt>
                <dd>
                  {displayValue(hintQuery.data.status_label)}
                  {hintQuery.data.status != null ? ` (${hintQuery.data.status})` : ''}
                </dd>
              </div>
            </dl>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}

export function TicketDetailPage() {
  const { ticketId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const id = Number(ticketId)
  const { hasMinProfile } = useAuth()
  const canReassign = hasMinProfile('ADMIN')
  const queryClient = useQueryClient()

  const [open, setOpen] = useState(
    () => canReassign && searchParams.get('direcionar') === '1',
  )
  const [reviewing, setReviewing] = useState(false)
  const [tab, setTab] = useState<'equipe' | 'pessoa'>('equipe')
  const [equipe, setEquipe] = useState('')
  const [tecnico, setTecnico] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [receipt, setReceipt] = useState<TicketReassignResult | null>(null)
  const [failMsg, setFailMsg] = useState<string | null>(null)
  const [highlightAssign, setHighlightAssign] = useState(false)

  const query = useQuery({
    queryKey: ['ticket', id],
    queryFn: ({ signal }) => fetchTicket(id, signal),
    enabled: Number.isFinite(id) && id >= 1,
    retry: (count, err) => {
      if (err instanceof ApiError && err.status === 404) return false
      return count < 2
    },
  })

  useEffect(() => {
    if (
      !canReassign ||
      searchParams.get('direcionar') !== '1' ||
      query.isLoading ||
      !query.data
    ) {
      return
    }
    const next = new URLSearchParams(searchParams)
    next.delete('direcionar')
    setSearchParams(next, { replace: true })
  }, [canReassign, query.data, query.isLoading, searchParams, setSearchParams])

  const teamsQuery = useQuery({
    queryKey: ['teams-guide'],
    queryFn: ({ signal }) => fetchTeamsGuide(signal),
    enabled: canReassign && open,
  })

  const techsQuery = useQuery({
    queryKey: ['technicians'],
    queryFn: ({ signal }) => fetchTechnicians(signal),
    enabled: canReassign && open,
  })

  const guideByEquipe = useMemo(() => {
    const map = new Map<string, { resumo: string; exemplos: string[]; ativos: number }>()
    for (const g of teamsQuery.data ?? []) {
      map.set(g.equipe.toUpperCase(), {
        resumo: g.resumo,
        exemplos: g.exemplos ?? [],
        ativos: g.tecnicos_ativos ?? 0,
      })
    }
    return map
  }, [teamsQuery.data])

  const activeTeams = useMemo(() => {
    const fromGuide = (teamsQuery.data ?? [])
      .filter((t) => (t.tecnicos_ativos ?? 0) > 0 && t.equipe?.trim())
      .map((t) => t.equipe.trim().toUpperCase())
    if (fromGuide.length) return fromGuide.sort()
    return Array.from(guideByEquipe.keys()).sort()
  }, [teamsQuery.data, guideByEquipe])

  const activeLogins = useMemo(() => {
    const items = techsQuery.data ?? []
    return items
      .filter((t) => String(t.sit) === '1')
      .map((t) => t.usuario)
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b, 'pt-BR'))
  }, [techsQuery.data])

  useEffect(() => {
    if (!highlightAssign) return
    const t = window.setTimeout(() => setHighlightAssign(false), 8000)
    return () => window.clearTimeout(t)
  }, [highlightAssign])

  const mutation = useMutation({
    mutationFn: () => {
      if (tab === 'equipe') {
        return reassignTicket(id, { mode: 'equipe', equipe })
      }
      return reassignTicket(id, { mode: 'pessoa', tecnico })
    },
    onSuccess: async (res) => {
      setOpen(false)
      setFormError(null)
      setFailMsg(null)
      setReceipt(res)
      setHighlightAssign(true)
      await queryClient.invalidateQueries({ queryKey: ['ticket', id] })
      await queryClient.invalidateQueries({ queryKey: ['tickets'] })
      await queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof ApiError ? err.message : 'Falha ao enviar o chamado.'
      setFormError(msg)
      setFailMsg(msg)
      setReceipt(null)
    },
  })

  if (!Number.isFinite(id) || id < 1) {
    return <ErrorState title="Chamado inválido" message="Informe um ID numérico válido." />
  }

  if (query.isLoading) return <LoadingState label="Carregando chamado…" />
  if (query.isError) {
    const missing = query.error instanceof ApiError && query.error.status === 404
    if (missing) {
      return (
        <div>
          <Link
            to="/chamados"
            className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            Voltar aos chamados
          </Link>
          <MissingInSgcPanel ticketId={id} />
        </div>
      )
    }
    return (
      <ErrorState
        message={query.error.message}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const t = query.data!
  const ml = t.ml_log
  const exp = t.explicacao
  const canConfirm =
    tab === 'equipe' ? Boolean(equipe.trim()) : Boolean(tecnico.trim())

  const deLabel = [
    receipt?.equipe_anterior || '—',
    receipt?.tecnico_anterior || '—',
  ].join(' / ')
  const paraLabel = [receipt?.equipe || '—', receipt?.tecnico || '—'].join(' / ')
  const selectedGuide = equipe ? guideByEquipe.get(equipe.toUpperCase()) : undefined

  return (
    <div>
      <Link
        to="/chamados"
        className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Voltar aos chamados
      </Link>
      <PageHeader
        title={`Chamado #${displayValue(t.id)}`}
        description={
          canReassign
            ? 'Confira o chamado e, se necessário, altere a equipe ou a pessoa responsável.'
            : 'Você pode consultar este chamado, mas não tem permissão para alterar o destino.'
        }
        actions={
          canReassign ? (
            <Button
              type="button"
              onClick={() => {
                setOpen(true)
                setTab('equipe')
                setEquipe('')
                setTecnico('')
                setReviewing(false)
                setFormError(null)
              }}
            >
              Alterar destino
            </Button>
          ) : undefined
        }
      />

      {receipt ? (
        <section
          className="mb-4 rounded-xl border border-emerald-300 bg-emerald-50 p-4 shadow-sm"
          aria-live="polite"
        >
          <h2 className="font-display text-sm font-semibold text-emerald-950">
            Comprovante da reatribuição
          </h2>
          <p className="mt-1 text-sm text-emerald-900">{receipt.message}</p>
          <p className="mt-2 text-xs text-emerald-900/80">
            De: <strong>{deLabel}</strong>
            <span className="mx-2">→</span>
            Para: <strong>{paraLabel}</strong>
          </p>
          <ul className="mt-3 space-y-1.5 text-emerald-950">
            <CheckRow ok={Boolean(receipt.glpi_ok)} label="GLPI atualizado" />
            <CheckRow ok={Boolean(receipt.sgc_ok ?? true)} label="SGC atualizado" />
            <CheckRow
              ok={Boolean(receipt.notification_created)}
              label="Notificação ao destino"
            />
            <CheckRow
              ok={Boolean(receipt.notification_admin)}
              label="Aviso no seu sino"
            />
          </ul>
          <button
            type="button"
            className="mt-3 text-xs font-semibold text-emerald-900 underline"
            onClick={() => setReceipt(null)}
          >
            Fechar comprovante
          </button>
        </section>
      ) : null}

      {failMsg && !open ? (
        <section className="mb-4 rounded-xl border border-rose-300 bg-rose-50 p-4 shadow-sm">
          <h2 className="font-display text-sm font-semibold text-rose-950">
            Não foi possível reatribuir
          </h2>
          <p className="mt-1 text-sm text-rose-900">{failMsg}</p>
          <button
            type="button"
            className="mt-3 text-xs font-semibold text-rose-900 underline"
            onClick={() => setFailMsg(null)}
          >
            Fechar
          </button>
        </section>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="rounded-xl border border-line bg-panel p-5 shadow-sm lg:col-span-2">
          <h2 className="font-display text-sm font-semibold">Dados do chamado</h2>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label="Título" value={displayValue(t.titulo)} />
            <Field label="Categoria" value={displayValue(t.categoria)} />
            <Field
              label="Equipe"
              value={displayValue(t.equipe)}
              highlight={highlightAssign}
              hint={highlightAssign ? 'atualizado agora' : undefined}
            />
            <Field
              label="Técnico"
              value={displayValue(t.tecnico)}
              highlight={highlightAssign}
              hint={highlightAssign ? 'atualizado agora' : undefined}
            />
            <Field label="Solicitante" value={displayValue(t.solicitante)} />
            <Field label="Situação" value={displayValue(t.sit)} />
            <Field label="Data" value={displayDate(t.data)} />
            <Field label="Prazo solução" value={displayDate(t.dat_sol)} />
          </dl>
          <div className="mt-6">
            <h3 className="text-xs font-semibold uppercase text-muted">Descrição</h3>
            <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-canvas/50 p-3 font-sans text-sm leading-relaxed text-ink">
              {displayValue(
                t.descricao
                  ? t.descricao.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
                  : null,
              )}
            </pre>
          </div>
        </section>

        <div className="space-y-4">
          <section className="rounded-xl border border-line bg-panel p-5 shadow-sm">
            <h2 className="font-display text-sm font-semibold">Por que foi atribuído?</h2>
            {exp ? (
              <div className="mt-3 space-y-3 text-sm text-ink">
                {exp.motivo_pessoa ? (
                  <div className="rounded-lg border border-accent/30 bg-accent-soft/40 px-3 py-2">
                    <p className="text-xs font-semibold uppercase text-muted">
                      Por que Fulano?
                    </p>
                    <p className="mt-1 font-medium leading-relaxed">{exp.motivo_pessoa}</p>
                  </div>
                ) : null}
                <p className="leading-relaxed">{exp.motivo_resumo || 'Sem detalhes.'}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold uppercase text-muted">Método</span>
                  <MethodBadge method={exp.metodo ?? t.metodo ?? ml?.metodo} />
                </div>
                {exp.keywords_matched?.length ? (
                  <div>
                    <p className="text-xs font-semibold uppercase text-muted">
                      Palavras que bateram
                    </p>
                    <p className="mt-1 text-sm">{exp.keywords_matched.join(', ')}</p>
                  </div>
                ) : null}
                {exp.confianca != null ? (
                  <p className="text-xs text-muted">
                    Confiança ML: {displayValue(exp.confianca)}
                    {exp.equipe_2a ? ` · 2ª opção: ${exp.equipe_2a}` : ''}
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted">
                Sem explicação disponível para este chamado.
              </p>
            )}
          </section>

          <section className="rounded-xl border border-line bg-panel p-5 shadow-sm">
            <h2 className="font-display text-sm font-semibold">Classificação (ML Log)</h2>
            <div className="mt-3">
              <p className="text-xs font-semibold uppercase text-muted">Método</p>
              <div className="mt-1">
                <MethodBadge method={t.metodo ?? ml?.metodo} />
              </div>
            </div>
            {!ml ? (
              <p className="mt-4 text-sm text-muted">Detalhes do log: Não disponível</p>
            ) : (
              <dl className="mt-4 space-y-4">
                <Field label="Equipe prevista" value={displayValue(ml.equipe_prevista)} />
                <Field label="Equipe ML" value={displayValue(ml.equipe_ml)} />
                <Field label="2ª opção" value={displayValue(ml.equipe_2a)} />
                <Field label="Confiança" value={displayValue(ml.confianca)} />
                <Field label="Margem" value={displayValue(ml.margem)} />
                <Field label="Motivo rejeição" value={displayValue(ml.motivo_rejeicao)} />
                <Field label="Localização" value={displayValue(ml.localizacao)} />
                <Field label="Registro" value={displayDate(ml.data_registro)} />
              </dl>
            )}
          </section>
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
            <DialogTitle className="pr-8 font-display text-lg font-semibold text-ink">
              {reviewing ? 'Confirme o novo destino' : `Para onde deve ir o chamado #${id}?`}
            </DialogTitle>
            <DialogDescription className="mt-1 text-sm text-muted">
              Esta alteração vale somente para este chamado. Chamados novos continuam sendo
              direcionados automaticamente pelo robô.
            </DialogDescription>

            {!reviewing ? (
              <Tabs
                value={tab}
                onValueChange={(value) => {
                  setTab(value as 'equipe' | 'pessoa')
                  setFormError(null)
                  setReviewing(false)
                }}
              >
                <TabsList className="mt-4">
                  <TabsTrigger value="equipe">
                    <span className="block">Enviar para uma equipe</span>
                    <span className="mt-1 block text-xs font-normal">O sistema escolhe um técnico disponível</span>
                  </TabsTrigger>
                  <TabsTrigger value="pessoa">
                    <span className="block">Escolher uma pessoa</span>
                    <span className="mt-1 block text-xs font-normal">Você define o técnico responsável</span>
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="equipe" className="mt-4">
                  <p className="mb-2 text-sm text-muted">
                    O sistema encaminha o chamado a um técnico ativo e disponível da equipe. As dicas ajudam a escolher a equipe certa.
                  </p>
                  {teamsQuery.isLoading ? (
                    <p className="text-sm text-muted">Carregando equipes…</p>
                  ) : activeTeams.length === 0 ? (
                    <p className="text-sm text-muted">Nenhuma equipe com técnico disponível.</p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {activeTeams.map((eq) => {
                        const guide = guideByEquipe.get(eq)
                        const hint =
                          guide?.exemplos?.slice(0, 3).join(', ') ||
                          guide?.resumo ||
                          'Equipe do SGC'
                        return (
                          <Button
                            key={eq}
                            type="button"
                            variant={equipe === eq ? 'secondary' : 'outline'}
                            aria-pressed={equipe === eq}
                            title={guide?.resumo || hint}
                            onClick={() => setEquipe(eq)}
                            className={cn(
                              'h-auto w-full justify-start px-3 py-2 text-left',
                              equipe === eq && 'ring-1 ring-accent/40',
                            )}
                          >
                            <span>
                              <span className="block font-semibold">Equipe {eq}</span>
                              <span className="mt-0.5 block text-xs font-normal text-muted">
                                {guide?.resumo || hint}
                                {guide && guide.ativos > 0 ? ` · ${guide.ativos} disponíveis` : ''}
                              </span>
                            </span>
                          </Button>
                        )
                      })}
                    </div>
                  )}
                  {selectedGuide ? (
                    <p className="mt-3 rounded-md border border-line bg-canvas/60 px-3 py-2 text-xs text-muted">
                      A equipe <strong className="text-ink">{equipe}</strong> atende:{' '}
                      {(selectedGuide.exemplos.slice(0, 6).join(', ') ||
                        selectedGuide.resumo) + '.'}
                    </p>
                  ) : null}
                </TabsContent>
                <TabsContent value="pessoa" className="mt-4">
                  <label className="block">
                    <span className="mb-1 block text-sm font-semibold text-ink">
                      Selecione a pessoa responsável
                    </span>
                    <Select value={tecnico} onValueChange={setTecnico}>
                      <SelectTrigger aria-label="Técnico responsável">
                        <SelectValue placeholder="Selecione um técnico ativo" />
                      </SelectTrigger>
                      <SelectContent>
                        {activeLogins.map((login) => {
                          const tech = techsQuery.data?.find(
                            (item) => item.usuario.toUpperCase() === login.toUpperCase(),
                          )
                          return (
                            <SelectItem key={login} value={login}>
                              {login}{tech?.equipe ? ` · Equipe ${tech.equipe}` : ''}
                            </SelectItem>
                          )
                        })}
                      </SelectContent>
                    </Select>
                    <span className="mt-1 block text-xs text-muted">
                      O chamado será atribuído diretamente a essa pessoa.
                    </span>
                  </label>
                </TabsContent>
              </Tabs>
            ) : (
              <div className="mt-4 rounded-md border border-line bg-canvas p-4">
                <p className="text-xs font-semibold uppercase text-muted">Resumo da alteração</p>
                <dl className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
                  <div>
                    <dt className="text-xs text-muted">Destino atual</dt>
                    <dd className="mt-1 text-sm font-semibold text-ink">
                      {displayValue(t.equipe)} · {displayValue(t.tecnico)}
                    </dd>
                  </div>
                  <span className="hidden text-lg text-muted sm:block" aria-hidden>→</span>
                  <div>
                    <dt className="text-xs text-muted">Novo destino</dt>
                    <dd className="mt-1 text-sm font-semibold text-ink">
                      {tab === 'equipe'
                        ? `Equipe ${equipe} · técnico escolhido pelo sistema`
                        : `${tecnico}${techsQuery.data?.find((item) => item.usuario === tecnico)?.equipe ? ` · Equipe ${techsQuery.data.find((item) => item.usuario === tecnico)?.equipe}` : ''}`}
                    </dd>
                  </div>
                </dl>
              </div>
            )}

            {formError ? (
              <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">
                {formError}
              </p>
            ) : null}

            <div className="mt-5 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  if (reviewing) setReviewing(false)
                  else setOpen(false)
                }}
                disabled={mutation.isPending}
              >
                {reviewing ? 'Voltar e ajustar' : 'Cancelar'}
              </Button>
              <Button
                type="button"
                disabled={!canConfirm || mutation.isPending}
                onClick={() => {
                  if (reviewing) mutation.mutate()
                  else setReviewing(true)
                }}
              >
                {mutation.isPending
                  ? 'Atualizando chamado…'
                  : reviewing
                    ? 'Confirmar alteração'
                    : 'Revisar destino'}
              </Button>
            </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
