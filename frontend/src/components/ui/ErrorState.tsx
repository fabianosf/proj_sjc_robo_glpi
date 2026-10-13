import { AlertTriangle } from 'lucide-react'

export function ErrorState({
  title = 'Falha ao carregar',
  message,
  onRetry,
}: {
  title?: string
  message?: string
  onRetry?: () => void
}) {
  return (
    <div
      className="flex flex-col items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 px-5 py-6 text-rose-950"
      role="alert"
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden />
        <h3 className="font-display text-base font-semibold">{title}</h3>
      </div>
      <p className="text-sm text-rose-900/80">{message ?? 'Não disponível'}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg bg-rose-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-800"
        >
          Tentar novamente
        </button>
      ) : null}
    </div>
  )
}
