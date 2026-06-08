import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useDashboardStore } from '../../store/dashboard'
import DeviceGrid from './DeviceGrid'
import TimeSeriesChart from './TimeSeriesChart'
import AlarmPanel from './AlarmPanel'

export default function DashboardPage() {
  const [selectedDevice, setSelectedDevice] = useState<string | null>(null)
  const [devices, setDevices] = useState<any[]>([])
  const realtimeDevices = useDashboardStore((s) => s.devices)

  useEffect(() => {
    api.get('/api/v1/devices').then((res) => setDevices(res.data)).catch(() => {})
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <div style={{ background: '#fff', borderRadius: 8, padding: 16 }}>
          <h3 style={{ margin: '0 0 12px' }}>Devices ({devices.length})</h3>
          <DeviceGrid
            devices={devices}
            realtimeData={realtimeDevices}
            onSelect={setSelectedDevice}
            selectedId={selectedDevice}
          />
        </div>
        <div style={{ background: '#fff', borderRadius: 8, padding: 16 }}>
          <h3 style={{ margin: '0 0 12px' }}>Active Alarms</h3>
          <AlarmPanel />
        </div>
      </div>
      {selectedDevice && (
        <div style={{ background: '#fff', borderRadius: 8, padding: 16 }}>
          <h3 style={{ margin: '0 0 12px' }}>Time Series: {selectedDevice}</h3>
          <TimeSeriesChart deviceId={selectedDevice} />
        </div>
      )}
    </div>
  )
}
