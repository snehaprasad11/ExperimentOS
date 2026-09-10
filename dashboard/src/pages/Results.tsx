import { useEffect, useState } from 'react'
import {
  Bar, BarChart, Cell, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { getResults, type Comparison, type ResultsResponse } from '../api'

const pct = (x: number) => `${(x * 100).toFixed(2)}%`
const signedPct = (x: number) => `${x >= 0 ? '+' : ''}${(x * 100).toFixed(2)}%`

// normal-approx 95% CI half-width on a proportion, in percentage points
function rateCiPct(conversions: number, n: number): number {
  if (n <= 0) return 0
  const p = conversions / n
  return 1.96 * Math.sqrt((p * (1 - p)) / n) * 100
}

function ChartTip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="chart-tip">
      <b>{d.variant}</b><br />
      {d.ratePct.toFixed(2)}% ± {d.ciPct.toFixed(2)}pp
    </div>
  )
}

function LiftInterval({ c }: { c: Comparison }) {
  const vals = [c.ci_low, c.ci_high, 0, c.absolute_lift]
  const min = Math.min(...vals), max = Math.max(...vals)
  const pad = (max - min) * 0.2 || 0.01
  const lo = min - pad, hi = max + pad
  const pos = (x: number) => ((x - lo) / (hi - lo)) * 100
  const color = c.significant ? 'var(--good)' : 'var(--muted)'
  return (
    <div className="ci-viz">
      <div className="ci-track">
        <div className="ci-zero" style={{ left: `${pos(0)}%` }} />
        <div className="ci-bar" style={{
          left: `${pos(c.ci_low)}%`, width: `${pos(c.ci_high) - pos(c.ci_low)}%`,
          background: color, opacity: 0.35,
        }} />
        <div className="ci-point" style={{ left: `${pos(c.absolute_lift)}%`, background: color }} />
      </div>
      <div className="ci-labels">
        <span>{signedPct(c.ci_low)}</span>
        <span>0 (no effect)</span>
        <span>{signedPct(c.ci_high)}</span>
      </div>
    </div>
  )
}

export function Results({ initialId }: { initialId: string | null }) {
  const [id, setId] = useState(initialId ?? '')
  const [metric, setMetric] = useState('')
  const [data, setData] = useState<ResultsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function load(e?: React.FormEvent) {
    e?.preventDefault()
    if (!id.trim()) return
    setLoading(true); setError(null)
    try {
      setData(await getResults(id.trim(), metric.trim() || undefined))
    } catch (er) {
      setError(er instanceof Error ? er.message : 'Failed to load results')
      setData(null)
    } finally { setLoading(false) }
  }

  useEffect(() => {
    if (initialId) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialId])

  const sigByVariant: Record<string, boolean> = {}
  data?.comparisons.forEach((c) => { sigByVariant[c.variant] = c.significant })

  const chartData = (data?.variants ?? [])
    .filter((v) => v.rate !== null)
    .map((v) => ({
      variant: v.key,
      ratePct: (v.rate ?? 0) * 100,
      ciPct: rateCiPct(v.conversions, v.n),
    }))
  // explicit, sensible y-axis max so bars fill the chart (recharts auto-domain misbehaves)
  const yMax = chartData.length
    ? Math.max(5, Math.ceil((Math.max(...chartData.map((d) => d.ratePct + d.ciPct)) * 1.25) / 5) * 5)
    : 10

  return (
    <section className="page">
      <header className="page-head">
        <h1>Results</h1>
        <p>
          Lift with confidence intervals and a p-value — plus the validity
          checks that tell you whether to trust them.
        </p>
      </header>

      <form className="connect-bar" onSubmit={load}>
        <input type="text" placeholder="Experiment ID" value={id}
               onChange={(e) => setId(e.target.value)} style={{ flex: 2 }} />
        <input type="text" placeholder="Metric key (e.g. retention_7)" value={metric}
               onChange={(e) => setMetric(e.target.value)} style={{ flex: 1 }} />
        <button className="primary auto" type="submit">Load</button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}
      {loading && <p className="muted">Loading…</p>}

      {data && (
        <div className="results" aria-live="polite">
          <div className="results-head">
            <h2 className="mono">{data.experiment.key}</h2>
            <span className={`status status-${data.experiment.status}`}>{data.experiment.status}</span>
          </div>

          {!data.reached_planned_sample_size ? (
            <div className="banner banner-lock">
              <strong>Not conclusive yet.</strong> {data.total_exposed.toLocaleString()} of{' '}
              {data.experiment.planned_sample_size.toLocaleString()} planned users exposed.
              The verdict stays locked until the plan is reached — no peeking.
            </div>
          ) : (
            <div className={`banner banner-${data.verdict === 'significant' ? 'good' : 'neutral'}`}>
              <strong>{data.verdict === 'significant' ? 'Significant result.' : 'No significant difference.'}</strong>{' '}
              Planned sample size reached ({data.total_exposed.toLocaleString()} exposed).
            </div>
          )}

          <div className={`banner ${data.srm.flagged ? 'banner-bad' : 'banner-subtle'}`}>
            {data.srm.flagged ? (
              <><strong>⚠ Sample Ratio Mismatch.</strong> Observed split is implausible for the
                configured allocation (χ²={data.srm.chi2.toFixed(2)}, p={data.srm.p_value.toFixed(4)}).
                Results are not trustworthy.</>
            ) : (
              <><strong>✓ SRM check passed.</strong> Split looks right
                (χ²={data.srm.chi2.toFixed(2)}, p={data.srm.p_value.toFixed(4)}).</>
            )}
          </div>

          {chartData.length > 0 && (
            <div className="card chart-card">
              <h3>Conversion rate by variant <span className="muted small">(95% CI)</span></h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={chartData} margin={{ top: 16, right: 12, left: 0, bottom: 4 }}>
                  <XAxis dataKey="variant" tickLine={false} axisLine={false} />
                  <YAxis domain={[0, yMax]} tickFormatter={(v) => `${v}%`}
                    ticks={Array.from({ length: yMax / 5 + 1 }, (_, i) => i * 5)}
                    tickLine={false} axisLine={false} width={44} />
                  <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(107,77,255,0.06)' }} />
                  <Bar dataKey="ratePct" radius={[6, 6, 0, 0]} maxBarSize={90}>
                    {chartData.map((d) => (
                      <Cell key={d.variant}
                        fill={sigByVariant[d.variant] ? 'var(--good)' : 'var(--accent)'} />
                    ))}
                    <ErrorBar dataKey="ciPct" width={5} strokeWidth={2}
                      stroke="var(--text-h)" direction="y" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="card table-card">
            <table>
              <thead><tr><th>Variant</th><th>Exposed</th><th>Conversions</th><th>Rate</th></tr></thead>
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

          {data.comparisons.length === 0 ? (
            <p className="muted small">
              {data.metric ? 'No comparison available yet.' : 'Provide a metric key above to compute lift.'}
            </p>
          ) : (
            data.comparisons.map((c) => (
              <div className="card comparison" key={c.variant}>
                <div className="comparison-head">
                  <span className="mono">{c.variant}</span> vs <span className="mono">{c.vs}</span>
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
                <LiftInterval c={c} />
              </div>
            ))
          )}
        </div>
      )}
    </section>
  )
}
