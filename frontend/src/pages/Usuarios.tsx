import { FormEvent, useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, invalidateApiCache } from '../api/client'
import { useAuth } from '../store/auth'
import { useToast } from '../store/toast'

interface Usuario {
  id: number
  username: string
  nombre: string
  email: string
  rol: string
  estado: string
  extracciones: number
  must_change_password: boolean
  password_changed_at: string | null
}

export default function Usuarios() {
  const { user, load: reloadAuth } = useAuth()
  const navigate = useNavigate()
  const toast = useToast((s) => s.show)
  const [lista, setLista] = useState<Usuario[]>([])
  const [editId, setEditId] = useState(0)
  const [username, setUsername] = useState('')
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [rol, setRol] = useState('usuario')
  const [estado, setEstado] = useState('activo')
  const [password, setPassword] = useState('')
  const [mustChangePassword, setMustChangePassword] = useState(true)

  useEffect(() => {
    if (user?.rol !== 'administrador') {
      navigate('/', { replace: true })
    }
  }, [user, navigate])

  const cargar = useCallback(async () => {
    setLista(await api.get<Usuario[]>('/api/usuarios'))
  }, [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const abrir = (u: Usuario) => {
    setEditId(u.id)
    setUsername(u.username)
    setNombre(u.nombre)
    setEmail(u.email)
    setRol(u.rol)
    setEstado(u.estado)
    setPassword('')
    setMustChangePassword(u.must_change_password)
  }

  const reset = () => {
    setEditId(0)
    setUsername('')
    setNombre('')
    setEmail('')
    setPassword('')
    setRol('usuario')
    setEstado('activo')
    setMustChangePassword(true)
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      if (editId) {
        await api.put(`/api/usuarios/${editId}`, { username, nombre, email, rol, estado, password, must_change_password: mustChangePassword })
        toast('Usuario actualizado', 'success')
      } else {
        await api.post('/api/usuarios', { username, nombre, email, rol, estado, password, must_change_password: mustChangePassword })
        toast('Usuario creado', 'success')
      }
      invalidateApiCache('/api/lotes/operadores')
      reset()
      await cargar()
      if (editId === user?.id) await reloadAuth()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Error', 'error')
    }
  }

  const eliminar = async (u: Usuario) => {
    if (!confirm(`¿Eliminar al usuario ${u.username}?`)) return
    try {
      await api.del(`/api/usuarios/${u.id}`)
      invalidateApiCache('/api/lotes/operadores')
      toast('Usuario eliminado', 'success')
      await cargar()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Error', 'error')
    }
  }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-800">Usuarios</h1>
      <p className="mb-4 text-sm text-slate-500">Administración de usuarios y roles.</p>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <div className="mb-3 text-sm font-semibold text-slate-700">
            {editId ? 'Editar usuario' : 'Nuevo usuario'}
          </div>
          <form onSubmit={onSubmit} className="space-y-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Correo electrónico</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="usuario@empresa.com" className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-red-400" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Nombre</label>
              <input
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Nombre y apellido"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-red-400"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Usuario</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-red-400"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Contraseña</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required={!editId}
                placeholder={editId ? 'Dejar en blanco para no cambiar' : ''}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-red-400"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Rol</label>
              <select
                value={rol}
                onChange={(e) => setRol(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none"
              >
                <option value="usuario">Usuario</option>
                <option value="supervisor">Supervisor</option>
                <option value="administrador">Administrador</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Estado</label>
              <select
                value={estado}
                onChange={(e) => setEstado(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none"
              >
                <option value="activo">Activo</option>
                <option value="inactivo">Inactivo</option>
              </select>
            </div>
            <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <input type="checkbox" checked={mustChangePassword} onChange={(e) => setMustChangePassword(e.target.checked)} className="mt-0.5 h-4 w-4 accent-red-600" />
              <span>
                <span className="block text-sm font-medium text-slate-700">Solicitar cambio de contraseña en el próximo inicio de sesión</span>
                <span className="mt-0.5 block text-xs text-slate-500">El usuario no podrá acceder al sistema hasta actualizarla.</span>
              </span>
            </label>
            <div className="flex gap-2">
              <button className="rounded-lg bg-red-600 px-4 py-2 font-semibold text-white hover:bg-red-700">
                {editId ? 'Guardar cambios' : 'Crear'}
              </button>
              {editId > 0 && (
                <button type="button" onClick={reset} className="rounded-lg bg-slate-100 px-4 py-2 text-slate-700 hover:bg-slate-200">
                  Cancelar
                </button>
              )}
            </div>
          </form>
        </div>

        <div className="rounded-xl bg-white p-4 shadow-sm">
          <div className="mb-3 text-sm font-semibold text-slate-700">Listado</div>
          {lista.length === 0 ? (
            <div className="text-sm text-slate-400">Sin usuarios.</div>
          ) : (
            <div className="overflow-x-auto"><table className="min-w-[940px] w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-slate-400">
                  <th className="py-1 pr-2">Usuario</th>
                  <th className="px-2 py-1">Nombre</th>
                  <th className="px-2 py-1">Correo</th>
                  <th className="px-2 py-1">Rol</th>
                  <th className="px-2 py-1">Estado</th>
                   <th className="px-2 py-1">Extracciones</th>
                   <th className="px-2 py-1">Contraseña</th>
                  <th className="px-2 py-1 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((u) => (
                  <tr key={u.id} className="border-t border-slate-100">
                    <td className="py-2 pr-2">
                      {u.username}
                      {u.id === user?.id && <span className="ml-1 text-xs text-slate-400">(tú)</span>}
                    </td>
                    <td className="px-2 py-2">{u.nombre || '—'}</td>
                    <td className="max-w-44 truncate px-2 py-2" title={u.email}>{u.email || 'Pendiente'}</td>
                    <td className="px-2 py-2">
                      <span
                        className={
                          u.rol === 'administrador'
                            ? 'rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700'
                            : 'rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600'
                        }
                      >
                        {u.rol}
                      </span>
                    </td>
                    <td className="px-2 py-2">
                      <span
                        className={
                          u.estado === 'activo'
                            ? 'rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700'
                            : 'rounded bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-500'
                        }
                      >
                        {u.estado}
                      </span>
                    </td>
                    <td className="px-2 py-2">{u.extracciones}</td>
                    <td className="px-2 py-2">
                      <span className={`rounded px-2 py-0.5 text-xs font-medium ${u.must_change_password ? 'bg-amber-100 text-amber-800' : u.password_changed_at ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                        {u.must_change_password ? 'Cambio pendiente' : u.password_changed_at ? 'Actualizada' : 'Nunca actualizada'}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-right">
                      <button onClick={() => abrir(u)} className="mr-2 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100">
                        Editar
                      </button>
                      {u.id !== user?.id && (
                        <button
                          onClick={() => eliminar(u)}
                          className="rounded border border-red-300 px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                        >
                          Eliminar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </div>
      </div>
    </div>
  )
}
