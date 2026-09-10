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
  const [abierto, setAbierto] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [resaltado, setResaltado] = useState(0)
  const [obs, setObs] = useState(observacionInicial)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const cajaRef = useRef<HTMLDivElement>(null)
  const buscarRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    let viva = true
    api.get<Observacion[]>('/api/observaciones').then((lista) => {
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
    if (!abierto) return
    setBusqueda('')
    setResaltado(0)
    const id = setTimeout(() => buscarRef.current?.focus(), 30)
    const fuera = (e: MouseEvent) => {
      if (!cajaRef.current?.contains(e.target as Node)) setAbierto(false)
    }
    document.addEventListener('mousedown', fuera)
    return () => { clearTimeout(id); document.removeEventListener('mousedown', fuera) }
  }, [abierto])

  useEffect(() => {
    if (sel === OTRA && !abierto) {
      const id = setTimeout(() => { textareaRef.current?.focus(); textareaRef.current?.select() }, 50)
      return () => clearTimeout(id)
    }
  }, [sel, abierto])

  const filtradas = catalogo.filter((o) => o.descripcion.toLowerCase().includes(busqueda.trim().toLowerCase()))
  const total = filtradas.length + 1

  const elegir = (valor: string) => {
    setSel(valor)
    setErr('')
    setAbierto(false)
  }

  const tecla = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setAbierto(false); return }
    if (e.key === 'ArrowDown') { e.preventDefault(); setResaltado((r) => Math.min(total - 1, r + 1)); return }
    if (e.key === 'ArrowUp') { e.preventDefault(); setResaltado((r) => Math.max(0, r - 1)); return }
    if (e.key === 'Enter') {
      e.preventDefault()
      elegir(resaltado < filtradas.length ? String(filtradas[resaltado].id) : OTRA)
    }
  }

  const elegida = catalogo.find((o) => String(o.id) === sel)
  const etiqueta = sel === OTRA ? 'Otra…' : (elegida?.descripcion ?? 'Seleccione observación…')

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
        <div ref={cajaRef} className="relative">
          <button
            type="button"
            onClick={() => setAbierto((v) => !v)}
            className="flex w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-3 py-2 text-left text-sm focus:border-red-400 focus:outline-none"
          >
            <span className={elegida || sel === OTRA ? 'text-slate-800' : 'text-slate-400'}>{etiqueta}</span>
            <span className="text-xs text-slate-400">▾</span>
          </button>
          {abierto && (
            <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-slate-300 bg-white shadow-lg">
              <div className="border-b border-slate-100 p-2">
                <input
                  ref={buscarRef}
                  value={busqueda}
                  onChange={(e) => { setBusqueda(e.target.value); setResaltado(0) }}
                  onKeyDown={tecla}
                  placeholder="Buscar observación…"
                  className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm focus:border-red-400 focus:outline-none"
                />
              </div>
              <ul className="max-h-52 overflow-auto py-1">
                {filtradas.map((o, i) => (
                  <li key={o.id}>
                    <button
                      type="button"
                      onMouseEnter={() => setResaltado(i)}
                      onClick={() => elegir(String(o.id))}
                      className={`block w-full px-3 py-2 text-left text-sm ${i === resaltado ? 'bg-red-50 text-red-800' : 'text-slate-700 hover:bg-slate-50'}`}
                    >
                      {o.descripcion}
                    </button>
                  </li>
                ))}
                <li>
                  <button
                    type="button"
                    onMouseEnter={() => setResaltado(filtradas.length)}
                    onClick={() => elegir(OTRA)}
                    className={`block w-full border-t border-slate-100 px-3 py-2 text-left text-sm font-medium ${filtradas.length === resaltado ? 'bg-red-50 text-red-800' : 'text-slate-700 hover:bg-slate-50'}`}
                  >
                    Otra…
                  </button>
                </li>
                {filtradas.length === 0 && (
                  <li className="px-3 py-2 text-xs text-slate-400">Sin coincidencias. Use Otra… para una personalizada.</li>
                )}
              </ul>
            </div>
          )}
        </div>
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
