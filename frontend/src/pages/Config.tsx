import { FormEvent, useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../store/auth'
import { useToast } from '../store/toast'

export default function Config() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast((s) => s.show)
  const [raizOrigen, setRaizOrigen] = useState('')
  const [raizRepo, setRaizRepo] = useState('')

  useEffect(() => {
    if (user?.rol !== 'administrador') navigate('/', { replace: true })
  }, [user, navigate])

  const cargar = useCallback(async () => {
    try {
      const s = await api.get<{ raiz_origen: string; raiz_repo: string }>('/api/settings')
      setRaizOrigen(s.raiz_origen)
      setRaizRepo(s.raiz_repo)
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Error', 'error')
    }
  }, [toast])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api.put('/api/settings', { raiz_origen: raizOrigen, raiz_repo: raizRepo })
      toast('Configuración guardada', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Error', 'error')
    }
  }

  return (
    <div className="max-w-xl">
      <h1 className="mb-1 text-2xl font-bold text-slate-800">Configuración</h1>
      <p className="mb-4 text-sm text-slate-500">Rutas del directorio de origen y de destino (repo).</p>

      <form onSubmit={onSubmit} className="space-y-4 rounded-xl bg-white p-4 shadow-sm">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Directorio de origen (PDFs)
          </label>
          <input
            value={raizOrigen}
            onChange={(e) => setRaizOrigen(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm outline-none focus:border-red-400"
          />
          <p className="mt-1 text-xs text-slate-400">
            Windows: C:/ruta · Linux: /mnt/nas/origen
          </p>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Directorio de destino (repo)
          </label>
          <input
            value={raizRepo}
            onChange={(e) => setRaizRepo(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm outline-none focus:border-red-400"
          />
        </div>
        <button className="rounded-lg bg-red-600 px-4 py-2 font-semibold text-white hover:bg-red-700">
          Guardar
        </button>
      </form>
    </div>
  )
}