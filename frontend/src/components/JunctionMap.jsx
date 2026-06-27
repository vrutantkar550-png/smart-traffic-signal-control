import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import { useJunctions } from '../context/JunctionContext'
import { useSignalState } from '../context/WebSocketContext'
import L from 'leaflet'
import { useEffect } from 'react'

// Custom coloured marker based on emergency/phase state
const makeIcon = (color) =>
  L.divIcon({
    className: '',
    html: `<div style="
      width:14px;height:14px;border-radius:50%;
      background:${color};
      border:2px solid white;
      box-shadow:0 0 8px ${color}88;
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })

const ICONS = {
  emergency: makeIcon('#EF4444'),
  normal:    makeIcon('#22C55E'),
  offline:   makeIcon('#6B7280'),
}

function FlyToSelected() {
  const map = useMap()
  const { junctions, selected } = useJunctions()
  useEffect(() => {
    const j = junctions.find(j => j.id === selected)
    if (j) map.flyTo([j.latitude, j.longitude], 15, { duration: 1 })
  }, [selected, junctions])
  return null
}

export default function JunctionMap() {
  const { junctions, selected, setSelected } = useJunctions()
  const { signalState } = useSignalState()

  const defaultCenter = junctions.length > 0
    ? [junctions[0].latitude, junctions[0].longitude]
    : [19.9975, 73.7898]

  return (
    <MapContainer
      center={defaultCenter}
      zoom={13}
      className="w-full h-full rounded-xl overflow-hidden"
      zoomControl={false}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='© OpenStreetMap'
        className="map-tiles-dark"
      />

      <FlyToSelected />

      {junctions.map(j => {
        const isSelected   = j.id === selected
        const hasEmergency = signalState?.emergency_active && j.id === selected

        return (
          <Marker
            key={j.id}
            position={[j.latitude, j.longitude]}
            icon={hasEmergency ? ICONS.emergency : ICONS.normal}
            eventHandlers={{ click: () => setSelected(j.id) }}
          >
            <Popup className="dark-popup">
              <div className="bg-surface-card border border-surface-border rounded-lg p-3 min-w-[160px]">
                <p className="font-semibold text-sm text-white">{j.name}</p>
                <p className="text-xs text-gray-400 mt-1">{j.junction_type} junction</p>
                {hasEmergency && (
                  <p className="text-xs text-red-400 mt-1 font-medium">⚠ Emergency active</p>
                )}
              </div>
            </Popup>
          </Marker>
        )
      })}
    </MapContainer>
  )
}
