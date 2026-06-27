import { phaseBg } from '../utils/helpers'

/**
 * Renders a vertical traffic light pole for one lane.
 * phase: "RED" | "YELLOW" | "GREEN"
 * laneId: "N" | "S" | "E" | "W"
 * vehicleCount: number
 */
export default function SignalLight({ phase = 'RED', laneId, vehicleCount = 0, emergency = false }) {
  return (
    <div className="flex flex-col items-center gap-2">
      {/* Lane label */}
      <span className={`text-xs font-mono font-medium px-2 py-0.5 rounded
        ${emergency ? 'text-red-400 bg-red-900/30' : 'text-gray-400 bg-surface-border/30'}`}>
        {laneId}
      </span>

      {/* Traffic light housing */}
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-2 flex flex-col gap-2 w-10">
        {['RED', 'YELLOW', 'GREEN'].map(p => (
          <div
            key={p}
            className={`w-6 h-6 rounded-full mx-auto transition-all duration-500
              ${phase === p
                ? phaseBg(p)
                : 'bg-gray-800 border border-gray-700'
              }
              ${phase === p && p === 'GREEN'  ? 'signal-green'  : ''}
              ${phase === p && p === 'YELLOW' ? 'signal-yellow' : ''}
              ${phase === p && p === 'RED'    ? 'signal-red'    : ''}
            `}
          />
        ))}
      </div>

      {/* Vehicle count */}
      <div className="text-center">
        <span className="text-lg font-mono font-semibold text-white">{vehicleCount}</span>
        <p className="text-xs text-gray-500">vehicles</p>
      </div>

      {/* Emergency flash badge */}
      {emergency && (
        <span className="badge-red text-xs animate-pulse">EMRG</span>
      )}
    </div>
  )
}
