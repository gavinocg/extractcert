import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface Contacto { id: number; nombre: string; email: string }
interface Props {
  ids: number[]
  onClose: () => void
  onSent: () => void
}

export default function EnviarErroresModal({ ids, onClose, onSent }: Props) {
  const [contactos, setContactos] = useState<Contacto[]>([])
  const [sel, setSel] = useState<number[]>([])
  const [extra, setExtra] = useState('')
  const [asunto, setAsunto] = useState('Trámites con error en digital')
  const [cuerpo, setCuerpo] = useState('Se adjunta listado de trámites con observaciones.')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [ok, setOk] = useState('')

  useEffect(() => { void api.get<Contacto[]>('/api/contactos').then(setContactos).catch(() => {}) }, [])

  const toggle = (id: number) => setSel((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))

  const enviar = async () => {
    if (ids.length === 0) { setErr('Sin trámites seleccionados'); return }
    if (sel.length === 0 && !extra.trim()) { setErr('Seleccione contactos o indique emails'); return }
    setBusy(true); setErr(''); setOk('')
    try {
      const emails_extra = extra.split(/[,;\n]+/).map((s) => s.trim()).filter(Boolean)
      await api.post('/api/errores/enviar', { ids, contactos_ids: sel, emails_extra, asunto, cuerpo })
      setOk('Correos enviados')
      setTimeout(onSent, 800)
    } catch (e) { setErr(e instanceof Error ? e.message : 'Error') } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-xl bg-white p-5 shadow-xl">
        <h3 className="text-base font-semibold text-slate-800">Enviar trámites con error ({ids.length})</h3>
        <div className="mt-4">
          <div className="text-sm font-medium text-slate-700">Contactos (libreta global)</div>
          <div className="mt-2 max-h-40 overflow-auto rounded-lg border border-slate-200 p-2">
            {contactos.length === 0 ? <div className="text-sm text-slate-400">Sin contactos — agrégalos en Contactos.</div> : contactos.map((c) => (
              <label key={c.id} className="flex items-center gap-2 py-1 text-sm">
                <input type="checkbox" checked={sel.includes(c.id)} onChange={() => toggle(c.id)} />
                <span className="font-medium">{c.nombre}</span><span className="text-slate-500">{c.email}</span>
              </label>
            ))}
          </div>
        </div>
        <div className="mt-4">
          <label className="text-sm font-medium text-slate-700">Emails adicionales (separados por coma)</label>
          <input value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="a@ej.com, b@ej.com" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        </div>
        <div className="mt-4">
          <label className="text-sm font-medium text-slate-700">Asunto (editable)</label>
          <input value={asunto} onChange={(e) => setAsunto(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        </div>
        <div className="mt-4">
          <label className="text-sm font-medium text-slate-700">Cuerpo (editable)</label>
          <textarea value={cuerpo} onChange={(e) => setCuerpo(e.target.value)} rows={3} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        </div>
        {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
        {ok && <div className="mt-2 text-sm text-emerald-600">{ok}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100">Cerrar</button>
          <button onClick={enviar} disabled={busy} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50">{busy ? 'Enviando…' : 'Enviar'}</button>
        </div>
      </div>
    </div>
  )
}
