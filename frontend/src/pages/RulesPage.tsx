import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchRules, fetchTechnicians, saveRules } from '../api/endpoints'
import type { RuleItem } from '../api/types'
import { ApiError } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'

type Draft = {
  keywordsText: string
  equipe: string
  tecnico: string
}

function ruleToDraft(r: RuleItem): Draft {
  return {
    keywordsText: r.keywords.join(', '),
    equipe: r.equipe,
    tecnico: r.tecnico ?? '',
  }
}

function parseKeywords(text: string): string[] {
  return text
    .split(/[,;\n]+/)
    .map((k) => k.trim())
    .filter(Boolean)
}

export function RulesPage() {
  const { hasMinProfile } = useAuth()
  const canEdit = hasMinProfile('ADMIN')
  const queryClient = useQueryClient()
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [banner, setBanner] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)

  const query = useQuery({
    queryKey: ['rules'],
    queryFn: ({ signal }) => fetchRules(signal),
  })
  const techQuery = useQuery({
    queryKey: ['technicians'],
    queryFn: ({ signal }) => fetchTechnicians(signal),
    enabled: canEdit,
  })

  useEffect(() => {
    if (query.data && !dirty) {
      setDrafts(query.data.map(ruleToDraft))
    }
  }, [query.data, dirty])

  const activeLogins = useMemo(
    () =>
      (techQuery.data ?? [])
        .filter((t) => t.sit === '1')
        .map((t) => t.usuario)
        .sort((a, b) => a.localeCompare(b)),
    [techQuery.data],
  )

  const saveMut = useMutation({
    mutationFn: (rules: RuleItem[]) => saveRules(rules),
    onSuccess: async (saved) => {
      setDirty(false)
      setFormError(null)
      setBanner(`${saved.length} regra(s) gravada(s) em arqaux.txt (backup .bak criado).`)
      await queryClient.invalidateQueries({ queryKey: ['rules'] })
    },
    onError: (err: unknown) => {
      setFormError(err instanceof ApiError ? err.message : 'Falha ao salvar regras.')
    },
  })

  function updateDraft(index: number, patch: Partial<Draft>) {
    setDirty(true)
    setDrafts((prev) => prev.map((d, i) => (i === index ? { ...d, ...patch } : d)))
  }

  function addRule() {
    setDirty(true)
    setDrafts((prev) => [{ keywordsText: '', equipe: 'N1', tecnico: '' }, ...prev])
  }

  function removeRule(index: number) {
    setDirty(true)
    setDrafts((prev) => prev.filter((_, i) => i !== index))
  }

  function moveRule(index: number, dir: -1 | 1) {
    const next = index + dir
    if (next < 0 || next >= drafts.length) return
    setDirty(true)
    setDrafts((prev) => {
      const copy = [...prev]
      const tmp = copy[index]
      copy[index] = copy[next]
      copy[next] = tmp
      return copy
    })
  }

  function onSave() {
    setFormError(null)
    const rules: RuleItem[] = []
    for (let i = 0; i < drafts.length; i++) {
      const d = drafts[i]
      const keywords = parseKeywords(d.keywordsText)
      const equipe = d.equipe.trim().toUpperCase()
      if (!equipe || equipe.length > 5) {
        setFormError(`Linha ${i + 1}: equipe inválida (1–5 caracteres).`)
        return
      }
      if (!keywords.length) {
        setFormError(`Linha ${i + 1}: informe ao menos uma palavra-chave.`)
        return
      }
      rules.push({
        equipe,
        keywords,
        tecnico: d.tecnico.trim() || null,
      })
    }
    saveMut.mutate(rules)
  }

  function reload() {
    setDirty(false)
    setFormError(null)
    setBanner(null)
    void query.refetch()
  }

  return (
    <div>
      <PageHeader
        title="Regras de atribuição"
        description={
          canEdit
            ? 'Palavra-chave → equipe (e pessoa opcional). Ordem = prioridade. Grava no mesmo arqaux.txt do robô.'
            : 'Consulta das regras DIRETO do robô. Edição apenas para ADMIN.'
        }
      />

      {canEdit ? (
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-lg border border-accent bg-accent px-3 py-2 text-sm font-semibold text-white hover:opacity-90"
            onClick={addRule}
          >
            Nova regra
          </button>
          <button
            type="button"
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm font-semibold text-accent hover:bg-canvas disabled:opacity-60"
            disabled={!dirty || saveMut.isPending}
            onClick={onSave}
          >
            {saveMut.isPending ? 'Salvando…' : 'Salvar'}
          </button>
          <button
            type="button"
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm font-semibold text-muted hover:bg-canvas"
            onClick={reload}
          >
            Recarregar
          </button>
          <p className="basis-full text-xs text-muted">
            Ex.: palavras <span className="font-mono">AR CONDICIONADO</span>, equipe{' '}
            <span className="font-mono">N8</span>, pessoa opcional{' '}
            <span className="font-mono">fulano.silva</span> → linha{' '}
            <span className="font-mono">N8@fulano.silva-...</span>
          </p>
        </div>
      ) : null}

      {banner ? (
        <p className="mb-4 rounded-lg border border-accent/30 bg-ok-soft px-3 py-2 text-sm text-ink">
          {banner}
        </p>
      ) : null}
      {formError ? (
        <p className="mb-4 rounded-lg border border-danger/40 bg-danger-soft px-3 py-2 text-sm text-ink">
          {formError}
        </p>
      ) : null}

      {query.isLoading ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !drafts.length ? (
        <EmptyState
          title="Sem regras"
          description={
            canEdit
              ? 'Clique em Nova regra para começar (ou o arqaux.txt está vazio).'
              : 'Nenhuma regra carregada do arqaux.txt.'
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-panel shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-canvas/80 text-xs uppercase text-muted">
              <tr>
                <th className="px-3 py-3 font-semibold">#</th>
                <th className="px-3 py-3 font-semibold">Palavras-chave</th>
                <th className="px-3 py-3 font-semibold">Equipe</th>
                <th className="px-3 py-3 font-semibold">Pessoa (opcional)</th>
                {canEdit ? <th className="px-3 py-3 font-semibold">Ações</th> : null}
              </tr>
            </thead>
            <tbody>
              {drafts.map((d, index) => (
                <tr key={index} className="border-t border-line align-top">
                  <td className="px-3 py-2.5 text-xs text-muted">{index + 1}</td>
                  <td className="px-3 py-2.5 min-w-[16rem]">
                    {canEdit ? (
                      <textarea
                        value={d.keywordsText}
                        onChange={(e) => updateDraft(index, { keywordsText: e.target.value })}
                        rows={2}
                        className="w-full rounded-lg border border-line bg-canvas px-2 py-1.5 text-sm"
                        placeholder="AR CONDICIONADO, LÂMPADA"
                      />
                    ) : (
                      <span>{d.keywordsText}</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    {canEdit ? (
                      <input
                        value={d.equipe}
                        onChange={(e) => updateDraft(index, { equipe: e.target.value })}
                        maxLength={5}
                        className="w-20 rounded-lg border border-line bg-canvas px-2 py-1.5 font-mono text-sm uppercase"
                      />
                    ) : (
                      <span className="font-mono">{d.equipe}</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    {canEdit ? (
                      <select
                        value={d.tecnico}
                        onChange={(e) => updateDraft(index, { tecnico: e.target.value })}
                        className="max-w-[12rem] rounded-lg border border-line bg-canvas px-2 py-1.5 text-sm"
                      >
                        <option value="">(qualquer da equipe)</option>
                        {d.tecnico && !activeLogins.includes(d.tecnico) ? (
                          <option value={d.tecnico}>{d.tecnico} (atual)</option>
                        ) : null}
                        {activeLogins.map((u) => (
                          <option key={u} value={u}>
                            {u}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="font-mono text-xs">{d.tecnico || '—'}</span>
                    )}
                  </td>
                  {canEdit ? (
                    <td className="px-3 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        <button
                          type="button"
                          className="rounded border border-line px-2 py-1 text-xs hover:bg-canvas"
                          onClick={() => moveRule(index, -1)}
                          disabled={index === 0}
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          className="rounded border border-line px-2 py-1 text-xs hover:bg-canvas"
                          onClick={() => moveRule(index, 1)}
                          disabled={index === drafts.length - 1}
                        >
                          ↓
                        </button>
                        <button
                          type="button"
                          className="rounded border border-danger/40 px-2 py-1 text-xs text-danger hover:bg-danger-soft"
                          onClick={() => removeRule(index)}
                        >
                          Excluir
                        </button>
                      </div>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
