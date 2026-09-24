import type { MetricasLote } from '../types/lotes'

export default function ProgressBar({ metricas }: { metricas: MetricasLote }) {
  const done = metricas.total ? (metricas.realizados * 100) / metricas.total : 0
  const errors = metricas.total ? (metricas.errores * 100) / metricas.total : 0
  return (
    <div className="min-w-44">
      <div className="mb-1 flex justify-between text-xs text-slate-500">
        <span>{metricas.realizados} realizados · {metricas.errores} errores</span>
        <strong className="text-slate-700">{metricas.porcentaje}%</strong>
      </div>
      <div className="flex h-2 overflow-hidden rounded-full bg-slate-200">
        <span className="bg-emerald-500" style={{ width: `${done}%` }} />
        <span className="bg-red-500" style={{ width: `${errors}%` }} />
      </div>
      <div className="mt-1 text-xs text-slate-400">{metricas.pendientes} pendientes · {metricas.total} total</div>
    </div>
  )
}
