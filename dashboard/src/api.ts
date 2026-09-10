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

// ---- admin key (stored locally; used for admin-scoped reads) ----
const ADMIN_KEY = 'eos_admin_key'
export const getAdminKey = () => localStorage.getItem(ADMIN_KEY) ?? ''
export const setAdminKey = (k: string) => localStorage.setItem(ADMIN_KEY, k)

async function get<T>(path: string, admin = false): Promise<T> {
  const headers: Record<string, string> = {}
  if (admin) headers.Authorization = `Bearer ${getAdminKey()}`
  const res = await fetch(path, { headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = (err as { detail?: unknown }).detail
    throw new Error(
      typeof detail === 'string' ? detail : `Request failed (HTTP ${res.status})`,
    )
  }
  return res.json() as Promise<T>
}

// ---- experiments list ----
export interface ExperimentSummary {
  id: string
  key: string
  status: string
  planned_sample_size: number
  started_at: string | null
  variants: number
}

export function listExperiments(): Promise<ExperimentSummary[]> {
  return get<ExperimentSummary[]>('/v1/experiments', true)
}

// ---- results ----
export interface VariantResult {
  key: string
  n: number
  conversions: number
  rate: number | null
}

export interface Comparison {
  variant: string
  vs: string
  control_rate: number
  treatment_rate: number
  absolute_lift: number
  relative_lift: number
  ci_low: number
  ci_high: number
  p_value: number
  significant: boolean
}

export interface ResultsResponse {
  experiment: { key: string; status: string; planned_sample_size: number }
  metric: string | null
  total_exposed: number
  reached_planned_sample_size: boolean
  peeking_warning: boolean
  srm: { chi2: number; p_value: number; flagged: boolean; observed: Record<string, number> }
  variants: VariantResult[]
  comparisons: Comparison[]
  verdict: string
}

export function getResults(id: string, metric?: string): Promise<ResultsResponse> {
  const q = metric ? `?metric=${encodeURIComponent(metric)}` : ''
  return get<ResultsResponse>(`/v1/experiments/${id}/results${q}`)
}
