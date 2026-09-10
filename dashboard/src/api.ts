// Typed client for the ExperimentOS API.
//
// In dev, VITE_API_BASE is unset, so requests go to relative /v1/... and Vite
// proxies them to the backend (see vite.config.ts). In production, set
// VITE_API_BASE to the deployed API origin.
const BASE = import.meta.env.VITE_API_BASE ?? ''

// ---- admin key (stored locally; used for admin-scoped calls) ----
const ADMIN_KEY = 'eos_admin_key'
export const getAdminKey = () => localStorage.getItem(ADMIN_KEY) ?? ''
export const setAdminKey = (k: string) => localStorage.setItem(ADMIN_KEY, k)

async function extractError(res: Response): Promise<string> {
  const err = await res.json().catch(() => ({}))
  const detail = (err as { detail?: unknown }).detail
  return typeof detail === 'string' ? detail : `Request failed (HTTP ${res.status})`
}

async function request<T>(
  method: string,
  path: string,
  opts: { body?: unknown; admin?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {}
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (opts.admin) headers.Authorization = `Bearer ${getAdminKey()}`
  const res = await fetch(BASE + path, {
    method,
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  })
  if (!res.ok) throw new Error(await extractError(res))
  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>)
}

// ---- calculator ----
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

export const calcSampleSize = (req: SampleSizeRequest) =>
  request<SampleSizeResult>('POST', '/v1/calculator/sample-size', { body: req })

// ---- projects ----
export interface CreatedProject {
  id: string
  name: string
  sdk_key: string
  admin_key: string
  created_at: string
}

export const createProject = (name: string) =>
  request<CreatedProject>('POST', '/v1/projects', { body: { name } })

// ---- experiments ----
export interface ExperimentSummary {
  id: string
  key: string
  status: string
  planned_sample_size: number
  started_at: string | null
  variants: number
}

export const listExperiments = () =>
  request<ExperimentSummary[]>('GET', '/v1/experiments', { admin: true })

export interface NewExperiment {
  key: string
  hypothesis: string
  planned_sample_size: number
  baseline_rate?: number
  mde?: number
  variants: { key: string; allocation_pct: number; is_control: boolean }[]
}

export const createExperiment = (body: NewExperiment) =>
  request<{ id: string; key: string; status: string }>(
    'POST', '/v1/experiments', { body, admin: true },
  )

export const updateStatus = (id: string, status: string) =>
  request<{ id: string; status: string }>(
    'PATCH', `/v1/experiments/${id}/status`, { body: { status }, admin: true },
  )

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

export const getResults = (id: string, metric?: string) =>
  request<ResultsResponse>(
    'GET',
    `/v1/experiments/${id}/results${metric ? `?metric=${encodeURIComponent(metric)}` : ''}`,
  )
