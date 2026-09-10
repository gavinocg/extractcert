import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react'
import * as pdfjs from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).href

const PDFJS_ASSETS = `${import.meta.env.BASE_URL}pdfjs-wasm/`

export interface Sel {
  inicio: number
  fin: number
}

export interface PdfViewerHandle {
  cargar: (url: string) => Promise<void>
  getSeleccion: () => Sel
  getRotation: () => number
  getPageOrder: () => number[]
  page: number
  next: () => void
  prev: () => void
}

interface Props {
  seleccion: boolean
  fit: boolean
  url: string
  ini?: number
  fin?: number
  onSeleccion?: (sel: Sel) => void
  onPage?: (page: number, numPages: number) => void
  onError?: (message: string) => void
  vertical?: boolean
  zoomRueda?: boolean
}

const PdfViewer = forwardRef<PdfViewerHandle, Props>(function PdfViewer(
  { seleccion, fit, url, ini, fin, onSeleccion, onPage, onError, vertical, zoomRueda },
  ref,
) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const pdfRef = useRef<PDFDocumentProxy | null>(null)
  const canvasMapRef = useRef<Map<number, HTMLCanvasElement>>(new Map())
  const [page, setPage] = useState(1)
  const [numPages, setNumPages] = useState(0)
  const [inicio, setInicio] = useState(ini ?? 0)
  const [finS, setFinS] = useState(fin ?? 0)
  const [cargando, setCargando] = useState(false)
  const [zoom, setZoom] = useState(75)
  const [rot, setRot] = useState(0)
  const rotRef = useRef(0)
  const [pageOrder, setPageOrder] = useState<number[]>([])
  const dragSrcRef = useRef<HTMLButtonElement | null>(null)
  const renderTaskRef = useRef(new Map<HTMLCanvasElement, { cancel(): void }>())
  const [paniendo, setPaniendo] = useState(false)
  const panRef = useRef({ activo: false, x: 0, y: 0, left: 0, top: 0 })

  useEffect(() => {
    if (numPages > 0 && pageOrder.length !== numPages) {
      setPageOrder(Array.from({ length: numPages }, (_, i) => i + 1))
    }
  }, [numPages])

  const handleDragStart = useCallback((e: React.DragEvent<HTMLButtonElement>, pageNum: number) => {
    dragSrcRef.current = e.currentTarget
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(pageNum))
    e.currentTarget.classList.add('dragging')
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent<HTMLButtonElement>) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    const target = e.currentTarget as HTMLButtonElement
    const src = dragSrcRef.current
    if (src && src !== target) {
      const rect = target.getBoundingClientRect()
      const midY = rect.top + rect.height / 2
      if (e.clientY < midY) {
        target.style.borderTop = '2px solid #ef4444'
        target.style.borderBottom = 'none'
      } else {
        target.style.borderBottom = '2px solid #ef4444'
        target.style.borderTop = 'none'
      }
    }
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLButtonElement>) => {
    const target = e.currentTarget as HTMLButtonElement
    target.style.borderTop = 'none'
    target.style.borderBottom = 'none'
  }, [])

  const handleDrop = useCallback((e: React.DragEvent<HTMLButtonElement>, targetNum: number) => {
    e.preventDefault()
    const target = e.currentTarget as HTMLButtonElement
    target.style.borderTop = 'none'
    target.style.borderBottom = 'none'

    const srcNum = Number(e.dataTransfer.getData('text/plain'))
    if (srcNum === targetNum) return

    setPageOrder((prev) => {
      const newOrder = [...prev]
      const srcIdx = newOrder.indexOf(srcNum)
      const targetIdx = newOrder.indexOf(targetNum)
      if (srcIdx === -1 || targetIdx === -1) return prev

      newOrder.splice(srcIdx, 1)
      newOrder.splice(targetIdx, 0, srcNum)
      return newOrder
    })
  }, [])

const handleDragEnd = useCallback(() => {
    if (dragSrcRef.current) {
      dragSrcRef.current.classList.remove('dragging')
      dragSrcRef.current = null
    }
    document.querySelectorAll('.page-box').forEach((el) => {
      const btn = el as HTMLButtonElement
      btn.style.borderTop = 'none'
      btn.style.borderBottom = 'none'
    })
  }, [])
  const dibujar = useCallback(
    async (pdf: PDFDocumentProxy, num: number, canvasOverride?: HTMLCanvasElement) => {
      const canvas = canvasOverride ?? canvasRef.current
      const wrap = wrapRef.current
      if (!canvas || !wrap) return
      if (wrap.clientWidth === 0 || wrap.clientHeight === 0) {
        await new Promise<void>((r) => requestAnimationFrame(() => r()))
        if ((!canvasRef.current && !canvasOverride) || wrap.clientWidth === 0) return
      }
      const pageObj: PDFPageProxy = await pdf.getPage(num)
      const vp1 = pageObj.getViewport({ scale: 1 })
      const maxW = (wrap.clientWidth || 1280) - 16
      let scale: number
      if (vertical) {
        scale = (maxW / vp1.width) * (zoom / 75)
      } else if (fit) {
        const maxH = (wrap.clientHeight || window.innerHeight * 0.78) - 8
        scale = Math.max(Math.min(maxW / vp1.width, maxH / vp1.height), 0.2) * (zoom / 75)
      } else {
        const maxH = (wrap.clientHeight || window.innerHeight * 0.6) - 8
        let base = 1.5
        if (vp1.height * base > maxH) base = maxH / vp1.height
        if (vp1.width * base > maxW) base = maxW / vp1.width
        scale = base * (zoom / 75)
      }
      const rotation = (pageObj.rotate + rotRef.current) % 360
      const viewport = pageObj.getViewport({ scale, rotation })
      canvas.width = viewport.width
      canvas.height = viewport.height
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.fillStyle = '#fff'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
      }
      try {
        renderTaskRef.current.get(canvas)?.cancel()
      } catch {
        /* sin tarea previa */
      }
      const task = pageObj.render({ canvas, viewport } as never) as unknown as { promise: Promise<void>; cancel(): void }
      renderTaskRef.current.set(canvas, task)
      try {
        await task.promise
      } catch (e) {
        if (ctx) {
          ctx.fillStyle = '#fff'
          ctx.fillRect(0, 0, canvas.width, canvas.height)
        }
        throw e
      } finally {
        if (renderTaskRef.current.get(canvas) === task) renderTaskRef.current.delete(canvas)
      }
    },
    [fit, vertical, zoom],
  )

  const ver = useCallback(
    async (num: number) => {
      const pdf = pdfRef.current
      if (!pdf) return
      const n = Math.max(1, Math.min(pdf.numPages, num))
      if (vertical) {
        const c = canvasMapRef.current.get(n)
        c?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        setPage(n)
        onPage?.(n, pdf.numPages)
        return
      }
      try {
        await dibujar(pdf, n)
      } catch {
        /* redibujo cancelado */
      }
      setPage(n)
      onPage?.(n, pdf.numPages)
    },
    [dibujar, onPage, vertical],
  )

  const dibujarVertical = useCallback(
    async (pdf: PDFDocumentProxy) => {
      const wrap = wrapRef.current
      if (!wrap) return
      for (let n = 1; n <= pdf.numPages; n++) {
        const canvas = canvasMapRef.current.get(n)
        if (!canvas) continue
        try {
          await dibujar(pdf, n, canvas)
        } catch {
          /* ignore */
        }
      }
    },
    [dibujar],
  )

  const rotateLeft = () => {
    const n = (rotRef.current - 90 + 360) % 360
    rotRef.current = n
    setRot(n)
  }
  const rotateRight = () => {
    const n = (rotRef.current + 90) % 360
    rotRef.current = n
    setRot(n)
  }

  const cargar = useCallback(
    async (u: string) => {
      setCargando(true)
      rotRef.current = 0
      setRot(0)
      try {
        if (pdfRef.current) {
          try {
            const lt = (pdfRef.current as unknown as { loadingTask?: { destroy(): Promise<void> } }).loadingTask
            await lt?.destroy()
          } catch {
            /* ignore */
          }
          pdfRef.current = null
        }
        const resp = await fetch(u, { credentials: 'include' })
        if (!resp.ok) {
          const msg = resp.status === 401 ? 'No autenticado para leer el PDF' : `HTTP ${resp.status}`
          throw new Error(msg)
        }
        const data = await resp.arrayBuffer()
        const doc = await pdfjs.getDocument({ data, wasmUrl: PDFJS_ASSETS }).promise
        pdfRef.current = doc
        setNumPages(doc.numPages)
        setInicio(ini ?? 0)
        setFinS(fin ?? 0)
        setPage(1)
        if (!vertical) {
          await new Promise<void>((r) => requestAnimationFrame(() => r()))
          await ver(1)
        }
      } catch (e) {
        onError?.(e instanceof Error ? e.message : 'No se pudo cargar el PDF')
      } finally {
        setCargando(false)
      }
    },
    [ini, fin, ver, vertical, onError],
  )

  useImperativeHandle(
    ref,
    () => ({
      cargar,
      getSeleccion: () => ({ inicio, fin: finS }),
      getRotation: () => rotRef.current,
      getPageOrder: () => pageOrder,
      page,
      next: () => ver(page + 1),
      prev: () => ver(page - 1),
    }),
    [cargar, inicio, finS, page, ver],
  )

  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (!e.ctrlKey) return
    e.preventDefault()
    const delta = e.deltaY < 0 ? 5 : -5
    setZoom((z) => Math.min(200, Math.max(25, z + delta)))
  }, [])

  useEffect(() => {
    if (!zoomRueda) return
    const el = wrapRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const delta = e.deltaY < 0 ? 5 : -5
      setZoom((z) => Math.min(200, Math.max(25, z + delta)))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomRueda])

  const finPan = useCallback(() => {
    panRef.current.activo = false
    setPaniendo(false)
  }, [])

  const inicioPan = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!zoomRueda || e.pointerType !== 'mouse' || e.button !== 0) return
      const el = wrapRef.current
      if (!el) return
      panRef.current = { activo: true, x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop }
      setPaniendo(true)
      el.setPointerCapture(e.pointerId)
    },
    [zoomRueda],
  )

  const moverPan = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const p = panRef.current
    const el = wrapRef.current
    if (!p.activo || !el) return
    el.scrollLeft = p.left - (e.clientX - p.x)
    el.scrollTop = p.top - (e.clientY - p.y)
  }, [])

  useEffect(() => {
    canvasMapRef.current.clear()
    if (url) void cargar(url)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])

  useEffect(() => {
    if (cargando || !pdfRef.current || numPages === 0) return
    if (vertical) {
      const id = requestAnimationFrame(() => void dibujarVertical(pdfRef.current!))
      return () => cancelAnimationFrame(id)
    }
    const id = requestAnimationFrame(() => void ver(page))
    return () => cancelAnimationFrame(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cargando, numPages, vertical])

  useEffect(() => {
    if (!pdfRef.current || numPages === 0 || cargando) return
    if (vertical) void dibujarVertical(pdfRef.current)
    else void ver(page)
  }, [zoom, rot])

  useEffect(() => {
    if (vertical) {
      const onResize = () => {
        const pdf = pdfRef.current
        if (pdf) void dibujarVertical(pdf)
      }
      window.addEventListener('resize', onResize)
      return () => window.removeEventListener('resize', onResize)
    }
    const onResize = () => {
      const pdf = pdfRef.current
      if (pdf) void ver(page)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, ver, vertical, dibujarVertical])

  const onBoxClick = (i: number) => {
    let a = inicio
    let b = finS
    if (a === 0) {
      a = i
    } else if (b === 0) {
      b = i
      if (b < a) {
        const t = a
        a = b
        b = t
      }
    } else {
      b = 0
      a = i
    }
    setInicio(a)
    setFinS(b)
    onSeleccion?.({ inicio: a, fin: b })
    void ver(i)
  }

  const selLabel = `Inicio: ${inicio || '—'} · Fin: ${finS || '—'}`

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-slate-200 px-3 py-2">
        <button onClick={rotateLeft} className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100" title="Girar izquierda">↺</button>
        <button onClick={rotateRight} className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100" title="Girar derecha">↻</button>
        <div className="h-4 w-px bg-slate-200" />
        <button
          onClick={() => ver(page - 1)}
          className="rounded border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-100"
          disabled={page <= 1}
        >
          ‹
        </button>

        {seleccion ? (
          <div className="flex flex-1 flex-wrap gap-1 overflow-x-auto px-1">
            {pageOrder.map((n) => (
              <button
                key={n}
                onClick={() => onBoxClick(n)}
                draggable
                onDragStart={(e) => handleDragStart(e, n)}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, n)}
                onDragEnd={handleDragEnd}
                className={`page-box ${n === inicio || n === finS ? 'inicio' : ''}`}
                title={`Página ${n}`}
              >
                {n}
              </button>
            ))}
          </div>
        ) : (
          <span className="flex-1 text-center text-xs text-slate-500">
            Página {numPages ? page : '…'} de {numPages || '…'}
          </span>
        )}

        <button
          onClick={() => ver(page + 1)}
          className="rounded border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-100"
          disabled={numPages === 0 || page >= numPages}
        >
          ›
        </button>
      </div>

      <div
        ref={wrapRef}
        onWheel={zoomRueda ? undefined : handleWheel}
        onPointerDown={inicioPan}
        onPointerMove={moverPan}
        onPointerUp={finPan}
        onPointerCancel={finPan}
        className={`flex-1 overflow-auto p-2 ${zoomRueda ? (paniendo ? 'cursor-grabbing' : 'cursor-grab') : ''}`}
        style={{ minHeight: 360 }}
      >
        {cargando ? (
          <div className="flex h-full min-h-[300px] items-center justify-center text-slate-400">
            Cargando PDF…
          </div>
        ) : vertical ? (
          <div className="flex flex-col items-center gap-4">
            {Array.from({ length: numPages }, (_, i) => i + 1).map((n) => (
              <canvas
                key={n}
                ref={(el) => {
                  if (el) canvasMapRef.current.set(n, el)
                  else canvasMapRef.current.delete(n)
                }}
                className="max-w-full shadow-sm"
              />
            ))}
          </div>
        ) : (
          <div className="flex min-w-fit justify-center">
            <canvas ref={canvasRef} />
          </div>
        )}
      </div>

      {seleccion && (
        <div className="flex items-center justify-between border-t border-slate-200 px-3 py-2 text-sm font-medium text-slate-600">
          <span>{selLabel}</span>
          {zoomRueda && <span className="text-xs font-normal text-slate-400">Rueda = zoom · Arrastra para mover</span>}
        </div>
      )}
    </div>
  )
})

export default PdfViewer