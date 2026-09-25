import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import ErrorModal from '../components/ErrorModal'
import EnviarErroresModal from '../components/EnviarErroresModal'
import ExtraerModal from '../components/ExtraerModal'
import { useToast } from '../store/toast'
import { useAuth } from '../store/auth'

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
  nombre_usuario: string | null
  fecha: string | null
  error: { id: number; observacion: string; username: string | null; nombre: string | null } | null
  documento_id: number | null
  lease: { reservado_por: number | { id: number; username: string; nombre?: string } | null; lease_expires_at: string | null } | null
}

interface Claim { documento_id: number; lease_token: string; lease_expires_at: string }

function formatoFecha(iso: string | null): string {
  if (!iso) return '—'
  const m = iso.match(/(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
  if (!m) return iso
  return `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}`
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
  const user = useAuth((state) => state.user)
  const canBrowse = user?.rol !== 'usuario'
  const [searchParams] = useSearchParams()
  const [dash, setDash] = useState<Dash | null>(null)
  const [path, setPath] = useState<string | null>(null)
  const [dirs, setDirs] = useState<string[]>([])
  const [err, setErr] = useState('')
  const [cargando, setCargando] = useState(true)
  const [errorTarget, setErrorTarget] = useState<{ item: Item; leaseToken: string } | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [showEnviar, setShowEnviar] = useState(false)
  const [extraerTarget, setExtraerTarget] = useState<{ ruta: string; documentoId: number; leaseToken: string; ini?: number; fin?: number; extraccionId?: number; reextra?: boolean; error?: { id: number; observacion: string; username: string | null } | null } | null>(null)
  const [claiming, setClaiming] = useState(0)
  const toast = useToast((s) => s.show)
  const requestId = useRef(0)

  const [dirsStats, setDirsStats] = useState<{ nombre: string; total: number; realizados: number; errores: number; pendientes: number; pctRealizado: number; pctError: number; pctPendiente: number; pctAvance: number }[]>([])

  const cargar = useCallback(async (ruta: string | null, pg?: number) => {
    const currentRequest = ++requestId.current
    setCargando(true)
    setErr('')
    try {
      const t = await api.get<{ base: string; actual: string; dirs: string[]; dirs_stats: { nombre: string; total: number; realizados: number; errores: number; pendientes: number; pctRealizado: number; pctError: number; pctPendiente: number; pctAvance: number }[]; pdfs: string[] }>(
        '/api/tree' + (ruta ? `?path=${encodeURIComponent(ruta)}` : ''),
      )
      if (currentRequest !== requestId.current) return
      setPath(t.actual)
      setDirs(t.dirs)
      setDirsStats(t.dirs_stats ?? [])
      const q = new URLSearchParams()
      if (t.actual) q.set('path', t.actual)
      if (pg !== undefined) q.set('pagina', String(pg))
      const d = await api.get<Dash>('/api/dashboard?' + q.toString())
      if (currentRequest !== requestId.current) return
      if (pg === undefined && d.pagina_sugerida !== d.pagina && d.total > d.tam) {
        const q2 = new URLSearchParams()
        q2.set('path', t.actual)
        q2.set('pagina', String(d.pagina_sugerida))
        const d2 = await api.get<Dash>('/api/dashboard?' + q2.toString())
        if (currentRequest !== requestId.current) return
        setDash(d2)
      } else {
        setDash(d)
      }
      setSelected([])
    } catch (e) {
      if (currentRequest !== requestId.current) return
      setErr(e instanceof Error ? e.message : 'Error')
    } finally {
      if (currentRequest === requestId.current) setCargando(false)
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
    try {
      await api.post('/api/errores', { ruta: errorTarget.item.ruta, observacion: obs, documento_id: errorTarget.item.documento_id, lease_token: errorTarget.leaseToken })
      toast('Error guardado', 'success')
      void cargar(path, dash?.pagina)
      window.dispatchEvent(new Event('lotes:changed'))
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudo guardar el error', 'error')
      if (error instanceof ApiError && (error.status === 409 || error.status === 403)) void cargar(path, dash?.pagina)
      throw error
    }
  }

  const closeError = () => {
    if (errorTarget?.item.documento_id) void api.post(`/api/lotes/documentos/${errorTarget.item.documento_id}/release`, { lease_token: errorTarget.leaseToken }).catch(() => undefined)
    setErrorTarget(null)
    void cargar(path, dash?.pagina)
  }

  useEffect(() => {
    if (!errorTarget?.item.documento_id) return
    const heartbeat = window.setInterval(() => {
      void api.post(`/api/lotes/documentos/${errorTarget.item.documento_id}/heartbeat`, { lease_token: errorTarget.leaseToken }).catch((error) => {
        toast(error instanceof Error ? error.message : 'Se perdió la reserva del documento', 'error')
        setErrorTarget(null)
        void cargar(path, dash?.pagina)
      })
    }, 4 * 60 * 1000)
    return () => window.clearInterval(heartbeat)
  }, [errorTarget, path, dash?.pagina, cargar, toast])

  const corregir = async (it: Item) => {
    if (!it.error || !it.documento_id) return
    setClaiming(it.documento_id)
    try {
      const claim = await api.post<Claim>(`/api/lotes/documentos/${it.documento_id}/claim`, {})
      await api.del(`/api/errores/${it.error.id}?lease_token=${encodeURIComponent(claim.lease_token)}`)
      toast('Marcado como corregido', 'success')
      void cargar(path, dash?.pagina)
      window.dispatchEvent(new Event('lotes:changed'))
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudo corregir', 'error')
      if (error instanceof ApiError && (error.status === 409 || error.status === 403)) void cargar(path, dash?.pagina)
    } finally { setClaiming(0) }
  }

  const claimAndOpen = async (it: Item, mode: 'error' | 'extract') => {
    if (!it.documento_id) { toast('Documento no disponible en el inventario', 'error'); return }
    setClaiming(it.documento_id)
    try {
      const claim = await api.post<Claim>(`/api/lotes/documentos/${it.documento_id}/claim`, {})
      if (mode === 'error') setErrorTarget({ item: it, leaseToken: claim.lease_token })
      else setExtraerTarget({ ruta: it.ruta, documentoId: it.documento_id, leaseToken: claim.lease_token, ini: it.pagina_inicio ?? undefined, fin: it.pagina_fin ?? undefined, extraccionId: it.extraccion_id ?? undefined, reextra: it.estado !== 'pendiente', error: it.error })
      void cargar(path, dash?.pagina)
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudo reservar el documento', 'error')
      if (error instanceof ApiError && (error.status === 409 || error.status === 403)) void cargar(path, dash?.pagina)
    } finally { setClaiming(0) }
  }

  const toggleSel = (id: number) => setSelected((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const errorIdsPagina = dash ? dash.items.filter((it) => it.error).map((it) => it.error!.id) : []
  const allSel = errorIdsPagina.length > 0 && errorIdsPagina.every((id) => selected.includes(id))

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-800">Bandeja</h1>
      <p className="mb-4 text-sm text-slate-500">Navega las carpetas y extrae certificados.</p>

      {dash && (
        <div className="mb-4 flex flex-wrap items-center gap-1 rounded-lg bg-white px-3 py-2 text-sm shadow-sm">
          {canBrowse ? <Link to="/lote" className="text-slate-600 hover:underline" onClick={() => void cargar(null)}>{dash.origen}</Link> : <span className="font-medium text-slate-700">{path?.split('/').filter(Boolean).at(-1)}</span>}
          {canBrowse && (() => {
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

      {canBrowse && subir && (
        <button onClick={() => cargar(subir)} className="mb-3 text-sm text-slate-600 hover:underline">
          ← Subir un nivel
        </button>
      )}

      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}

      {cargando && !dash ? (
        <div className="text-slate-500">Cargando…</div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="rounded-xl bg-white p-4 shadow-sm">
            <div className="mb-3 text-sm font-semibold text-slate-700">Carpetas</div>
{dirs.length === 0 ? (
              <div className="text-sm text-slate-400">Sin subdirectorios.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-400">
                    <th className="px-2 py-1">Directorio</th>
                    <th className="px-2 py-1">Avance</th>
                  </tr>
                </thead>
                <tbody>
                  {dirs.map((d) => {
                    const s = dirsStats.find((x) => x.nombre === d)
                    const isFinal = s && s.total > 0
                    const destino = path ? `${path}/${d}` : d
                    return (
                      <tr
                        key={d}
                        onClick={() => cargar(destino)}
                        className="cursor-pointer border-t border-slate-100 align-top hover:bg-slate-50"
                      >
                        <td className="px-2 py-1.5">
                          <span className="flex items-center gap-2 text-left">
                            <span className="text-amber-500">□</span> <span className="truncate hover:underline">{d}</span>
                          </span>
                          {isFinal && (
                            <div className="ml-6 text-[11px] text-slate-400">
                              {s!.realizados} realizado · {s!.errores} error · {s!.pendientes} pendiente · {s!.total} total
                            </div>
                          )}
                        </td>
                        <td className="px-2 py-1.5">
                          {isFinal ? (
                            <span className="flex items-center justify-start gap-2">
                              <span className="flex h-2 w-32 shrink-0 overflow-hidden rounded-full bg-slate-200">
                                {s!.pctRealizado > 0 && <span className="h-full shrink-0 bg-emerald-500" style={{ width: `${s!.pctRealizado}%` }} />}
                                {s!.pctError > 0 && <span className="h-full shrink-0 bg-red-500" style={{ width: `${s!.pctError}%` }} />}
                                {s!.pctPendiente > 0 && <span className="h-full shrink-0 bg-slate-300" style={{ width: `${s!.pctPendiente}%` }} />}
                              </span>
                              <span className="shrink-0 text-xs font-medium whitespace-nowrap text-emerald-700">{s!.pctAvance}% ({s!.errores} errores, {s!.pendientes} pendientes)</span>
                            </span>
                          ) : (
                            <span className="text-xs text-slate-300">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
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
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-400">
                      <th className="px-2 py-1">Archivo</th>
                      <th className="px-2 py-1">Nombre</th>
                      <th className="px-2 py-1">Fecha</th>
                      <th className="px-2 py-1">Acción</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dash.items.map((it) => {
                      const pendiente = it.estado === 'pendiente'
                      const hasError = !!it.error
                      const realizado = !pendiente && !hasError
                      const usuario = it.nombre_usuario || it.error?.nombre || it.username || it.error?.username || '—'
                      const activeLease = !!it.lease?.lease_expires_at && new Date(it.lease.lease_expires_at).getTime() > Date.now()
                      const leaseOwner = it.lease?.reservado_por
                      const reservedBy = leaseOwner && typeof leaseOwner === 'object' ? (leaseOwner.nombre || leaseOwner.username) : leaseOwner === user?.id ? 'ti' : `usuario ${leaseOwner}`
                      return (
                        <tr key={it.ruta} className={`${hasError ? 'bg-red-50' : realizado ? 'bg-emerald-50' : 'hover:bg-slate-50'}`}>
                          <td className="max-w-[220px] px-2 py-1.5">
                            <span className="flex min-w-0 items-center gap-2 truncate">
                              {hasError && <input type="checkbox" checked={selected.includes(it.error!.id)} onChange={() => toggleSel(it.error!.id)} />}
                              <span className={hasError ? 'text-red-600' : pendiente ? 'text-slate-300' : 'text-emerald-600'}>{hasError ? '⚠' : pendiente ? '○' : '✓'}</span>
                              <span className={hasError ? 'truncate text-red-700' : pendiente ? 'truncate text-slate-700' : 'truncate text-emerald-800'}>📄 {it.nombre}</span>
                              {hasError ? <span className="shrink-0 rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-700">Error en digital</span> : !pendiente && <span className="shrink-0 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">{it.estado === 'rehecho' ? 're-extraído' : 'realizado'}</span>}
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-2 py-1.5 text-slate-600">{usuario}</td>
                          <td className="whitespace-nowrap px-2 py-1.5 text-slate-600">{formatoFecha(it.fecha)}</td>
                          <td className="px-2 py-1.5">
                            <span className="flex shrink-0 items-center gap-1">
                              <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${activeLease ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'}`}>{activeLease ? `En uso por ${reservedBy}` : 'Disponible'}</span>
                              {hasError && (
                                <>
                                  <button disabled={claiming === it.documento_id} onClick={() => void claimAndOpen(it, 'error')} className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-white disabled:opacity-40">Ver/modificar error</button>
                                  <button disabled={claiming === it.documento_id} onClick={() => void corregir(it)} className="rounded bg-emerald-600 px-2 py-1 text-xs text-white hover:bg-emerald-700 disabled:opacity-40">Corregido</button>
                                </>
                              )}
                              {pendiente && !hasError ? (
                                <button disabled={claiming === it.documento_id} onClick={() => void claimAndOpen(it, 'extract')} className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-40">Extraer</button>
                              ) : !hasError ? (
                                <button disabled={claiming === it.documento_id} onClick={() => void claimAndOpen(it, 'extract')} className="rounded border border-amber-300 px-2 py-1 text-xs text-amber-700 hover:bg-amber-50 disabled:opacity-40">Crear nueva versión</button>
                              ) : null}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
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
        </div>
      )}
      {errorTarget && <ErrorModal archivo={errorTarget.item.nombre} observacionInicial={errorTarget.item.error?.observacion} onClose={closeError} onSave={guardarError} />}
      {showEnviar && <EnviarErroresModal ids={selected} onClose={() => setShowEnviar(false)} onSent={() => { setShowEnviar(false); toast('Enviado', 'success'); setSelected([]) }} />}
      {extraerTarget && <ExtraerModal ruta={extraerTarget.ruta} documentoId={extraerTarget.documentoId} leaseToken={extraerTarget.leaseToken} ini={extraerTarget.ini} fin={extraerTarget.fin} extraccionId={extraerTarget.extraccionId} reextra={extraerTarget.reextra} error={extraerTarget.error ?? null} onClose={() => setExtraerTarget(null)} onLeaseLost={() => void cargar(path, dash?.pagina)} onGuardado={() => { void cargar(path, dash?.pagina); window.dispatchEvent(new Event('lotes:changed')) }} onErrorSaved={() => { void cargar(path, dash?.pagina); window.dispatchEvent(new Event('lotes:changed')) }} />}
    </div>
  )
}
