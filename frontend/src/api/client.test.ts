import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, clearApiCache, csrfToken } from './client'

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
    clearApiCache()
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    document.cookie = 'csrf_token=tok123'
  })
  afterEach(() => {
    clearApiCache()
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

  it('deduplica GET idénticos mientras están en curso', async () => {
    let resolveFetch!: (response: Response) => void
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => { resolveFetch = resolve }))
    const first = api.get<{ ok: boolean }>('/api/shared')
    const second = api.get<{ ok: boolean }>('/api/shared')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    resolveFetch(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    await expect(Promise.all([first, second])).resolves.toEqual([{ ok: true }, { ok: true }])
  })

  it('propaga AbortSignal y no muestra overlay si globalLoading es false', async () => {
    const events: string[] = []
    const onStart = () => events.push('start')
    window.addEventListener('app:loading-start', onStart)
    fetchMock.mockImplementation((_path, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    }))
    const controller = new AbortController()
    const result = api.get('/api/cancellable', { signal: controller.signal, globalLoading: false })
    controller.abort()
    await expect(result).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true)
    expect(events).toEqual([])
    window.removeEventListener('app:loading-start', onStart)
  })

  it('no deduplica GET con headers u opciones efectivas diferentes', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 })))
    await Promise.all([
      api.get('/api/scoped', { headers: { 'X-Scope': 'one' } }),
      api.get('/api/scoped', { headers: { 'X-Scope': 'two' } }),
      api.get('/api/scoped', { headers: { 'X-Scope': 'one' }, globalLoading: false }),
    ])
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('cancela un suscriptor sin cancelar otro GET deduplicado', async () => {
    let resolveFetch!: (response: Response) => void
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => { resolveFetch = resolve }))
    const firstController = new AbortController()
    const secondController = new AbortController()
    const first = api.get<{ ok: boolean }>('/api/shared-signals', { signal: firstController.signal })
    const second = api.get<{ ok: boolean }>('/api/shared-signals', { signal: secondController.signal })
    firstController.abort()
    await expect(first).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    resolveFetch(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    await expect(second).resolves.toEqual({ ok: true })
  })

  it('respeta señales abortadas al servir caché y permite limpiarlo', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ value: 1 }), { status: 200 }))
    await api.get('/api/cached', { cacheTtl: 60_000 })
    const controller = new AbortController()
    controller.abort()
    await expect(api.get('/api/cached', { cacheTtl: 60_000, signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetchMock).toHaveBeenCalledTimes(1)

    clearApiCache()
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ value: 2 }), { status: 200 }))
    await expect(api.get('/api/cached', { cacheTtl: 60_000 })).resolves.toEqual({ value: 2 })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
