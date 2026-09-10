import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useToast } from '../store/toast'

interface Observacion { id: number; descripcion: string; orden: number }

export default function Observaciones() {
  const [lista, setLista] = useState<Observacion[]>([])
  const [descripcion, setDescripcion] = useState('')
  const [orden, setOrden] = useState('0')
  const [edit, setEdit] = useState<Observacion | null>(null)
  const toast = useToast((s) => s.show)

  const cargar = async () => setLista(await api.get<Observacion[]>('/api/observaciones'))
  useEffect(() => { void cargar() }, [])

  const guardar = async () => {
    if (!descripcion.trim()) { toast('Descripción requerida', 'error'); return }
    const nOrden = Number.parseInt(orden, 10)
    if (Number.isNaN(nOrden)) { toast('Orden debe ser número', 'error'); return }
    if (edit) await api.put(`/api/observaciones/${edit.id}`, { descripcion, orden: nOrden })
    else await api.post('/api/observaciones', { descripcion, orden: nOrden })
    toast('Guardado', 'success'); setDescripcion(''); setOrden('0'); setEdit(null); void cargar()
  }
  const eliminar = async (id: number) => { await api.del(`/api/observaciones/${id}`); toast('Eliminado', 'success'); void cargar() }
  const editar = (o: Observacion) => { setEdit(o); setDescripcion(o.descripcion); setOrden(String(o.orden)) }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-800">Observaciones</h1>
      <p className="mb-4 text-sm text-slate-500">Catálogo de observaciones para el modal de error en PDF.</p>
      <div className="mb-6 flex flex-wrap gap-2 rounded-xl bg-white p-4 shadow-sm">
        <input value={orden} onChange={(e) => setOrden(e.target.value)} placeholder="Orden" inputMode="numeric" className="w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm" title="Orden de aparición en el select" />
        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Descripción del error" maxLength={500} className="min-w-64 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <button onClick={guardar} className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">{edit ? 'Actualizar' : 'Agregar'}</button>
        {edit && <button onClick={() => { setEdit(null); setDescripcion(''); setOrden('0') }} className="rounded-lg border px-4 py-2 text-sm">Cancelar</button>}
      </div>
      <div className="rounded-xl bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-slate-400"><th className="px-3 py-2">Orden</th><th className="px-3 py-2">Descripción</th><th className="px-3 py-2">Acción</th></tr></thead>
          <tbody>
            {lista.map((o) => (
              <tr key={o.id} className="border-t border-slate-100"><td className="px-3 py-2">{o.orden}</td><td className="px-3 py-2">{o.descripcion}</td><td className="px-3 py-2 flex gap-2"><button onClick={() => editar(o)} className="rounded border px-2 py-1 text-xs">Editar</button><button onClick={() => eliminar(o.id)} className="rounded bg-red-600 px-2 py-1 text-xs text-white">Eliminar</button></td></tr>
            ))}
            {lista.length === 0 && <tr><td colSpan={3} className="px-3 py-6 text-center text-sm text-slate-400">Sin observaciones.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
