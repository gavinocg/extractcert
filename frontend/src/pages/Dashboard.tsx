import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import ErrorModal from '../components/ErrorModal'
import EnviarErroresModal from '../components/EnviarErroresModal'
import ExtraerModal from '../components/ExtraerModal'
import { useToast } from '../store/toast'

interface Realizado {
  id: number
  archivo: string
  original_path: string
  destino_path: string
  destino: string
  pagina_inicio: number
  pagina_fin: number
  estado: string
  username: string
  created_at: string | null
}

interface Item {
  nombre: string
  ruta: string
  estado: string
  extraccion_id: number | null
  destino_path: string | null
  pagina_inicio: number | null
  pagina_fin: number | null
  username: string | null
  error: { id: number; observacion: string; username: string | null } | null
}

interface Dash {
  origen: string
  repo: string
  pendientes: string[]
  realizados: Realizado[]
  total_realizados: number
  pagina: number
  tam: number
  items: Item[]
  total: number
  pendientes_count: number
  pagina_sugerida: number
}

export default function Dashboard() {
  const [searchParams] = useSearchParams()
  const [dash, setDash] = useState<Dash | null>(null)
  const [path, setPath] = useState<string | null>(null)
  const [dirs, setDirs] = useState<string[]>([])
  const [err, setErr] = useState('')
  const [cargando, setCargando] = useState(true)
  const [errorTarget, setErrorTarget] = useState<Item | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [showEnviar, setShowEnviar] = useState(false)
  const [extraerTarget, setExtraerTarget] = useState<{ ruta: string; ini?: number; fin?: number; extraccionId?: number; reextra?: boolean; error?: { id: number; observacion: string; username: string | null } | null } | null>(null)
  const toast = useToast((s) => s.show)

  const [dirsStats, setDirsStats] = useState<{ nombre: string; total: number; realizados: number; errores: number; pendientes: number; pctRealizado: number; pctError: number; pctPendiente: number }[]>([])

  const cargar = useCallback(async (ruta: string | null, pg?: number) => {
    setCargando(true)
    setErr('')
    try {
      const t = await api.get<{ base: string; actual: string; dirs: string[]; dirs_stats: { nombre: string; total: number; realizados: number; errores: number; pendientes: number; pctRealizado: number; pctError: number; pctPendiente: number }[]; pdfs: string[] }>(
        '/api/tree' + (ruta ? `?path=${encodeURIComponent(ruta)}` : ''),
      )
      setPath(t.actual)
      setDirs(t.dirs)
      setDirsStats(t.dirs_stats ?? [])
      const q = new URLSearchParams()
      if (t.actual) q.set('path', t.actual)
      if (pg !== undefined) q.set('pagina', String(pg))
      const d = await api.get<Dash>('/api/dashboard?' + q.toString())
      if (pg === undefined && d.pagina_sugerida !== d.pagina && d.total > d.tam) {
        const q2 = new URLSearchParams()
        q2.set('path', t.actual)
        q2.set('pagina', String(d.pagina_sugerida))
        const d2 = await api.get<Dash>('/api/dashboard?' + q2.toString())
        setDash(d2)
      } else {
        setDash(d)
      }
      setSelected([])
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Error')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    const qp = searchParams.get('path')
    const pg = parseInt(searchParams.get('pagina') ?? '', 10)
    if (qp) void cargar(qp, Number.isNaN(pg) ? undefined : pg)
    else void cargar(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const subir = (() => {
    if (!path || !dash) return null
    const idx = path.indexOf(dash.origen)
    if (idx < 0) return null
    const dentro = path.substring(idx + dash.origen.length).split('/').filter(Boolean)
    if (dentro.length === 0) return null
    const partes = dash.origen.split('/').filter(Boolean).concat(dentro.slice(0, -1))
    return '/' + partes.join('/')
  })()

  const guardarError = async (obs: string) => {
    if (!errorTarget) return
    await api.post('/api/errores', { ruta: errorTarget.ruta, observacion: obs })
    toast('Error guardado', 'success')
    void cargar(path, dash?.pagina)
  }

  const corregir = async (it: Item) => {
    if (!it.error) return
    await api.del(`/api/errores/${it.error.id}`)
    toast('Marcado como corregido', 'success')
    void cargar(path, dash?.pagina)
  }

  const toggleSel = (id: number) => setSelected((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const errorIdsPagina = dash ? dash.items.filter((it) => it.error).map((it) => it.error!.id) : []
  const allSel = errorIdsPagina.length > 0 && errorIdsPagina.every((id) => selected.includes(id))

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-800">Dashboard</h1>
      <p className="mb-4 text-sm text-slate-500">Navega las carpetas y extrae certificados.</p>

      {dash && (
        <div className="mb-4 flex flex-wrap items-center gap-1 rounded-lg bg-white px-3 py-2 text-sm shadow-sm">
          <Link to="/" className="text-slate-600 hover:underline" onClick={() => void cargar(null)}>
            {dash.origen}
          </Link>
          {(() => {
            const base = dash.origen.split('/').filter(Boolean)
            const rel = path ? path.substring(dash.origen.length).split('/').filter(Boolean) : []
            let acc = [...base]
            return rel.map((seg, i) => {
              acc = acc.concat(seg)
              const target = '/' + acc.join('/')
              return (
                <span key={i} className="flex items-center gap-1">
                  <span className="text-slate-300">/</span>
                  <button onClick={() => cargar(target)} className="font-medium text-slate-700 hover:underline">
                    {seg}
                  </button>
                </span>
              )
            })
          })()}
          {dash.repo && <span className="ml-auto text-xs text-slate-400">repo: {dash.repo}</span>}
        </div>
      )}

      {subir && (
        <button onClick={() => cargar(subir)} className="mb-3 text-sm text-slate-600 hover:underline">
          ← Subir un nivel
        </button>
      )}

      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}

      {cargando && !dash ? (
        <div className="text-slate-500">Cargando…</div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl bg-white p-4 shadow-sm">
            <div className="mb-3 text-sm font-semibold text-slate-700">Carpetas</div>
{dirs.length === 0 ? (
              <div className="text-sm text-slate-400">Sin subdirectorios.</div>
            ) : (
              <ul className="space-y-1">
                {dirs.map((d) => {
                  const s = dirsStats.find((x) => x.nombre === d)
                  const isFinal = s && s.total > 0
                  return (
                    <li key={d}>
                      <button
                        onClick={() => cargar(path ? `${path}/${d}` : d)}
                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-slate-100"
                      >
                        <span className="text-amber-500">□</span> <span className="flex-1 truncate">{d}</span>
                        {isFinal && (
                          <span className="ml-auto flex shrink-0 items-center gap-2">
                            <span className="flex h-2 w-24 shrink-0 overflow-hidden rounded-full bg-slate-200">
                              {s!.pctRealizado > 0 && <span className="h-full shrink-0 bg-emerald-500" style={{ width: `${s!.pctRealizado}%` }} />}
                              {s!.pctError > 0 && <span className="h-full shrink-0 bg-red-500" style={{ width: `${s!.pctError}%` }} />}
                              {s!.pctPendiente > 0 && <span className="h-full shrink-0 bg-slate-300" style={{ width: `${s!.pctPendiente}%` }} />}
                            </span>
                            <span className="shrink-0 text-right text-xs font-medium whitespace-nowrap text-emerald-700">{s!.pctRealizado}% ({s!.errores} errores, {s!.pendientes} pendientes)</span>
                          </span>
                        )}
                      </button>
                      {isFinal && (
                        <div className="ml-6 text-[11px] text-slate-400">
                          {s!.realizados} realizado · {s!.errores} error · {s!.pendientes} pendiente · {s!.total} total
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
            

            {dash && (
              <div className="mt-4 mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-700">PDFs en esta carpeta</span>
                <span className="text-xs text-slate-400">
                  {dash.pendientes_count} pendientes · {dash.total} total
                </span>
              </div>
            )}
            {dash && errorIdsPagina.length > 0 && (
              <div className="mb-2 flex items-center gap-2 text-xs">
                <label className="flex items-center gap-1">
                  <input type="checkbox" checked={allSel} onChange={() => setSelected(allSel ? [] : [...errorIdsPagina])} />
                  Seleccionar errores pág
                </label>
                <button
                  onClick={() => setShowEnviar(true)}
                  disabled={selected.length === 0}
                  className="rounded bg-amber-600 px-2 py-1 text-white disabled:opacity-40"
                >
                  Enviar ({selected.length})
                </button>
              </div>
            )}
            {!dash || dash.items.length === 0 ? (
              <div className="text-sm text-slate-400">Sin PDFs en esta carpeta.</div>
            ) : (
              <>
                <ul className="space-y-1">
                  {dash.items.map((it) => {
                    const pendiente = it.estado === 'pendiente'
                    const hasError = !!it.error
                    return (
                      <li key={it.ruta} className={`flex items-center justify-between gap-2 rounded px-2 py-1.5 ${hasError ? 'bg-red-50' : 'hover:bg-slate-50'}`}>
                        <span className="flex min-w-0 items-center gap-2 truncate text-sm">
                          {hasError && <input type="checkbox" checked={selected.includes(it.error!.id)} onChange={() => toggleSel(it.error!.id)} />}
                          <span className={hasError ? 'text-red-600' : pendiente ? 'text-slate-300' : 'text-emerald-600'}>{hasError ? '⚠' : pendiente ? '○' : '✓'}</span>
                          <span className={hasError ? 'text-red-700' : pendiente ? 'text-slate-700' : 'text-slate-500'}>📄 {it.nombre}</span>
                          {hasError ? <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-700">Error en digital</span> : !pendiente && <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">{it.estado === 'rehecho' ? 're-extraído' : 'realizado'}</span>}
                        </span>
                        <span className="flex shrink-0 items-center gap-1">
                          {hasError && (
                            <>
                              <button onClick={() => setErrorTarget(it)} className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-white">Ver error</button>
                              <button onClick={() => corregir(it)} className="rounded bg-emerald-600 px-2 py-1 text-xs text-white hover:bg-emerald-700">Corregido</button>
                            </>
                          )}
                          {pendiente && !hasError ? (
                            <button onClick={() => setExtraerTarget({ ruta: it.ruta, error: it.error })} className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700">Extraer</button>
                          ) : !hasError ? (
                            <button onClick={() => setExtraerTarget({ ruta: it.ruta, ini: it.pagina_inicio ?? 0, fin: it.pagina_fin ?? 0, extraccionId: it.extraccion_id ?? 0, reextra: true, error: it.error })} className="rounded border border-amber-300 px-2 py-1 text-xs text-amber-700 hover:bg-amber-50">Volver a extraer</button>
                          ) : null}
                        </span>
                      </li>
                    )
                  })}
                </ul>
                {dash.total > dash.tam && (
                  <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3 text-sm">
                    <span className="text-xs text-slate-400">
                      {(() => {
                        const desde = (dash.pagina - 1) * dash.tam + 1
                        const hasta = Math.min(dash.pagina * dash.tam, dash.total)
                        return `Mostrando ${desde}–${hasta} de ${dash.total} · pág ${dash.pagina}`
                      })()}
                    </span>
                    <div className="flex items-center gap-2">
                      <button onClick={() => void cargar(path, dash.pagina - 1)} disabled={dash.pagina <= 1} className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 disabled:opacity-40">‹ Anterior</button>
                      <button onClick={() => void cargar(path, dash.pagina + 1)} disabled={dash.pagina * dash.tam >= dash.total} className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 disabled:opacity-40">Siguiente ›</button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          <div className="rounded-xl bg-white p-4 shadow-sm">
            <div className="mb-3 text-sm font-semibold text-slate-700">Realizados</div>
            {!dash || dash.realizados.length === 0 ? (
              <div className="text-sm text-slate-400">Sin extracciones en esta carpeta.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-400">
                    <th className="py-1 pr-2">Archivo</th>
                    <th className="px-2 py-1">Págs</th>
                    <th className="px-2 py-1">Estado</th>
                    <th className="px-2 py-1">Usuario</th>
                    <th className="px-2 py-1">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {dash.realizados.map((r) => (
                    <tr key={r.id} className="border-t border-slate-100">
                      <td className="max-w-[160px] truncate py-1.5 pr-2"><a href={`/api/pdf/extraido?ruta=${encodeURIComponent(r.destino_path)}`} target="_blank" rel="noreferrer" className="text-red-600 hover:underline">{r.destino}</a></td>
                      <td className="px-2 py-1.5">{r.pagina_inicio}–{r.pagina_fin}</td>
                      <td className="px-2 py-1.5"><span className={r.estado === 'rehecho' ? 'rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700' : 'rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700'}>{r.estado === 'rehecho' ? 're-extraído' : 'realizado'}</span></td>
                      <td className="px-2 py-1.5">{r.username}</td>
                      <td className="px-2 py-1.5"><button onClick={() => setExtraerTarget({ ruta: r.original_path, ini: r.pagina_inicio, fin: r.pagina_fin, extraccionId: r.id, reextra: true })} className="rounded border border-amber-300 px-2 py-1 text-xs text-amber-700 hover:bg-amber-50">Re-extraer</button></td>

                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {dash && dash.total_realizados > dash.tam && (
              <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-sm">
                <span className="text-xs text-slate-400">{(() => { const desde = (dash.pagina - 1) * dash.tam + 1; const hasta = Math.min(dash.pagina * dash.tam, dash.total_realizados); return `Mostrando ${desde}–${hasta} de ${dash.total_realizados} · página ${dash.pagina}` })()}</span>
                <div className="flex items-center gap-2">
                  <button onClick={() => void cargar(path, dash.pagina - 1)} disabled={dash.pagina <= 1} className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 disabled:opacity-40">‹ Anterior</button>
                  <button onClick={() => void cargar(path, dash.pagina + 1)} disabled={dash.pagina * dash.tam >= dash.total_realizados} className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 disabled:opacity-40">Siguiente ›</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {errorTarget && <ErrorModal archivo={errorTarget.nombre} observacionInicial={errorTarget.error?.observacion} onClose={() => setErrorTarget(null)} onSave={guardarError} />}
      {showEnviar && <EnviarErroresModal ids={selected} onClose={() => setShowEnviar(false)} onSent={() => { setShowEnviar(false); toast('Enviado', 'success'); setSelected([]) }} />}
      {extraerTarget && <ExtraerModal ruta={extraerTarget.ruta} ini={extraerTarget.ini} fin={extraerTarget.fin} extraccionId={extraerTarget.extraccionId} reextra={extraerTarget.reextra} error={extraerTarget.error ?? null} onClose={() => setExtraerTarget(null)} onGuardado={() => void cargar(path, dash?.pagina)} onErrorSaved={() => void cargar(path, dash?.pagina)} />}
    </div>
  )
}
