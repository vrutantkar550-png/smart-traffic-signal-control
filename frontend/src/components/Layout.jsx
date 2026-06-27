import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useSignalState } from '../context/WebSocketContext'
import { useJunctions } from '../context/JunctionContext'

const navItems = [
  { to: '/dashboard',     icon: '⬡', label: 'Dashboard'     },
  { to: '/junctions',     icon: '⊕', label: 'Junctions'     },
  { to: '/analytics',     icon: '◈', label: 'Analytics'     },
  { to: '/emergency-log', icon: '⚑', label: 'Emergency Log' },
]

export default function Layout() {
  const { connected }         = useSignalState()
  const { junctions, selected, setSelected } = useJunctions()

  return (
    <div className="flex h-screen overflow-hidden bg-surface">

      {/* ── Sidebar ── */}
      <aside className="w-56 flex-shrink-0 bg-surface-card border-r border-surface-border flex flex-col">
        {/* Logo */}
        <div className="px-5 py-4 border-b border-surface-border">
          <div className="flex items-center gap-2">
            <span className="text-signal-green text-2xl">▶</span>
            <div>
              <p className="font-semibold text-sm leading-tight">Smart Traffic</p>
              <p className="text-xs text-gray-500 leading-tight">Control System</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 flex flex-col gap-1">
          {navItems.map(({ to, icon, label }) => (
            <NavLink
              key={to} to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all
                 ${isActive
                   ? 'bg-accent/15 text-accent font-medium'
                   : 'text-gray-400 hover:text-white hover:bg-surface-border/40'}`
              }
            >
              <span className="text-base w-5 text-center">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Junction selector */}
        <div className="px-3 pb-4 border-t border-surface-border pt-4">
          <p className="text-xs text-gray-500 mb-2 px-1 uppercase tracking-wider">Active junction</p>
          {junctions.length === 0 ? (
            <p className="text-xs text-gray-600 px-1">No junctions added yet</p>
          ) : (
            <select
              value={selected ?? ''}
              onChange={e => setSelected(Number(e.target.value))}
              className="w-full bg-surface border border-surface-border rounded-lg
                         text-sm text-white px-3 py-2 focus:outline-none focus:border-accent"
            >
              {junctions.map(j => (
                <option key={j.id} value={j.id}>{j.name}</option>
              ))}
            </select>
          )}
        </div>
      </aside>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Topbar */}
        <header className="h-14 bg-surface-card border-b border-surface-border
                           flex items-center justify-between px-6 flex-shrink-0">
          <h1 className="text-sm font-medium text-gray-300">
            Smart Traffic Signal Control
          </h1>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${connected ? 'bg-signal-green animate-pulse' : 'bg-signal-red'}`} />
              <span className="text-xs text-gray-400">
                {connected ? 'Live' : 'Disconnected'}
              </span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
