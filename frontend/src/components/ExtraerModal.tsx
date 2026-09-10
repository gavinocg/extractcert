import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import ErrorModal from './ErrorModal'
import PdfViewer, { PdfViewerHandle, Sel } from './PdfViewer'
import { useToast } from '../store/toast'

interface Props {
  ruta: string
  ini?: number
  fin?: number
  extraccionId?: number
  reextra?: boolean
  error?: { id: number; observacion: string; username: string | null } | null
  onClose: () => void
  onGuardado: () => void
  onErrorSaved?: () => void
}

interface PreviewResp {
  ok: boolean
  nombre: string
  paginas: number
  url: string
}

export default function ExtraerModal({ ruta, ini = 0, fin = 0, extraccionId = 0, reextra = false, error, onClose, onGuardado, onErrorSaved }: Props) {
  const toast = useToast((s) => s.show)
  const nombre = decodeURIComponent(ruta.split('/').pop() ?? '')
  const original = `/api/pdf/original?ruta=${encodeURIComponent(ruta)}`
  const [pred, setPred] = useState<Sel>({ inicio: ini, fin })
  const [prev, setPrev] = useState<PreviewResp | null>(null)
  const [prevUrl, setPrevUrl] = useState('')
  const [busyPre, setBusyPre] = useState(false)
  const [busyGuardar, setBusyGuardar] = useState(false)
  const [ayuda, setAyuda] = useState(false)
  const [showErrorModal, setShowErrorModal] = useState(false)
  const [errorLocal, setErrorLocal] = useState(error ?? null)
  const viewerRef = useRef<PdfViewerHandle>(null)

  useEffect(() => {
    setPred({ inicio: ini, fin })
    setPrev(null)
    setPrevUrl('')
    setErrorLocal(error ?? null)
  }, [ruta, ini, fin, error])

  const seleccionValida = pred.inicio > 0 && pred.fin >= pred.inicio

  const previsualizar = async () => {
    setBusyPre(true)
    try {
      const rot = viewerRef.current?.getRotation() ?? 0
      const r = await api.post<PreviewResp>('/api/extracciones/preview', { ruta, inicio: pred.inicio, fin: pred.fin, rotacion: rot })
      setPrevUrl(r.url)
      setPrev(r)
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Error', 'error')
    } finally {
      setBusyPre(false)
    }
  }

  const guardar = async () => {
    if (!pred.inicio) return
    setBusyGuardar(true)
    try {
      const rot = viewerRef.current?.getRotation() ?? 0
      const r = await api.post<{ nombre: string }>('/api/extracciones/guardar', { ruta, inicio: pred.inicio, fin: pred.fin, reextra: reextra ? 1 : 0, extraccion_id: extraccionId, rotacion: rot })
      toast(`Extracción guardada: ${r.nombre}`, 'success')
      onGuardado()
      onClose()
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Error', 'error')
      setBusyGuardar(false)
    }
  }

  const isPreview = !!prev

  const guardarError = async (obs: string) => {
    await api.post('/api/errores', { ruta, observacion: obs })
    toast('Error guardado', 'success')
    const nueva = { id: errorLocal?.id ?? Date.now(), observacion: obs, username: null }
    setErrorLocal(nueva as never)
    setShowErrorModal(false)
    onErrorSaved?.()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-2" onClick={onClose}>
      <div className="flex h-[96vh] w-[96vw] max-w-[1600px] flex-col overflow-hidden rounded-xl bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-3">
          <div className="min-w-0">
            <h2 className="flex items-center gap-2 text-base font-bold text-slate-800 truncate"><span className="text-red-500">▨</span> {isPreview ? 'Vista previa del archivo final' : nombre}</h2>
            <p className="truncate font-mono text-xs text-slate-400">{isPreview ? `${prev?.nombre} · Páginas ${pred.inicio}–${pred.fin} (${prev?.paginas})` : ruta}</p>
          </div>
          <div className="flex shrink-0 gap-2">
            {!isPreview && (
              <button onClick={() => setAyuda((v) => !v)} className={`rounded-lg border px-3 py-2 text-sm hover:bg-slate-100 ${ayuda ? 'border-red-300 bg-red-50 text-red-700' : 'border-slate-300'}`}>{ayuda ? 'Ocultar ayuda' : 'Ayuda'}</button>
            )}
            <button onClick={onClose} className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100">✕</button>
          </div>
        </div>

        {ayuda && !isPreview && (
          <div className="mx-5 mt-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm leading-relaxed text-slate-600">
            <b className="text-slate-800">¿Cómo funciona?</b> Los cuadros superiores son las páginas. Primer clic = <b>inicio</b>, segundo clic = <b>fin</b>. Luego pulsa «Previsualizar y Extraer».
          </div>
        )}

        {reextra && !isPreview && <div className="mx-5 mt-3 rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-700">Modo re-extracción: se sobrescribirá el archivo generado.</div>}

        {!isPreview ? (
          <>
            <div className="mx-5 mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-3">
              <div className="text-sm text-slate-700"><span className="font-semibold">Selección</span> · Inicio: <b>{pred.inicio || '—'}</b> · Fin: <b>{pred.fin || '—'}</b></div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowErrorModal(true)}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium ${errorLocal ? 'border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100' : 'border border-red-300 bg-white text-red-600 hover:bg-red-50'}`}
                >
                  <span className="text-base leading-none">⚠</span> {errorLocal ? 'Ver error' : 'Error en PDF'}
                </button>
                <button onClick={previsualizar} disabled={!seleccionValida || busyPre} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50">{busyPre ? 'Preparando…' : 'Previsualizar y Extraer'}</button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden p-3">
              <PdfViewer ref={viewerRef} key={original} seleccion fit={false} url={original} ini={ini} fin={fin} onSeleccion={setPred} onError={(m) => toast(m, 'error')} zoomRueda />
            </div>
            <div className="flex justify-end border-t border-slate-200 px-5 py-3">
              <button onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100">Cerrar</button>
            </div>
          </>
        ) : (
          <>
            <div className="mx-5 mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-3">
              <button onClick={() => setPrev(null)} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm hover:bg-slate-100">← Volver al original</button>
              <button onClick={guardar} disabled={busyGuardar} className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50">{busyGuardar ? 'Guardando…' : '✓ Sí, guardar archivo'}</button>
            </div>
            <div className="flex-1 overflow-auto p-3">
              <PdfViewer seleccion={false} fit vertical url={prevUrl} onError={(m) => toast(m, 'error')} zoomCtrl />
            </div>
          </>
        )}
        {showErrorModal && <ErrorModal archivo={nombre} observacionInicial={errorLocal?.observacion ?? ''} onClose={() => setShowErrorModal(false)} onSave={guardarError} />}
      </div>
    </div>
  )
}
