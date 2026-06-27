import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, ResponsiveContainer, Legend,
} from 'recharts'
import { format } from 'date-fns'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface-card border border-surface-border rounded-lg px-3 py-2 text-xs">
      <p className="text-gray-400 mb-1">{label}</p>
      <p className="text-accent font-mono">{payload[0].value.toFixed(1)}s avg wait</p>
    </div>
  )
}

export default function AnalyticsChart({ data = [] }) {
  const chartData = data.map(d => ({
    time:     format(new Date(d.timestamp), 'HH:mm'),
    avg_wait: d.avg_wait,
  }))

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-xs text-gray-500">
        No data for selected period
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid stroke="#2A2D3A" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="time" tick={{ fill: '#6B7280', fontSize: 11 }}
          axisLine={false} tickLine={false}
        />
        <YAxis
          tick={{ fill: '#6B7280', fontSize: 11 }}
          axisLine={false} tickLine={false}
          unit="s"
        />
        <Tooltip content={<CustomTooltip />} />
        <Line
          type="monotone" dataKey="avg_wait"
          stroke="#3B82F6" strokeWidth={2}
          dot={false} activeDot={{ r: 4, fill: '#3B82F6' }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
