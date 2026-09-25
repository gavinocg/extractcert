import { useEffect, useRef, useState } from 'react'

const DELAY_MS = 1000

export default function LoadingOverlay() {
  const [visible, setVisible] = useState(false)
  const active = useRef(0)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    const start = () => {
      active.current += 1
      if (active.current === 1) {
        timer.current = window.setTimeout(() => {
          timer.current = null
          if (active.current > 0) setVisible(true)
        }, DELAY_MS)
      }
    }
    const end = () => {
      active.current = Math.max(0, active.current - 1)
      if (active.current === 0) {
        if (timer.current !== null) window.clearTimeout(timer.current)
        timer.current = null
        setVisible(false)
      }
    }
    window.addEventListener('app:loading-start', start)
    window.addEventListener('app:loading-end', end)
    return () => {
      window.removeEventListener('app:loading-start', start)
      window.removeEventListener('app:loading-end', end)
      if (timer.current !== null) window.clearTimeout(timer.current)
    }
  }, [])

  if (!visible) return null
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/25 backdrop-blur-[2px]" role="status" aria-live="polite" aria-label="Cargando datos">
      <div className="flex items-center gap-3 rounded-2xl border border-white/60 bg-white/90 px-6 py-4 shadow-2xl">
        <span className="h-7 w-7 animate-spin rounded-full border-4 border-slate-200 border-t-red-600" aria-hidden="true" />
        <span className="font-semibold text-slate-800">Cargando datos...</span>
      </div>
    </div>
  )
}
