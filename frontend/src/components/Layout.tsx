import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'
import CambiarPassword from './CambiarPassword'

const nav = [
  { to: '/', label: 'Bandeja', icon: 'M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10' },
  { to: '/historial', label: 'Historial', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  { to: '/errores', label: 'Errores', icon: 'M12 9v2m0 4h.01M10.3 4.3a8 8 0 013.4 0l.6 1.7 1.8-.5a8 8 0 012.4 2.4l-.5 1.8 1.7.6a8 8 0 010 3.4l-1.7.6.5 1.8a8 8 0 01-2.4 2.4l-1.8-.5-.6 1.7a8 8 0 01-3.4 0l-.6-1.7-1.8.5a8 8 0 01-2.4-2.4l.5-1.8-1.7-.6a8 8 0 010-3.4l1.7-.6-.5-1.8a8 8 0 012.4-2.4l1.8.5.6-1.7z' },
  { to: '/contactos', label: 'Contactos', icon: 'M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87M16 3.13a4 4 0 010 7.75' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const isAdmin = user?.rol === 'administrador'
  const isVisor = location.pathname === '/visor'

  const items = isAdmin ? [...nav, { to: '/observaciones', label: 'Observaciones', icon: 'M4 6h16M4 12h16M4 18h10' }, { to: '/usuarios', label: 'Usuarios', icon: 'M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87M16 3.13a4 4 0 010 7.75M12 12a4 4 0 100-8 4 4 0 000 8z' }, { to: '/config', label: 'Configuración', icon: 'M10.3 4.3a8 8 0 013.4 0l.6 1.7 1.8-.5a8 8 0 012.4 2.4l-.5 1.8 1.7.6a8 8 0 010 3.4l-1.7.6.5 1.8a8 8 0 01-2.4 2.4l-1.8-.5-.6 1.7a8 8 0 01-3.4 0l-.6-1.7-1.8.5a8 8 0 01-2.4-2.4l.5-1.8-1.7-.6a8 8 0 010-3.4l1.7-.6-.5-1.8a8 8 0 012.4-2.4l1.8.5.6-1.7zM12 15a3 3 0 100-6 3 3 0 000 6z' }] : nav

  const [menuAbierto, setMenuAbierto] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const onLogout = async () => {
    setMenuAbierto(false)
    await logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-col bg-slate-900 text-slate-200">
        <div className="px-5 py-4 text-lg font-semibold text-white">
          <span className="text-red-400">■</span> ExtractCert
        </div>
        <nav className="mt-2 flex-1 space-y-1 px-3">
          {items.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition ${
                  isActive ? 'bg-slate-700 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d={it.icon} />
              </svg>
              {it.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-700 px-5 py-4">
          <div className="text-sm">{user?.username}</div>
          <div className="text-xs text-slate-400">
            {isAdmin ? 'Administrador' : 'Usuario'}
          </div>
        </div>
      </aside>
      <main
        className={
          isVisor
            ? 'flex-1 flex flex-col overflow-hidden'
            : 'flex-1 flex flex-col overflow-x-hidden'
        }
      >
        <div className="flex flex-none items-center justify-end border-b border-slate-200 bg-white px-4 py-2">
          <div className="relative">
            <button
              onClick={() => setMenuAbierto((v) => !v)}
              title={user?.username}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-sm font-bold text-white hover:bg-slate-700"
            >
              {(user?.username ?? '?').charAt(0).toUpperCase()}
            </button>
            {menuAbierto && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setMenuAbierto(false)} />
                <div className="absolute right-0 z-50 mt-2 w-52 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
                  <div className="border-b border-slate-100 px-4 py-2">
                    <div className="truncate text-sm font-medium text-slate-800">{user?.username}</div>
                    <div className="text-xs text-slate-400">{isAdmin ? 'Administrador' : 'Usuario'}</div>
                  </div>
                  <button
                    onClick={() => { setMenuAbierto(false); setShowPassword(true) }}
                    className="block w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                  >
                    Cambiar contraseña
                  </button>
                  <button
                    onClick={onLogout}
                    className="block w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50"
                  >
                    Salir
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
        <div className={isVisor ? 'flex min-h-0 flex-1 flex-col' : 'flex-1 p-6'}>
          <Outlet />
        </div>
        {showPassword && <CambiarPassword onClose={() => setShowPassword(false)} />}
      </main>
    </div>
  )
}