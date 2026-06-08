import { useEffect, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { api } from '../../api/client'

interface Props {
  deviceId: string
}

export default function TimeSeriesChart({ deviceId }: Props) {
  const [tempData, setTempData] = useState<{ timestamp: string; value: number }[]>([])
  const [humData, setHumData] = useState<{ timestamp: string; value: number }[]>([])

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [tempRes, humRes] = await Promise.all([
          api.get(`/api/v1/dashboard/device/${deviceId}/timeseries`, {
            params: { metric: 'temperature', range_start: '-30m', aggregate: '30s' },
          }),
          api.get(`/api/v1/dashboard/device/${deviceId}/timeseries`, {
            params: { metric: 'humidity', range_start: '-30m', aggregate: '30s' },
          }),
        ])
        setTempData(tempRes.data)
        setHumData(humRes.data)
      } catch {}
    }

    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [deviceId])

  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Temperature', 'Humidity'] },
    xAxis: {
      type: 'time',
      axisLabel: { fontSize: 10 },
    },
    yAxis: [
      { type: 'value', name: 'Temp (C)', position: 'left' },
      { type: 'value', name: 'Humidity (%)', position: 'right', max: 100 },
    ],
    series: [
      {
        name: 'Temperature',
        type: 'line',
        smooth: true,
        yAxisIndex: 0,
        data: tempData.map((d) => [d.timestamp, d.value]),
        lineStyle: { color: '#ff6b6b' },
        itemStyle: { color: '#ff6b6b' },
      },
      {
        name: 'Humidity',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: humData.map((d) => [d.timestamp, d.value]),
        lineStyle: { color: '#4dabf7' },
        itemStyle: { color: '#4dabf7' },
      },
    ],
    dataZoom: [{ type: 'inside' }],
    grid: { left: 60, right: 60, bottom: 30, top: 40 },
  }

  return <ReactECharts option={option} style={{ height: 300 }} />
}
