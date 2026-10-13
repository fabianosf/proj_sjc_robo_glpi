import { NavLink } from 'react-router-dom'
import {
  Bot,
  CalendarClock,
  ClipboardList,
  LayoutDashboard,
  ListTree,
  Settings,
  Ticket,
  Users,
  UsersRound,
  X,
} from 'lucide-react'
import type { Profile } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'

const NAV: {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
  minProfile: Profile
}[] = [
  { to: '/', label: 'Operação', icon: LayoutDashboard, end: true, minProfile: 'CONSULTA' },
  { to: '/chamados', label: 'Chamados', icon: Ticket, minProfile: 'CONSULTA' },
  { to: '/equipes', label: 'Equipes', icon: UsersRound, minProfile: 'CONSULTA' },
  { to: '/tecnicos', label: 'Técnicos', icon: Users, minProfile: 'CONSULTA' },
  { to: '/regras', label: 'Regras', icon: ListTree, minProfile: 'CONSULTA' },
  { to: '/relatorios', label: 'Relatórios', icon: ClipboardList, minProfile: 'CONSULTA' },
  { to: '/ia', label: 'Inteligência artificial', icon: Bot, minProfile: 'GESTOR' },
  { to: '/agendamentos', label: 'Agendamentos', icon: CalendarClock, minProfile: 'OPERADOR' },
  { to: '/configuracoes', label: 'Configurações', icon: Settings, minProfile: 'CONSULTA' },
]

type Props = {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: Props) {
  const { hasMinProfile } = useAuth()
  const items = NAV.filter((item) => hasMinProfile(item.minProfile))

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-ink/40 transition-opacity md:hidden ${open ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
        onClick={onClose}
        aria-hidden={!open}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-panel/95 backdrop-blur transition-transform md:static md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
        aria-label="Navegação principal"
      >
        <div className="flex items-center justify-between border-b border-line px-4 py-4">
          <div>
            <p className="font-display text-sm font-semibold tracking-wide text-accent">SGC</p>
            <p className="text-xs text-muted">Operação</p>
          </div>
          <button
            type="button"
            className="rounded-lg p-2 text-muted hover:bg-canvas md:hidden"
            onClick={onClose}
            aria-label="Fechar menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {items.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                `flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? 'bg-accent-soft text-accent'
                    : 'text-ink hover:bg-canvas'
                }`
              }
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  )
}
