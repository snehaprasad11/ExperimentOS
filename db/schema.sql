-- ExperimentOS database schema (v0.2 MVP) -- faithful to spec section 10.
-- Apply with:  python -m db.apply_schema   (reads DATABASE_URL from .env)

create extension if not exists pgcrypto;   -- for gen_random_uuid()

-- A tenant. The sdk_key is public (config read + event ingest only);
-- admin actions authenticate against admin_key_hash.
create table if not exists projects (
  id             uuid primary key default gen_random_uuid(),
  name           text not null,
  sdk_key        text not null unique,
  admin_key_hash text not null,
  created_at     timestamptz default now()
);

-- planned_sample_size is set BEFORE the experiment starts (from the
-- calculator) -- that is what makes peeking detectable later.
create table if not exists experiments (
  id                  uuid primary key default gen_random_uuid(),
  project_id          uuid not null references projects(id) on delete cascade,
  key                 text not null,          -- stable id used in the hash
  hypothesis          text not null,
  status              text not null default 'draft'
      check (status in ('draft','running','stopped','rolled_out','archived')),
  primary_metric_id   uuid,
  started_at          timestamptz,
  ended_at            timestamptz,
  planned_sample_size int not null,
  baseline_rate       numeric,
  mde                 numeric,
  alpha               numeric default 0.05,
  power               numeric default 0.80,
  unique (project_id, key)
);

create table if not exists variants (
  id             uuid primary key default gen_random_uuid(),
  experiment_id  uuid not null references experiments(id) on delete cascade,
  key            text not null,               -- 'control' | 'treatment' | ...
  allocation_pct numeric not null check (allocation_pct >= 0 and allocation_pct <= 100),
  is_control     boolean default false,
  unique (experiment_id, key)
);
-- allocations must sum to 100: enforced in the service layer + a test

create table if not exists metric_definitions (
  id              uuid primary key default gen_random_uuid(),
  project_id      uuid not null references projects(id) on delete cascade,
  key             text not null,
  kind            text not null check (kind in ('binary','continuous','count')),
  event_name      text not null,
  is_guardrail    boolean default false,
  definition_hash text not null,              -- detects mid-experiment redefinition
  unique (project_id, key)
);

create table if not exists experiment_metrics (
  experiment_id uuid references experiments(id) on delete cascade,
  metric_id     uuid references metric_definitions(id) on delete cascade,
  role          text check (role in ('primary','secondary','guardrail')),
  primary key (experiment_id, metric_id)
);

-- EXPOSURE: the analysis population. The (experiment_id, user_id) primary key
-- is how "first exposure wins" is enforced and how leakage is detected.
create table if not exists exposures (
  experiment_id uuid not null references experiments(id) on delete cascade,
  user_id       text not null,
  variant_key   text not null,
  exposed_at    timestamptz not null,
  event_id      text not null,
  primary key (experiment_id, user_id)
);
create index if not exists idx_exposures_variant on exposures (experiment_id, variant_key);

-- Append-only metric events. unique(project_id, event_id) gives idempotency.
create table if not exists metric_events (
  id          bigserial primary key,
  project_id  uuid not null references projects(id) on delete cascade,
  user_id     text not null,
  metric_key  text not null,
  value       numeric not null default 1,
  occurred_at timestamptz not null,
  event_id    text not null,
  unique (project_id, event_id)
);
create index if not exists idx_metric_events_key  on metric_events (project_id, metric_key, occurred_at);
create index if not exists idx_metric_events_user on metric_events (project_id, user_id);

-- Pre-aggregated results so the dashboard reads fast.
create table if not exists result_snapshots (
  id             uuid primary key default gen_random_uuid(),
  experiment_id  uuid references experiments(id) on delete cascade,
  metric_id      uuid references metric_definitions(id),
  computed_at    timestamptz default now(),
  per_variant    jsonb not null,             -- n, converted, rate per variant
  absolute_lift  numeric,
  relative_lift  numeric,
  ci_low         numeric,
  ci_high        numeric,
  p_value        numeric,
  achieved_power numeric,
  is_conclusive  boolean not null default false
);

create table if not exists quality_findings (
  id            bigserial primary key,
  experiment_id uuid references experiments(id) on delete cascade,
  kind          text not null,               -- srm | multi_variant_user | peeking | ...
  severity      text check (severity in ('info','warn','critical')),
  detail        jsonb,
  detected_at   timestamptz default now()
);

create table if not exists decisions (
  experiment_id uuid primary key references experiments(id) on delete cascade,
  outcome       text check (outcome in ('ship','no_ship','iterate','inconclusive')),
  rationale     text not null,
  decided_by    text,
  decided_at    timestamptz default now()
);
