import { useEffect, useRef, useState } from 'react'

interface Props {
  archivo: string
  observacionInicial?: string
  onClose: () => void
  onSave: (obs: string) => Promise<void>
}

export default function ErrorModal({ archivo, observacionInicial = '', onClose, onSave }: Props) {
  const [obs, setObs] = useState(observacionInicial)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const id = setTimeout(() => {
      textareaRef.current?.focus()
      textareaRef.current?.select()
    }, 50)
    return () => clearTimeout(id)
  }, [])

  const guardar = async () => {
    if (!obs.trim()) { setErr('Observación requerida'); return }
    setBusy(true)
    try { await onSave(obs.trim()); onClose() } catch (e) { setErr(e instanceof Error ? e.message : 'Error') } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-5 shadow-xl">
        <h3 className="text-base font-semibold text-slate-800">Error en PDF — {archivo}</h3>
        <p className="mb-3 mt-1 text-xs text-slate-500">Describe el error para el listado de trámites.</p>
        <textarea
          ref={textareaRef}
          autoFocus
          value={obs}
          onChange={(e) => setObs(e.target.value)}
          rows={4}
          placeholder="Ej. Faltan páginas, ilegible, trámite duplicado..."
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-red-400 focus:outline-none"
        />
        {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100">Cancelar</button>
          <button onClick={guardar} disabled={busy} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">{busy ? 'Guardando…' : 'Guardar observación'}</button>
        </div>
      </div>
    </div>
  )
}
