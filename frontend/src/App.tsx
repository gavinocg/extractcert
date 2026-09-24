import { lazy, Suspense, useEffect } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './store/auth'
import Layout from './components/Layout'
import { ToastHost } from './components/Toast'
import Login from './pages/Login'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Visor = lazy(() => import('./pages/Visor'))
const Historial = lazy(() => import('./pages/Historial'))
const Usuarios = lazy(() => import('./pages/Usuarios'))
const Config = lazy(() => import('./pages/Config'))
const Errores = lazy(() => import('./pages/Errores'))
const Contactos = lazy(() => import('./pages/Contactos'))
const Observaciones = lazy(() => import('./pages/Observaciones'))
const Lotes = lazy(() => import('./pages/Lotes'))
const Asignar = lazy(() => import('./pages/Asignar'))

function RoleGate({ allow, children }: { allow: Array<'usuario' | 'supervisor' | 'administrador'>; children: React.ReactNode }) {
  const user = useAuth((state) => state.user)
  return user && allow.includes(user.rol) ? <>{children}</> : <Navigate to="/" replace />
}

function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading, load } = useAuth()
  useEffect(() => {
    void load()
    const onUnauth = () => useAuth.getState().logout()
    window.addEventListener('auth:unauthorized', onUnauth)
    return () => window.removeEventListener('auth:unauthorized', onUnauth)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-500">
        Cargando…
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function RouteLoader() {
  return (
    <Suspense fallback={<div className="p-6 text-slate-500">Cargando módulo…</div>}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <AuthGate>
              <Layout />
            </AuthGate>
          }
        >
          <Route index element={<Lotes />} />
          <Route path="supervision" element={<RoleGate allow={['supervisor', 'administrador']}><Lotes supervisionView /></RoleGate>} />
          <Route path="lote" element={<Dashboard />} />
          <Route path="asignar" element={<RoleGate allow={['supervisor', 'administrador']}><Asignar /></RoleGate>} />
          <Route path="visor" element={<Visor />} />
          <Route path="historial" element={<Historial />} />
          <Route path="errores" element={<Errores />} />
          <Route path="contactos" element={<RoleGate allow={['supervisor', 'administrador']}><Contactos /></RoleGate>} />
          <Route path="observaciones" element={<RoleGate allow={['administrador']}><Observaciones /></RoleGate>} />
          <Route path="usuarios" element={<RoleGate allow={['administrador']}><Usuarios /></RoleGate>} />
          <Route path="config" element={<RoleGate allow={['administrador']}><Config /></RoleGate>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <>
      <RouteLoader />
      <ToastHost />
    </>
  )
}
