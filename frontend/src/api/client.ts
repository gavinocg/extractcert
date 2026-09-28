const csrfFromCookie = () =>
  document.cookie
    .split('; ')
    .find((c) => c.startsWith('csrf_token='))
    ?.split('=')[1] ?? ''

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export interface RequestOptions extends RequestInit {
  globalLoading?: boolean
  cacheTtl?: number
}

interface PendingGet {
  promise: Promise<unknown>
  controller: AbortController
  subscribers: number
}

const pendingGets = new Map<string, PendingGet>()
const responseCache = new Map<string, { expires: number; value: unknown }>()

const abortError = () => new DOMException('Aborted', 'AbortError')

function getKey(path: string, init: RequestOptions) {
  const headers = [...new Headers(init.headers).entries()]
    .map(([name, value]) => [name.toLowerCase(), value] as const)
    .sort(([a], [b]) => a.localeCompare(b))
  return JSON.stringify({
    path,
    headers,
    cache: init.cache,
    mode: init.mode,
    redirect: init.redirect,
    referrer: init.referrer,
    referrerPolicy: init.referrerPolicy,
    integrity: init.integrity,
    globalLoading: init.globalLoading ?? true,
    cacheTtl: init.cacheTtl ?? 0,
  })
}

function subscribe<T>(entry: PendingGet, signal?: AbortSignal | null): Promise<T> {
  if (signal?.aborted) return Promise.reject(abortError())
  entry.subscribers++
  return new Promise<T>((resolve, reject) => {
    let active = true
    const finish = () => {
      if (!active) return false
      active = false
      signal?.removeEventListener('abort', onAbort)
      entry.subscribers--
      return true
    }
    const onAbort = () => {
      if (!finish()) return
      if (entry.subscribers === 0) entry.controller.abort()
      reject(abortError())
    }
    signal?.addEventListener('abort', onAbort, { once: true })
    entry.promise.then(
      (value) => { if (finish()) resolve(value as T) },
      (error) => { if (finish()) reject(error) },
    )
  })
}

async function execute<T>(path: string, init: RequestOptions): Promise<T> {
  const { globalLoading = true, cacheTtl: _cacheTtl, ...fetchInit } = init
  if (globalLoading) window.dispatchEvent(new Event('app:loading-start'))
  try {
  const opts: RequestInit = { ...fetchInit }
  const method = (opts.method ?? 'GET').toUpperCase()
  if (method !== 'GET') {
    opts.headers = { ...(opts.headers ?? {}) }
    if (!(opts.body instanceof FormData)) {
      ;(opts.headers as Record<string, string>)['Content-Type'] = 'application/json'
    }
    ;(opts.headers as Record<string, string>)['X-CSRF-Token'] = csrfFromCookie()
  }
  const res = await fetch(path, { ...opts, credentials: 'include' })
  if (res.status === 401) window.dispatchEvent(new Event('auth:unauthorized'))
  if (!res.ok) {
    let msg = `Error ${res.status}`
    try {
      const j = await res.json()
      if (j?.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
      else if (j?.error) msg = j.error
    } catch {
      /* cuerpo no JSON */
    }
    if (res.status === 401) clearApiCache()
    throw new ApiError(res.status, msg)
  }
    return (await res.json()) as T
  } finally {
    if (globalLoading) window.dispatchEvent(new Event('app:loading-end'))
  }
}

function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  if (method !== 'GET') return execute<T>(path, init)
  if (init.signal?.aborted) return Promise.reject(abortError())
  const key = getKey(path, init)
  const cached = responseCache.get(key)
  if (cached && cached.expires > Date.now()) return subscribe<T>({ promise: Promise.resolve(cached.value), controller: new AbortController(), subscribers: 0 }, init.signal)
  if (cached) responseCache.delete(key)
  const existing = pendingGets.get(key)
  if (existing) return subscribe<T>(existing, init.signal)

  const controller = new AbortController()
  const entry: PendingGet = { controller, subscribers: 0, promise: Promise.resolve() }
  const promise = execute<T>(path, { ...init, signal: controller.signal }).then((value) => {
    if (init.cacheTtl) responseCache.set(key, { expires: Date.now() + init.cacheTtl, value })
    return value
  }).finally(() => {
    if (pendingGets.get(key) === entry) pendingGets.delete(key)
  })
  entry.promise = promise
  pendingGets.set(key, entry)
  return subscribe<T>(entry, init.signal)
}

export const api = {
  get: <T>(path: string, options: RequestOptions = {}) => request<T>(path, options),
  post: <T>(path: string, body: unknown, options: RequestOptions = {}) => request<T>(path, { ...options, method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown, options: RequestOptions = {}) => request<T>(path, { ...options, method: 'PUT', body: JSON.stringify(body) }),
  del: <T>(path: string, options: RequestOptions = {}) => request<T>(path, { ...options, method: 'DELETE' }),
}

export function invalidateApiCache(path: string) {
  for (const key of responseCache.keys()) {
    const cachedPath = (JSON.parse(key) as { path: string }).path
    if (cachedPath === path || cachedPath.startsWith(`${path}?`)) responseCache.delete(key)
  }
}

export function clearApiCache() {
  responseCache.clear()
  for (const entry of pendingGets.values()) entry.controller.abort()
  pendingGets.clear()
}

export function csrfToken() {
  return csrfFromCookie()
}
export { ApiError }
