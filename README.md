# ExperimentOS

A feature-flag and **A/B experimentation platform** that treats *statistical validity as a
first-class output* — it actively warns you when an experiment result cannot be trusted
(sample-ratio mismatch, peeking, missing exposure, users in multiple variants), because a
confidently-wrong result is worse than no result at all.

> **Status:** early development — building the statistics core first (v0.1), then the
> ingestion + assignment platform on top of it.

## Why this exists

Small teams either don't run experiments or run them badly: no sample-size planning, peeking
at results daily, stopping when the number looks good. And even teams *with* a tool often
can't tell whether an experiment was **valid**. ExperimentOS makes validity a product feature,
not an afterthought.

## Real data, not synthetic

The statistical engine is developed and validated against **real, published A/B-test datasets**
(e.g. the Cookie Cats mobile-games experiment) rather than fabricated numbers — pulled
reproducibly via the Kaggle API. Every statistic is cross-checked three ways: hand-computed
textbook values, `statsmodels`, and the dataset's known published result.

## Tech stack

| Layer | Choice |
|-------|--------|
| Statistics | Python · SciPy · statsmodels (pure, independently tested) |
| Backend | FastAPI |
| Assignment SDK | TypeScript → tiny JS bundle, deterministic `hash(experiment_id + user_id)` |
| Storage | PostgreSQL |
| Dashboard | React + TypeScript |
| CI | GitHub Actions |

## Roadmap

- **v0.1** — stats core: two-proportion test (lift, CI, p-value) + sample-size/MDE calculator, validated three ways (textbook · statsmodels · real Cookie Cats result). ✅ **done**
- **v0.2** — working MVP: FastAPI + Postgres + React, JS SDK with deterministic assignment, exposure tracking, ingestion, results with CIs, SRM detection. *(in progress: deterministic assignment core — Python + JS SDK, cross-language parity verified over 1,800 cases)*
- **v0.3** — guardrail metrics, segment analysis, quality-warning engine.
- **v1.0** — CUPED, multiple-comparison correction, sequential testing, progressive rollout.

## Getting started

```bash
pip install -r requirements.txt
pytest -q                          # 13 tests: textbook + statsmodels cross-checks

# Analyse a real published experiment (needs a Kaggle token, see below)
python data/download.py            # fetch Cookie Cats into data/raw/ (gitignored)
python -m analysis.cookie_cats     # run the engine on 90k real players
```

The engine reproduces the dataset's known result — moving the game's progression
gate from level 30 to 40 significantly **hurt** 7-day retention (p = 0.0016) — which
serves as a third validation alongside the textbook and statsmodels checks.

### Kaggle token (for the real-data analysis)

Create a token at kaggle.com → Settings → API Tokens → *Create Legacy API Key*, then
place the downloaded `kaggle.json` at `~/.kaggle/kaggle.json` (`C:\Users\<you>\.kaggle\`
on Windows). It is gitignored and never committed.

## Project layout

```
stats/          # the statistics core (pure functions, no I/O)
  proportions.py    # two-proportion test: lift, CI, p-value
  sample_size.py    # required sample size / MDE / power + duration
assignment/     # deterministic variant assignment (Python side)
  core.py           # FNV-1a hash -> bucket -> variant, no state, no network
sdk/            # the JS SDK
  assign.mjs        # same hash + mapping, byte-identical to Python
  verify_parity.mjs # checks JS against the shared golden fixture
tracking/       # exposure tracking (the analysis population)
  exposure.py       # idempotency, first-exposure-wins, leakage, assignment audit
tests/          # 53 tests: stats + assignment + parity + exposure
  fixtures/         # assignment_golden.json: the parity contract
data/           # download.py: reproducible Kaggle pull (raw data gitignored)
analysis/       # cookie_cats.py: the engine run on a real experiment
```

### Deterministic assignment (the heart)

A user's variant is a pure local computation — `fnv1a("experiment_id:user_id") % 10000`
mapped to a variant by cumulative allocation. The **same** function is implemented in
Python (backend audit) and JavaScript (browser SDK), and verified byte-identical over 1,800
cases, so both sides always agree with no per-request network call or server state.

```bash
python -m scripts.generate_parity_fixture   # regenerate the contract
node sdk/verify_parity.mjs                   # JS must match Python exactly
```

### Exposure ≠ assignment (where validity is won)

Assignment happens for every user the SDK evaluates; **exposure** fires only when the
user actually sees the variant, and the analysis population is the *exposed* users. The
tracker enforces idempotency (retries can't inflate counts), *first-exposure-wins* (a user
belongs to exactly one variant), flags **cross-variant leakage**, and runs an independent
**assignment audit** — re-deriving each exposure with the same hash the SDK used and
flagging any disagreement (stale SDK, config drift, tampering).
