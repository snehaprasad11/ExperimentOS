// Typed client for the ExperimentOS API. In dev, requests to /v1/... are
// proxied to the FastAPI backend (see vite.config.ts).

export interface SampleSizeResult {
  baseline_rate: number
  target_rate: number
  absolute_mde: number
  relative_mde: number
  alpha: number
  power: number
  per_variant_n: number
  total_n: number
}

export interface SampleSizeRequest {
  baseline_rate: number
  mde: number
  alpha: number
  power: number
  mde_type: 'absolute' | 'relative'
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = (err as { detail?: unknown }).detail
    throw new Error(
      typeof detail === 'string' ? detail : `Request failed (HTTP ${res.status})`,
    )
  }
  return res.json() as Promise<T>
}

export function calcSampleSize(req: SampleSizeRequest): Promise<SampleSizeResult> {
  return post<SampleSizeResult>('/v1/calculator/sample-size', req)
}
