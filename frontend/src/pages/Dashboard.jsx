import { useSignalState } from '../context/WebSocketContext'
import { useJunctions } from '../context/JunctionContext'
import JunctionMap from '../components/JunctionMap'
import SignalLight from '../components/SignalLight'
import EmergencyPanel from '../components/EmergencyPanel'
import TimingControl from '../components/TimingControl'
import VehicleCounter from '../components/VehicleCounter'
import { formatTime } from '../utils/helpers'

export default function Dashboard() {
  const { signalState, connected } = useSignalState()
  const { junctions, selected }    = useJunctions()
  const junction = junctions.find(j => j.id === selected)

  const lanes = signalState?.lanes ?? []

  return (
    <div className="space-y-4">

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-white">
            {junction?.name ?? 'Select a junction'}
          </h1>
          <p className="text-xs text-gray-400 mt-0.5">
            {junction?.junction_type ?? ''} junction
            {signalState && ` · updated ${formatTime(signalState.timestamp)}`}
          </p>
        </div>
        {signalState?.emergency_active && (
          <div className="flex items-center gap-2 bg-red-900/30 border border-red-700
                          rounded-lg px-3 py-2 animate-pulse">
            <span className="text-red-400 text-sm">⚠</span>
            <span className="text-red-400 text-sm font-medium">
              Emergency: {signalState.emergency_type?.replace('_',' ')}
            </span>
          </div>
        )}
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-3 gap-4" style={{ minHeight: '520px' }}>

        {/* Left — Map */}
        <div className="col-span-2 card p-0 overflow-hidden" style={{ minHeight: '420px' }}>
          <JunctionMap />
        </div>

        {/* Right — Signal lights */}
        <div className="card flex flex-col gap-4">
          <h2 className="text-sm font-semibold text-white">Signal Status</h2>

          {lanes.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-xs text-gray-500">
              {connected ? 'Waiting for signal data…' : 'Controller offline'}
            </div>
          ) : (
            <div className={`flex flex-wrap gap-4 justify-center items-end flex-1`}>
              {lanes.map(lane => (
                <SignalLight
                  key={lane.lane_id}
                  laneId={lane.lane_id}
                  phase={lane.phase}
                  vehicleCount={lane.vehicle_count}
                  emergency={signalState?.emergency_active}
                />
              ))}
            </div>
          )}

          {/* Phase info */}
          {signalState && (
            <div className="border-t border-surface-border pt-3 text-xs text-gray-400 space-y-1">
              <div className="flex justify-between">
                <span>Phase index</span>
                <span className="font-mono text-white">{signalState.active_phase_index ?? '--'}</span>
              </div>
              <div className="flex justify-between">
                <span>Emergency</span>
                <span className={signalState.emergency_active ? 'text-red-400 font-medium' : 'text-gray-500'}>
                  {signalState.emergency_active ? 'Active' : 'None'}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-3 gap-4">
        <VehicleCounter />
        <EmergencyPanel />
        <TimingControl />
      </div>
    </div>
  )
}
