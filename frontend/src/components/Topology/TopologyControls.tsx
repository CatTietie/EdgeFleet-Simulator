import { useState } from 'react'
import { apiClient } from '../../api/client'

interface Props {
  onCreated: () => void
}

export default function TopologyControls({ onCreated }: Props) {
  const [parentId, setParentId] = useState('')
  const [childId, setChildId] = useState('')
  const [depType, setDepType] = useState('gateway_sensor')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await apiClient.post('/api/v1/dependencies', {
        parent_device_id: parentId.trim(),
        child_device_id: childId.trim(),
        dependency_type: depType,
      })
      setParentId('')
      setChildId('')
      onCreated()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create dependency')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e0e0e0', padding: 16 }}>
      <h3 style={{ margin: '0 0 12px' }}>Add Dependency</h3>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>Parent Device ID</label>
          <input
            value={parentId}
            onChange={(e) => setParentId(e.target.value)}
            placeholder="e.g. gateway-01"
            style={{ width: '100%', padding: '6px 8px', boxSizing: 'border-box' }}
            required
          />
        </div>
        <div style={{ marginBottom: 8 }}>
          <label style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>Child Device ID</label>
          <input
            value={childId}
            onChange={(e) => setChildId(e.target.value)}
            placeholder="e.g. sensor-01"
            style={{ width: '100%', padding: '6px 8px', boxSizing: 'border-box' }}
            required
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>Dependency Type</label>
          <select
            value={depType}
            onChange={(e) => setDepType(e.target.value)}
            style={{ width: '100%', padding: '6px 8px' }}
          >
            <option value="gateway_sensor">Gateway → Sensor</option>
            <option value="power_device">Power → Device</option>
            <option value="switch_device">Switch → Device</option>
          </select>
        </div>
        {error && (
          <div style={{ color: '#f44336', fontSize: 12, marginBottom: 8 }}>{error}</div>
        )}
        <button
          type="submit"
          disabled={loading}
          style={{ width: '100%', padding: '8px', cursor: 'pointer', background: '#1976d2', color: '#fff', border: 'none', borderRadius: 4 }}
        >
          {loading ? 'Creating...' : 'Create Dependency'}
        </button>
      </form>

      <div style={{ marginTop: 24, borderTop: '1px solid #eee', paddingTop: 12 }}>
        <h4 style={{ margin: '0 0 8px', fontSize: 13 }}>Legend</h4>
        <div style={{ fontSize: 12, lineHeight: 1.8 }}>
          <div><span style={{ display: 'inline-block', width: 12, height: 12, background: '#1976d2', borderRadius: '50%', marginRight: 6, verticalAlign: 'middle' }}></span>Gateway</div>
          <div><span style={{ display: 'inline-block', width: 12, height: 12, background: '#388e3c', borderRadius: '50%', marginRight: 6, verticalAlign: 'middle' }}></span>Sensor</div>
          <div><span style={{ display: 'inline-block', width: 12, height: 12, background: '#f57c00', borderRadius: '50%', marginRight: 6, verticalAlign: 'middle' }}></span>Switch</div>
          <div><span style={{ display: 'inline-block', width: 12, height: 12, background: '#7b1fa2', borderRadius: '50%', marginRight: 6, verticalAlign: 'middle' }}></span>Power</div>
          <div style={{ marginTop: 4 }}>
            <span style={{ display: 'inline-block', width: 12, height: 12, border: '2px solid #f44336', borderRadius: '50%', marginRight: 6, verticalAlign: 'middle' }}></span>Active Alarm
          </div>
          <div>
            <span style={{ display: 'inline-block', width: 20, height: 2, background: '#f44336', marginRight: 6, verticalAlign: 'middle' }}></span>Propagating
          </div>
        </div>
      </div>
    </div>
  )
}
