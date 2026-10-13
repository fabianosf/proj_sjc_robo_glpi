import { Inbox } from 'lucide-react'

export function EmptyState({
  title = 'Nenhum dado',
  description = 'Não há informações para exibir.',
}: {
  title?: string
  description?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line bg-panel/60 px-6 py-14 text-center">
      <Inbox className="h-8 w-8 text-muted" aria-hidden />
      <h3 className="font-display text-base font-semibold text-ink">{title}</h3>
      <p className="max-w-md text-sm text-muted">{description}</p>
    </div>
  )
}
