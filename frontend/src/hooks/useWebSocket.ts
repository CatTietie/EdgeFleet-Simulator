import { useEffect, useRef } from 'react'
import { useAuthStore } from '../store/auth'
import { useDashboardStore } from '../store/dashboard'

export function useWebSocket() {
  const token = useAuthStore((s) => s.token)
  const { updateDevice, updateDeviceStatus, addAlarm } = useDashboardStore()
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!token) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws?token=${token}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        switch (msg.type) {
          case 'telemetry_update':
            updateDevice({
              device_id: msg.data.device_id,
              metrics: msg.data.metrics,
              timestamp: msg.data.timestamp,
            })
            break
          case 'device_status_change':
            updateDeviceStatus(msg.data.device_id, msg.data.status)
            break
          case 'alarm_event':
            addAlarm(msg.data)
            break
        }
      } catch {}
    }

    ws.onclose = () => {
      // Reconnect after 3 seconds
      setTimeout(() => {
        if (wsRef.current === ws) {
          wsRef.current = null
        }
      }, 3000)
    }

    // Ping to keep alive
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 30000)

    return () => {
      clearInterval(pingInterval)
      ws.close()
    }
  }, [token])
}
