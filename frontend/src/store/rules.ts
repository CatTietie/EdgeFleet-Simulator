import { create } from 'zustand'
import { api } from '../api/client'

export interface Rule {
  id: string
  org_id: string
  name: string
  description: string
  enabled: boolean
  severity: string
  target: Record<string, unknown>
  trigger_condition: Record<string, unknown>
  recovery_condition: Record<string, unknown> | null
  actions: Record<string, unknown>
  version: number
  created_at: string | null
  updated_at: string | null
}

interface RuleEditable {
  name: string
  description?: string
  severity?: string
  enabled?: boolean
  target: Record<string, unknown>
  trigger_condition: Record<string, unknown>
  recovery_condition?: Record<string, unknown> | null
  actions: Record<string, unknown>
}

interface RulesState {
  rules: Rule[]
  loading: boolean
  selectedRule: Rule | null
  isEditing: boolean
  isCreating: boolean
  fetchRules: () => Promise<void>
  selectRule: (rule: Rule | null) => void
  setEditing: (v: boolean) => void
  setCreating: (v: boolean) => void
  createRule: (data: RuleEditable) => Promise<void>
  updateRule: (id: string, data: Partial<RuleEditable>, version: number) => Promise<'ok' | 'conflict'>
  deleteRule: (id: string) => Promise<void>
}

export const useRulesStore = create<RulesState>((set, get) => ({
  rules: [],
  loading: false,
  selectedRule: null,
  isEditing: false,
  isCreating: false,

  fetchRules: async () => {
    set({ loading: true })
    try {
      const res = await api.get('/api/v1/rules')
      set({ rules: res.data })
    } finally {
      set({ loading: false })
    }
  },

  selectRule: (rule) => set({ selectedRule: rule }),
  setEditing: (v) => set({ isEditing: v }),
  setCreating: (v) => set({ isCreating: v }),

  createRule: async (data) => {
    await api.post('/api/v1/rules', data)
    await get().fetchRules()
    set({ isCreating: false })
  },

  updateRule: async (id, data, version) => {
    try {
      await api.put(`/api/v1/rules/${id}`, { ...data, version })
      await get().fetchRules()
      set({ isEditing: false, selectedRule: null })
      return 'ok'
    } catch (err: any) {
      if (err.response?.status === 409) {
        return 'conflict'
      }
      throw err
    }
  },

  deleteRule: async (id) => {
    await api.delete(`/api/v1/rules/${id}`)
    await get().fetchRules()
    set({ selectedRule: null })
  },
}))
