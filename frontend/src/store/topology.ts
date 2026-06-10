import { create } from 'zustand'
import { apiClient } from '../api/client'

export interface TopologyNode {
  device_id: string
  name: string
  device_type: string
  status: string
  has_active_alarm: boolean
}

export interface TopologyEdge {
  id: string
  parent_device_id: string
  child_device_id: string
  dependency_type: string
  suppress_derived_notifications: boolean
  is_propagating?: boolean
}

interface TopologyState {
  nodes: TopologyNode[]
  edges: TopologyEdge[]
  loading: boolean
  fetchTopology: () => Promise<void>
  updateEdgePropagation: (parentDeviceId: string, propagating: boolean) => void
  handleTopologyUpdate: (data: { action: string; edge: TopologyEdge }) => void
}

export const useTopologyStore = create<TopologyState>((set, get) => ({
  nodes: [],
  edges: [],
  loading: false,

  fetchTopology: async () => {
    set({ loading: true })
    try {
      const res = await apiClient.get('/api/v1/dependencies/topology')
      set({ nodes: res.data.nodes, edges: res.data.edges, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  updateEdgePropagation: (parentDeviceId, propagating) => {
    set((state) => ({
      edges: state.edges.map((e) =>
        e.parent_device_id === parentDeviceId
          ? { ...e, is_propagating: propagating }
          : e
      ),
    }))
  },

  handleTopologyUpdate: (data) => {
    const { action, edge } = data
    set((state) => {
      if (action === 'edge_added') {
        return { edges: [...state.edges, edge] }
      } else if (action === 'edge_removed') {
        return { edges: state.edges.filter((e) => e.id !== edge.id) }
      }
      return state
    })
  },
}))
