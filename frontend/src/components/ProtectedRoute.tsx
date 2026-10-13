import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { Profile } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { LoadingState } from './ui/LoadingState'
import { ErrorState } from './ui/ErrorState'

export function ProtectedRoute({ minProfile = 'CONSULTA' as Profile }: { minProfile?: Profile }) {
  const { user, loading, hasMinProfile } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <LoadingState label="Validando sessão…" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (!hasMinProfile(minProfile)) {
    return (
      <div className="mx-auto max-w-lg p-8">
        <ErrorState
          title="Acesso negado"
          message="Seu perfil não tem permissão para este recurso."
        />
      </div>
    )
  }

  return <Outlet />
}
