export interface PersonaResumen {
  id: number
  username: string
  nombre: string
}

export interface MetricasLote {
  total: number
  realizados: number
  errores: number
  pendientes: number
  porcentaje: number
}

export interface Lote {
  id: number
  nombre: string
  relative_path: string
  operador: PersonaResumen | null
  asignado_por: PersonaResumen | null
  estado: string
  assigned_at: string | null
  completed_at: string | null
  notified_at: string | null
  metricas: MetricasLote
}

export interface Operador extends PersonaResumen {
  email: string
}
