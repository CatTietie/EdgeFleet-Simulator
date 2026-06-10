import { useEffect } from 'react'
import { useTopologyStore } from '../../store/topology'
import TopologyGraph from './TopologyGraph'
import TopologyControls from './TopologyControls'

export default function TopologyPage() {
  const { nodes, edges, loading, fetchTopology } = useTopologyStore()

  useEffect(() => {
    fetchTopology()
  }, [])

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Device Topology</h2>
        <button onClick={fetchTopology} style={{ padding: '6px 12px', cursor: 'pointer' }}>
          Refresh
        </button>
      </div>

      <div style={{ display: 'flex', gap: 16 }}>
        <div style={{
          flex: 1,
          background: '#fff',
          borderRadius: 8,
          border: '1px solid #e0e0e0',
          overflow: 'hidden',
          position: 'relative',
          minHeight: 500,
        }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 500 }}>
              Loading...
            </div>
          ) : nodes.length === 0 ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 500, color: '#999' }}>
              No device dependencies configured. Use the panel on the right to add dependencies.
            </div>
          ) : (
            <TopologyGraph nodes={nodes} edges={edges} />
          )}
        </div>

        <div style={{ width: 320, flexShrink: 0 }}>
          <TopologyControls onCreated={fetchTopology} />
        </div>
      </div>
    </div>
  )
}
