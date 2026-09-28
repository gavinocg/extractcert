import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { passwordPolicyError } from '../authPolicy'
import { useAuth } from '../store/auth'

function PasswordField({ label, value, onChange, autoFocus = false }: { label: string; value: string; onChange: (value: string) => void; autoFocus?: boolean }) {
  const [visible, setVisible] = useState(false)
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-slate-700">{label}</label>
      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoFocus={autoFocus}
          required
          autoComplete={label === 'Contraseña actual' ? 'current-password' : 'new-password'}
          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 pr-20 outline-none transition focus:border-red-500 focus:ring-2 focus:ring-red-100"
        />
        <button type="button" onClick={() => setVisible((current) => !current)} className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-slate-500 hover:text-slate-800">
          {visible ? 'Ocultar' : 'Mostrar'}
        </button>
      </div>
    </div>
  )
}

export default function CambiarPasswordObligatorio() {
  const { user, changePassword } = useAuth()
  const navigate = useNavigate()
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const policyError = passwordPolicyError(nueva, user?.username ?? '')
    if (policyError) { setError(policyError); return }
    if (nueva !== confirmacion) { setError('La confirmación no coincide con la nueva contraseña.'); return }
    setError('')
    setBusy(true)
    try {
      await changePassword(actual, nueva)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo actualizar la contraseña.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-8 sm:flex sm:items-center sm:justify-center">
      <section className="mx-auto w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl shadow-black/30">
        <div className="border-b border-slate-200 px-6 py-5 sm:px-8">
          <div className="mb-5 text-lg font-bold text-slate-900"><span className="text-red-600">■</span> ExtractCert</div>
          <div className="mb-3 inline-flex rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">Acción requerida</div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Actualiza tu contraseña</h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">Por seguridad, debes establecer una nueva contraseña antes de continuar. Tu sesión permanecerá restringida hasta completar este paso.</p>
        </div>
        <form onSubmit={submit} className="space-y-4 px-6 py-6 sm:px-8">
          <PasswordField label="Contraseña actual" value={actual} onChange={setActual} autoFocus />
          <PasswordField label="Nueva contraseña" value={nueva} onChange={setNueva} />
          <PasswordField label="Confirmar nueva contraseña" value={confirmacion} onChange={setConfirmacion} />
          <div className="rounded-lg bg-slate-50 px-3 py-2.5 text-xs leading-5 text-slate-600">Usa entre 6 caracteres y 72 bytes. No incluyas tu nombre de usuario. La contraseña debe ser distinta a la actual.</div>
          {error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
          <button type="submit" disabled={busy} className="w-full rounded-lg bg-red-600 px-4 py-2.5 font-semibold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60">
            {busy ? 'Actualizando…' : 'Actualizar contraseña y continuar'}
          </button>
        </form>
      </section>
    </main>
  )
}
