import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react'
import * as pdfjs from 'pdfjs-dist'
import type { PDFDocumentLoadingTask, PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).href

const PDFJS_ASSETS = `${import.meta.env.BASE_URL}pdfjs-wasm/`
const MOBILE_MAX_ZOOM = 400

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
  zoomCtrl?: boolean
  mobileTouch?: boolean
  mobileRotationGesture?: boolean
}

const PdfViewer = forwardRef<PdfViewerHandle, Props>(function PdfViewer(
  { seleccion, fit, url, ini, fin, onSeleccion, onPage, onError, vertical, zoomRueda, zoomCtrl, mobileTouch = false, mobileRotationGesture = false },
  ref,
) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const pdfRef = useRef<PDFDocumentProxy | null>(null)
  const loadingTaskRef = useRef<PDFDocumentLoadingTask | null>(null)
  const fetchControllerRef = useRef<AbortController | null>(null)
  const loadGenerationRef = useRef(0)
  const canvasMapRef = useRef<Map<number, HTMLCanvasElement>>(new Map())
  const [page, setPage] = useState(1)
  const [numPages, setNumPages] = useState(0)
  const [inicio, setInicio] = useState(ini ?? 0)
  const [finS, setFinS] = useState(fin ?? 0)
  const [cargando, setCargando] = useState(false)
  const [zoom, setZoom] = useState(75)
  const zoomRef = useRef(75)
  const [rot, setRot] = useState(0)
  const rotRef = useRef(0)
  const [pageOrder, setPageOrder] = useState<number[]>([])
  const dragSrcRef = useRef<HTMLButtonElement | null>(null)
  const renderTaskRef = useRef(new Map<HTMLCanvasElement, { cancel(): void }>())
  const [paniendo, setPaniendo] = useState(false)
  const panRef = useRef({ activo: false, x: 0, y: 0, left: 0, top: 0 })
  const [mobileGestures, setMobileGestures] = useState(false)
  const [showGestureHint, setShowGestureHint] = useState(false)
  const [gestureRotation, setGestureRotation] = useState<number | null>(null)
  const touchPointsRef = useRef(new Map<number, { x: number; y: number }>())
  const pinchRef = useRef({ distance: 0, zoom: 75, angle: 0, rotation: 0 })
  const rotationHintTimer = useRef<number | null>(null)

  useEffect(() => {
    if (numPages > 0 && pageOrder.length !== numPages) {
      setPageOrder(Array.from({ length: numPages }, (_, i) => i + 1))
    }
  }, [numPages])

  useEffect(() => { zoomRef.current = zoom }, [zoom])

  useEffect(() => () => {
    if (rotationHintTimer.current !== null) window.clearTimeout(rotationHintTimer.current)
  }, [])

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
        if (ctx && renderTaskRef.current.get(canvas) === task) {
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
      const generation = ++loadGenerationRef.current
      fetchControllerRef.current?.abort()
      fetchControllerRef.current = new AbortController()
      for (const task of renderTaskRef.current.values()) task.cancel()
      renderTaskRef.current.clear()
      await loadingTaskRef.current?.destroy().catch(() => undefined)
      loadingTaskRef.current = null
      setCargando(true)
      rotRef.current = 0
      setRot(0)
      try {
        pdfRef.current = null
        const resp = await fetch(u, { credentials: 'include', signal: fetchControllerRef.current.signal })
        if (!resp.ok) {
          const msg = resp.status === 401 ? 'No autenticado para leer el PDF' : `HTTP ${resp.status}`
          throw new Error(msg)
        }
        const data = await resp.arrayBuffer()
        if (generation !== loadGenerationRef.current) return
        const loadingTask = pdfjs.getDocument({ data, wasmUrl: PDFJS_ASSETS })
        loadingTaskRef.current = loadingTask
        const doc = await loadingTask.promise
        if (generation !== loadGenerationRef.current) { await loadingTask.destroy(); return }
        pdfRef.current = doc
        setNumPages(doc.numPages)
        setInicio(ini ?? 0)
        setFinS(fin ?? 0)
        setPage(1)
      } catch (e) {
        if (generation === loadGenerationRef.current && !(e instanceof DOMException && e.name === 'AbortError')) onError?.(e instanceof Error ? e.message : 'No se pudo cargar el PDF')
      } finally {
        if (generation === loadGenerationRef.current) setCargando(false)
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
    const delta = e.deltaY < 0 ? 10 : -10
    setZoom((z) => Math.min(200, Math.max(25, z + delta)))
  }, [])

  const gestoRueda = zoomRueda || zoomCtrl

  useEffect(() => {
    if (!gestoRueda) return
    const el = wrapRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      if (zoomCtrl && !e.ctrlKey) return
      e.preventDefault()
      const delta = e.deltaY < 0 ? 10 : -10
      setZoom((z) => Math.min(200, Math.max(25, z + delta)))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [gestoRueda, zoomCtrl])

  useEffect(() => {
    if (!zoomCtrl && !mobileTouch) { setMobileGestures(false); return }
    const media = window.matchMedia('(max-width: 767px)')
    const update = () => setMobileGestures(media.matches && (navigator.maxTouchPoints > 0 || window.matchMedia('(pointer: coarse)').matches))
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [zoomCtrl, mobileTouch])

  useEffect(() => {
    if (!mobileGestures) { setShowGestureHint(false); return }
    setShowGestureHint(true)
    const timer = window.setTimeout(() => setShowGestureHint(false), 3000)
    return () => window.clearTimeout(timer)
  }, [mobileGestures, url])

  const finPan = useCallback(() => {
    panRef.current.activo = false
    setPaniendo(false)
  }, [])

  const inicioPan = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const el = wrapRef.current
      if (!el) return
      if (mobileGestures && e.pointerType === 'touch') {
        setShowGestureHint(false)
        e.currentTarget.setPointerCapture(e.pointerId)
        touchPointsRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
        const points = [...touchPointsRef.current.values()]
        if (points.length === 2) {
          pinchRef.current = {
            distance: Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y),
            zoom: zoomRef.current,
            angle: Math.atan2(points[1].y - points[0].y, points[1].x - points[0].x) * 180 / Math.PI,
            rotation: rotRef.current,
          }
        } else if (points.length === 1) {
          panRef.current = { activo: true, x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop }
          setPaniendo(true)
        }
        return
      }
      if (!gestoRueda || e.pointerType !== 'mouse' || e.button !== 0) return
      panRef.current = { activo: true, x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop }
      setPaniendo(true)
      el.setPointerCapture(e.pointerId)
    },
    [gestoRueda, mobileGestures],
  )

  const moverPan = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const el = wrapRef.current
    if (mobileGestures && e.pointerType === 'touch' && touchPointsRef.current.has(e.pointerId)) {
      touchPointsRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
      const points = [...touchPointsRef.current.values()]
      if (points.length >= 2 && pinchRef.current.distance > 0) {
        const currentDistance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y)
        const ratio = currentDistance / pinchRef.current.distance
        setZoom(Math.min(MOBILE_MAX_ZOOM, Math.max(25, Math.round(pinchRef.current.zoom * ratio))))
        if (mobileRotationGesture) {
          const currentAngle = Math.atan2(points[1].y - points[0].y, points[1].x - points[0].x) * 180 / Math.PI
          let delta = currentAngle - pinchRef.current.angle
          if (delta > 180) delta -= 360
          if (delta < -180) delta += 360
          const steps = Math.round(delta / 90)
          const nextRotation = (pinchRef.current.rotation + steps * 90 + 360) % 360
          if (nextRotation !== rotRef.current) {
            rotRef.current = nextRotation
            setRot(nextRotation)
            setGestureRotation(nextRotation)
            if (rotationHintTimer.current !== null) window.clearTimeout(rotationHintTimer.current)
            rotationHintTimer.current = window.setTimeout(() => setGestureRotation(null), 900)
          }
        }
      } else if (points.length === 1 && el) {
        const p = panRef.current
        el.scrollLeft = p.left - (points[0].x - p.x)
        el.scrollTop = p.top - (points[0].y - p.y)
      }
      return
    }
    const p = panRef.current
    if (!p.activo || !el) return
    el.scrollLeft = p.left - (e.clientX - p.x)
    el.scrollTop = p.top - (e.clientY - p.y)
  }, [mobileGestures, mobileRotationGesture])

  const finPuntero = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType === 'touch') {
      touchPointsRef.current.delete(e.pointerId)
      const el = wrapRef.current
      const remaining = [...touchPointsRef.current.values()]
      pinchRef.current.distance = 0
      if (remaining.length === 1 && el) {
        panRef.current = { activo: true, x: remaining[0].x, y: remaining[0].y, left: el.scrollLeft, top: el.scrollTop }
      } else if (!remaining.length) {
        finPan()
      }
      return
    }
    finPan()
  }, [finPan])

  useEffect(() => {
    canvasMapRef.current.clear()
    if (url) void cargar(url)
    return () => {
      ++loadGenerationRef.current
      fetchControllerRef.current?.abort()
      void loadingTaskRef.current?.destroy().catch(() => undefined)
      loadingTaskRef.current = null
      for (const task of renderTaskRef.current.values()) task.cancel()
      renderTaskRef.current.clear()
      pdfRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])

  useEffect(() => {
    if (cargando || !pdfRef.current || numPages === 0) return
    const pdf = pdfRef.current
    const generation = loadGenerationRef.current
    if (vertical) {
      const id = requestAnimationFrame(() => {
        if (generation === loadGenerationRef.current && pdfRef.current === pdf) void dibujarVertical(pdf)
      })
      return () => cancelAnimationFrame(id)
    }
    const id = requestAnimationFrame(() => {
      if (generation === loadGenerationRef.current && pdfRef.current === pdf) void ver(page)
    })
    return () => cancelAnimationFrame(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cargando, numPages, vertical])

  useEffect(() => {
    if (!pdfRef.current || numPages === 0 || cargando) return
    const pdf = pdfRef.current
    const generation = loadGenerationRef.current
    const timer = window.setTimeout(() => {
      if (generation !== loadGenerationRef.current || pdfRef.current !== pdf) return
      if (vertical) void dibujarVertical(pdf)
      else void ver(page)
    }, mobileGestures ? 16 : 100)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoom, rot, mobileGestures])

  useEffect(() => {
    if (vertical) {
      let timer: number | undefined
      const onResize = () => {
        window.clearTimeout(timer)
        const pdf = pdfRef.current
        const generation = loadGenerationRef.current
        if (!pdf) return
        timer = window.setTimeout(() => {
          if (generation === loadGenerationRef.current && pdfRef.current === pdf) void dibujarVertical(pdf)
        }, 120)
      }
      window.addEventListener('resize', onResize)
      return () => { window.removeEventListener('resize', onResize); window.clearTimeout(timer) }
    }
    let timer: number | undefined
    const onResize = () => {
      window.clearTimeout(timer)
      const pdf = pdfRef.current
      const generation = loadGenerationRef.current
      if (!pdf) return
      timer = window.setTimeout(() => {
        if (generation === loadGenerationRef.current && pdfRef.current === pdf) void ver(page)
      }, 120)
    }
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); window.clearTimeout(timer) }
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

  const selLabel = inicio && finS ? `Página ${inicio} a ${finS}` : inicio ? `Página ${inicio} a …` : 'Seleccione páginas'

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl bg-white shadow-sm">
      <div className="flex items-center gap-1 border-b border-slate-200 px-1.5 py-1.5 sm:gap-2 sm:px-3 sm:py-2">
        <button onClick={rotateLeft} className={`${mobileRotationGesture ? 'hidden sm:inline-flex' : 'inline-flex'} min-h-10 min-w-10 items-center justify-center rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 sm:min-h-0 sm:min-w-0`} title="Girar izquierda" aria-label="Girar izquierda">↺</button>
        <button onClick={rotateRight} className={`${mobileRotationGesture ? 'hidden sm:inline-flex' : 'inline-flex'} min-h-10 min-w-10 items-center justify-center rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 sm:min-h-0 sm:min-w-0`} title="Girar derecha" aria-label="Girar derecha">↻</button>
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
          <span className="flex-1 whitespace-nowrap text-center text-xs text-slate-500">
            <span className="sm:hidden">{numPages ? page : '…'}/{numPages || '…'}</span>
            <span className="hidden sm:inline">Página {numPages ? page : '…'} de {numPages || '…'}</span>
          </span>
        )}

        <button
          onClick={() => ver(page + 1)}
          className="rounded border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-100"
          disabled={numPages === 0 || page >= numPages}
        >
          ›
        </button>
        {mobileGestures && <><div className="h-4 w-px bg-slate-200" /><button onClick={() => setZoom((value) => Math.max(25, value - 25))} className="min-h-10 min-w-10 rounded border border-slate-300 px-2 py-1 text-xs font-bold" aria-label="Alejar">−</button><span className="min-w-11 text-center text-[11px] font-semibold text-slate-500">{zoom}%</span><button onClick={() => setZoom((value) => Math.min(MOBILE_MAX_ZOOM, value + 25))} className="min-h-10 min-w-10 rounded border border-slate-300 px-2 py-1 text-xs font-bold" aria-label="Acercar">+</button></>}
      </div>

      <div
        ref={wrapRef}
        onWheel={gestoRueda ? undefined : handleWheel}
        onPointerDown={inicioPan}
        onPointerMove={moverPan}
        onPointerUp={finPuntero}
        onPointerCancel={finPuntero}
        className={`relative flex-1 overflow-auto p-2 ${gestoRueda ? (paniendo ? 'cursor-grabbing' : 'cursor-grab') : ''}`}
        style={{ minHeight: 360, touchAction: mobileGestures ? 'none' : 'auto' }}
      >
        {showGestureHint && !cargando && <div className="pointer-events-none sticky left-1/2 top-2 z-10 w-fit -translate-x-1/2 rounded-full bg-slate-900/75 px-3 py-1 text-[11px] font-medium text-white shadow">{mobileRotationGesture ? 'Pellizca · Arrastra · Gira' : 'Pellizca · Arrastra'}</div>}
        {gestureRotation !== null && <div className="pointer-events-none fixed left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2 rounded-full bg-slate-950/80 px-5 py-3 text-xl font-bold text-white shadow-xl">{gestureRotation}°</div>}
        {cargando ? (
          <div className="flex h-full min-h-[300px] items-center justify-center text-slate-400">
            Cargando PDF…
          </div>
        ) : vertical ? (
          <div className={mobileGestures ? 'pdf-mobile-track flex flex-col gap-4' : 'flex flex-col items-center gap-4'}>
            {Array.from({ length: numPages }, (_, i) => i + 1).map((n) => (
              <canvas
                key={n}
                ref={(el) => {
                  if (el) canvasMapRef.current.set(n, el)
                  else canvasMapRef.current.delete(n)
                }}
                className={`${mobileGestures ? 'pdf-mobile-preview' : zoomCtrl ? '' : 'max-w-full'} shadow-sm`}
              />
            ))}
          </div>
        ) : (
          <div className={mobileGestures ? 'pdf-mobile-track flex justify-start' : 'flex min-w-fit justify-center'}>
            <canvas ref={canvasRef} className={mobileGestures ? 'pdf-mobile-preview' : ''} />
          </div>
        )}
      </div>

      {seleccion && (
        <div className="border-t border-slate-200 px-3 py-2 text-sm font-medium text-slate-600">
          {selLabel}
        </div>
      )}
    </div>
  )
})

export default PdfViewer
