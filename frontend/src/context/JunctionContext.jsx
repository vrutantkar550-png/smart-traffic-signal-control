import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { getJunctions } from '../utils/api'

const JunctionContext = createContext(null)

export function JunctionProvider({ children }) {
  const [junctions, setJunctions]     = useState([])
  const [selected,  setSelected]      = useState(null)  // active junction id
  const [loading,   setLoading]       = useState(true)
  const [error,     setError]         = useState(null)

  const fetchJunctions = useCallback(async () => {
    try {
      setLoading(true)
      const { data } = await getJunctions()
      setJunctions(data)
      // Auto-select first junction if none selected
      if (!selected && data.length > 0) setSelected(data[0].id)
    } catch (e) {
      setError('Could not load junctions from server.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchJunctions() }, [fetchJunctions])

  return (
    <JunctionContext.Provider value={{
      junctions, selected, setSelected,
      loading, error, refetch: fetchJunctions,
    }}>
      {children}
    </JunctionContext.Provider>
  )
}

export const useJunctions = () => useContext(JunctionContext)
