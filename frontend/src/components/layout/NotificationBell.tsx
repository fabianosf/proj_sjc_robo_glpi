import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../../api/endpoints'
import { displayDate } from '../../lib/format'
import { useAuth } from '../../auth/AuthContext'

export function NotificationBell() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const query = useQuery({
    queryKey: ['notifications', user?.username],
    queryFn: ({ signal }) => fetchNotifications({ limit: 20 }, signal),
    enabled: !!user,
    refetchInterval: 30_000,
  })

  const markOne = useMutation({
    mutationFn: (id: number) => markNotificationRead(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  const markAll = useMutation({
    mutationFn: () => markAllNotificationsRead(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  useEffect(() => {
    if (!open) return
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!user) return null

  const unread = query.data?.unread ?? 0
  const items = query.data?.items ?? []

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative inline-flex items-center justify-center rounded-lg border border-line bg-panel p-2 text-ink hover:bg-canvas"
        aria-label={unread ? `${unread} notificações não lidas` : 'Notificações'}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <Bell className="h-4 w-4" aria-hidden />
        {unread > 0 ? (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold text-white">
            {unread > 99 ? '99+' : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label="Notificações"
          className="absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-line bg-panel shadow-lg"
        >
          <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
            <p className="text-sm font-semibold text-ink">Notificações</p>
            {unread > 0 ? (
              <button
                type="button"
                className="text-xs font-semibold text-accent hover:underline disabled:opacity-50"
                disabled={markAll.isPending}
                onClick={() => markAll.mutate()}
              >
                Marcar todas
              </button>
            ) : null}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {query.isLoading ? (
              <p className="px-3 py-6 text-center text-sm text-muted">Carregando…</p>
            ) : !items.length ? (
              <p className="px-3 py-6 text-center text-sm text-muted">Nenhuma notificação.</p>
            ) : (
              <ul className="divide-y divide-line">
                {items.map((n) => (
                  <li
                    key={n.id}
                    className={`px-3 py-2.5 ${n.lida ? 'bg-panel' : 'bg-accent-soft/40'}`}
                  >
                    <button
                      type="button"
                      className="w-full text-left"
                      onClick={() => {
                        if (!n.lida) markOne.mutate(n.id)
                      }}
                    >
                      <p className="text-sm font-semibold text-ink">{n.titulo}</p>
                      <p className="mt-0.5 text-xs text-muted">{n.mensagem}</p>
                      <p className="mt-1 text-[11px] text-muted">
                        {displayDate(n.criado_em)}
                        {n.criado_por ? ` · por ${n.criado_por}` : ''}
                      </p>
                    </button>
                    {n.ref_ids.length > 0 ? (
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {n.ref_ids.slice(0, 8).map((id) => (
                          <Link
                            key={id}
                            to={`/chamados/${id}`}
                            className="rounded border border-line bg-canvas px-1.5 py-0.5 text-[11px] font-semibold text-accent hover:underline"
                            onClick={() => setOpen(false)}
                          >
                            #{id}
                          </Link>
                        ))}
                        {n.ref_ids.length > 8 ? (
                          <span className="text-[11px] text-muted">
                            +{n.ref_ids.length - 8}
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
