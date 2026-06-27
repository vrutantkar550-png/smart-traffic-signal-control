import { useState } from 'react'
import { useJunctions } from '../context/JunctionContext'
import { getAnalyticsSummary, getWaitTimeSeries } from '../utils/api'
import { useFetch } from '../hooks/useFetch'
import StatCard from '../components/StatCard'
import AnalyticsChart from '../components/AnalyticsChart'

const PERIODS = [
  { value: 'today', label: 'Today'      },
  { value: 'week',  label: 'This week'  },
  { value: 'month', label: 'This month' },
]

const HOURS_OPTIONS = [
  { value: 6,   label: '6h'  },
  { value: 24,  label: '24h' },
  { value: 72,  label: '3d'  },
  { value: 168, label: '7d'  },
]

export default function Analytics() {
  const { selected } = useJunctions()
  const [period, setPeriod] = useState('today')
  const [hours,  setHours]  = useState(24)

  const { data: summary } = useFetch(
    () => selected ? getAnalyticsSummary(selected, period) : Promise.reject(),
    [selected, period]
  )

  const { data: series } = useFetch(
    () => selected ? getWaitTimeSeries(selected, hours) : Promise.reject(),
    [selected, hours]
  )

  if (!selected) return (
    <p className="text-sm text-gray-400">Select a junction from the sidebar to view analytics.</p>
  )

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Analytics</h1>

        {/* Period selector */}
        <div className="flex gap-1 bg-surface-card border border-surface-border rounded-lg p-1">
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`text-xs px-3 py-1.5 rounded-md transition-all
                ${period === p.value
                  ? 'bg-accent text-white'
                  : 'text-gray-400 hover:text-white'}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Avg wait time"
          value={summary?.avg_wait_time_seconds?.toFixed(1) ?? '--'}
          unit="s" accent
        />
        <StatCard
          label="Total vehicles"
          value={summary?.total_vehicles?.toLocaleString() ?? '--'}
        />
        <StatCard
          label="Peak hour"
          value={summary?.peak_hour ?? '--'}
        />
        <StatCard
          label="Emergency events"
          value={summary?.emergency_count ?? '--'}
        />
      </div>

      {/* Wait time chart */}
      <div className="card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Average wait time</h2>

          {/* Hours range */}
          <div className="flex gap-1 bg-surface border border-surface-border rounded-lg p-1">
            {HOURS_OPTIONS.map(h => (
              <button
                key={h.value}
                onClick={() => setHours(h.value)}
                className={`text-xs px-2.5 py-1 rounded-md transition-all
                  ${hours === h.value
                    ? 'bg-accent/20 text-accent'
                    : 'text-gray-500 hover:text-gray-300'}`}
              >
                {h.label}
              </button>
            ))}
          </div>
        </div>

        <AnalyticsChart data={series ?? []} />
      </div>
    </div>
  )
}
