import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../store/auth'

interface Reg {
  id: number
  archivo: string
  destino: string
  original_path: string
  destino_path: string
  pagina_inicio: number
  pagina_fin: number
  estado: string
  username: string
  created_at: string | null
}

interface Hist {
  registros: Reg[]
  total: number
  pagina: number
  tam: number
  usuarios: { id: number; username: string }[]
}

export default function Historial() {
  const { user } = useAuth()
  const isAdmin = user?.rol === 'administrador'
  const [data, setData] = useState<Hist | null>(null)
  const [usuario, setUsuario] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [err, setErr] = useState('')

  const cargar = useCallback(async (uid: number, pg: number) => {
    try {
      const params = new URLSearchParams()
      if (uid) params.set('usuario', String(uid))
      params.set('pagina', String(pg))
      setData(await api.get<Hist>('/api/historial?' + params.toString()))
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Error')
    }
  }, [])

  useEffect(() => {
    void cargar(usuario, pagina)
  }, [cargar, usuario, pagina])

  const totalPaginas = data ? Math.max(1, Math.ceil(data.total / data.tam)) : 1
  const irA = (p: number) => setPagina(Math.min(totalPaginas, Math.max(1, p)))

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Historial de extracciones</h1>
          <p className="text-sm text-slate-500">Trazabilidad de los documentos extraídos.</p>
        </div>
        {isAdmin && data && (
          <select
            value={usuario}
            onChange={(e) => {
              setUsuario(Number(e.target.value))
              setPagina(1)
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value={0}>Todos los usuarios</option>
            {data.usuarios.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </select>
        )}
      </div>

      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}

      {!data ? (
        <div className="text-slate-500">Cargando…</div>
      ) : (
        <div className="overflow-x-auto rounded-xl bg-white p-4 shadow-sm">
          {data.registros.length === 0 ? (
            <div className="text-sm text-slate-400">Sin registros.</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-slate-400">
                  <th className="py-2 pr-2">#</th>
                  <th className="px-2 py-2">PDF origen</th>
                  <th className="px-2 py-2">Extraído</th>
                  <th className="px-2 py-2">Páginas</th>
                  <th className="px-2 py-2">Estado</th>
                  <th className="px-2 py-2">Usuario</th>
                  <th className="px-2 py-2">Fecha</th>
                </tr>
              </thead>
              <tbody>
                {data.registros.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100 align-baseline">
                    <td className="py-2 pr-2">{r.id}</td>
                    <td className="max-w-[220px] truncate py-2 pr-2 font-mono text-xs">{r.original_path}</td>
                    <td className="max-w-[220px] truncate py-2 pr-2 font-mono text-xs text-emerald-700">
                      {r.destino_path}
                    </td>
                    <td className="px-2 py-2">
                      {r.pagina_inicio}–{r.pagina_fin}
                    </td>
                    <td className="px-2 py-2">
                      <span
                        className={
                          r.estado === 'rehecho'
                            ? 'rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700'
                            : 'rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700'
                        }
                      >
                        {r.estado === 'rehecho' ? 're-extraído' : 'realizado'}
                      </span>
                    </td>
                    <td className="px-2 py-2">{r.username}</td>
                    <td className="px-2 py-2">{r.created_at ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {totalPaginas > 1 && (
            <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-sm">
              <span className="text-xs text-slate-400">
                {data.registros.length > 0 &&
                  `Mostrando ${(data.pagina - 1) * data.tam + 1}–${(data.pagina - 1) * data.tam + data.registros.length} de ${data.total}`}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => irA(data.pagina - 1)}
                  disabled={data.pagina <= 1}
                  className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 disabled:opacity-40"
                >
                  ‹ Anterior
                </button>
                <span className="text-xs text-slate-500">
                  Página {data.pagina} / {totalPaginas}
                </span>
                <button
                  onClick={() => irA(data.pagina + 1)}
                  disabled={data.pagina >= totalPaginas}
                  className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 disabled:opacity-40"
                >
                  Siguiente ›
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}