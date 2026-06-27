import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Junctions ─────────────────────────────────────────────────────────────────
export const getJunctions        = ()         => api.get('/junctions/')
export const getJunction         = (id)       => api.get(`/junctions/${id}`)
export const createJunction      = (data)     => api.post('/junctions/', data)
export const deleteJunction      = (id)       => api.delete(`/junctions/${id}`)

// ── Signals ───────────────────────────────────────────────────────────────────
export const getSignalState      = (id)       => api.get(`/signals/${id}/state`)
export const updateTimingConfig  = (id, data) => api.put(`/signals/${id}/timing`, data)

// ── Emergency ─────────────────────────────────────────────────────────────────
export const triggerEmergency    = (id, data) => api.post(`/emergency/${id}/trigger`, data)
export const clearEmergency      = (id)       => api.post(`/emergency/${id}/clear`)
export const getEmergencyHistory = (id, limit=50) => api.get(`/emergency/${id}/history?limit=${limit}`)
export const getAllActiveEmergencies = ()     => api.get('/emergency/active/all')

// ── Analytics ─────────────────────────────────────────────────────────────────
export const getAnalyticsSummary = (id, period='today') => api.get(`/analytics/${id}/summary?period=${period}`)
export const getWaitTimeSeries   = (id, hours=24)       => api.get(`/analytics/${id}/wait-time-series?hours=${hours}`)

export default api
