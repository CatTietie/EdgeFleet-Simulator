import { create } from 'zustand'
import { api } from '../api/client'

interface AuthState {
  token: string | null
  orgId: string | null
  role: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  orgId: localStorage.getItem('orgId'),
  role: localStorage.getItem('role'),

  login: async (username, password) => {
    const res = await api.post('/api/v1/auth/login', { username, password })
    const { access_token } = res.data
    // Decode JWT to get org_id and role
    const payload = JSON.parse(atob(access_token.split('.')[1]))
    localStorage.setItem('token', access_token)
    localStorage.setItem('orgId', payload.org_id)
    localStorage.setItem('role', payload.role)
    set({ token: access_token, orgId: payload.org_id, role: payload.role })
  },

  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('orgId')
    localStorage.removeItem('role')
    set({ token: null, orgId: null, role: null })
  },
}))
