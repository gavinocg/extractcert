import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useToast } from '../store/toast'
import type { Lote } from '../types/lotes'

interface ArchiveSummary {
  lote: Lote
  resumen: {
    extracciones: number
    reextracciones: number
    errores: number
    paginas_extraidas: number
    primer_procesamiento: string | null
    ultimo_procesamiento: string | null
    duracion_atencion_segundos: number | null
  }
  participantes: Array<{ id: number; username: string; nombre: string; realizados: number; paginas: number; errores: number }>
  historial: Array<{ id: number; operador: string; asignado_por: string | null; assigned_at: string; unassigned_at: string | null; completed_at: string | null; notified_at: string | null; motivo: string | null }>
  notificaciones: Array<{ tipo: string; destinatario: string; estado: string; intentos: number; sent_at: string | null }>
}

interface ArchiveGroup {
  key: string
  label: string
  timestamp: number
  items: Lote[]
}

const MONTHS = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

function dateLabel(value: string | null) {
  return value ? new Date(value).toLocaleString('es-EC') : '—'
}

function durationLabel(seconds: number | null) {
  if (seconds === null) return '—'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return [days ? `${days} d` : '', hours ? `${hours} h` : '', `${minutes} min`].filter(Boolean).join(' ')
}

function lotMonth(lote: Lote) {
  const match = lote.nombre.match(/(?:^|\D)(\d{1,2})-(\d{1,2})-(\d{4})(?:\D|$)/)
  if (!match) return null

  const first = Number(match[1])
  const second = Number(match[2])
  const year = Number(match[3])
  if (first < 1 || second < 1) return null

  if (second <= 12 && first <= 31) return { year, month: second, day: first, timestamp: Date.UTC(year, second - 1, first) }
  if (first <= 12 && second <= 31) return { year, month: first, day: second, timestamp: Date.UTC(year, first - 1, second) }
  return null
}

function groupLots(items: Lote[]): ArchiveGroup[] {
  const groups = new Map<string, ArchiveGroup>()
  const stamps = new Map<number, number>()

  items.forEach((lote) => {
    const date = lotMonth(lote)
    const key = date ? `${date.year}-${String(date.month).padStart(2, '0')}` : 'sin-fecha'
    const group = groups.get(key) ?? {
      key,
      label: date ? `${MONTHS[date.month - 1]} ${date.year}` : 'Sin fecha',
      timestamp: date ? Date.UTC(date.year, date.month - 1) : Number.NEGATIVE_INFINITY,
      items: [],
    }
    group.items.push(lote)
    groups.set(key, group)
    stamps.set(lote.id, date?.timestamp ?? 0)
  })

  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      items: group.items.sort((a, b) => (stamps.get(b.id) ?? 0) - (stamps.get(a.id) ?? 0) || b.nombre.localeCompare(a.nombre, 'es', { numeric: true })),
    }))
    .sort((a, b) => b.timestamp - a.timestamp)
}

function withOperatorLabel(lote: Lote): Lote {
  const names = lote.operadores.map((operator) => operator.nombre || operator.username).join(', ')
  return names ? { ...lote, operador: { ...(lote.operador ?? lote.operadores[0]), nombre: names } } : lote
}

export default function Archivados() {
  const toast = useToast((state) => state.show)
  const [items, setItems] = useState<Lote[]>([])
  const [expandedMonth, setExpandedMonth] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<ArchiveSummary | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(0)
  const detailController = useRef<AbortController | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const lots = (await api.get<Lote[]>('/api/lotes?scope=archived')).map(withOperatorLabel)
      setItems(lots)
      setExpandedMonth(null)
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudieron cargar los archivados', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void load()
    return () => detailController.current?.abort()
  }, [load])

  const openDetail = async (lote: Lote) => {
    detailController.current?.abort()
    const controller = new AbortController()
    detailController.current = controller
    setLoadingDetail(lote.id)
    try {
      const summary = await api.get<ArchiveSummary>(`/api/lotes/${lote.id}/archive-summary`, { signal: controller.signal })
      if (controller.signal.aborted) return
      setDetail({ ...summary, lote: withOperatorLabel(summary.lote) })
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) toast(error instanceof Error ? error.message : 'No se pudo cargar el resumen', 'error')
    } finally {
      if (!controller.signal.aborted) setLoadingDetail(0)
    }
  }

  const groups = groupLots(items)

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-2 text-xs font-bold uppercase tracking-[.22em] text-red-600">Histórico</div>
          <h1 className="text-3xl font-bold text-slate-900">Archivados</h1>
          <p className="mt-1 text-sm text-slate-500">Lotes atendidos al 100% y despachados correctamente.</p>
        </div>
        <button onClick={() => void load()} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Actualizar</button>
      </div>

      {loading ? (
        <div className="text-slate-500">Cargando archivados…</div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">Todavía no hay lotes archivados.</div>
      ) : (
        <div className="space-y-3">
          {groups.map((group) => {
            const expanded = expandedMonth === group.key
            const pdfCount = group.items.reduce((total, lote) => total + lote.metricas.total, 0)
            return (
              <section key={group.key} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <button
                  type="button"
                  onClick={() => setExpandedMonth(expanded ? null : group.key)}
                  aria-expanded={expanded}
                  aria-controls={`archive-month-${group.key}`}
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-slate-50"
                >
                  <div>
                    <h2 className="text-lg font-bold tracking-wide text-slate-900">{group.label}</h2>
                    <p className="mt-0.5 text-xs text-slate-500">{group.items.length} {group.items.length === 1 ? 'lote' : 'lotes'} · {pdfCount} PDF</p>
                  </div>
                  <svg className={`h-5 w-5 shrink-0 text-slate-500 transition-transform ${expanded ? 'rotate-180' : ''}`} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fillRule="evenodd" d="M5.22 7.22a.75.75 0 011.06 0L10 10.94l3.72-3.72a.75.75 0 111.06 1.06l-4.25 4.25a.75.75 0 01-1.06 0L5.22 8.28a.75.75 0 010-1.06z" clipRule="evenodd" />
                  </svg>
                </button>
                {expanded && (
                  <div id={`archive-month-${group.key}`} className="overflow-x-auto border-t border-slate-200">
                    <table className="w-full min-w-[900px] text-sm">
                      <thead className="bg-slate-50">
                        <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                          <th className="px-4 py-3">Lote</th><th className="px-4 py-3">Responsable</th><th className="px-4 py-3 text-center">PDF</th><th className="px-4 py-3">Asignado</th><th className="px-4 py-3">Finalizado</th><th className="px-4 py-3">Despachado</th><th className="px-4 py-3 text-right">Acción</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.items.map((lote) => (
                          <tr key={lote.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/70">
                            <td className="max-w-72 px-4 py-3"><div className="truncate font-semibold text-slate-900">{lote.nombre}</div><div className="truncate text-xs text-slate-400" title={lote.relative_path}>{lote.relative_path}</div></td>
                            <td className="px-4 py-3"><div className="font-medium text-slate-700">{lote.operador?.nombre || lote.operador?.username || '—'}</div>{lote.operador?.nombre && <div className="text-xs text-slate-400">@{lote.operador.username}</div>}</td>
                            <td className="px-4 py-3 text-center font-bold text-slate-700">{lote.metricas.total}</td>
                            <td className="whitespace-nowrap px-4 py-3 text-xs">{dateLabel(lote.assigned_at)}</td>
                            <td className="whitespace-nowrap px-4 py-3 text-xs">{dateLabel(lote.completed_at)}</td>
                            <td className="whitespace-nowrap px-4 py-3 text-xs">{dateLabel(lote.notified_at)}</td>
                            <td className="px-4 py-3 text-right"><button onClick={() => void openDetail(lote)} disabled={loadingDetail === lote.id} className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700 disabled:opacity-50">{loadingDetail === lote.id ? 'Cargando…' : 'Ver'}</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            )
          })}
        </div>
      )}

      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3 sm:p-6" role="dialog" aria-modal="true">
          <div className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-200 bg-white px-5 py-4">
              <div><div className="text-xs font-bold uppercase tracking-widest text-emerald-600">Atendido y despachado</div><h2 className="text-xl font-bold text-slate-900">{detail.lote.nombre}</h2><p className="text-xs text-slate-400">{detail.lote.relative_path}</p></div>
              <button onClick={() => setDetail(null)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50">Cerrar</button>
            </div>
            <div className="space-y-6 p-5">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[
                ['PDF atendidos', detail.lote.metricas.total], ['Extracciones', detail.resumen.extracciones], ['Con error', detail.resumen.errores], ['Páginas extraídas', detail.resumen.paginas_extraidas], ['Reextracciones', detail.resumen.reextracciones], ['Duración de atención', durationLabel(detail.resumen.duracion_atencion_segundos)], ['Inicio procesamiento', dateLabel(detail.resumen.primer_procesamiento)], ['Último procesamiento', dateLabel(detail.resumen.ultimo_procesamiento)],
              ].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-slate-200 bg-slate-50 p-4"><div className="text-xs uppercase tracking-wide text-slate-400">{label}</div><div className="mt-1 text-lg font-bold text-slate-800">{value}</div></div>)}</div>
              <div><h3 className="mb-3 font-bold text-slate-800">Información de atención</h3><div className="grid gap-3 rounded-xl border border-slate-200 p-4 sm:grid-cols-2 lg:grid-cols-4"><div><div className="text-xs text-slate-400">Responsable final</div><div className="font-semibold">{detail.lote.operador?.nombre || detail.lote.operador?.username || '—'}</div></div><div><div className="text-xs text-slate-400">Asignado por</div><div className="font-semibold">{detail.lote.asignado_por?.nombre || detail.lote.asignado_por?.username || '—'}</div></div><div><div className="text-xs text-slate-400">Completado</div><div className="font-semibold">{dateLabel(detail.lote.completed_at)}</div></div><div><div className="text-xs text-slate-400">Despachado</div><div className="font-semibold">{dateLabel(detail.lote.notified_at)}</div></div></div></div>
              <div><h3 className="mb-3 font-bold text-slate-800">Participación por usuario</h3>{detail.participantes.length ? <div className="overflow-x-auto rounded-xl border border-slate-200"><table className="w-full min-w-[650px] text-sm"><thead className="bg-slate-50"><tr className="text-left text-xs uppercase text-slate-400"><th className="px-4 py-2">Usuario</th><th className="px-4 py-2 text-center">PDF realizados</th><th className="px-4 py-2 text-center">Páginas</th><th className="px-4 py-2 text-center">Errores</th></tr></thead><tbody>{detail.participantes.map((item) => <tr key={item.id} className="border-t"><td className="px-4 py-2"><div className="font-medium">{item.nombre || item.username}</div><div className="text-xs text-slate-400">@{item.username}</div></td><td className="px-4 py-2 text-center">{item.realizados}</td><td className="px-4 py-2 text-center">{item.paginas}</td><td className="px-4 py-2 text-center">{item.errores}</td></tr>)}</tbody></table></div> : <p className="text-sm text-slate-400">Sin actividad individual registrada.</p>}</div>
              <div><h3 className="mb-3 font-bold text-slate-800">Historial de responsables</h3><div className="space-y-2">{detail.historial.map((item) => <div key={item.id} className="rounded-xl border border-slate-200 p-3 text-sm"><div className="font-semibold">{item.operador}</div><div className="mt-1 grid gap-1 text-xs text-slate-500 sm:grid-cols-3"><span>Asignado: {dateLabel(item.assigned_at)}</span><span>Completado: {dateLabel(item.completed_at)}</span><span>Notificado: {dateLabel(item.notified_at)}</span></div>{item.asignado_por && <div className="mt-1 text-xs text-slate-400">Asignado por {item.asignado_por}</div>}{item.motivo && <div className="mt-1 text-xs text-slate-500">{item.motivo}</div>}</div>)}</div></div>
              <div><h3 className="mb-3 font-bold text-slate-800">Notificaciones</h3><div className="space-y-2">{detail.notificaciones.map((item, index) => <div key={`${item.destinatario}-${index}`} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm"><span>{item.destinatario}</span><span className="text-xs text-slate-500">{item.tipo} · {item.estado} · {dateLabel(item.sent_at)}</span></div>)}</div></div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
