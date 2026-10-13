import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { fetchMe, loginRequest, logoutRequest } from '../api/endpoints'
import type { Profile, UserPublic } from '../api/types'
import { ApiError } from '../api/types'
import { clearSession, getStoredToken, getStoredUser, storeSession } from './storage'

type AuthState = {
  user: UserPublic | null
  token: string | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  hasMinProfile: (perfil: Profile) => boolean
}

const RANK: Record<Profile, number> = {
  CONSULTA: 1,
  OPERADOR: 2,
  GESTOR: 3,
  ADMIN: 4,
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(() => getStoredUser())
  const [token, setToken] = useState<string | null>(() => getStoredToken())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function bootstrap() {
      const t = getStoredToken()
      if (!t) {
        if (!cancelled) {
          setUser(null)
          setToken(null)
          setLoading(false)
        }
        return
      }
      try {
        const me = await fetchMe()
        if (!cancelled) {
          setUser(me)
          setToken(t)
          storeSession(t, me)
        }
      } catch {
        clearSession()
        if (!cancelled) {
          setUser(null)
          setToken(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const res = await loginRequest(username, password)
    // Nunca logar access_token
    storeSession(res.access_token, res.user)
    setToken(res.access_token)
    setUser(res.user)
  }, [])

  const logout = useCallback(async () => {
    try {
      await logoutRequest()
    } catch (e) {
      if (!(e instanceof ApiError && (e.status === 401 || e.status === 0))) {
        /* ignora falha de rede no logout */
      }
    } finally {
      clearSession()
      setToken(null)
      setUser(null)
    }
  }, [])

  const hasMinProfile = useCallback(
    (perfil: Profile) => {
      if (!user) return false
      return RANK[user.perfil] >= RANK[perfil]
    },
    [user],
  )

  const value = useMemo(
    () => ({ user, token, loading, login, logout, hasMinProfile }),
    [user, token, loading, login, logout, hasMinProfile],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider')
  return ctx
}
