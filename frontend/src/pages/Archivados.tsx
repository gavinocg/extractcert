import { useCallback, useEffect, useState } from 'react'
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

export default function Archivados() {
  const toast = useToast((state) => state.show)
  const [items, setItems] = useState<Lote[]>([])
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<ArchiveSummary | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await api.get<Lote[]>('/api/lotes?scope=archived'))
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudieron cargar los archivados', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => { void load() }, [load])

  const openDetail = async (lote: Lote) => {
    setLoadingDetail(lote.id)
    try {
      setDetail(await api.get<ArchiveSummary>(`/api/lotes/${lote.id}/archive-summary`))
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudo cargar el resumen', 'error')
    } finally {
      setLoadingDetail(0)
    }
  }

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div><div className="mb-2 text-xs font-bold uppercase tracking-[.22em] text-red-600">Histórico</div><h1 className="text-3xl font-bold text-slate-900">Archivados</h1><p className="mt-1 text-sm text-slate-500">Lotes atendidos al 100% y despachados correctamente.</p></div>
        <button onClick={() => void load()} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Actualizar</button>
      </div>

      {loading ? <div className="text-slate-500">Cargando archivados…</div> : items.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">Todavía no hay lotes archivados.</div> : (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="bg-slate-50"><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500"><th className="px-4 py-3">Lote</th><th className="px-4 py-3">Responsable</th><th className="px-4 py-3 text-center">PDF</th><th className="px-4 py-3">Asignado</th><th className="px-4 py-3">Finalizado</th><th className="px-4 py-3">Despachado</th><th className="px-4 py-3 text-right">Acción</th></tr></thead><tbody>{items.map((lote) => <tr key={lote.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/70"><td className="max-w-72 px-4 py-3"><div className="truncate font-semibold text-slate-900">{lote.nombre}</div><div className="truncate text-xs text-slate-400" title={lote.relative_path}>{lote.relative_path}</div></td><td className="px-4 py-3"><div className="font-medium text-slate-700">{lote.operador?.nombre || lote.operador?.username || '—'}</div>{lote.operador?.nombre && <div className="text-xs text-slate-400">@{lote.operador.username}</div>}</td><td className="px-4 py-3 text-center font-bold text-slate-700">{lote.metricas.total}</td><td className="whitespace-nowrap px-4 py-3 text-xs">{dateLabel(lote.assigned_at)}</td><td className="whitespace-nowrap px-4 py-3 text-xs">{dateLabel(lote.completed_at)}</td><td className="whitespace-nowrap px-4 py-3 text-xs">{dateLabel(lote.notified_at)}</td><td className="px-4 py-3 text-right"><button onClick={() => void openDetail(lote)} disabled={loadingDetail === lote.id} className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700 disabled:opacity-50">{loadingDetail === lote.id ? 'Cargando…' : 'Ver'}</button></td></tr>)}</tbody></table></div><div className="border-t border-slate-100 bg-slate-50 px-4 py-2 text-xs text-slate-500">{items.length} lotes archivados</div></div>
      )}

      {detail && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3 sm:p-6" role="dialog" aria-modal="true"><div className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-2xl bg-white shadow-2xl"><div className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-200 bg-white px-5 py-4"><div><div className="text-xs font-bold uppercase tracking-widest text-emerald-600">Atendido y despachado</div><h2 className="text-xl font-bold text-slate-900">{detail.lote.nombre}</h2><p className="text-xs text-slate-400">{detail.lote.relative_path}</p></div><button onClick={() => setDetail(null)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50">Cerrar</button></div><div className="space-y-6 p-5">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[
          ['PDF atendidos', detail.lote.metricas.total], ['Extracciones', detail.resumen.extracciones], ['Con error', detail.resumen.errores], ['Páginas extraídas', detail.resumen.paginas_extraidas], ['Reextracciones', detail.resumen.reextracciones], ['Duración de atención', durationLabel(detail.resumen.duracion_atencion_segundos)], ['Inicio procesamiento', dateLabel(detail.resumen.primer_procesamiento)], ['Último procesamiento', dateLabel(detail.resumen.ultimo_procesamiento)],
        ].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-slate-200 bg-slate-50 p-4"><div className="text-xs uppercase tracking-wide text-slate-400">{label}</div><div className="mt-1 text-lg font-bold text-slate-800">{value}</div></div>)}</div>
        <div><h3 className="mb-3 font-bold text-slate-800">Información de atención</h3><div className="grid gap-3 rounded-xl border border-slate-200 p-4 sm:grid-cols-2 lg:grid-cols-4"><div><div className="text-xs text-slate-400">Responsable final</div><div className="font-semibold">{detail.lote.operador?.nombre || detail.lote.operador?.username || '—'}</div></div><div><div className="text-xs text-slate-400">Asignado por</div><div className="font-semibold">{detail.lote.asignado_por?.nombre || detail.lote.asignado_por?.username || '—'}</div></div><div><div className="text-xs text-slate-400">Completado</div><div className="font-semibold">{dateLabel(detail.lote.completed_at)}</div></div><div><div className="text-xs text-slate-400">Despachado</div><div className="font-semibold">{dateLabel(detail.lote.notified_at)}</div></div></div></div>
        <div><h3 className="mb-3 font-bold text-slate-800">Participación por usuario</h3>{detail.participantes.length ? <div className="overflow-x-auto rounded-xl border border-slate-200"><table className="w-full min-w-[650px] text-sm"><thead className="bg-slate-50"><tr className="text-left text-xs uppercase text-slate-400"><th className="px-4 py-2">Usuario</th><th className="px-4 py-2 text-center">PDF realizados</th><th className="px-4 py-2 text-center">Páginas</th><th className="px-4 py-2 text-center">Errores</th></tr></thead><tbody>{detail.participantes.map((item) => <tr key={item.id} className="border-t"><td className="px-4 py-2"><div className="font-medium">{item.nombre || item.username}</div><div className="text-xs text-slate-400">@{item.username}</div></td><td className="px-4 py-2 text-center">{item.realizados}</td><td className="px-4 py-2 text-center">{item.paginas}</td><td className="px-4 py-2 text-center">{item.errores}</td></tr>)}</tbody></table></div> : <p className="text-sm text-slate-400">Sin actividad individual registrada.</p>}</div>
        <div><h3 className="mb-3 font-bold text-slate-800">Historial de responsables</h3><div className="space-y-2">{detail.historial.map((item) => <div key={item.id} className="rounded-xl border border-slate-200 p-3 text-sm"><div className="font-semibold">{item.operador}</div><div className="mt-1 grid gap-1 text-xs text-slate-500 sm:grid-cols-3"><span>Asignado: {dateLabel(item.assigned_at)}</span><span>Completado: {dateLabel(item.completed_at)}</span><span>Notificado: {dateLabel(item.notified_at)}</span></div>{item.asignado_por && <div className="mt-1 text-xs text-slate-400">Asignado por {item.asignado_por}</div>}{item.motivo && <div className="mt-1 text-xs text-slate-500">{item.motivo}</div>}</div>)}</div></div>
        <div><h3 className="mb-3 font-bold text-slate-800">Notificaciones</h3><div className="space-y-2">{detail.notificaciones.map((item, index) => <div key={`${item.destinatario}-${index}`} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm"><span>{item.destinatario}</span><span className="text-xs text-slate-500">{item.tipo} · {item.estado} · {dateLabel(item.sent_at)}</span></div>)}</div></div>
      </div></div></div>}
    </div>
  )
}
