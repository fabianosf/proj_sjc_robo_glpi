import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './auth/AuthContext'
import { AppShell } from './components/layout/AppShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'

const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
)
const TicketsPage = lazy(() =>
  import('./pages/TicketsPage').then((m) => ({ default: m.TicketsPage })),
)
const TicketDetailPage = lazy(() =>
  import('./pages/TicketDetailPage').then((m) => ({ default: m.TicketDetailPage })),
)
const TeamsPage = lazy(() =>
  import('./pages/TeamsPage').then((m) => ({ default: m.TeamsPage })),
)
const TechniciansPage = lazy(() =>
  import('./pages/TechniciansPage').then((m) => ({ default: m.TechniciansPage })),
)
const MlPage = lazy(() =>
  import('./pages/MlPage').then((m) => ({ default: m.MlPage })),
)
const JobsPage = lazy(() =>
  import('./pages/JobsPage').then((m) => ({ default: m.JobsPage })),
)
const SettingsPage = lazy(() =>
  import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
)
const WeeklyReportPage = lazy(() =>
  import('./pages/WeeklyReportPage').then((m) => ({ default: m.WeeklyReportPage })),
)
const RulesPage = lazy(() =>
  import('./pages/RulesPage').then((m) => ({ default: m.RulesPage })),
)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function PageFallback() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">
      Carregando…
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />

              <Route element={<ProtectedRoute minProfile="CONSULTA" />}>
                <Route element={<AppShell />}>
                  <Route index element={<DashboardPage />} />
                  <Route path="chamados" element={<TicketsPage />} />
                  <Route path="chamados/:ticketId" element={<TicketDetailPage />} />
                  <Route path="equipes" element={<TeamsPage />} />
                  <Route path="tecnicos" element={<TechniciansPage />} />
                  <Route path="regras" element={<RulesPage />} />
                  <Route path="relatorios" element={<WeeklyReportPage />} />
                  <Route path="configuracoes" element={<SettingsPage />} />

                  <Route element={<ProtectedRoute minProfile="OPERADOR" />}>
                    <Route path="agendamentos" element={<JobsPage />} />
                  </Route>

                  <Route element={<ProtectedRoute minProfile="GESTOR" />}>
                    <Route path="ia" element={<MlPage />} />
                  </Route>

                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
