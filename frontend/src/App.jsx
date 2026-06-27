import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { JunctionProvider } from './context/JunctionContext'
import { WebSocketProvider } from './context/WebSocketContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import JunctionConfig from './pages/JunctionConfig'
import Analytics from './pages/Analytics'
import EmergencyLog from './pages/EmergencyLog'

export default function App() {
  return (
    <BrowserRouter>
      <JunctionProvider>
        <WebSocketProvider>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard"       element={<Dashboard />} />
              <Route path="junctions"       element={<JunctionConfig />} />
              <Route path="analytics"       element={<Analytics />} />
              <Route path="emergency-log"   element={<EmergencyLog />} />
            </Route>
          </Routes>
        </WebSocketProvider>
      </JunctionProvider>
    </BrowserRouter>
  )
}
