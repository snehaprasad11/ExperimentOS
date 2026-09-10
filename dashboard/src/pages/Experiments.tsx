import { useEffect, useState } from 'react'
import {
  getAdminKey,
  listExperiments,
  setAdminKey,
  type ExperimentSummary,
} from '../api'

export function Experiments({ onOpenResults }: { onOpenResults: (id: string) => void }) {
  const [key, setKey] = useState(getAdminKey())
  const [experiments, setExperiments] = useState<ExperimentSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setExperiments(await listExperiments())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load experiments')
      setExperiments(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (getAdminKey()) load()
  }, [])

  function connect(e: React.FormEvent) {
    e.preventDefault()
    setAdminKey(key.trim())
    load()
  }

  return (
    <section className="page">
      <header className="page-head">
        <h1>Experiments</h1>
        <p className="muted">
          Connect a project with its admin key to list its experiments.
          The key is stored only in your browser.
        </p>
      </header>

      <form className="connect-bar" onSubmit={connect}>
        <input
          type="password"
          placeholder="Project admin key (ak_…)"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
        <button className="primary" type="submit">Connect</button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}
      {loading && <p className="muted">Loading…</p>}

      {experiments &&
        (experiments.length === 0 ? (
          <p className="muted">No experiments in this project yet.</p>
        ) : (
          <div className="card table-card">
            <table>
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Status</th>
                  <th>Variants</th>
                  <th>Planned N</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {experiments.map((x) => (
                  <tr key={x.id}>
                    <td className="mono">{x.key}</td>
                    <td>
                      <span className={`status status-${x.status}`}>{x.status}</span>
                    </td>
                    <td>{x.variants}</td>
                    <td>{x.planned_sample_size.toLocaleString()}</td>
                    <td>
                      <button className="link" onClick={() => onOpenResults(x.id)}>
                        View results →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </section>
  )
}
