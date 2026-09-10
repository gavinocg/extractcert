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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const opts: RequestInit = { ...init }
  const method = (opts.method ?? 'GET').toUpperCase()
  if (method !== 'GET') {
    opts.headers = { ...(opts.headers ?? {}) }
    if (!(opts.body instanceof FormData)) {
      ;(opts.headers as Record<string, string>)['Content-Type'] = 'application/json'
    }
    ;(opts.headers as Record<string, string>)['X-CSRF-Token'] = csrfFromCookie()
  }
  const res = await fetch(path, { ...opts, credentials: 'include' })
  if (res.status === 401) {
    window.dispatchEvent(new Event('auth:unauthorized'))
  }
  if (!res.ok) {
    let msg = `Error ${res.status}`
    try {
      const j = await res.json()
      if (j?.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
      else if (j?.error) msg = j.error
    } catch {
      /* cuerpo no JSON */
    }
    throw new ApiError(res.status, msg)
  }
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

export function csrfToken() {
  return csrfFromCookie()
}
export { ApiError }