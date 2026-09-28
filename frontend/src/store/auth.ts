import { create } from 'zustand'
import { api, clearApiCache } from '../api/client'

export interface User {
  id: number
  username: string
  nombre: string
  email: string
  rol: 'usuario' | 'supervisor' | 'administrador'
  must_change_password: boolean
  password_changed_at?: string | null
}

interface AuthState {
  user: User | null
  loading: boolean
  load: () => Promise<void>
  login: (username: string, password: string) => Promise<void>
  changePassword: (actual: string, nueva: string) => Promise<void>
  logout: () => Promise<void>
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,

  load: async () => {
    try {
      const u = await api.get<User>('/api/auth/me')
      set({ user: u, loading: false })
    } catch {
      set({ user: null, loading: false })
    }
  },

  login: async (username, password) => {
    clearApiCache()
    const r = await api.post<{ user: User }>('/api/auth/login', { username, password })
    clearApiCache()
    set({ user: r.user })
  },

  changePassword: async (actual, nueva) => {
    const r = await api.post<{ user: User }>('/api/auth/password', { actual, nueva })
    clearApiCache()
    set({ user: r.user })
  },

  logout: async () => {
    try {
      await api.post<{ ok: boolean }>('/api/auth/logout', {})
    } finally {
      clearApiCache()
      set({ user: null })
    }
  },
}))
