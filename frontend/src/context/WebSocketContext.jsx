import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react'
import { useJunctions } from './JunctionContext'

const WebSocketContext = createContext(null)

const WS_BASE = `ws://${window.location.host}/ws/junction`

export function WebSocketProvider({ children }) {
  const { selected } = useJunctions()
  const [signalState, setSignalState]   = useState(null)
  const [connected,   setConnected]     = useState(false)
  const wsRef = useRef(null)

  const connect = useCallback((junctionId) => {
    if (wsRef.current) wsRef.current.close()

    const ws = new WebSocket(`${WS_BASE}/${junctionId}`)
    wsRef.current = ws

    ws.onopen  = () => setConnected(true)
    ws.onclose = () => { setConnected(false); setSignalState(null) }
    ws.onerror = () => setConnected(false)

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (!data.error) setSignalState(data)
      } catch {}
    }

    return ws
  }, [])

  useEffect(() => {
    if (!selected) return
    const ws = connect(selected)
    return () => ws.close()
  }, [selected, connect])

  return (
    <WebSocketContext.Provider value={{ signalState, connected }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export const useSignalState = () => useContext(WebSocketContext)
