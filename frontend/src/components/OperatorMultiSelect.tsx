import { useEffect, useRef, useState } from 'react'
import type { Operador } from '../types/lotes'

interface Props {
  operators: Operador[]
  selected: number[]
  search: string
  onSearch: (value: string) => void
  onChange: (ids: number[]) => void
  disabled?: boolean
}

export default function OperatorMultiSelect({ operators, selected, search, onSearch, onChange, disabled = false }: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const visible = operators.filter((operator) =>
    `${operator.nombre} ${operator.username}`.toLowerCase().includes(search.trim().toLowerCase()),
  )
  const toggle = (id: number) => onChange(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id])

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <div ref={rootRef} className="relative space-y-2">
      <button type="button" disabled={disabled} onClick={() => setOpen((value) => !value)} aria-expanded={open} className="flex w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-3 py-2 text-left text-sm outline-none hover:border-blue-400 focus:border-blue-500 disabled:bg-slate-100">
        <span className={selected.length ? 'font-medium text-slate-700' : 'text-slate-400'}>{selected.length ? `${selected.length} responsable${selected.length === 1 ? '' : 's'} seleccionado${selected.length === 1 ? '' : 's'}` : 'Seleccionar responsables'}</span>
        <span className={`text-xs text-slate-400 transition ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>
      {open && <div className="absolute z-40 mt-1 w-full min-w-72 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
        <div className="border-b border-slate-100 p-2"><input autoFocus value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Buscar nombre o usuario" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500" /></div>
        <div className="max-h-56 overflow-auto p-1">
          {visible.map((operator) => (
            <label key={operator.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-blue-50">
              <input type="checkbox" checked={selected.includes(operator.id)} onChange={() => toggle(operator.id)} className="h-4 w-4 accent-blue-600" />
              <span className="min-w-0 truncate">{operator.nombre || operator.username} <span className="text-slate-400">@{operator.username}</span></span>
            </label>
          ))}
          {visible.length === 0 && <div className="px-2 py-4 text-center text-xs text-slate-400">Sin coincidencias</div>}
        </div>
        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50 px-3 py-2"><span className="text-xs text-slate-500">{selected.length} seleccionados</span><button type="button" onClick={() => setOpen(false)} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700">Listo</button></div>
      </div>}
      <div className="flex min-h-6 flex-wrap gap-1">
        {selected.map((id) => {
          const operator = operators.find((item) => item.id === id)
          return operator ? <span key={id} className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">{operator.nombre || operator.username}<button type="button" disabled={disabled} onClick={() => toggle(id)} className="font-bold text-blue-400 hover:text-blue-700" aria-label={`Quitar ${operator.nombre || operator.username}`}>×</button></span> : null
        })}
      </div>
    </div>
  )
}
