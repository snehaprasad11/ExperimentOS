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

- **v0.1** — stats core: two-proportion test (lift, CI, p-value) + sample-size/MDE calculator, validated. *(in progress)*
- **v0.2** — working MVP: FastAPI + Postgres + React, JS SDK with deterministic assignment, exposure tracking, ingestion, results with CIs, SRM detection.
- **v0.3** — guardrail metrics, segment analysis, quality-warning engine.
- **v1.0** — CUPED, multiple-comparison correction, sequential testing, progressive rollout.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```

## Project layout

```
stats/          # the statistics core (pure functions, no I/O)
  proportions.py    # two-proportion test: lift, CI, p-value
tests/          # textbook fixtures + statsmodels cross-checks
```
