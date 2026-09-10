import { create } from 'zustand'
import { api } from '../api/client'

export interface User {
  id: number
  username: string
  rol: 'usuario' | 'administrador'
}

interface AuthState {
  user: User | null
  loading: boolean
  load: () => Promise<void>
  login: (username: string, password: string) => Promise<void>
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
    const r = await api.post<{ user: User }>('/api/auth/login', { username, password })
    set({ user: r.user })
  },

  logout: async () => {
    try {
      await api.post<{ ok: boolean }>('/api/auth/logout', {})
    } finally {
      set({ user: null })
    }
  },
}))