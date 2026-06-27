import { useState } from 'react'
import { createJunction, deleteJunction } from '../utils/api'
import { useJunctions } from '../context/JunctionContext'
import { junctionTypeLabel } from '../utils/helpers'

const EMPTY = { name: '', junction_type: '4way', latitude: '', longitude: '', lane_count: 4 }

export default function JunctionConfig() {
  const { junctions, refetch, setSelected } = useJunctions()
  const [form,    setForm]    = useState(EMPTY)
  const [saving,  setSaving]  = useState(false)
  const [error,   setError]   = useState(null)
  const [success, setSuccess] = useState(false)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const submit = async () => {
    if (!form.name || !form.latitude || !form.longitude) {
      setError('Name, latitude and longitude are required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const { data } = await createJunction({
        ...form,
        latitude:   parseFloat(form.latitude),
        longitude:  parseFloat(form.longitude),
        lane_count: Number(form.lane_count),
      })
      await refetch()
      setSelected(data.id)
      setForm(EMPTY)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 2500)
    } catch (e) {
      setError(e?.response?.data?.detail ?? 'Failed to create junction.')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('Delete this junction?')) return
    await deleteJunction(id)
    await refetch()
  }

  const Field = ({ label, k, type='text', ...rest }) => (
    <div>
      <label className="text-xs text-gray-400 block mb-1">{label}</label>
      <input
        type={type}
        value={form[k]}
        onChange={e => set(k, e.target.value)}
        className="w-full bg-surface border border-surface-border rounded-lg
                   text-sm text-white px-3 py-2 focus:outline-none focus:border-accent"
        {...rest}
      />
    </div>
  )

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-lg font-semibold text-white">Junction Configuration</h1>

      <div className="grid grid-cols-2 gap-6">

        {/* Add form */}
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-white">Add new junction</h2>

          <Field label="Junction name" k="name" placeholder="e.g. MG Road Crossroads" />

          <div>
            <label className="text-xs text-gray-400 block mb-1">Junction type</label>
            <select
              value={form.junction_type}
              onChange={e => set('junction_type', e.target.value)}
              className="w-full bg-surface border border-surface-border rounded-lg
                         text-sm text-white px-3 py-2 focus:outline-none focus:border-accent"
            >
              <option value="2way">2-Way (linear)</option>
              <option value="3way">3-Way (T / Y junction)</option>
              <option value="4way">4-Way (crossroads)</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Latitude"  k="latitude"  type="number" placeholder="19.9975" />
            <Field label="Longitude" k="longitude" type="number" placeholder="73.7898" />
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">
              Lane count <span className="text-gray-600">(2–8)</span>
            </label>
            <input
              type="number" min={2} max={8} value={form.lane_count}
              onChange={e => set('lane_count', Number(e.target.value))}
              className="w-full bg-surface border border-surface-border rounded-lg
                         text-sm text-white px-3 py-2 focus:outline-none focus:border-accent"
            />
          </div>

          {error   && <p className="text-xs text-red-400 bg-red-900/20 rounded-lg px-3 py-2">{error}</p>}
          {success && <p className="text-xs text-green-400 bg-green-900/20 rounded-lg px-3 py-2">Junction created successfully</p>}

          <button onClick={submit} disabled={saving} className="btn-primary w-full justify-center disabled:opacity-40">
            {saving ? 'Creating…' : '+ Add junction'}
          </button>
        </div>

        {/* Junction list */}
        <div className="card">
          <h2 className="text-sm font-semibold text-white mb-3">
            All junctions <span className="text-gray-500 font-normal">({junctions.length})</span>
          </h2>

          {junctions.length === 0 ? (
            <p className="text-xs text-gray-500 text-center py-8">No junctions yet. Add one to get started.</p>
          ) : (
            <div className="space-y-2">
              {junctions.map(j => (
                <div key={j.id}
                  className="flex items-center justify-between bg-surface rounded-lg px-3 py-2.5">
                  <div>
                    <p className="text-sm text-white font-medium">{j.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {junctionTypeLabel[j.junction_type]} · {j.lane_count} lanes ·
                      {j.latitude.toFixed(4)}, {j.longitude.toFixed(4)}
                    </p>
                  </div>
                  <button
                    onClick={() => remove(j.id)}
                    className="text-xs text-gray-500 hover:text-red-400 transition-colors ml-3"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
