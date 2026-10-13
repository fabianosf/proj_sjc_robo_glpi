import { resolveMethodBadge } from '../lib/methodLabels'

type Props = {
  method?: unknown
}

export function MethodBadge({ method }: Props) {
  const info = resolveMethodBadge(method)
  if (!info) {
    return <span className="text-sm text-muted">Não disponível</span>
  }
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${info.className}`}
      title={info.hint || info.code}
    >
      {info.label}
    </span>
  )
}
