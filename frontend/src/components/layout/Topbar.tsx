import { useQuery, useQueryClient } from '@tanstack/react-query'
import { LogOut, Menu, Moon, RefreshCw, Sun } from 'lucide-react'
import { fetchHealth } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { useTheme } from '../../theme/ThemeContext'
import { useNavigate } from 'react-router-dom'
import { NotificationBell } from './NotificationBell'

type Props = {
  onMenuClick: () => void
}

const iconBtn =
  'inline-flex min-h-10 min-w-10 items-center justify-center rounded-xl border border-line bg-panel text-ink hover:bg-canvas'

export function Topbar({ onMenuClick }: Props) {
  const queryClient = useQueryClient()
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 30_000,
    retry: 1,
  })

  const apiOk = health.data?.status === 'ok' && health.data?.database === 'ok'
  const apiLabel = health.isLoading
    ? 'Verificando API…'
    : health.isError
      ? 'API indisponível'
      : apiOk
        ? 'API online'
        : `API: ${health.data?.status ?? 'degradada'}`

  return (
    <header className="sticky top-0 z-20 flex items-center gap-2 border-b border-line bg-panel/90 px-3 py-2 backdrop-blur sm:gap-3 sm:px-4">
      <button
        type="button"
        className="rounded-xl p-2.5 text-ink hover:bg-canvas md:hidden"
        onClick={onMenuClick}
        aria-label="Abrir menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-muted">
          {user ? `${user.nome || user.username} · ${user.perfil}` : 'Sessão'}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        <div
          className="hidden items-center gap-2 rounded-full border border-line bg-canvas px-2.5 py-1.5 text-xs font-medium lg:flex"
          role="status"
          aria-live="polite"
          title={apiLabel}
        >
          <span
            className={`h-2 w-2 rounded-full ${
              health.isError ? 'bg-danger' : apiOk ? 'bg-ok' : 'bg-warn'
            }`}
            aria-hidden
          />
          <span className="hidden xl:inline">{apiLabel}</span>
        </div>

        <NotificationBell />

        <button
          type="button"
          onClick={toggleTheme}
          className={iconBtn}
          aria-label={theme === 'dark' ? 'Ativar modo claro' : 'Ativar modo escuro'}
          title={theme === 'dark' ? 'Modo claro' : 'Modo escuro'}
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        <button
          type="button"
          onClick={() => {
            void queryClient.invalidateQueries()
          }}
          className={iconBtn}
          aria-label="Atualizar dados"
          title="Atualizar"
        >
          <RefreshCw className="h-4 w-4" aria-hidden />
        </button>

        <button
          type="button"
          onClick={() => {
            void logout().then(() => navigate('/login', { replace: true }))
          }}
          className={iconBtn}
          aria-label="Sair"
          title="Sair"
        >
          <LogOut className="h-4 w-4" aria-hidden />
        </button>
      </div>
    </header>
  )
}
