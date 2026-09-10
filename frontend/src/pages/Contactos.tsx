import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useToast } from '../store/toast'

interface Contacto { id: number; nombre: string; email: string }

export default function Contactos() {
  const [lista, setLista] = useState<Contacto[]>([])
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [edit, setEdit] = useState<Contacto | null>(null)
  const toast = useToast((s) => s.show)

  const cargar = async () => setLista(await api.get<Contacto[]>('/api/contactos'))
  useEffect(() => { void cargar() }, [])

  const guardar = async () => {
    if (!nombre.trim() || !email.trim()) { toast('Nombre y email requeridos', 'error'); return }
    if (edit) await api.put(`/api/contactos/${edit.id}`, { nombre, email })
    else await api.post('/api/contactos', { nombre, email })
    toast('Guardado', 'success'); setNombre(''); setEmail(''); setEdit(null); void cargar()
  }
  const eliminar = async (id: number) => { await api.del(`/api/contactos/${id}`); toast('Eliminado', 'success'); void cargar() }
  const editar = (c: Contacto) => { setEdit(c); setNombre(c.nombre); setEmail(c.email) }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-800">Libreta de direcciones</h1>
      <p className="mb-4 text-sm text-slate-500">Contactos globales para envío de errores (individual o lote).</p>
      <div className="mb-6 flex flex-wrap gap-2 rounded-xl bg-white p-4 shadow-sm">
        <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="correo@ej.com" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <button onClick={guardar} className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">{edit ? 'Actualizar' : 'Agregar'}</button>
        {edit && <button onClick={() => { setEdit(null); setNombre(''); setEmail('') }} className="rounded-lg border px-4 py-2 text-sm">Cancelar</button>}
      </div>
      <div className="rounded-xl bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-slate-400"><th className="px-3 py-2">Nombre</th><th className="px-3 py-2">Email</th><th className="px-3 py-2">Acción</th></tr></thead>
          <tbody>
            {lista.map((c) => (
              <tr key={c.id} className="border-t border-slate-100"><td className="px-3 py-2">{c.nombre}</td><td className="px-3 py-2">{c.email}</td><td className="px-3 py-2 flex gap-2"><button onClick={() => editar(c)} className="rounded border px-2 py-1 text-xs">Editar</button><button onClick={() => eliminar(c.id)} className="rounded bg-red-600 px-2 py-1 text-xs text-white">Eliminar</button></td></tr>
            ))}
            {lista.length === 0 && <tr><td colSpan={3} className="px-3 py-6 text-center text-sm text-slate-400">Sin contactos.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
