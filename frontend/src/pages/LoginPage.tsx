import { type FormEvent, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Moon, Sun } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { ApiError } from '../api/types'
import { getApiBaseUrl } from '../api/client'
import { useTheme } from '../theme/ThemeContext'

export function LoginPage() {
  const { user, loading, login } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from || '/'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!loading && user) {
    return <Navigate to={from} replace />
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      if (err instanceof ApiError) setError(err.message)
      else setError('Falha ao autenticar.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-12">
      <button
        type="button"
        onClick={toggleTheme}
        className="absolute right-4 top-4 inline-flex min-h-10 min-w-10 items-center justify-center rounded-xl border border-line bg-panel text-ink hover:bg-canvas"
        aria-label={theme === 'dark' ? 'Ativar modo claro' : 'Ativar modo escuro'}
        title={theme === 'dark' ? 'Modo claro' : 'Modo escuro'}
      >
        {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>

      <div className="sgc-panel w-full max-w-md p-8 sm:p-10">
        <p className="font-display text-sm font-semibold tracking-wide text-accent">SGC</p>
        <h1 className="mt-1 font-display text-xl font-semibold tracking-tight text-ink sm:text-[1.35rem]">
          Operação
        </h1>
        <p className="mt-2 text-sm text-muted">Acesso com conta Windows.</p>

        <form className="mt-8 space-y-5" onSubmit={onSubmit} noValidate>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-muted">
              Matrícula ou usuário
            </span>
            <input
              type="text"
              autoComplete="username"
              required
              placeholder="59817 ou fabiano.freitas"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-canvas px-3 py-2.5"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-muted">
              Senha
            </span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-canvas px-3 py-2.5"
            />
          </label>

          {error ? (
            <p className="rounded-xl border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-accent py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60"
          >
            {submitting ? 'Entrando…' : 'Entrar'}
          </button>
        </form>

        <p className="mt-8 text-[11px] text-muted">
          <span className="font-mono">{getApiBaseUrl()}</span>
        </p>
      </div>
    </div>
  )
}
