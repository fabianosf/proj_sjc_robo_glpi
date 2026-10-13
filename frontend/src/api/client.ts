import { ApiError } from './types'
import { clearSession, getStoredToken } from '../auth/storage'

const DEFAULT_BASE = 'http://127.0.0.1:8001'

/**
 * Base da API.
 * - VITE_API_BASE_URL vazio → mesma origem (painel servido pela API; ideal p/ celular na LAN).
 * - omitido → DEFAULT_BASE (dev Vite em localhost).
 */
export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (raw !== undefined && raw.trim() === '') {
    return ''
  }
  const base = (raw ?? DEFAULT_BASE).trim().replace(/\/+$/, '')
  return base || DEFAULT_BASE
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT'
  body?: unknown
  signal?: AbortSignal
  auth?: boolean
}

async function parseError(response: Response): Promise<string> {
  let detail = `Erro HTTP ${response.status}`
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string' && body.detail.trim()) {
      detail = body.detail
    } else if (Array.isArray(body.detail)) {
      const msgs = body.detail
        .map((e: unknown) => {
          if (typeof e === 'string') return e
          if (e && typeof e === 'object' && 'msg' in e) {
            return String((e as { msg: unknown }).msg)
          }
          return null
        })
        .filter(Boolean)
      detail = msgs.length ? msgs.join('; ') : 'Parâmetros inválidos na requisição.'
    }
  } catch {
    /* ignore */
  }
  return detail
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, auth = true } = options
  const url = `${getApiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = getStoredToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch {
    throw new ApiError(0, 'Não foi possível conectar à API. Verifique se o servidor está em execução.')
  }

  if (response.status === 401 && auth) {
    clearSession()
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      window.location.assign('/login')
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response))
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { method: 'GET', signal, auth: true })
}

function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header)
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1].trim())
    } catch {
      return star[1].trim()
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header)
  return plain?.[1]?.trim() || fallback
}

export async function apiGetBlob(
  path: string,
  fallbackName: string,
  signal?: AbortSignal,
): Promise<{ blob: Blob; filename: string }> {
  const url = `${getApiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`
  const headers: Record<string, string> = { Accept: '*/*' }
  const token = getStoredToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(url, { method: 'GET', headers, signal })
  } catch {
    throw new ApiError(
      0,
      'Não foi possível conectar à API. Verifique se o servidor está em execução.',
    )
  }

  if (response.status === 401) {
    clearSession()
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      window.location.assign('/login')
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response))
  }

  return {
    blob: await response.blob(),
    filename: filenameFromDisposition(response.headers.get('Content-Disposition'), fallbackName),
  }
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  options?: { signal?: AbortSignal; auth?: boolean },
): Promise<T> {
  return apiRequest<T>(path, {
    method: 'POST',
    body,
    signal: options?.signal,
    auth: options?.auth ?? true,
  })
}

export async function apiPatch<T>(
  path: string,
  body?: unknown,
  options?: { signal?: AbortSignal; auth?: boolean },
): Promise<T> {
  return apiRequest<T>(path, {
    method: 'PATCH',
    body,
    signal: options?.signal,
    auth: options?.auth ?? true,
  })
}

export async function apiPut<T>(
  path: string,
  body?: unknown,
  options?: { signal?: AbortSignal; auth?: boolean },
): Promise<T> {
  return apiRequest<T>(path, {
    method: 'PUT',
    body,
    signal: options?.signal,
    auth: options?.auth ?? true,
  })
}
