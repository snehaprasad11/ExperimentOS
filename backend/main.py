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

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from stats import required_sample_size

from .db import get_db

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
