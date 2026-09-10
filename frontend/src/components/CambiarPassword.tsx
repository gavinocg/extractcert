import { useState } from 'react'
import { api } from '../api/client'
import { useToast } from '../store/toast'

interface Props {
  onClose: () => void
}

export default function CambiarPassword({ onClose }: Props) {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [confirmar, setConfirmar] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const toast = useToast((s) => s.show)

  const guardar = async () => {
    if (!actual || !nueva || !confirmar) { setErr('Complete todos los campos'); return }
    if (nueva.length < 4) { setErr('La nueva contraseña debe tener al menos 4 caracteres'); return }
    if (nueva !== confirmar) { setErr('La confirmación no coincide'); return }
    setBusy(true)
    try {
      await api.post('/api/auth/password', { actual, nueva })
      toast('Contraseña actualizada', 'success')
      onClose()
    } catch (e) { setErr(e instanceof Error ? e.message : 'Error') } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
        <h3 className="text-base font-semibold text-slate-800">Cambiar contraseña</h3>
        <p className="mb-3 mt-1 text-xs text-slate-500">Mínimo 4 caracteres.</p>
        <input type="password" autoFocus value={actual} onChange={(e) => setActual(e.target.value)} placeholder="Contraseña actual" className="mb-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none" />
        <input type="password" value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="Nueva contraseña" className="mb-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none" />
        <input type="password" value={confirmar} onChange={(e) => setConfirmar(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void guardar() }} placeholder="Confirmar nueva contraseña" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none" />
        {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100">Cancelar</button>
          <button onClick={() => void guardar()} disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50">{busy ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </div>
    </div>
  )
}
