import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import ProgressBar from '../components/ProgressBar'
import { useToast } from '../store/toast'
import type { Lote, MetricasLote, Operador } from '../types/lotes'

interface TreeItem {
  nombre: string
  relative_path: string
  es_lote: boolean
  tiene_hijos: boolean
  total: number
  lote: Lote | null
  metricas: MetricasLote | null
}

export default function Asignar() {
  const toast = useToast((state) => state.show)
  const [path, setPath] = useState('')
  const [items, setItems] = useState<TreeItem[]>([])
  const [operators, setOperators] = useState<Operador[]>([])
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Record<string, number>>({})
  const [saving, setSaving] = useState('')
  const [releasing, setReleasing] = useState('')
  const activePath = useRef('')
  const displayedPath = useRef('')

  const loadTree = useCallback(async (target: string) => {
    activePath.current = target
    try {
      const response = await api.get<{ actual: string; items: TreeItem[] }>(`/api/lotes/arbol?path=${encodeURIComponent(target)}`)
      if (activePath.current !== target) return
      displayedPath.current = response.actual
      setPath(response.actual)
      setItems(response.items)
      setSelected(Object.fromEntries(response.items.filter((item) => item.lote?.operador).map((item) => [item.relative_path, item.lote!.operador!.id])))
    } catch (error) {
      if (activePath.current !== target) return
      activePath.current = displayedPath.current
      toast(error instanceof Error ? error.message : 'No se pudo abrir la carpeta', 'error')
    }
  }, [toast])

  useEffect(() => {
    void Promise.all([
      loadTree(''),
      api.get<Operador[]>('/api/lotes/operadores').then(setOperators),
    ]).catch((error) => toast(error instanceof Error ? error.message : 'No se pudieron cargar los operadores', 'error'))
  }, [loadTree, toast])

  const assign = async (item: TreeItem) => {
    const operatorId = selected[item.relative_path]
    if (!operatorId) return
    setSaving(item.relative_path)
    try {
      const response = await api.post<{ notificacion: { fallidos: string[]; sin_correo: boolean } }>('/api/lotes/asignar', { relative_path: item.relative_path, operador_id: operatorId })
      if (response.notificacion.sin_correo) toast('Asignado, pero el operador no tiene correo registrado', 'error')
      else if (response.notificacion.fallidos.length) toast('Asignado; el correo no pudo enviarse', 'error')
      else toast('Lote asignado y correo enviado', 'success')
      if (activePath.current === path) await loadTree(path)
      window.dispatchEvent(new Event('lotes:changed'))
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudo asignar', 'error')
    } finally {
      setSaving('')
    }
  }

  const release = async (item: TreeItem) => {
    if (!item.lote?.operador) return
    if (!confirm(`¿Liberar el lote ${item.nombre}? El avance se conservará.`)) return
    const pathToReload = path
    setReleasing(item.relative_path)
    try {
      await api.post(`/api/lotes/${item.lote.id}/liberar`, {})
      toast('Lote liberado', 'success')
      if (activePath.current === pathToReload) await loadTree(pathToReload)
      window.dispatchEvent(new Event('lotes:changed'))
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudo liberar el lote', 'error')
    } finally {
      setReleasing('')
    }
  }

  const filteredOperators = operators.filter((item) => `${item.nombre} ${item.username}`.toLowerCase().includes(search.toLowerCase()))
  const operatorOptions = (selectedId: number) => {
    const selectedOperator = operators.find((item) => item.id === selectedId)
    return selectedOperator && !filteredOperators.some((item) => item.id === selectedId)
      ? [selectedOperator, ...filteredOperators]
      : filteredOperators
  }
  const up = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : ''

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6">
        <div className="mb-2 text-xs font-bold uppercase tracking-[.22em] text-red-600">Gestión de trabajo</div>
        <h1 className="text-3xl font-bold text-slate-900">Asignar lotes</h1>
        <p className="mt-1 text-sm text-slate-500">Seleccione una carpeta final y el operador responsable.</p>
      </div>
      <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Buscar operador</label>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Nombre o usuario" className="w-full max-w-md rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-red-500" />
      </div>
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-3 border-b border-slate-200 bg-slate-50 px-5 py-3 text-sm">
          <button disabled={!path} onClick={() => void loadTree(up)} className="font-semibold text-red-600 disabled:text-slate-300">← Subir</button>
          <span className="truncate text-slate-500">/{path}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead><tr className="border-b text-left text-xs uppercase tracking-wide text-slate-400"><th className="px-5 py-3">Carpeta</th><th className="px-4 py-3">Operador</th><th className="px-4 py-3">Archivos</th><th className="min-w-64 px-4 py-3">Avance</th><th className="px-5 py-3 text-right">Acción</th></tr></thead>
            <tbody>{items.map((item) => (
              <tr key={item.relative_path} className="border-b border-slate-100 last:border-0">
                <td className="px-5 py-4"><button disabled={!item.tiene_hijos} onClick={() => void loadTree(item.relative_path)} className={`inline-flex items-center gap-2 font-semibold ${item.tiene_hijos ? 'text-slate-900 hover:text-blue-700' : 'text-slate-700'}`}>{item.tiene_hijos && <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-700">+</span>}<svg className={`h-5 w-5 shrink-0 ${item.tiene_hijos ? 'text-blue-500' : 'text-amber-500'}`} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3 5.75A1.75 1.75 0 014.75 4h4.19c.46 0 .9.18 1.23.51L11.66 6h7.59A1.75 1.75 0 0121 7.75v9.5A2.75 2.75 0 0118.25 20H5.75A2.75 2.75 0 013 17.25V5.75z" /></svg><span>{item.nombre}</span></button>{item.es_lote && <div className="ml-9 mt-1 text-xs text-emerald-600">Carpeta final</div>}</td>
                <td className="px-4 py-4"><select disabled={!item.es_lote} value={selected[item.relative_path] || ''} onChange={(event) => setSelected((current) => ({ ...current, [item.relative_path]: Number(event.target.value) }))} className="w-56 rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-100"><option value="">Seleccionar operador</option>{operatorOptions(selected[item.relative_path] || 0).map((operator) => <option key={operator.id} value={operator.id}>{operator.nombre || operator.username} (@{operator.username})</option>)}</select></td>
                <td className="px-4 py-4 font-semibold text-slate-700">{item.es_lote ? item.total : '—'}</td>
                <td className="px-4 py-4">{item.metricas ? <ProgressBar metricas={item.metricas} /> : <span className="text-slate-300">—</span>}</td>
                <td className="px-5 py-4 text-right">{item.metricas?.porcentaje === 100 ? <span className="inline-flex rounded-full bg-emerald-100 px-3 py-1.5 text-xs font-bold text-emerald-700">Completado</span> : <div className="flex justify-end gap-2"><button disabled={!item.es_lote || !selected[item.relative_path] || saving === item.relative_path || releasing === item.relative_path} onClick={() => void assign(item)} className="rounded-lg bg-red-600 px-4 py-2 font-semibold text-white hover:bg-red-700 disabled:bg-slate-200 disabled:text-slate-400">{saving === item.relative_path ? 'Guardando…' : item.lote?.operador ? 'Reasignar' : 'Asignar'}</button>{item.lote?.operador && <button disabled={releasing === item.relative_path || saving === item.relative_path} onClick={() => void release(item)} className="rounded-lg bg-amber-600 px-4 py-2 font-semibold text-white hover:bg-amber-700 disabled:bg-slate-200 disabled:text-slate-400">{releasing === item.relative_path ? 'Liberando…' : 'Liberar'}</button>}</div>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        {items.length === 0 && <div className="p-10 text-center text-slate-400">No hay subdirectorios.</div>}
      </div>
    </div>
  )
}
