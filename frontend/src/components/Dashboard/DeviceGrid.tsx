import { DeviceData } from '../../store/dashboard'

interface Props {
  devices: any[]
  realtimeData: Record<string, DeviceData>
  onSelect: (id: string) => void
  selectedId: string | null
}

export default function DeviceGrid({ devices, realtimeData, onSelect, selectedId }: Props) {
  return (
    <div style={{ maxHeight: 400, overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#f5f5f5' }}>
            <th style={{ padding: 8, textAlign: 'left' }}>Device</th>
            <th style={{ padding: 8, textAlign: 'left' }}>Status</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Temperature</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Humidity</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((dev) => {
            const rt = realtimeData[dev.id]
            const isSelected = dev.id === selectedId
            return (
              <tr
                key={dev.id}
                onClick={() => onSelect(dev.id)}
                style={{
                  cursor: 'pointer',
                  background: isSelected ? '#e8e8ff' : undefined,
                  borderBottom: '1px solid #eee',
                }}
              >
                <td style={{ padding: 8 }}>{dev.name || dev.id}</td>
                <td style={{ padding: 8 }}>
                  <span style={{
                    display: 'inline-block',
                    width: 8, height: 8,
                    borderRadius: '50%',
                    background: (rt?.status || dev.status) === 'online' ? '#4caf50' : '#f44336',
                    marginRight: 6,
                  }} />
                  {rt?.status || dev.status || 'offline'}
                </td>
                <td style={{ padding: 8, textAlign: 'right', fontFamily: 'monospace' }}>
                  {rt?.metrics?.temperature?.toFixed(1) ?? '-'}
                </td>
                <td style={{ padding: 8, textAlign: 'right', fontFamily: 'monospace' }}>
                  {rt?.metrics?.humidity?.toFixed(1) ?? '-'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
