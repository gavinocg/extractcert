import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, csrfToken } from './client'

describe('csrfToken', () => {
  it('lee el token de la cookie', () => {
    document.cookie = 'csrf_token=abc123'
    expect(csrfToken()).toBe('abc123')
  })

  it('devuelve vacío sin cookie', () => {
    document.cookie = 'csrf_token=; Max-Age=0'
    expect(csrfToken()).toBe('')
  })
})

describe('request', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    document.cookie = 'csrf_token=tok123'
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    document.cookie = 'csrf_token=; Max-Age=0'
  })

  it('añade X-CSRF-Token y Content-Type JSON en POST', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const res = await api.post('/api/x', { a: 1 })
    expect(res).toEqual({ ok: true })
    const [, init] = fetchMock.mock.calls[0]
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe('tok123')
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')
  })

  it('emite auth:unauthorized y lanza ApiError en 401', async () => {
    const dispatched: Event[] = []
    const onEvt = (e: Event) => dispatched.push(e)
    window.addEventListener('auth:unauthorized', onEvt)

    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'No autenticado' }), { status: 401 }),
    )
    await expect(api.get('/api/auth/me')).rejects.toBeInstanceOf(ApiError)
    expect(dispatched).toHaveLength(1)

    window.removeEventListener('auth:unauthorized', onEvt)
  })

  it('usa el detail del error como mensaje', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Ruta no permitida.' }), { status: 400 }),
    )
    await expect(api.get('/api/tree?path=..')).rejects.toMatchObject({ message: 'Ruta no permitida.' })
  })
})
