import { useSignalState } from '../context/WebSocketContext'
import { phaseColor } from '../utils/helpers'

export default function VehicleCounter() {
  const { signalState, connected } = useSignalState()

  const lanes = signalState?.lanes ?? []
  const total = lanes.reduce((s, l) => s + (l.vehicle_count ?? 0), 0)

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-white">Live Vehicle Counts</h2>
        <span className={`text-xs ${connected ? 'text-signal-green' : 'text-gray-500'}`}>
          {connected ? '● Live' : '○ Offline'}
        </span>
      </div>

      {lanes.length === 0 ? (
        <p className="text-xs text-gray-500 text-center py-4">
          {connected ? 'Waiting for data…' : 'No connection to controller'}
        </p>
      ) : (
        <>
          {/* Total */}
          <div className="bg-surface rounded-lg px-4 py-2 flex justify-between items-center mb-3">
            <span className="text-xs text-gray-400">Total vehicles</span>
            <span className="text-xl font-mono font-bold text-white">{total}</span>
          </div>

          {/* Per lane */}
          <div className="space-y-2">
            {lanes.map(lane => {
              const pct = total > 0 ? Math.round((lane.vehicle_count / total) * 100) : 0
              return (
                <div key={lane.lane_id} className="flex items-center gap-3">
                  <span className="text-xs font-mono text-gray-400 w-5">{lane.lane_id}</span>

                  {/* Progress bar */}
                  <div className="flex-1 h-2 bg-surface rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500
                        ${lane.phase === 'GREEN'  ? 'bg-signal-green'  :
                          lane.phase === 'YELLOW' ? 'bg-signal-yellow' : 'bg-signal-red'}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>

                  <span className={`text-xs font-mono w-6 text-right ${phaseColor(lane.phase)}`}>
                    {lane.vehicle_count}
                  </span>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
