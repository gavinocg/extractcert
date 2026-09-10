import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import PdfViewer, { Sel } from '../components/PdfViewer'
import { useToast } from '../store/toast'

interface PreviewResp {
  ok: boolean
  nombre: string
  paginas: number
  url: string
}

export default function Visor() {
  const [sp] = useSearchParams()
  const navigate = useNavigate()
  const toast = useToast((s) => s.show)

  const ruta = sp.get('ruta') ?? ''
  const reextra = parseInt(sp.get('reextra') ?? '0', 10) === 1
  const extraccionId = parseInt(sp.get('extraccion_id') ?? '0', 10)
  const ini = parseInt(sp.get('ini') ?? '0', 10)
  const fin = parseInt(sp.get('fin') ?? '0', 10)
  const nombre = useMemo(() => decodeURIComponent(ruta.split('/').pop() ?? ''), [ruta])

  const fromPath = sp.get('from_path') ?? ''
  const fromPagina = sp.get('from_pagina') ?? ''

  const original = `/api/pdf/original?ruta=${encodeURIComponent(ruta)}`

  const [pred, setPred] = useState<Sel>({ inicio: ini, fin })
  const [prev, setPrev] = useState<PreviewResp | null>(null)
  const [prevUrl, setPrevUrl] = useState('')
  const [busyPre, setBusyPre] = useState(false)
  const [busyGuardar, setBusyGuardar] = useState(false)
  const [ayuda, setAyuda] = useState(false)

  useEffect(() => {
    setPred({ inicio: ini, fin })
    setPrev(null)
    setPrevUrl('')
  }, [ruta, ini, fin])

  const seleccionValida = pred.inicio > 0 && pred.fin >= pred.inicio

  const previsualizar = async () => {
    setBusyPre(true)
    try {
      const r = await api.post<PreviewResp>('/api/extracciones/preview', {
        ruta,
        inicio: pred.inicio,
        fin: pred.fin,
      })
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
      const r = await api.post<{ nombre: string }>('/api/extracciones/guardar', {
        ruta,
        inicio: pred.inicio,
        fin: pred.fin,
        reextra: reextra ? 1 : 0,
        extraccion_id: extraccionId,
      })
      toast(`Extracción guardada: ${r.nombre}`, 'success')
      setTimeout(() => {
        if (fromPath) navigate(`/?path=${encodeURIComponent(fromPath)}&pagina=${fromPagina || '1'}`)
        else {
          const dir = ruta.includes('/') ? ruta.substring(0, ruta.lastIndexOf('/')) : ''
          navigate(dir ? `/?path=${encodeURIComponent(dir)}` : '/')
        }
      }, 700)
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Error', 'error')
      setBusyGuardar(false)
    }
  }

  return (
    <div className="flex h-[100dvh] flex-col">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 px-6 pt-4">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-slate-800">
            <span className="text-red-500">▨</span> {nombre}
          </h1>
          <p className="break-all font-mono text-xs text-slate-400">{ruta}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setAyuda((v) => !v)}
            className={`rounded-lg border px-3 py-2 text-sm hover:bg-slate-100 ${
              ayuda ? 'border-red-300 bg-red-50 text-red-700' : 'border-slate-300'
            }`}
          >
            {ayuda ? 'Ocultar ayuda' : 'Ayuda'}
          </button>
          <Link
            to={fromPath ? `/?path=${encodeURIComponent(fromPath)}&pagina=${fromPagina || '1'}` : '/'}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
          >
            ← Volver
          </Link>
        </div>
      </div>

      {/* Panel de ayuda (inline) */}
      {ayuda && (
        <div className="mx-6 mt-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-relaxed text-slate-600 shadow-sm">
          <b className="text-slate-800">¿Cómo funciona?</b> Los cuadros superiores son las páginas.
          Primer clic = <b>inicio</b>, segundo clic = <b>fin</b>. Luego pulsa «Previsualizar y
          Extraer» para revisar el archivo final antes de guardarlo.
        </div>
      )}

      {reextra && (
        <div className="mx-6 mt-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-700">
          Modo re-extracción: se sobrescribirá el archivo generado previamente.
        </div>
      )}

      {/* Barra de selección superior */}
      <div className="mx-6 mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white px-4 py-3 shadow-sm">
        <div className="text-sm text-slate-700">
          <span className="font-semibold">Selección</span> · Inicio:{' '}
          <b>{pred.inicio || '—'}</b> · Fin: <b>{pred.fin || '—'}</b>
        </div>
        <button
          onClick={previsualizar}
          disabled={!seleccionValida || busyPre}
          className="rounded-lg bg-red-600 px-4 py-2 font-semibold text-white hover:bg-red-700 disabled:opacity-50"
        >
          {busyPre ? 'Preparando…' : 'Previsualizar y Extraer'}
        </button>
      </div>

      {/* Visor a pantalla completa (del área de contenido) */}
      <div className="mt-3 min-h-0 flex-1">
        <PdfViewer
          key={original}
          seleccion
          fit={false}
          url={original}
          ini={ini}
          fin={fin}
          onSeleccion={(s) => setPred(s)}
          onError={(m) => toast(m, 'error')}
        />
      </div>

      {/* Modal a pantalla completa: vista previa final */}
      <div
        className={`fixed inset-0 z-50 flex flex-col bg-white ${prev ? 'visible' : 'invisible'}`}
        aria-hidden={!prev}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="text-lg font-semibold text-emerald-700">
              Vista previa del archivo final
            </span>
            {prev && (
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                {prev.nombre} · Páginas {pred.inicio}–{pred.fin} ({prev.paginas})
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPrev(null)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100"
            >
              ← Volver al original
            </button>
            <button
              onClick={guardar}
              disabled={busyGuardar}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {busyGuardar ? 'Guardando…' : '✓ Sí, guardar archivo'}
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden p-2">
          {prev && (
            <div className="h-full">
              <PdfViewer
                seleccion={false}
                fit
                url={prevUrl}
                onError={(m) => toast(m, 'error')}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}