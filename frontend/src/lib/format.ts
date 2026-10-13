export function displayValue(value: unknown): string {
  if (value === null || value === undefined) return 'Não disponível'
  if (typeof value === 'string' && value.trim() === '') return 'Não disponível'
  if (typeof value === 'number' && Number.isNaN(value)) return 'Não disponível'
  return String(value)
}

export function displayNumber(value: number | null | undefined, suffix = ''): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'Não disponível'
  return `${value.toLocaleString('pt-BR')}${suffix}`
}

export function displayPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'Não disponível'
  return `${value.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%`
}

/** Aceita ISO (`YYYY-MM-DDTHH:mm:ss`), legado com espaço, ou só data. */
export function parseApiDate(value: string | null | undefined): Date | null {
  if (!value || !String(value).trim()) return null
  const raw = String(value).trim()
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T')
  const d = new Date(normalized)
  if (Number.isNaN(d.getTime())) return null
  return d
}

export function displayBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value) || value < 0) {
    return 'Não disponível'
  }
  if (value < 1024) return `${value} B`
  const kb = value / 1024
  if (kb < 1024) return `${kb.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} KB`
  return `${(kb / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`
}

export function displayAgeSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value) || value < 0) {
    return 'Não disponível'
  }
  if (value < 60) return `há ${value} s`
  const min = Math.floor(value / 60)
  if (min < 60) return `há ${min} min`
  const h = Math.floor(min / 60)
  return `há ${h} h`
}

export function displayDate(value: string | null | undefined): string {
  const d = parseApiDate(value)
  if (!d) {
    if (!value || !String(value).trim()) return 'Não disponível'
    return String(value)
  }
  // Só data (YYYY-MM-DD) → formato curto
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(value).trim())) {
    return d.toLocaleDateString('pt-BR')
  }
  return d.toLocaleString('pt-BR')
}
