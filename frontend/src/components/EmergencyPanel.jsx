import { useState } from 'react'
import { triggerEmergency, clearEmergency } from '../utils/api'
import { useJunctions } from '../context/JunctionContext'
import { useSignalState } from '../context/WebSocketContext'

const TYPES = [
  {
    id:    'ambulance',
    label: 'Ambulance',
    icon:  '🚑',
    desc:  'Green corridor for emergency vehicle',
    color: 'border-red-700 hover:bg-red-900/20',
    badge: 'badge-red',
  },
  {
    id:    'fire_truck',
    label: 'Fire Truck',
    icon:  '🚒',
    desc:  'Full intersection clear — all red',
    color: 'border-red-700 hover:bg-red-900/20',
    badge: 'badge-red',
  },
  {
    id:    'accident',
    label: 'Accident',
    icon:  '⚠',
    desc:  'Block affected lane, reroute traffic',
    color: 'border-yellow-700 hover:bg-yellow-900/20',
    badge: 'badge-yellow',
  },
  {
    id:    'construction',
    label: 'Construction',
    icon:  '🚧',
    desc:  'Lane merge mode, extended green',
    color: 'border-yellow-700 hover:bg-yellow-900/20',
    badge: 'badge-yellow',
  },
]

export default function EmergencyPanel() {
  const { selected } = useJunctions()
  const { signalState } = useSignalState()
  const [direction, setDirection] = useState('N')
  const [loading,   setLoading]   = useState(false)
  const [message,   setMessage]   = useState(null)

  const isActive = signalState?.emergency_active

  const trigger = async (type) => {
    if (!selected) return
    setLoading(true)
    setMessage(null)
    try {
      await triggerEmergency(selected, {
        emergency_type: type,
        direction,
        notes: `Triggered from dashboard — direction ${direction}`,
      })
      setMessage({ text: `${type.replace('_',' ')} override activated`, type: 'success' })
    } catch (e) {
      setMessage({ text: 'Failed to trigger emergency', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const clear = async () => {
    if (!selected) return
    setLoading(true)
    try {
      await clearEmergency(selected)
      setMessage({ text: 'Emergency cleared', type: 'success' })
    } catch {
      setMessage({ text: 'No active emergency to clear', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-white">Emergency Override</h2>
        {isActive && (
          <span className="badge-red animate-pulse">ACTIVE</span>
        )}
      </div>

      {/* Direction selector */}
      <div>
        <label className="text-xs text-gray-400 mb-1 block">Emergency direction</label>
        <div className="flex gap-2">
          {['N', 'S', 'E', 'W'].map(d => (
            <button
              key={d}
              onClick={() => setDirection(d)}
              className={`w-9 h-9 rounded-lg text-sm font-mono font-medium border transition-all
                ${direction === d
                  ? 'bg-accent border-accent text-white'
                  : 'border-surface-border text-gray-400 hover:border-gray-500'}`}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Emergency type buttons */}
      <div className="grid grid-cols-2 gap-2">
        {TYPES.map(t => (
          <button
            key={t.id}
            onClick={() => trigger(t.id)}
            disabled={loading || !selected}
            className={`border rounded-xl p-3 text-left transition-all disabled:opacity-40
                        disabled:cursor-not-allowed ${t.color}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{t.icon}</span>
              <span className="text-sm font-semibold text-white">{t.label}</span>
            </div>
            <p className="text-xs text-gray-400 leading-tight">{t.desc}</p>
          </button>
        ))}
      </div>

      {/* Clear button */}
      {isActive && (
        <button
          onClick={clear}
          disabled={loading}
          className="btn-danger w-full justify-center disabled:opacity-40"
        >
          ✕ Clear Emergency Override
        </button>
      )}

      {/* Feedback message */}
      {message && (
        <p className={`text-xs px-3 py-2 rounded-lg
          ${message.type === 'success'
            ? 'bg-green-900/30 text-green-400'
            : 'bg-red-900/30 text-red-400'}`}>
          {message.text}
        </p>
      )}
    </div>
  )
}
