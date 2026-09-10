"""ExperimentOS API (v0.2).

Wraps the pure domain core (stats, assignment, exposure) in an HTTP API.

  GET   /health                              liveness
  POST  /v1/calculator/sample-size           plan an experiment (pure stats)

  Admin (Bearer <admin_key>):
    POST  /v1/projects                       create a project (keys shown once)
    GET   /v1/projects                       list projects
    POST  /v1/experiments                    create experiment + variants
    PATCH /v1/experiments/{id}/status        move through the lifecycle

  SDK (public, keyed by sdk_key):
    GET   /v1/config/{sdk_key}               running experiments + variants

Event ingestion and results arrive in the next slice.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from quality import srm_test
from stats import required_sample_size, two_proportion_test

from .db import get_db
from .tables import exposures as exposures_t
from .tables import metric_events as metric_events_t

app = FastAPI(title="ExperimentOS API", version="0.2.0")

VALID_STATUSES = {"draft", "running", "stopped", "rolled_out", "archived"}


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def require_project(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> str:
    """Admin auth: resolve the project id from a Bearer admin key."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing admin key")
    admin_key = authorization.split(" ", 1)[1]
    row = db.execute(
        text("select id from projects where admin_key_hash = :h"),
        {"h": _hash_key(admin_key)},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=403, detail="invalid admin key")
    return str(row[0])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Calculator -- pure stats, no database.
# ---------------------------------------------------------------------------
class SampleSizeRequest(BaseModel):
    baseline_rate: float = Field(gt=0, lt=1)
    mde: float = Field(gt=0)
    alpha: float = Field(default=0.05, gt=0, lt=1)
    power: float = Field(default=0.80, gt=0, lt=1)
    mde_type: str = "absolute"


@app.post("/v1/calculator/sample-size")
def calculator_sample_size(req: SampleSizeRequest) -> dict:
    try:
        r = required_sample_size(
            baseline_rate=req.baseline_rate, mde=req.mde,
            alpha=req.alpha, power=req.power, mde_type=req.mde_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "baseline_rate": r.baseline_rate, "target_rate": r.target_rate,
        "absolute_mde": r.absolute_mde, "relative_mde": r.relative_mde,
        "alpha": r.alpha, "power": r.power,
        "per_variant_n": r.per_variant_n, "total_n": r.total_n,
    }


# ---------------------------------------------------------------------------
# Projects.
# ---------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@app.post("/v1/projects", status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    sdk_key = "sk_" + secrets.token_urlsafe(24)
    admin_key = "ak_" + secrets.token_urlsafe(24)
    row = db.execute(
        text("insert into projects (name, sdk_key, admin_key_hash) "
             "values (:name, :sdk_key, :h) returning id, created_at"),
        {"name": body.name, "sdk_key": sdk_key, "h": _hash_key(admin_key)},
    ).fetchone()
    db.commit()
    return {
        "id": str(row[0]), "name": body.name, "sdk_key": sdk_key,
        "admin_key": admin_key,   # save now -- not shown again
        "created_at": row[1].isoformat(),
    }


@app.get("/v1/projects")
def list_projects(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        text("select id, name, sdk_key, created_at from projects "
             "order by created_at desc")
    ).fetchall()
    return [{"id": str(r[0]), "name": r[1], "sdk_key": r[2],
             "created_at": r[3].isoformat()} for r in rows]


# ---------------------------------------------------------------------------
# Experiments (admin).
# ---------------------------------------------------------------------------
class VariantIn(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    allocation_pct: float = Field(ge=0, le=100)
    is_control: bool = False


class ExperimentCreate(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    hypothesis: str = Field(min_length=1)
    planned_sample_size: int = Field(gt=0)
    variants: list[VariantIn] = Field(min_length=2)
    baseline_rate: float | None = None
    mde: float | None = None
    alpha: float = 0.05
    power: float = 0.80


@app.post("/v1/experiments", status_code=201)
def create_experiment(
    body: ExperimentCreate,
    project_id: str = Depends(require_project),
    db: Session = Depends(get_db),
) -> dict:
    total = sum(v.allocation_pct for v in body.variants)
    if abs(total - 100.0) > 1e-6:
        raise HTTPException(status_code=422,
                            detail=f"allocations must sum to 100, got {total}")
    try:
        row = db.execute(
            text("insert into experiments "
                 "(project_id, key, hypothesis, planned_sample_size, "
                 " baseline_rate, mde, alpha, power) "
                 "values (:p, :k, :h, :n, :br, :mde, :a, :pw) returning id"),
            {"p": project_id, "k": body.key, "h": body.hypothesis,
             "n": body.planned_sample_size, "br": body.baseline_rate,
             "mde": body.mde, "a": body.alpha, "pw": body.power},
        ).fetchone()
        experiment_id = row[0]
        for v in body.variants:
            db.execute(
                text("insert into variants "
                     "(experiment_id, key, allocation_pct, is_control) "
                     "values (:e, :k, :a, :c)"),
                {"e": experiment_id, "k": v.key,
                 "a": v.allocation_pct, "c": v.is_control},
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409,
                            detail=f"experiment key '{body.key}' already exists")
    return {"id": str(experiment_id), "key": body.key, "status": "draft",
            "variants": [v.model_dump() for v in body.variants]}


class StatusUpdate(BaseModel):
    status: str


@app.patch("/v1/experiments/{experiment_id}/status")
def update_experiment_status(
    experiment_id: str,
    body: StatusUpdate,
    project_id: str = Depends(require_project),
    db: Session = Depends(get_db),
) -> dict:
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="invalid status")
    row = db.execute(
        text("select status from experiments "
             "where id = :id and project_id = :p"),
        {"id": experiment_id, "p": project_id},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="experiment not found")

    # stamp started_at the first time it goes running
    set_started = ", started_at = now()" if body.status == "running" else ""
    db.execute(
        text(f"update experiments set status = :s {set_started} where id = :id"),
        {"s": body.status, "id": experiment_id},
    )
    db.commit()
    return {"id": experiment_id, "status": body.status}


# ---------------------------------------------------------------------------
# Config (public) -- what the SDK fetches to assign users.
# ---------------------------------------------------------------------------
@app.get("/v1/config/{sdk_key}")
def get_config(sdk_key: str, db: Session = Depends(get_db)) -> dict:
    proj = db.execute(
        text("select id from projects where sdk_key = :k"), {"k": sdk_key},
    ).fetchone()
    if proj is None:
        raise HTTPException(status_code=404, detail="unknown sdk_key")

    exps = db.execute(
        text("select id, key from experiments "
             "where project_id = :p and status = 'running' order by key"),
        {"p": proj[0]},
    ).fetchall()

    experiments = []
    for exp_id, exp_key in exps:
        variants = db.execute(
            text("select key, allocation_pct from variants "
                 "where experiment_id = :e order by key"),
            {"e": exp_id},
        ).fetchall()
        experiments.append({
            "key": exp_key, "status": "running",
            "variants": [{"key": vk, "alloc": float(va)} for vk, va in variants],
        })

    return {"experiments": experiments,
            "fetched_at": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Event ingestion (public, keyed by sdk_key). Idempotent + batched.
# ---------------------------------------------------------------------------
class EventIn(BaseModel):
    event_id: str = Field(min_length=1)
    type: Literal["exposure", "metric"]
    user_id: str = Field(min_length=1)
    occurred_at: datetime | None = None
    experiment_key: str | None = None   # exposure
    variant_key: str | None = None      # exposure
    metric_key: str | None = None       # metric
    value: float = 1.0


class EventBatch(BaseModel):
    events: list[EventIn] = Field(min_length=1)


def _bulk_upsert(db, table, rows, conflict_cols, returning_col, chunk=1000):
    """Insert rows, ignoring conflicts (idempotency / first-write-wins).

    Dedupes within the batch by the conflict key (first wins), then inserts in
    chunked multi-row statements. Returns the number of rows actually inserted.
    """
    seen, unique = set(), []
    for r in rows:
        key = tuple(r[c] for c in conflict_cols)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    inserted = 0
    for i in range(0, len(unique), chunk):
        part = unique[i:i + chunk]
        stmt = (pg_insert(table).values(part)
                .on_conflict_do_nothing(index_elements=conflict_cols)
                .returning(returning_col))
        inserted += len(db.execute(stmt).fetchall())
    return inserted


@app.post("/v1/events", status_code=202)
def ingest_events(
    batch: EventBatch,
    x_sdk_key: str = Header(...),
    db: Session = Depends(get_db),
) -> dict:
    proj = db.execute(
        text("select id from projects where sdk_key = :k"), {"k": x_sdk_key},
    ).fetchone()
    if proj is None:
        raise HTTPException(status_code=404, detail="unknown sdk_key")
    project_id = str(proj[0])

    exp_map = {
        k: str(i) for k, i in db.execute(
            text("select key, id from experiments where project_id = :p"),
            {"p": project_id},
        ).fetchall()
    }

    now = datetime.now(timezone.utc)
    exposure_rows, metric_rows, rejected = [], [], 0
    for e in batch.events:
        ts = e.occurred_at or now
        if e.type == "exposure":
            exp_id = exp_map.get(e.experiment_key or "")
            if exp_id is None or not e.variant_key:
                rejected += 1
                continue
            exposure_rows.append({
                "experiment_id": exp_id, "user_id": e.user_id,
                "variant_key": e.variant_key, "exposed_at": ts,
                "event_id": e.event_id,
            })
        else:  # metric
            if not e.metric_key:
                rejected += 1
                continue
            metric_rows.append({
                "project_id": project_id, "user_id": e.user_id,
                "metric_key": e.metric_key, "value": e.value,
                "occurred_at": ts, "event_id": e.event_id,
            })

    accepted = 0
    accepted += _bulk_upsert(db, exposures_t, exposure_rows,
                             ["experiment_id", "user_id"], exposures_t.c.user_id)
    accepted += _bulk_upsert(db, metric_events_t, metric_rows,
                             ["project_id", "event_id"], metric_events_t.c.id)
    db.commit()

    total = len(exposure_rows) + len(metric_rows)
    return {"accepted": accepted, "duplicates": total - accepted,
            "rejected": rejected}


# ---------------------------------------------------------------------------
# Results -- exposure/metric counts -> two-proportion test + SRM.
# ---------------------------------------------------------------------------
@app.get("/v1/experiments/{experiment_id}/results")
def experiment_results(
    experiment_id: str,
    metric: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    exp = db.execute(
        text("select project_id, key, status, planned_sample_size, "
             "primary_metric_id from experiments where id = :id"),
        {"id": experiment_id},
    ).fetchone()
    if exp is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    project_id, exp_key, status, planned_n, primary_metric_id = exp

    variants = db.execute(
        text("select key, allocation_pct, is_control from variants "
             "where experiment_id = :e order by key"),
        {"e": experiment_id},
    ).fetchall()

    # exposed users per variant (the analysis population)
    exposed_counts = {vk: 0 for vk, _, _ in variants}
    for vk, c in db.execute(
        text("select variant_key, count(*) from exposures "
             "where experiment_id = :e group by variant_key"),
        {"e": experiment_id},
    ).fetchall():
        if vk in exposed_counts:
            exposed_counts[vk] = c
    total_exposed = sum(exposed_counts.values())

    # which metric? explicit query param, else the experiment's primary metric
    metric_key = metric
    if metric_key is None and primary_metric_id is not None:
        row = db.execute(
            text("select key from metric_definitions where id = :id"),
            {"id": str(primary_metric_id)},
        ).fetchone()
        metric_key = row[0] if row else None

    # conversions = exposed users with >= 1 metric event for that metric
    conversions = {vk: 0 for vk in exposed_counts}
    if metric_key:
        for vk, c in db.execute(
            text("select e.variant_key, count(distinct e.user_id) "
                 "from exposures e where e.experiment_id = :e and exists "
                 "(select 1 from metric_events m where m.project_id = :p "
                 " and m.metric_key = :mk and m.user_id = e.user_id) "
                 "group by e.variant_key"),
            {"e": experiment_id, "p": str(project_id), "mk": metric_key},
        ).fetchall():
            if vk in conversions:
                conversions[vk] = c

    # SRM on the exposed population vs configured allocation
    srm = srm_test(exposed_counts, {vk: float(a) for vk, a, _ in variants})

    # control vs each treatment
    control_key = next((vk for vk, _, isc in variants if isc),
                       variants[0][0] if variants else None)
    comparisons = []
    if metric_key and control_key:
        for vk in exposed_counts:
            if vk == control_key:
                continue
            nc, xc = exposed_counts[control_key], conversions[control_key]
            nt, xt = exposed_counts[vk], conversions[vk]
            if nc > 0 and nt > 0:
                r = two_proportion_test(nc, xc, nt, xt)
                comparisons.append({
                    "variant": vk, "vs": control_key,
                    "control_rate": r.control_rate,
                    "treatment_rate": r.treatment_rate,
                    "absolute_lift": r.absolute_lift,
                    "relative_lift": r.relative_lift,
                    "ci_low": r.ci_low, "ci_high": r.ci_high,
                    "p_value": r.p_value, "significant": r.significant,
                })

    # Verdict stays LOCKED until the planned sample size is reached (anti-peeking).
    reached = total_exposed >= planned_n
    any_significant = any(c["significant"] for c in comparisons)
    if not reached:
        verdict = "not_conclusive_yet"
    elif any_significant:
        verdict = "significant"
    else:
        verdict = "no_significant_difference"

    return {
        "experiment": {"key": exp_key, "status": status,
                       "planned_sample_size": planned_n},
        "metric": metric_key,
        "total_exposed": total_exposed,
        "reached_planned_sample_size": reached,
        "peeking_warning": (not reached) and total_exposed > 0,
        "srm": {"chi2": srm.chi2, "p_value": srm.p_value,
                "flagged": srm.flagged, "observed": srm.observed},
        "variants": [
            {"key": vk, "n": exposed_counts[vk], "conversions": conversions[vk],
             "rate": (conversions[vk] / exposed_counts[vk]
                      if exposed_counts[vk] else None)}
            for vk in exposed_counts
        ],
        "comparisons": comparisons,
        "verdict": verdict,
    }
