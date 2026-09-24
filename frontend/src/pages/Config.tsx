import { FormEvent, useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../store/auth'
import { useToast } from '../store/toast'

interface SmtpSettings {
  host: string
  port: number
  user: string
  tls: boolean
  from_email: string
  password_configured: boolean
}

export default function Config() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast((state) => state.show)
  const [tab, setTab] = useState<'general' | 'smtp'>('general')
  const [raizOrigen, setRaizOrigen] = useState('')
  const [raizRepo, setRaizRepo] = useState('')
  const [smtp, setSmtp] = useState<SmtpSettings>({ host: '', port: 587, user: '', tls: true, from_email: '', password_configured: false })
  const [password, setPassword] = useState('')
  const [testEmail, setTestEmail] = useState('')
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    if (user?.rol !== 'administrador') navigate('/', { replace: true })
  }, [user, navigate])

  const load = useCallback(async () => {
    const [general, smtpConfig] = await Promise.allSettled([
      api.get<{ raiz_origen: string; raiz_repo: string }>('/api/settings'),
      api.get<SmtpSettings>('/api/settings/smtp'),
    ])
    if (general.status === 'fulfilled') {
      setRaizOrigen(general.value.raiz_origen)
      setRaizRepo(general.value.raiz_repo)
    } else {
      toast(general.reason instanceof Error ? general.reason.message : 'No se pudo cargar la configuración general', 'error')
    }
    if (smtpConfig.status === 'fulfilled') {
      setSmtp(smtpConfig.value)
    } else {
      toast(smtpConfig.reason instanceof Error ? smtpConfig.reason.message : 'No se pudo cargar SMTP', 'error')
    }
  }, [toast])

  useEffect(() => { void load() }, [load])

  const saveGeneral = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await api.put('/api/settings', { raiz_origen: raizOrigen, raiz_repo: raizRepo })
      toast('Configuración general guardada', 'success')
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Error', 'error')
    }
  }

  const saveSmtp = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await api.put('/api/settings/smtp', { ...smtp, password })
      setPassword('')
      setSmtp((current) => ({ ...current, password_configured: current.password_configured || !!password }))
      toast('Configuración SMTP guardada', 'success')
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Error', 'error')
    }
  }

  const testSmtp = async () => {
    if (!testEmail.trim()) {
      toast('Ingrese el correo que recibirá la prueba', 'error')
      return
    }
    setTesting(true)
    try {
      await api.post('/api/settings/smtp/test', { ...smtp, password, recipient: testEmail })
      toast(`Correo de prueba enviado a ${testEmail}`, 'success')
    } catch (error) {
      toast(error instanceof Error ? error.message : 'No se pudo enviar la prueba', 'error')
    } finally {
      setTesting(false)
    }
  }

  const fieldClass = 'w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-red-500 focus:ring-2 focus:ring-red-100'

  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold text-slate-800">Configuración</h1>
      <p className="mb-5 text-sm text-slate-500">Parámetros generales y servicio de correo.</p>

      <div className="mb-4 flex w-fit rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
        <button onClick={() => setTab('general')} className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === 'general' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-50'}`}>General</button>
        <button onClick={() => setTab('smtp')} className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === 'smtp' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-50'}`}>SMTP</button>
      </div>

      {tab === 'general' ? (
        <form onSubmit={saveGeneral} className="space-y-4 rounded-xl bg-white p-5 shadow-sm">
          <div><label className="mb-1 block text-sm font-medium text-slate-700">Directorio de origen (PDFs)</label><input value={raizOrigen} onChange={(event) => setRaizOrigen(event.target.value)} required className={`${fieldClass} font-mono text-sm`} /><p className="mt-1 text-xs text-slate-400">Windows: C:/ruta · Linux: /mnt/nas/origen</p></div>
          <div><label className="mb-1 block text-sm font-medium text-slate-700">Directorio de destino (repo)</label><input value={raizRepo} onChange={(event) => setRaizRepo(event.target.value)} required className={`${fieldClass} font-mono text-sm`} /></div>
          <button className="rounded-lg bg-red-600 px-4 py-2 font-semibold text-white hover:bg-red-700">Guardar</button>
        </form>
      ) : (
        <form onSubmit={saveSmtp} className="space-y-5 rounded-xl bg-white p-5 shadow-sm">
          <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">Estos datos se utilizarán para las notificaciones de asignación y finalización de lotes.</div>
          <div className="grid gap-4 sm:grid-cols-[1fr_140px]">
            <div><label className="mb-1 block text-sm font-medium text-slate-700">Servidor SMTP</label><input value={smtp.host} onChange={(event) => setSmtp({ ...smtp, host: event.target.value })} placeholder="smtp.gmail.com" required className={fieldClass} /></div>
            <div><label className="mb-1 block text-sm font-medium text-slate-700">Puerto</label><input type="number" min="1" max="65535" value={smtp.port} onChange={(event) => setSmtp({ ...smtp, port: Number(event.target.value) })} required className={fieldClass} /></div>
          </div>
          <div><label className="mb-1 block text-sm font-medium text-slate-700">Usuario SMTP</label><input value={smtp.user} onChange={(event) => setSmtp({ ...smtp, user: event.target.value })} autoComplete="username" required className={fieldClass} /></div>
          <div><label className="mb-1 block text-sm font-medium text-slate-700">Contraseña</label><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" placeholder={smtp.password_configured ? 'Configurada; dejar vacío para conservar' : 'Contraseña SMTP'} required={!smtp.password_configured} className={fieldClass} /><p className="mt-1 text-xs text-slate-400">La contraseña almacenada nunca se muestra en pantalla.</p></div>
          <div><label className="mb-1 block text-sm font-medium text-slate-700">Correo remitente</label><input type="email" value={smtp.from_email} onChange={(event) => setSmtp({ ...smtp, from_email: event.target.value })} placeholder="extractcert@empresa.com" className={fieldClass} /></div>
          <label className="flex items-center gap-3 rounded-lg border border-slate-200 px-4 py-3"><input type="checkbox" checked={smtp.tls} onChange={(event) => setSmtp({ ...smtp, tls: event.target.checked })} className="h-4 w-4 accent-red-600" /><span><span className="block text-sm font-medium text-slate-700">Usar TLS</span><span className="block text-xs text-slate-400">Recomendado para el puerto 587. El puerto 465 usa SSL automáticamente.</span></span></label>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="mb-1 text-sm font-semibold text-slate-800">Probar configuración</div>
            <p className="mb-3 text-xs text-slate-500">Se utilizarán los parámetros actuales del formulario, aunque todavía no los haya guardado.</p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input type="email" value={testEmail} onChange={(event) => setTestEmail(event.target.value)} placeholder="Correo que recibirá la prueba" className={`${fieldClass} bg-white`} />
              <button type="button" onClick={() => void testSmtp()} disabled={testing} className="shrink-0 rounded-lg border border-slate-900 bg-white px-4 py-2 font-semibold text-slate-800 hover:bg-slate-100 disabled:opacity-50">{testing ? 'Enviando…' : '+ Probar envío'}</button>
            </div>
          </div>
          <button className="rounded-lg bg-red-600 px-4 py-2 font-semibold text-white hover:bg-red-700">Guardar SMTP</button>
        </form>
      )}
    </div>
  )
}
