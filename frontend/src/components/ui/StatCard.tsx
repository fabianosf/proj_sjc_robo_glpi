import type { LucideIcon } from 'lucide-react'

export function StatCard({
  title,
  value,
  hint,
  icon: Icon,
  tone = 'default',
}: {
  title: string
  value: string
  hint?: string
  icon: LucideIcon
  tone?: 'default' | 'warn'
}) {
  return (
    <article
      className={`rounded-xl border p-4 shadow-sm ${
        tone === 'warn' ? 'border-amber-300 bg-amber-50' : 'border-line bg-panel'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</p>
          <p className="mt-2 font-display text-2xl font-semibold tabular-nums text-ink">{value}</p>
          {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
        </div>
        <span className="rounded-lg bg-accent-soft p-2 text-accent" aria-hidden>
          <Icon className="h-5 w-5" />
        </span>
      </div>
    </article>
  )
}
