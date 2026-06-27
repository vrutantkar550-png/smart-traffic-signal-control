import { useState, useEffect, useCallback } from 'react'

/**
 * Generic data-fetching hook.
 * Usage: const { data, loading, error, refetch } = useFetch(fetchFn, deps)
 */
export function useFetch(fetchFn, deps = []) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const run = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await fetchFn()
      setData(res.data)
    } catch (e) {
      setError(e?.response?.data?.detail ?? e.message ?? 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, deps)

  useEffect(() => { run() }, [run])

  return { data, loading, error, refetch: run }
}

/**
 * Polling hook — re-fetches every `interval` ms.
 */
export function usePoll(fetchFn, interval = 5000, deps = []) {
  const result = useFetch(fetchFn, deps)

  useEffect(() => {
    const id = setInterval(result.refetch, interval)
    return () => clearInterval(id)
  }, [result.refetch, interval])

  return result
}
