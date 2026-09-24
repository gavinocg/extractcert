import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import ProgressBar from '../components/ProgressBar'
import { useAuth } from '../store/auth'
import { useToast } from '../store/toast'
import type { Lote, Operador } from '../types/lotes'

function dateLabel(value: string | null) {
  return value ? new Date(value).toLocaleString('es-EC') : '—'
}

interface OperatorStats {
  id: number
  username: string
  nombre: string
  lotes_asignados: number
  lotes_completados: number
  total: number
  realizados: number
  errores: number
  pendientes: number
  porcentaje: number
  realizados_30_dias: number
  promedio_diario_30_dias: number
}

export default function Lotes({ supervisionView = false }: { supervisionView?: boolean }) {
  const user = useAuth((state) => state.user)
  const toast = useToast((state) => state.show)
  const [items, setItems] = useState<Lote[]>([])
  const [loading, setLoading] = useState(true)
  const [notifying, setNotifying] = useState(0)
  const [releasing, setReleasing] = useState(0)
  const [operatorStats, setOperatorStats] = useState<OperatorStats[]>([])
  const [operators, setOperators] = useState<Operador[]>([])
  const [reassigning, setReassigning] = useState<Lote | null>(null)
  const [newOperatorId, setNewOperatorId] = useState(0)
  const [operatorSearch, setOperatorSearch] = useState('')
  const [savingReassignment, setSavingReassignment] = useState(false)
  const requestGeneration = useRef(0)
  const currentScope = useRef(supervisionView)
  currentScope.current = supervisionView

  const load = useCallback(async () => {
    const scope = supervisionView
    if (currentScope.current !== scope) return
    const generation = ++requestGeneration.current
    setLoading(true)
    try {
      if (scope) {
        const [lots, stats, availableOperators] = await Promise.all([
          api.get<Lote[]>('/api/lotes?scope=supervision'),
          api.get<OperatorStats[]>('/api/lotes/operator-stats'),
          api.get<Operador[]>('/api/lotes/operadores'),
        ])
        if (generation !== requestGeneration.current || currentScope.current !== scope) return
        setItems(lots)
        setOperatorStats(stats)
        setOperators(availableOperators)
      } else {
        const lots = await api.get<Lote[]>('/api/lotes?scope=mine')
        if (generation !== requestGeneration.current || currentScope.current !== scope) return
        setItems(lots)
      }
    } catch (error) {
      if (generation !== requestGeneration.current || currentScope.current !== scope) return
      toast(error instanceof Error ? error.message : 'No se pudieron cargar los lotes', 'error')
    } finally {
      if (generation === requestGeneration.current && currentScope.current === scope) setLoading(false)
    }
  }, [supervisionView, toast])

  useEffect(() => {
    ++requestGeneration.current
    setItems([])
    setOperatorStats([])
    setOperators([])
    setReassigning(null)
    setNewOperatorId(0)
    setOperatorSearch('')
    setSavingReassignment(false)
    setNotifying(0)
    setReleasing(0)
    void load()
    return () => { ++requestGeneration.current }
  }, [load])

  const notify = async (lote: Lote) => {
    if (!confirm(`¿Notificar la finalización del lote ${lote.nombre}?`)) return
    setNotifying(lote.id)
    try {
      const response = await api.post<{ ok: boolean; notificacion: { fallidos: string[] } }>(`/api/lotes/${lote.id}/notificar-finalizacion`, {})
      if (response.ok) toast('Finalización notificada', 'success')
      else toast(`No se pudo enviar a: ${response.notificacion.fallidos.join(', ')}`, 'error')
      await load()
      window.dispatchEvent(new Event('lotes:changed'))
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudo notificar', 'error')
    } finally {
      setNotifying(0)
    }
  }

  const release = async (lote: Lote) => {
    if (!confirm(`¿Liberar el lote ${lote.nombre}? El avance se conservará, pero quedará sin operador responsable.`)) return
    setReleasing(lote.id)
    try {
      await api.post(`/api/lotes/${lote.id}/liberar`, {})
      toast('Lote liberado', 'success')
      await load()
      window.dispatchEvent(new Event('lotes:changed'))
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudo liberar el lote', 'error')
    } finally {
      setReleasing(0)
    }
  }

  const openReassignment = (lote: Lote) => {
    setReassigning(lote)
    setNewOperatorId(lote.operador?.id || 0)
    setOperatorSearch('')
  }

  const saveReassignment = async () => {
    if (!reassigning || !newOperatorId) return
    setSavingReassignment(true)
    try {
      const response = await api.post<{ notificacion: { fallidos: string[]; sin_correo: boolean } }>('/api/lotes/asignar', { relative_path: reassigning.relative_path, operador_id: newOperatorId })
      if (response.notificacion.sin_correo) toast('Lote reasignado, pero el operador no tiene correo registrado', 'error')
      else if (response.notificacion.fallidos.length) toast(`Lote reasignado; no se pudo enviar a: ${response.notificacion.fallidos.join(', ')}`, 'error')
      else toast('Lote reasignado y correo enviado', 'success')
      setReassigning(null)
      await load()
      window.dispatchEvent(new Event('lotes:changed'))
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudo reasignar el lote', 'error')
    } finally {
      setSavingReassignment(false)
    }
  }

  const filteredOperators = operators.filter((operator) =>
    `${operator.nombre} ${operator.username}`.toLowerCase().includes(operatorSearch.toLowerCase()),
  )

  const supervisor = user?.rol !== 'usuario'
  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-2 text-xs font-bold uppercase tracking-[.22em] text-red-600">ExtractCert</div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">{supervisionView ? 'Bandeja supervisión' : 'Pendientes'}</h1>
          <p className="mt-1 text-sm text-slate-500">{supervisionView ? 'Lotes con responsable asignado para seguimiento.' : 'Lotes asignados personalmente y trabajo pendiente.'}</p>
        </div>
        <button onClick={() => void load()} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Actualizar</button>
      </div>

      {loading ? <div className="text-slate-500">Cargando lotes…</div> : !supervisionView && items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">No hay lotes asignados.</div>
      ) : supervisionView && supervisor ? (
        <><div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1050px] text-sm">
              <thead className="bg-slate-50">
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3">Lote</th>
                  <th className="px-4 py-3">Operador</th>
                  <th className="px-4 py-3">Estado</th>
                  <th className="min-w-64 px-4 py-3">Avance</th>
                  <th className="px-4 py-3">Asignado</th>
                  <th className="px-4 py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {items.map((lote) => (
                  <tr key={lote.id} className="border-b border-slate-100 align-middle last:border-0 hover:bg-slate-50/70">
                    <td className="max-w-72 px-4 py-3">
                      <div className="truncate font-semibold text-slate-900" title={lote.nombre}>{lote.nombre}</div>
                      <div className="truncate text-xs text-slate-400" title={lote.relative_path}>{lote.relative_path}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-700">{lote.operador?.nombre || lote.operador?.username || 'Sin asignar'}</div>
                      {lote.operador?.nombre && <div className="text-xs text-slate-400">@{lote.operador.username}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${lote.estado === 'notificado' ? 'bg-blue-100 text-blue-700' : lote.estado === 'completado' ? 'bg-emerald-100 text-emerald-700' : lote.estado === 'en_progreso' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
                        {lote.estado.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3"><ProgressBar metricas={lote.metricas} /></td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">{dateLabel(lote.assigned_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <Link to={`/lote?path=${encodeURIComponent(lote.relative_path)}`} className="whitespace-nowrap rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100">Abrir</Link>
                        <button onClick={() => openReassignment(lote)} className="whitespace-nowrap rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700">Reasignar</button>
                        <button
                          disabled={!lote.operador || releasing === lote.id}
                          onClick={() => void release(lote)}
                          title="Liberar lote y dejarlo sin responsable"
                          className="whitespace-nowrap rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500"
                        >
                          {releasing === lote.id ? 'Liberando…' : 'Liberar'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-slate-100 bg-slate-50 px-4 py-2 text-xs text-slate-500">{items.length} lotes mostrados</div>
        </div>

        <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="text-lg font-bold text-slate-900">Productividad de operadores</h2>
            <p className="mt-1 text-sm text-slate-500">Carga actual y producción registrada durante los últimos 30 días.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px] text-sm">
              <thead className="bg-slate-50">
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3">Operador</th>
                  <th className="px-4 py-3 text-center">Lotes asignados</th>
                  <th className="px-4 py-3 text-center">Lotes completados</th>
                  <th className="px-4 py-3 text-center">PDF asignados</th>
                  <th className="px-4 py-3">Avance</th>
                  <th className="px-4 py-3 text-center">PDF procesados 30 días</th>
                  <th className="px-4 py-3 text-center">Promedio PDF/día</th>
                </tr>
              </thead>
              <tbody>
                {operatorStats.map((operator) => (
                  <tr key={operator.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/70">
                    <td className="px-4 py-3"><div className="font-semibold text-slate-800">{operator.nombre || operator.username}</div><div className="text-xs text-slate-400">@{operator.username}</div></td>
                    <td className="px-4 py-3 text-center font-medium">{operator.lotes_asignados}</td>
                    <td className="px-4 py-3 text-center text-emerald-700">{operator.lotes_completados}</td>
                    <td className="px-4 py-3 text-center">{operator.total}</td>
                    <td className="px-4 py-3"><div className="flex items-center gap-2"><div className="h-2 w-24 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-emerald-500" style={{ width: `${operator.porcentaje}%` }} /></div><span className="text-xs font-bold text-slate-700">{operator.porcentaje}%</span></div></td>
                    <td className="px-4 py-3 text-center"><span className="rounded-full bg-blue-100 px-2.5 py-1 font-bold text-blue-700">{operator.realizados_30_dias}</span></td>
                    <td className="px-4 py-3 text-center font-semibold text-slate-700">{operator.promedio_diario_30_dias}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {operatorStats.length === 0 && <div className="p-8 text-center text-sm text-slate-400">No hay operadores activos.</div>}
        </div></>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {items.map((lote) => (
            <article key={lote.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-100 px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="truncate text-lg font-bold text-slate-900">{lote.nombre}</h2>
                    <p className="truncate text-xs text-slate-400" title={lote.relative_path}>{lote.relative_path}</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{lote.estado.replace('_', ' ')}</span>
                </div>
              </div>
              <div className="space-y-4 p-5">
                <ProgressBar metricas={lote.metricas} />
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><div className="text-xs text-slate-400">Operador</div><div className="font-medium text-slate-700">{lote.operador?.nombre || lote.operador?.username || 'Sin asignar'}</div></div>
                  <div><div className="text-xs text-slate-400">Asignado</div><div className="font-medium text-slate-700">{dateLabel(lote.assigned_at)}</div></div>
                </div>
                <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
                  <Link to={`/lote?path=${encodeURIComponent(lote.relative_path)}`} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700">Abrir lote</Link>
                  <button
                    disabled={lote.metricas.total === 0 || lote.metricas.pendientes > 0 || !!lote.notified_at || notifying === lote.id}
                    onClick={() => void notify(lote)}
                    className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500"
                  >
                    {lote.notified_at ? `Notificado ${dateLabel(lote.notified_at)}` : notifying === lote.id ? 'Notificando…' : 'Notificar finalización'}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      {reassigning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4" role="dialog" aria-modal="true" aria-labelledby="reassign-title">
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl">
            <div className="border-b border-slate-200 px-5 py-4">
              <h2 id="reassign-title" className="text-lg font-bold text-slate-900">Reasignar lote</h2>
              <p className="mt-1 truncate text-sm text-slate-500" title={reassigning.relative_path}>{reassigning.nombre}</p>
            </div>
            <div className="space-y-4 p-5">
              <div><label className="mb-1 block text-sm font-medium text-slate-700">Buscar responsable</label><input autoFocus value={operatorSearch} onChange={(event) => setOperatorSearch(event.target.value)} placeholder="Nombre o usuario" className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" /></div>
              <div><label className="mb-1 block text-sm font-medium text-slate-700">Nuevo responsable</label><select value={newOperatorId} onChange={(event) => setNewOperatorId(Number(event.target.value))} className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-blue-500"><option value="0">Seleccione un responsable</option>{filteredOperators.map((operator) => <option key={operator.id} value={operator.id}>{operator.nombre || operator.username} (@{operator.username})</option>)}</select></div>
              <div className="rounded-lg bg-slate-50 px-4 py-3 text-xs text-slate-500">El avance y el historial del lote se conservarán. El nuevo responsable recibirá una notificación por correo.</div>
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4"><button disabled={savingReassignment} onClick={() => setReassigning(null)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Cancelar</button><button disabled={!newOperatorId || savingReassignment || newOperatorId === reassigning.operador?.id} onClick={() => void saveReassignment()} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400">{savingReassignment ? 'Reasignando…' : 'Confirmar reasignación'}</button></div>
          </div>
        </div>
      )}
    </div>
  )
}
