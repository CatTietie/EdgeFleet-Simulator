import { useEffect, useRef } from 'react'
import { useAuthStore } from '../store/auth'
import { useDashboardStore } from '../store/dashboard'
import { useTopologyStore } from '../store/topology'

const RECONNECT_DELAY_INIT_MS = 3000
const MAX_RECONNECT_DELAY_MS = 30000

export function useWebSocket() {
  const token = useAuthStore((s) => s.token)
  const { updateDevice, updateDeviceStatus, addAlarm } = useDashboardStore()
  const { updateEdgePropagation, handleTopologyUpdate } = useTopologyStore()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!token) return

    let intentionallyClosed = false
    let reconnectDelay = RECONNECT_DELAY_INIT_MS

    const connect = () => {
      if (intentionallyClosed) return

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws?token=${token}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        reconnectDelay = RECONNECT_DELAY_INIT_MS
      }

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
              if (msg.data.is_derived && msg.data.root_cause_device_id) {
                updateEdgePropagation(
                  msg.data.root_cause_device_id,
                  msg.data.event_type === 'triggered'
                )
              }
              break
            case 'topology_update':
              handleTopologyUpdate(msg.data)
              break
          }
        } catch {}
      }

      ws.onclose = () => {
        wsRef.current = null
        if (intentionallyClosed) return
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY_MS)
          connect()
        }, reconnectDelay)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 30000)

    return () => {
      intentionallyClosed = true
      clearInterval(pingInterval)
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [token])
}
