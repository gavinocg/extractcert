import { useEffect, useState } from 'react'
import { api } from '../api/client'
import EnviarErroresModal from '../components/EnviarErroresModal'
import { useToast } from '../store/toast'

interface Registro { id: number; original_path: string; archivo: string; observacion: string; username: string; created_at: string | null }

export default function Errores() {
  const [regs, setRegs] = useState<Registro[]>([])
  const [total, setTotal] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [sel, setSel] = useState<number[]>([])
  const [showEnviar, setShowEnviar] = useState(false)
  const toast = useToast((s) => s.show)

  const cargar = async (pg = 1) => {
    const r = await api.get<{ registros: Registro[]; total: number; pagina: number; tam: number }>('/api/errores?pagina=' + pg)
    setRegs(r.registros); setTotal(r.total); setPagina(r.pagina); setSel([])
  }
  useEffect(() => { void cargar(1) }, [])

  const toggle = (id: number) => setSel((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const corregir = async (id: number) => { await api.del(`/api/errores/${id}`); toast('Corregido', 'success'); void cargar(pagina) }
  const all = regs.length > 0 && regs.every((r) => sel.includes(r.id))

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-800">Trámites con error</h1>
      <p className="mb-4 text-sm text-slate-500">Listado de números de trámite (archivo con extensión) y observaciones.</p>
      <div className="mb-3 flex items-center gap-2 text-sm">
        <label className="flex items-center gap-1"><input type="checkbox" checked={all} onChange={() => setSel(all ? [] : regs.map((r) => r.id))} /> Seleccionar pág</label>
        <button onClick={() => setShowEnviar(true)} disabled={sel.length === 0} className="rounded bg-amber-600 px-3 py-1 text-white disabled:opacity-40">Enviar ({sel.length})</button>
        <span className="ml-auto text-xs text-slate-400">{total} total</span>
      </div>
      <div className="overflow-auto rounded-xl bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-slate-400"><th className="px-3 py-2">✓</th><th className="px-3 py-2">Trámite</th><th className="px-3 py-2">Observación</th><th className="px-3 py-2">Usuario</th><th className="px-3 py-2">Acción</th></tr></thead>
          <tbody>
            {regs.map((r) => (
              <tr key={r.id} className="border-t border-slate-100">
                <td className="px-3 py-2"><input type="checkbox" checked={sel.includes(r.id)} onChange={() => toggle(r.id)} /></td>
                <td className="px-3 py-2 font-mono text-xs">{r.archivo}</td>
                <td className="px-3 py-2">{r.observacion}</td>
                <td className="px-3 py-2">{r.username}</td>
                <td className="px-3 py-2"><button onClick={() => corregir(r.id)} className="rounded bg-emerald-600 px-2 py-1 text-xs text-white">Corregido</button></td>
              </tr>
            ))}
            {regs.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-sm text-slate-400">Sin errores.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex justify-between text-sm">
        <button onClick={() => cargar(pagina - 1)} disabled={pagina <= 1} className="rounded border px-3 py-1 disabled:opacity-40">‹ Anterior</button>
        <span className="text-xs text-slate-400">Pág {pagina} · {total} total</span>
        <button onClick={() => cargar(pagina + 1)} disabled={pagina * 20 >= total} className="rounded border px-3 py-1 disabled:opacity-40">Siguiente ›</button>
      </div>
      {showEnviar && <EnviarErroresModal ids={sel} onClose={() => setShowEnviar(false)} onSent={() => { setShowEnviar(false); toast('Enviado', 'success'); void cargar(pagina) }} />}
    </div>
  )
}
