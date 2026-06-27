import { useJunctions } from '../context/JunctionContext'
import { getEmergencyHistory } from '../utils/api'
import { useFetch } from '../hooks/useFetch'
import { formatDate, timeAgo, emergencyLabel } from '../utils/helpers'

export default function EmergencyLog() {
  const { selected } = useJunctions()

  const { data: events, loading, refetch } = useFetch(
    () => selected ? getEmergencyHistory(selected, 100) : Promise.reject(),
    [selected]
  )

  if (!selected) return (
    <p className="text-sm text-gray-400">Select a junction to view its emergency log.</p>
  )

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Emergency Log</h1>
        <button onClick={refetch} className="btn-ghost text-xs">↻ Refresh</button>
      </div>

      <div className="card p-0 overflow-hidden">
        {loading ? (
          <p className="text-xs text-gray-500 text-center py-8">Loading…</p>
        ) : !events?.length ? (
          <p className="text-xs text-gray-500 text-center py-8">No emergency events recorded.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border">
                {['Type', 'Direction', 'Status', 'Triggered', 'Cleared', 'Notes'].map(h => (
                  <th key={h} className="text-left text-xs text-gray-500 font-medium px-4 py-3">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {events.map(ev => {
                const meta = emergencyLabel[ev.emergency_type] ?? { label: ev.emergency_type, color: 'badge-blue' }
                return (
                  <tr key={ev.id} className="border-b border-surface-border/50 hover:bg-surface-card/50">
                    <td className="px-4 py-3">
                      <span className={meta.color}>{meta.label}</span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-white">
                      {ev.direction ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={ev.status === 'active' ? 'badge-red' : 'badge-green'}>
                        {ev.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      <span title={formatDate(ev.triggered_at)}>{timeAgo(ev.triggered_at)}</span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {ev.cleared_at ? timeAgo(ev.cleared_at) : '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                      {ev.notes ?? '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs text-gray-500">
        Showing last {events?.length ?? 0} events for this junction.
      </p>
    </div>
  )
}
