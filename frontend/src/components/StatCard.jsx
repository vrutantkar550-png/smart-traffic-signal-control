export default function StatCard({ label, value, unit, sub, accent = false }) {
  return (
    <div className={`card ${accent ? 'border-accent/30 bg-accent/5' : ''}`}>
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <div className="flex items-baseline gap-1">
        <span className={`text-2xl font-mono font-semibold
          ${accent ? 'text-accent' : 'text-white'}`}>
          {value ?? '--'}
        </span>
        {unit && <span className="text-xs text-gray-500">{unit}</span>}
      </div>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}
