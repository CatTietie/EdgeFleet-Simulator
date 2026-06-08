import { useDashboardStore, AlarmEventData } from '../../store/dashboard'

const severityColors: Record<string, string> = {
  critical: '#f44336',
  warning: '#ff9800',
  info: '#2196f3',
}

export default function AlarmPanel() {
  const alarms = useDashboardStore((s) => s.alarms)

  if (alarms.length === 0) {
    return <p style={{ color: '#888', fontSize: 14 }}>No active alarms</p>
  }

  return (
    <div style={{ maxHeight: 400, overflow: 'auto' }}>
      {alarms.map((alarm, idx) => (
        <div
          key={alarm.alarm_id || idx}
          style={{
            padding: 10,
            marginBottom: 8,
            borderRadius: 4,
            border: `1px solid ${severityColors[alarm.severity] || '#ccc'}`,
            borderLeft: `4px solid ${severityColors[alarm.severity] || '#ccc'}`,
            background: '#fafafa',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <strong style={{ fontSize: 13 }}>{alarm.rule_name}</strong>
            <span style={{
              fontSize: 11,
              padding: '2px 6px',
              borderRadius: 3,
              background: alarm.event_type === 'triggered' ? '#ffebee' : '#e8f5e9',
              color: alarm.event_type === 'triggered' ? '#c62828' : '#2e7d32',
            }}>
              {alarm.event_type}
            </span>
          </div>
          <div style={{ fontSize: 12, color: '#666' }}>
            Device: {alarm.device_id} | Severity: {alarm.severity}
          </div>
          <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
            {new Date(alarm.timestamp_ms).toLocaleTimeString()}
          </div>
        </div>
      ))}
    </div>
  )
}
