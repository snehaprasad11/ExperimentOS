import { useEffect, useState } from 'react'
import {
  createExperiment, createProject, getAdminKey, listExperiments, setAdminKey,
  updateStatus, type CreatedProject, type ExperimentSummary,
} from '../api'

type Modal = 'none' | 'project' | 'experiment'

export function Experiments({ onOpenResults }: { onOpenResults: (id: string) => void }) {
  const [connected, setConnected] = useState(!!getAdminKey())
  const [keyInput, setKeyInput] = useState(getAdminKey())
  const [experiments, setExperiments] = useState<ExperimentSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState<Modal>('none')
  const [createdProject, setCreatedProject] = useState<CreatedProject | null>(null)

  async function load() {
    setLoading(true); setError(null)
    try { setExperiments(await listExperiments()) }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed to load'); setExperiments(null) }
    finally { setLoading(false) }
  }

  useEffect(() => { if (getAdminKey()) load() }, [])

  function connect(e: React.FormEvent) {
    e.preventDefault()
    setAdminKey(keyInput.trim())
    setConnected(true)
    load()
  }

  function disconnect() {
    setAdminKey('')
    setConnected(false)
    setExperiments(null)
    setKeyInput('')
  }

  async function toggleStatus(x: ExperimentSummary) {
    const next = x.status === 'running' ? 'stopped' : 'running'
    try { await updateStatus(x.id, next); load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed to update status') }
  }

  // ---- not connected: connect or create ----
  if (!connected) {
    return (
      <section className="page">
        <header className="page-head">
          <h1>Experiments</h1>
          <p>Connect a project to manage its experiments, or spin up a new project to start from scratch.</p>
        </header>

        <div className="grid-2">
          <form className="card" onSubmit={connect}>
            <h2>Connect a project</h2>
            <label>Admin key
              <input type="password" placeholder="ak_…" value={keyInput}
                     onChange={(e) => setKeyInput(e.target.value)} />
            </label>
            <button className="primary" type="submit">Connect</button>
            <p className="muted small" style={{ marginTop: 12 }}>
              Stored only in your browser. Never sent anywhere but the API.
            </p>
          </form>

          <div className="card">
            <h2>New here?</h2>
            <p className="muted" style={{ marginBottom: 18 }}>
              Create a project to get your SDK key and admin key, then create your first experiment.
            </p>
            <button className="primary" onClick={() => { setCreatedProject(null); setModal('project') }}>
              Create a project
            </button>
          </div>
        </div>

        {modal === 'project' && (
          <ProjectModal
            created={createdProject}
            onCreated={(p) => { setCreatedProject(p); setAdminKey(p.admin_key) }}
            onClose={() => { setModal('none'); if (createdProject) { setConnected(true); load() } }}
          />
        )}
      </section>
    )
  }

  // ---- connected ----
  return (
    <section className="page">
      <header className="page-head">
        <h1>Experiments</h1>
        <p>Create, launch, and monitor experiments in your project.</p>
      </header>

      <div className="toolbar">
        <button className="primary auto" onClick={() => setModal('experiment')}>＋ New experiment</button>
        <button className="ghost" onClick={load}>Refresh</button>
        <div className="spacer" />
        <button className="link" onClick={disconnect}>Disconnect</button>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {loading && <p className="muted">Loading…</p>}

      {experiments && (experiments.length === 0 ? (
        <div className="card empty">
          <h3>No experiments yet</h3>
          <p>Create your first experiment to get started.</p>
          <button className="primary auto" style={{ marginTop: 16 }}
                  onClick={() => setModal('experiment')}>＋ New experiment</button>
        </div>
      ) : (
        <div className="card table-card">
          <table>
            <thead>
              <tr><th>Key</th><th>Status</th><th>Variants</th><th>Planned N</th><th></th></tr>
            </thead>
            <tbody>
              {experiments.map((x) => (
                <tr key={x.id}>
                  <td className="mono">{x.key}</td>
                  <td><span className={`status status-${x.status}`}>{x.status}</span></td>
                  <td>{x.variants}</td>
                  <td>{x.planned_sample_size.toLocaleString()}</td>
                  <td style={{ display: 'flex', gap: 14, justifyContent: 'flex-end' }}>
                    {(x.status === 'draft' || x.status === 'stopped') && (
                      <button className="link" onClick={() => toggleStatus(x)}>Start</button>
                    )}
                    {x.status === 'running' && (
                      <button className="link" onClick={() => toggleStatus(x)}>Stop</button>
                    )}
                    <button className="link" onClick={() => onOpenResults(x.id)}>Results →</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {modal === 'experiment' && (
        <ExperimentModal onClose={() => setModal('none')} onCreated={() => { setModal('none'); load() }} />
      )}
    </section>
  )
}

// ---------- Create-project modal ----------
function ProjectModal({ created, onCreated, onClose }:
  { created: CreatedProject | null; onCreated: (p: CreatedProject) => void; onClose: () => void }) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try { onCreated(await createProject(name.trim() || 'My Project')) }
    catch (er) { setError(er instanceof Error ? er.message : 'Failed') }
    finally { setBusy(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{created ? 'Project created 🎉' : 'Create a project'}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        {!created ? (
          <form onSubmit={submit}>
            <label>Project name
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Pricing experiments" autoFocus />
            </label>
            {error && <p className="error">{error}</p>}
            <button className="primary" type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create project'}</button>
          </form>
        ) : (
          <>
            <p className="muted small">Save your <strong>admin key</strong> now — it is shown only once.
              You're already connected with it.</p>
            <div className="key-box"><div className="k">SDK key (public)</div><div className="v">{created.sdk_key}</div></div>
            <div className="key-box"><div className="k">Admin key (secret)</div><div className="v">{created.admin_key}</div></div>
            <button className="primary" style={{ marginTop: 18 }} onClick={onClose}>Done — show my experiments</button>
          </>
        )}
      </div>
    </div>
  )
}

// ---------- Create-experiment modal ----------
function ExperimentModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [key, setKey] = useState('')
  const [hypothesis, setHypothesis] = useState('')
  const [planned, setPlanned] = useState('2188')
  const [ctrl, setCtrl] = useState('control')
  const [ctrlAlloc, setCtrlAlloc] = useState('50')
  const [treat, setTreat] = useState('treatment')
  const [treatAlloc, setTreatAlloc] = useState('50')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await createExperiment({
        key: key.trim(), hypothesis: hypothesis.trim(),
        planned_sample_size: Number(planned),
        variants: [
          { key: ctrl.trim(), allocation_pct: Number(ctrlAlloc), is_control: true },
          { key: treat.trim(), allocation_pct: Number(treatAlloc), is_control: false },
        ],
      })
      onCreated()
    } catch (er) { setError(er instanceof Error ? er.message : 'Failed') }
    finally { setBusy(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>New experiment</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={submit}>
          <label>Experiment key
            <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="pricing_page_v2" autoFocus required />
          </label>
          <label>Hypothesis
            <input value={hypothesis} onChange={(e) => setHypothesis(e.target.value)}
                   placeholder="A cleaner pricing page lifts checkout conversion" required />
          </label>
          <label>Planned sample size (total)
            <input type="number" value={planned} onChange={(e) => setPlanned(e.target.value)} min="1" required />
          </label>

          <h3 style={{ marginTop: 8 }}>Variants</h3>
          <div className="variant-row">
            <label>Control key<input value={ctrl} onChange={(e) => setCtrl(e.target.value)} required /></label>
            <label>Alloc %<input type="number" value={ctrlAlloc} onChange={(e) => setCtrlAlloc(e.target.value)} /></label>
          </div>
          <div className="variant-row">
            <label>Treatment key<input value={treat} onChange={(e) => setTreat(e.target.value)} required /></label>
            <label>Alloc %<input type="number" value={treatAlloc} onChange={(e) => setTreatAlloc(e.target.value)} /></label>
          </div>
          <p className="muted small">Allocations must sum to 100.</p>

          {error && <p className="error">{error}</p>}
          <button className="primary" type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create experiment'}</button>
        </form>
      </div>
    </div>
  )
}
