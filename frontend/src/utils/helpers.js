import { format, formatDistanceToNow } from 'date-fns'

export const formatTime = (iso) =>
  iso ? format(new Date(iso), 'HH:mm:ss') : '--'

export const formatDate = (iso) =>
  iso ? format(new Date(iso), 'dd MMM yyyy, HH:mm') : '--'

export const timeAgo = (iso) =>
  iso ? formatDistanceToNow(new Date(iso), { addSuffix: true }) : '--'

export const phaseColor = (phase) => ({
  GREEN:  'text-signal-green',
  YELLOW: 'text-signal-yellow',
  RED:    'text-signal-red',
}[phase] ?? 'text-gray-400')

export const phaseBg = (phase) => ({
  GREEN:  'bg-signal-green signal-green',
  YELLOW: 'bg-signal-yellow signal-yellow',
  RED:    'bg-signal-red signal-red',
}[phase] ?? 'bg-gray-600')

export const emergencyLabel = {
  ambulance:    { label: 'Ambulance',    color: 'badge-red'    },
  fire_truck:   { label: 'Fire Truck',   color: 'badge-red'    },
  accident:     { label: 'Accident',     color: 'badge-yellow' },
  construction: { label: 'Construction', color: 'badge-yellow' },
}

export const junctionTypeLabel = {
  '2way': '2-Way',
  '3way': '3-Way',
  '4way': '4-Way',
}

export const clamp = (v, min, max) => Math.max(min, Math.min(max, v))
