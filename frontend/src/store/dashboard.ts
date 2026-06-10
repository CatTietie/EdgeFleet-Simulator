import { create } from 'zustand'

export interface DeviceData {
  device_id: string
  metrics: Record<string, number>
  timestamp: number
  status?: string
}

export interface AlarmEventData {
  alarm_id: string
  rule_id: string
  rule_name: string
  device_id: string
  event_type: string
  severity: string
  values: Record<string, number>
  timestamp_ms: number
  is_derived?: boolean
  root_cause_device_id?: string
  root_cause_alarm_id?: string
}

interface DashboardState {
  devices: Record<string, DeviceData>
  alarms: AlarmEventData[]
  updateDevice: (data: DeviceData) => void
  updateDeviceStatus: (deviceId: string, status: string) => void
  addAlarm: (alarm: AlarmEventData) => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  devices: {},
  alarms: [],

  updateDevice: (data) =>
    set((state) => ({
      devices: { ...state.devices, [data.device_id]: data },
    })),

  updateDeviceStatus: (deviceId, status) =>
    set((state) => ({
      devices: {
        ...state.devices,
        [deviceId]: { ...state.devices[deviceId], status },
      },
    })),

  addAlarm: (alarm) =>
    set((state) => ({
      alarms: [alarm, ...state.alarms].slice(0, 200),
    })),
}))
