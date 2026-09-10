import { useState } from 'react'
import { calcSampleSize, type SampleSizeResult } from '../api'

export function Calculator() {
  const [baseline, setBaseline] = useState('20')
  const [mde, setMde] = useState('5')
  const [mdeType, setMdeType] = useState<'absolute' | 'relative'>('absolute')
  const [alpha, setAlpha] = useState('0.05')
  const [power, setPower] = useState('0.8')
  const [dailyTraffic, setDailyTraffic] = useState('500')

  const [result, setResult] = useState<SampleSizeResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      // UI uses friendly units: baseline & relative MDE as %, absolute MDE as
      // percentage points. The API takes fractions.
      const res = await calcSampleSize({
        baseline_rate: Number(baseline) / 100,
        mde: Number(mde) / 100,
        alpha: Number(alpha),
        power: Number(power),
        mde_type: mdeType,
      })
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const days =
    result && Number(dailyTraffic) > 0
      ? result.total_n / Number(dailyTraffic)
      : null

  return (
    <section className="page">
      <header className="page-head">
        <h1>Plan an experiment</h1>
        <p className="muted">
          Work out how many users you need <em>before</em> you start — so you
          never have to guess, and never peek early.
        </p>
      </header>

      <div className="grid-2">
        <form className="card" onSubmit={onSubmit}>
          <h2>Inputs</h2>

          <label>
            Baseline conversion rate
            <div className="input-unit">
              <input
                type="number" step="any" min="0" max="100" required
                value={baseline} onChange={(e) => setBaseline(e.target.value)}
              />
              <span>%</span>
            </div>
          </label>

          <label>
            Minimum detectable effect
            <div className="input-unit">
              <input
                type="number" step="any" min="0" required
                value={mde} onChange={(e) => setMde(e.target.value)}
              />
              <span>{mdeType === 'absolute' ? 'pp' : '%'}</span>
            </div>
          </label>

          <div className="toggle" role="radiogroup" aria-label="MDE type">
            <button
              type="button"
              className={mdeType === 'absolute' ? 'active' : ''}
              onClick={() => setMdeType('absolute')}
            >
              Absolute (pp)
            </button>
            <button
              type="button"
              className={mdeType === 'relative' ? 'active' : ''}
              onClick={() => setMdeType('relative')}
            >
              Relative (%)
            </button>
          </div>

          <div className="row">
            <label>
              Significance (α)
              <input
                type="number" step="any" min="0" max="1" required
                value={alpha} onChange={(e) => setAlpha(e.target.value)}
              />
            </label>
            <label>
              Power
              <input
                type="number" step="any" min="0" max="1" required
                value={power} onChange={(e) => setPower(e.target.value)}
              />
            </label>
          </div>

          <label>
            Daily eligible traffic
            <input
              type="number" step="any" min="0"
              value={dailyTraffic} onChange={(e) => setDailyTraffic(e.target.value)}
            />
          </label>

          <button className="primary" type="submit" disabled={loading}>
            {loading ? 'Calculating…' : 'Calculate sample size'}
          </button>

          {error && <p className="error" role="alert">{error}</p>}
        </form>

        <div className="card result" aria-live="polite">
          <h2>Required sample size</h2>
          {result ? (
            <>
              <div className="big-number">
                {result.per_variant_n.toLocaleString()}
                <span> per variant</span>
              </div>
              <dl>
                <div><dt>Total users</dt><dd>{result.total_n.toLocaleString()}</dd></div>
                <div>
                  <dt>Detecting</dt>
                  <dd>
                    {(result.baseline_rate * 100).toFixed(2)}% →{' '}
                    {(result.target_rate * 100).toFixed(2)}%
                  </dd>
                </div>
                <div>
                  <dt>Relative effect</dt>
                  <dd>{(result.relative_mde * 100).toFixed(1)}%</dd>
                </div>
                {days !== null && (
                  <div>
                    <dt>Estimated duration</dt>
                    <dd>{days.toFixed(1)} days</dd>
                  </div>
                )}
              </dl>
              <p className="muted small">
                At α={result.alpha} and {(result.power * 100).toFixed(0)}% power.
              </p>
            </>
          ) : (
            <p className="muted">Enter your inputs and calculate to see the plan.</p>
          )}
        </div>
      </div>
    </section>
  )
}
