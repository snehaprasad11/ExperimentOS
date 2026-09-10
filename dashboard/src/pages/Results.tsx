import { useEffect, useState } from 'react'
import { getResults, type ResultsResponse } from '../api'

const pct = (x: number) => `${(x * 100).toFixed(2)}%`
const signedPct = (x: number) => `${x >= 0 ? '+' : ''}${(x * 100).toFixed(2)}%`

export function Results({ initialId }: { initialId: string | null }) {
  const [id, setId] = useState(initialId ?? '')
  const [metric, setMetric] = useState('')
  const [data, setData] = useState<ResultsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function load(e?: React.FormEvent) {
    e?.preventDefault()
    if (!id.trim()) return
    setLoading(true)
    setError(null)
    try {
      setData(await getResults(id.trim(), metric.trim() || undefined))
    } catch (er) {
      setError(er instanceof Error ? er.message : 'Failed to load results')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (initialId) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialId])

  return (
    <section className="page">
      <header className="page-head">
        <h1>Results</h1>
        <p className="muted">
          Lift with confidence intervals and a p-value — plus the validity
          checks that tell you whether to trust them.
        </p>
      </header>

      <form className="connect-bar" onSubmit={load}>
        <input
          type="text" placeholder="Experiment ID"
          value={id} onChange={(e) => setId(e.target.value)}
          style={{ flex: 2 }}
        />
        <input
          type="text" placeholder="Metric key (e.g. retention_7)"
          value={metric} onChange={(e) => setMetric(e.target.value)}
          style={{ flex: 1 }}
        />
        <button className="primary" type="submit">Load</button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}
      {loading && <p className="muted">Loading…</p>}

      {data && (
        <div className="results" aria-live="polite">
          <div className="results-head">
            <h2 className="mono">{data.experiment.key}</h2>
            <span className={`status status-${data.experiment.status}`}>
              {data.experiment.status}
            </span>
          </div>

          {/* Verdict / peeking lock */}
          {!data.reached_planned_sample_size ? (
            <div className="banner banner-lock">
              <strong>Not conclusive yet.</strong> {data.total_exposed.toLocaleString()} of{' '}
              {data.experiment.planned_sample_size.toLocaleString()} planned users exposed.
              The verdict stays locked until the plan is reached — no peeking.
            </div>
          ) : (
            <div className={`banner banner-${data.verdict === 'significant' ? 'good' : 'neutral'}`}>
              <strong>
                {data.verdict === 'significant'
                  ? 'Significant result.'
                  : 'No significant difference.'}
              </strong>{' '}
              Planned sample size reached ({data.total_exposed.toLocaleString()} exposed).
            </div>
          )}

          {/* SRM validity check */}
          <div className={`banner ${data.srm.flagged ? 'banner-bad' : 'banner-subtle'}`}>
            {data.srm.flagged ? (
              <><strong>⚠ Sample Ratio Mismatch.</strong> Observed split is implausible
                for the configured allocation (χ²={data.srm.chi2.toFixed(2)},
                p={data.srm.p_value.toFixed(4)}). Results are not trustworthy.</>
            ) : (
              <><strong>✓ SRM check passed.</strong> Split looks right
                (χ²={data.srm.chi2.toFixed(2)}, p={data.srm.p_value.toFixed(4)}).</>
            )}
          </div>

          {/* Per-variant exposure + conversion */}
          <div className="card table-card">
            <table>
              <thead>
                <tr><th>Variant</th><th>Exposed</th><th>Conversions</th><th>Rate</th></tr>
              </thead>
              <tbody>
                {data.variants.map((v) => (
                  <tr key={v.key}>
                    <td className="mono">{v.key}</td>
                    <td>{v.n.toLocaleString()}</td>
                    <td>{v.conversions.toLocaleString()}</td>
                    <td>{v.rate === null ? '—' : pct(v.rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Comparisons */}
          {data.comparisons.length === 0 ? (
            <p className="muted small">
              {data.metric
                ? 'No comparison available yet.'
                : 'Provide a metric key above to compute lift.'}
            </p>
          ) : (
            data.comparisons.map((c) => (
              <div className="card comparison" key={c.variant}>
                <div className="comparison-head">
                  <span className="mono">{c.variant}</span> vs{' '}
                  <span className="mono">{c.vs}</span>
                  {/* colour-blind-safe: icon + word + colour, never colour alone */}
                  <span className={`badge ${c.significant ? 'badge-sig' : 'badge-nsig'}`}>
                    {c.significant ? '▲ significant' : '● not significant'}
                  </span>
                </div>
                <div className="comparison-grid">
                  <div><span className="muted">Absolute lift</span><b>{signedPct(c.absolute_lift)}</b></div>
                  <div><span className="muted">Relative lift</span><b>{signedPct(c.relative_lift)}</b></div>
                  <div><span className="muted">95% CI</span><b>[{signedPct(c.ci_low)}, {signedPct(c.ci_high)}]</b></div>
                  <div><span className="muted">p-value</span><b>{c.p_value.toFixed(4)}</b></div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </section>
  )
}
