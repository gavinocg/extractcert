import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

interface Props {
  archivo: string
  observacionInicial?: string
  onClose: () => void
  onSave: (obs: string) => Promise<void>
}

interface Observacion { id: number; descripcion: string }

const OTRA = '__otra__'

export default function ErrorModal({ archivo, observacionInicial = '', onClose, onSave }: Props) {
  const [catalogo, setCatalogo] = useState<Observacion[]>([])
  const [sel, setSel] = useState<string>('')
  const [obs, setObs] = useState(observacionInicial)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    let viva = true
    api.get<Observacion[]>('/api/observaciones', { cacheTtl: 60_000 }).then((lista) => {
      if (!viva) return
      setCatalogo(lista)
      const ini = observacionInicial.trim()
      if (!ini) setSel('')
      else {
        const hallada = lista.find((o) => o.descripcion.toLowerCase() === ini.toLowerCase())
        setSel(hallada ? String(hallada.id) : OTRA)
      }
    }).catch(() => { if (viva) setSel(observacionInicial.trim() ? OTRA : '') })
    return () => { viva = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (sel === OTRA) {
      const id = setTimeout(() => { textareaRef.current?.focus(); textareaRef.current?.select() }, 50)
      return () => clearTimeout(id)
    }
  }, [sel])

  const elegida = catalogo.find((o) => String(o.id) === sel)

  const guardar = async () => {
    let texto = ''
    if (sel === OTRA) {
      texto = obs.trim()
      if (!texto) { setErr('Observación requerida'); return }
    } else {
      if (!elegida) { setErr('Seleccione una observación'); return }
      texto = elegida.descripcion
    }
    setBusy(true)
    try { await onSave(texto); onClose() } catch (e) { setErr(e instanceof Error ? e.message : 'Error') } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-5 shadow-xl">
        <h3 className="text-base font-semibold text-slate-800">Error en PDF — {archivo}</h3>
        <p className="mb-3 mt-1 text-xs text-slate-500">Seleccione una observación u Otra… para escribir una personalizada.</p>
        <select value={sel} onChange={(event) => { setSel(event.target.value); setErr('') }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-red-400 focus:outline-none">
          <option value="">Seleccione observación…</option>
          {catalogo.map((item) => <option key={item.id} value={item.id}>{item.descripcion}</option>)}
          <option value={OTRA}>Otra…</option>
        </select>
        {sel === OTRA && (
          <textarea
            ref={textareaRef}
            value={obs}
            onChange={(e) => setObs(e.target.value)}
            rows={4}
            placeholder="Ej. Faltan páginas, ilegible, trámite duplicado..."
            className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-red-400 focus:outline-none"
          />
        )}
        {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100">Cancelar</button>
          <button onClick={guardar} disabled={busy} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">{busy ? 'Guardando…' : 'Guardar observación'}</button>
        </div>
      </div>
    </div>
  )
}
