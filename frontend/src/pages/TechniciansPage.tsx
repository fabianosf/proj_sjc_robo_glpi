import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchTeams,
  fetchTechnicians,
  importMatriculasCsv,
  redirectTechnician,
  syncMatriculas,
  updateTechnician,
} from '../api/endpoints'
import type { TechnicianItem } from '../api/types'
import { ApiError } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { useDebounce } from '../hooks/useDebounce'
import { displayNumber, displayValue } from '../lib/format'

type EditForm = {
  equipe: string
  sit: string
  matricula: string
  h1: string
  h2: string
  empresa: string
}

function toForm(t: TechnicianItem): EditForm {
  return {
    equipe: t.equipe ?? '',
    sit: t.sit === '0' ? '0' : '1',
    matricula: t.matricula ?? '',
    h1: t.h1 ?? '',
    h2: t.h2 ?? '',
    empresa: t.empresa ?? '',
  }
}

function displayMatricula(m: string | null | undefined): string {
  if (!m || m === '0' || m === '00000') return 'sem matrícula'
  return m
}

export function TechniciansPage() {
  const { hasMinProfile } = useAuth()
  const canEdit = hasMinProfile('ADMIN')
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState('')
  const debounced = useDebounce(filter, 300)
  const [editing, setEditing] = useState<TechnicianItem | null>(null)
  const [form, setForm] = useState<EditForm | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [redirectFrom, setRedirectFrom] = useState<TechnicianItem | null>(null)
  const [redirectTo, setRedirectTo] = useState('')
  const [redirectOff, setRedirectOff] = useState(true)
  const [banner, setBanner] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['technicians'],
    queryFn: ({ signal }) => fetchTechnicians(signal),
  })
  const teamsQuery = useQuery({
    queryKey: ['teams'],
    queryFn: ({ signal }) => fetchTeams(signal),
    enabled: canEdit,
  })

  const mutation = useMutation({
    mutationFn: ({ usuario, body }: { usuario: string; body: EditForm }) =>
      updateTechnician(usuario, {
        equipe: body.equipe.trim(),
        sit: body.sit,
        matricula: body.matricula.trim(),
        h1: body.h1.trim(),
        h2: body.h2.trim(),
        empresa: body.empresa.trim(),
      }),
    onSuccess: async () => {
      setEditing(null)
      setForm(null)
      setFormError(null)
      setBanner('Técnico atualizado.')
      await queryClient.invalidateQueries({ queryKey: ['technicians'] })
      await queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) setFormError(err.message)
      else setFormError('Falha ao salvar.')
    },
  })

  const redirectMut = useMutation({
    mutationFn: () =>
      redirectTechnician({
        de: redirectFrom!.usuario,
        para: redirectTo.trim(),
        desativar_origem: redirectOff,
      }),
    onSuccess: async (res) => {
      setRedirectFrom(null)
      setRedirectTo('')
      const failed = res.glpi_failed_ids ?? []
      const failTxt =
        failed.length > 0
          ? `; GLPI falhou em ${failed.length}: #${failed.slice(0, 8).join(', #')}` +
            (failed.length > 8 ? '…' : '')
          : ''
      setBanner(
        `Redirecionado ${res.de} → ${res.para} (${res.tickets_moved} ticket(s) local(is)` +
          `${res.origem_desativada ? '; origem desativada' : ''}` +
          `${res.notification_created ? '; notificação enviada' : ''}` +
          `${failTxt}).`,
      )
      await queryClient.invalidateQueries({ queryKey: ['technicians'] })
      await queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
    onError: (err: unknown) => {
      setFormError(err instanceof ApiError ? err.message : 'Falha ao redirecionar.')
    },
  })

  const syncMut = useMutation({
    mutationFn: () => syncMatriculas(),
    onSuccess: async (res) => {
      setBanner(
        `Matrículas: ${res.updated} atualizada(s) ` +
          `(Oracle ${res.from_oracle ?? 0} · GLPI ${res.from_glpi ?? 0} · ` +
          `AD ${res.from_ad ?? 0} · mapa ${res.from_map ?? 0}), ` +
          `${res.skipped} sem fonte. ` +
          (res.details.slice(0, 5).join(' · ') || ''),
      )
      await queryClient.invalidateQueries({ queryKey: ['technicians'] })
    },
    onError: (err: unknown) => {
      setBanner(err instanceof ApiError ? err.message : 'Falha ao sincronizar matrículas.')
    },
  })

  const importMut = useMutation({
    mutationFn: (content: string) => importMatriculasCsv(content),
    onSuccess: async (res) => {
      setBanner(
        `CSV: ${res.updated} atualizada(s), ${res.not_found} não encontrado(s), ` +
          `${res.invalid} inválida(s). ` +
          (res.details.slice(0, 6).join(' · ') || ''),
      )
      await queryClient.invalidateQueries({ queryKey: ['technicians'] })
    },
    onError: (err: unknown) => {
      setBanner(err instanceof ApiError ? err.message : 'Falha ao importar CSV.')
    },
  })

  function onCsvFile(file: File | null) {
    if (!file) return
    setBanner(null)
    const reader = new FileReader()
    reader.onload = () => {
      const text = String(reader.result ?? '')
      if (!text.trim()) {
        setBanner('Arquivo CSV vazio.')
        return
      }
      importMut.mutate(text)
    }
    reader.onerror = () => setBanner('Não foi possível ler o arquivo.')
    reader.readAsText(file, 'UTF-8')
  }

  function downloadCsvTemplate() {
    const sample =
      'usuario;matricula\n' +
      'fulano.silva;12345\n' +
      'ciclano.souza;67890\n'
    const blob = new Blob([sample], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'matriculas_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const filtered = useMemo(() => {
    const list = query.data ?? []
    const q = debounced.trim().toLowerCase()
    if (!q) return list
    return list.filter(
      (t) =>
        t.usuario.toLowerCase().includes(q) ||
        (t.equipe ?? '').toLowerCase().includes(q) ||
        (t.empresa ?? '').toLowerCase().includes(q) ||
        (t.matricula ?? '').toLowerCase().includes(q),
    )
  }, [query.data, debounced])

  const matriculaStats = useMemo(() => {
    const list = query.data ?? []
    const withMat = list.filter(
      (t) => t.matricula && t.matricula !== '0' && t.matricula !== '00000',
    ).length
    return { total: list.length, withMat, missing: list.length - withMat }
  }, [query.data])

  const activeLogins = useMemo(
    () =>
      (query.data ?? [])
        .filter((t) => t.sit === '1')
        .map((t) => t.usuario)
        .sort((a, b) => a.localeCompare(b)),
    [query.data],
  )

  const teamOptions = useMemo(() => {
    const fromApi = (teamsQuery.data ?? []).map((t) => t.equipe).filter(Boolean)
    const fromRows = (query.data ?? []).map((t) => t.equipe ?? '').filter(Boolean)
    return Array.from(new Set([...fromApi, ...fromRows, 'N1', 'N2', 'N3'])).sort()
  }, [teamsQuery.data, query.data])

  function openEdit(t: TechnicianItem) {
    setEditing(t)
    setForm(toForm(t))
    setFormError(null)
    setBanner(null)
  }

  function saveEdit() {
    if (!editing || !form) return
    if (!form.equipe.trim()) {
      setFormError('Informe a equipe (máx. 5 caracteres).')
      return
    }
    if (form.equipe.trim().length > 5) {
      setFormError('Equipe deve ter no máximo 5 caracteres.')
      return
    }
    mutation.mutate({ usuario: editing.usuario, body: form })
  }

  return (
    <div>
      <PageHeader
        title="Técnicos"
        description={
          canEdit
            ? 'Edite equipe/matrícula, importe CSV, redirecione login ou aplique o mapa do .env.'
            : 'Cadastro operacional. Edição apenas para ADMIN.'
        }
      />

      {canEdit ? (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <label className="cursor-pointer rounded-lg border border-accent bg-accent px-3 py-2 text-sm font-semibold text-white hover:opacity-90">
            {importMut.isPending ? 'Importando…' : 'Importar CSV'}
            <input
              type="file"
              accept=".csv,text/csv,text/plain"
              className="hidden"
              disabled={importMut.isPending}
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null
                onCsvFile(f)
                e.target.value = ''
              }}
            />
          </label>
          <button
            type="button"
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm font-semibold text-accent hover:bg-canvas"
            onClick={downloadCsvTemplate}
          >
            Baixar modelo CSV
          </button>
          <button
            type="button"
            className="rounded-lg border border-line bg-panel px-3 py-2 text-sm font-semibold text-accent hover:bg-canvas disabled:opacity-60"
            disabled={syncMut.isPending}
            onClick={() => {
              setBanner(null)
              syncMut.mutate()
            }}
          >
            {syncMut.isPending ? 'Sincronizando…' : 'Sincronizar Oracle/GLPI/AD'}
          </button>
          <p className="basis-full text-xs text-muted sm:basis-auto sm:self-center">
            Prioridade: Oracle Globus (<span className="font-mono">CHAPAFUNC</span>) →
            GLPI Número administrativo → AD <span className="font-mono">employeeNumber</span> →
            mapa .env / CSV. Valores <span className="font-mono">00000</span> contam como vazios.
          </p>
        </div>
      ) : null}

      {query.data ? (
        <p className="mb-3 text-xs text-muted">
          Matrículas preenchidas:{' '}
          <span className="font-semibold text-ink">
            {matriculaStats.withMat}/{matriculaStats.total}
          </span>
          {matriculaStats.missing > 0
            ? ` · ${matriculaStats.missing} sem matrícula (aparecem como “sem matrícula”)`
            : null}
        </p>
      ) : null}

      {banner ? (
        <p className="mb-4 rounded-lg border border-accent/30 bg-ok-soft px-3 py-2 text-sm text-ink">
          {banner}
        </p>
      ) : null}

      <label className="mb-4 block max-w-md">
        <span className="mb-1 block text-xs font-semibold uppercase text-muted">Filtrar</span>
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full rounded-lg border border-line bg-panel px-3 py-2.5 text-sm"
          placeholder="Usuário, equipe, matrícula…"
          aria-label="Filtrar técnicos"
        />
      </label>

      {query.isLoading ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !filtered.length ? (
        <EmptyState title="Sem técnicos" description="Nenhum registro corresponde ao filtro." />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-panel shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-canvas/80 text-xs uppercase text-muted">
              <tr>
                <th className="px-3 py-3 font-semibold">Usuário</th>
                <th className="px-3 py-3 font-semibold">Equipe</th>
                <th className="px-3 py-3 font-semibold">Matrícula</th>
                <th className="px-3 py-3 font-semibold">Carga</th>
                <th className="px-3 py-3 font-semibold">Situação</th>
                <th className="px-3 py-3 font-semibold">Horário</th>
                <th className="px-3 py-3 font-semibold">Empresa</th>
                {canEdit ? <th className="px-3 py-3 font-semibold">Ações</th> : null}
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.usuario} className="border-t border-line">
                  <td className="px-3 py-2.5 font-medium">{displayValue(t.usuario)}</td>
                  <td className="px-3 py-2.5">{displayValue(t.equipe)}</td>
                  <td className="px-3 py-2.5 font-mono text-xs">
                    {t.matricula && t.matricula !== '0' && t.matricula !== '00000' ? (
                      <span className="font-semibold text-ink">{t.matricula}</span>
                    ) : (
                      <span className="text-muted">{displayMatricula(t.matricula)}</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">{displayNumber(t.qtdc)}</td>
                  <td className="px-3 py-2.5">
                    {t.sit === '1' ? 'Ativo' : t.sit === '0' ? 'Inativo' : displayValue(t.sit)}
                  </td>
                  <td className="px-3 py-2.5">
                    {t.h1 || t.h2
                      ? `${displayValue(t.h1)} – ${displayValue(t.h2)}`
                      : 'Não disponível'}
                  </td>
                  <td className="px-3 py-2.5">{displayValue(t.empresa)}</td>
                  {canEdit ? (
                    <td className="px-3 py-2.5">
                      <div className="flex flex-wrap gap-1.5">
                        <button
                          type="button"
                          onClick={() => openEdit(t)}
                          className="rounded-lg border border-line px-2.5 py-1 text-xs font-semibold text-accent hover:bg-canvas"
                        >
                          Editar
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setRedirectFrom(t)
                            setRedirectTo('')
                            setRedirectOff(true)
                            setFormError(null)
                            setBanner(null)
                          }}
                          className="rounded-lg border border-line px-2.5 py-1 text-xs font-semibold hover:bg-canvas"
                        >
                          Redirecionar
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

      {editing && form ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-2xl border border-line bg-panel p-6 shadow-lg">
            <h2 className="font-display text-lg font-semibold text-ink">Editar {editing.usuario}</h2>
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase text-muted">Equipe</span>
                <input
                  list="equipe-options"
                  maxLength={5}
                  value={form.equipe}
                  onChange={(e) => setForm({ ...form, equipe: e.target.value.toUpperCase() })}
                  className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
                />
                <datalist id="equipe-options">
                  {teamOptions.map((eq) => (
                    <option key={eq} value={eq} />
                  ))}
                </datalist>
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase text-muted">Situação</span>
                <select
                  value={form.sit}
                  onChange={(e) => setForm({ ...form, sit: e.target.value })}
                  className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
                >
                  <option value="1">Ativo</option>
                  <option value="0">Inativo</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase text-muted">Matrícula</span>
                <input
                  maxLength={10}
                  value={form.matricula}
                  onChange={(e) => setForm({ ...form, matricula: e.target.value })}
                  className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm font-mono"
                  placeholder="Ex.: 27237 (obrigatório para análise por matrícula)"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="mb-1 block text-xs font-semibold uppercase text-muted">H1</span>
                  <input
                    maxLength={10}
                    value={form.h1}
                    onChange={(e) => setForm({ ...form, h1: e.target.value })}
                    className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs font-semibold uppercase text-muted">H2</span>
                  <input
                    maxLength={10}
                    value={form.h2}
                    onChange={(e) => setForm({ ...form, h2: e.target.value })}
                    className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
                  />
                </label>
              </div>
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase text-muted">Empresa</span>
                <input
                  maxLength={25}
                  value={form.empresa}
                  onChange={(e) => setForm({ ...form, empresa: e.target.value })}
                  className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
                />
              </label>
            </div>
            {formError ? (
              <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">
                {formError}
              </p>
            ) : null}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border border-line px-3 py-2 text-sm"
                onClick={() => {
                  setEditing(null)
                  setForm(null)
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                onClick={saveEdit}
                disabled={mutation.isPending}
              >
                {mutation.isPending ? 'Salvando…' : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {redirectFrom ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-2xl border border-line bg-panel p-6 shadow-lg">
            <h2 className="font-display text-lg font-semibold text-ink">
              Redirecionar {redirectFrom.usuario}
            </h2>
            <p className="mt-1 text-xs text-muted">
              Move tickets locais deste login para o destino. O robô deixa de usar a origem se
              desativar.
            </p>
            <label className="mt-4 block">
              <span className="mb-1 block text-xs font-semibold uppercase text-muted">
                Novo login (destino ativo)
              </span>
              <select
                value={redirectTo}
                onChange={(e) => setRedirectTo(e.target.value)}
                className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
              >
                <option value="">Selecione…</option>
                {activeLogins
                  .filter((u) => u.toUpperCase() !== redirectFrom.usuario.toUpperCase())
                  .map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
              </select>
            </label>
            <label className="mt-3 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={redirectOff}
                onChange={(e) => setRedirectOff(e.target.checked)}
              />
              Desativar origem (Sit=0)
            </label>
            {formError ? (
              <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">
                {formError}
              </p>
            ) : null}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border border-line px-3 py-2 text-sm"
                onClick={() => setRedirectFrom(null)}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                disabled={!redirectTo || redirectMut.isPending}
                onClick={() => redirectMut.mutate()}
              >
                {redirectMut.isPending ? 'Aplicando…' : 'Confirmar'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
