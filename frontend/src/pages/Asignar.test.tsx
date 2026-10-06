import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Asignar from './Asignar'

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(async (url: string) => {
    if (url.startsWith('/api/lotes/arbol')) {
      return {
        actual: 'SEPTIEMBRE 2026',
        pagina: 1,
        tam: 5,
        total: 2,
        items: [
          {
            nombre: '02-09-2026',
            relative_path: 'SEPTIEMBRE 2026/02-09-2026',
            es_lote: true,
            tiene_hijos: false,
            total: 159,
            lote: null,
            metricas: { total: 159, realizados: 112, errores: 47, pendientes: 0, porcentaje: 100 },
          },
          {
            nombre: '01-09-2026',
            relative_path: 'SEPTIEMBRE 2026/01-09-2026',
            es_lote: true,
            tiene_hijos: false,
            total: 126,
            lote: {
              id: 1,
              nombre: '01-09-2026',
              relative_path: 'SEPTIEMBRE 2026/01-09-2026',
              operador: { id: 7, username: 'gcarranco', nombre: 'Gavino Carranco' },
              operadores: [{ id: 7, username: 'gcarranco', nombre: 'Gavino Carranco' }],
              asignado_por: null,
              estado: 'completado',
              assigned_at: null,
              completed_at: null,
              notified_at: null,
              metricas: { total: 126, realizados: 102, errores: 24, pendientes: 0, porcentaje: 100 },
            },
            metricas: { total: 126, realizados: 102, errores: 24, pendientes: 0, porcentaje: 100 },
          },
        ],
      }
    }
    if (url === '/api/lotes/operadores') return [{ id: 7, username: 'gcarranco', nombre: 'Gavino Carranco', email: 'g@example.com' }]
    throw new Error(`GET inesperado: ${url}`)
  }),
  post: vi.fn(async () => ({ notificacion: { fallidos: [], sin_correo: true } })),
}))

vi.mock('../api/client', () => ({
  api: { get, post },
  ApiError: class ApiError extends Error { status = 409 },
}))

describe('Asignar carpeta completada sin responsables', () => {
  afterEach(() => { get.mockClear(); post.mockClear() })

  it('muestra Asignar (no solo el badge) y lo habilita al elegir responsable', async () => {
    const user = userEvent.setup()
    render(<Asignar />)

    const assignButton = await screen.findByRole('button', { name: 'Asignar' })
    expect(screen.getByText('Completado')).toBeInTheDocument()
    expect(assignButton).toBeDisabled()

    await user.click(screen.getByRole('button', { name: /seleccionar responsables/i }))
    await user.click(screen.getByRole('checkbox', { name: /Gavino Carranco/ }))

    await waitFor(() => expect(assignButton).toBeEnabled())
    await user.click(assignButton)

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/lotes/asignar',
      { relative_path: 'SEPTIEMBRE 2026/02-09-2026', operador_ids: [7] },
    ))
  })
})
