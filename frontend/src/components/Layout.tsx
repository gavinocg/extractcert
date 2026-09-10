import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'

const nav = [
  { to: '/', label: 'Dashboard', icon: 'M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10' },
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

  const items = isAdmin ? [...nav, { to: '/usuarios', label: 'Usuarios', icon: 'M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87M16 3.13a4 4 0 010 7.75M12 12a4 4 0 100-8 4 4 0 000 8z' }, { to: '/config', label: 'Configuración', icon: 'M10.3 4.3a8 8 0 013.4 0l.6 1.7 1.8-.5a8 8 0 012.4 2.4l-.5 1.8 1.7.6a8 8 0 010 3.4l-1.7.6.5 1.8a8 8 0 01-2.4 2.4l-1.8-.5-.6 1.7a8 8 0 01-3.4 0l-.6-1.7-1.8.5a8 8 0 01-2.4-2.4l.5-1.8-1.7-.6a8 8 0 010-3.4l1.7-.6-.5-1.8a8 8 0 012.4-2.4l1.8.5.6-1.7zM12 15a3 3 0 100-6 3 3 0 000 6z' }] : nav

  const onLogout = async () => {
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
          <div className="mb-2 text-xs text-slate-400">
            {isAdmin ? 'Administrador' : 'Usuario'}
          </div>
          <button onClick={onLogout} className="text-sm text-slate-300 hover:text-white">
            Cerrar sesión
          </button>
        </div>
      </aside>
      <main
        className={
          isVisor
            ? 'flex-1 flex flex-col overflow-hidden'
            : 'flex-1 overflow-x-hidden p-6'
        }
      >
        <Outlet />
      </main>
    </div>
  )
}