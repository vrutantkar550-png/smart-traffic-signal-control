import { useState } from 'react'
import { updateTimingConfig } from '../utils/api'
import { useJunctions } from '../context/JunctionContext'
import { clamp } from '../utils/helpers'

export default function TimingControl() {
  const { selected } = useJunctions()

  const [minGreen,   setMinGreen]   = useState(10)
  const [maxGreen,   setMaxGreen]   = useState(90)
  const [yellowTime, setYellowTime] = useState(3)
  const [saving,     setSaving]     = useState(false)
  const [saved,      setSaved]      = useState(false)

  const save = async () => {
    if (!selected) return
    setSaving(true)
    try {
      await updateTimingConfig(selected, {
        junction_id: selected,
        min_green:   minGreen,
        max_green:   maxGreen,
        yellow_time: yellowTime,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const Row = ({ label, value, set, min, max, unit }) => (
    <div>
      <div className="flex justify-between mb-1">
        <label className="text-xs text-gray-400">{label}</label>
        <span className="text-xs font-mono text-white">{value}{unit}</span>
      </div>
      <input
        type="range" min={min} max={max} step={1} value={value}
        onChange={e => set(clamp(Number(e.target.value), min, max))}
        className="w-full accent-accent h-1.5 rounded cursor-pointer"
      />
      <div className="flex justify-between mt-0.5">
        <span className="text-xs text-gray-600">{min}{unit}</span>
        <span className="text-xs text-gray-600">{max}{unit}</span>
      </div>
    </div>
  )

  return (
    <div className="card space-y-4">
      <h2 className="text-sm font-semibold text-white">Timing Config</h2>

      <Row label="Min green time" value={minGreen}   set={setMinGreen}   min={5}  max={30}  unit="s" />
      <Row label="Max green time" value={maxGreen}   set={setMaxGreen}   min={30} max={180} unit="s" />
      <Row label="Yellow time"    value={yellowTime} set={setYellowTime} min={2}  max={6}   unit="s" />

      <button
        onClick={save}
        disabled={saving || !selected}
        className="btn-primary w-full justify-center disabled:opacity-40"
      >
        {saving ? 'Saving…' : saved ? '✓ Saved' : 'Apply timing'}
      </button>
    </div>
  )
}
