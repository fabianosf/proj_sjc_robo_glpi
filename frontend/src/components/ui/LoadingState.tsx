import { Loader2 } from 'lucide-react'

export function LoadingState({ label = 'Carregando…' }: { label?: string }) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 rounded-xl border border-line bg-panel/80 px-6 py-16 text-muted"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="h-8 w-8 animate-spin text-accent" aria-hidden />
      <p className="text-sm font-medium">{label}</p>
    </div>
  )
}
