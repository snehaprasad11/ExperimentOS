"""ExperimentOS API (v0.2).

Wraps the pure domain core (stats, assignment, exposure) in an HTTP API.
This module wires up the app and the first endpoints:

  GET  /health                        liveness
  POST /v1/calculator/sample-size     plan an experiment (no DB, pure stats)
  POST /v1/projects                   create a project (returns keys ONCE)
  GET  /v1/projects                   list projects

Auth, config delivery, and event ingestion arrive in the next slices.
"""

from __future__ import annotations

import hashlib
import secrets

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from stats import required_sample_size

from .db import get_db

app = FastAPI(title="ExperimentOS API", version="0.2.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Calculator -- "plan before you run". Pure stats, no database.
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
        "baseline_rate": r.baseline_rate,
        "target_rate": r.target_rate,
        "absolute_mde": r.absolute_mde,
        "relative_mde": r.relative_mde,
        "alpha": r.alpha,
        "power": r.power,
        "per_variant_n": r.per_variant_n,
        "total_n": r.total_n,
    }


# ---------------------------------------------------------------------------
# Projects -- a tenant with a public sdk_key and a secret admin key.
# ---------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@app.post("/v1/projects", status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    # sdk_key is public (config read + ingest). admin_key is secret and shown
    # exactly once; we store only its hash, never the plaintext.
    sdk_key = "sk_" + secrets.token_urlsafe(24)
    admin_key = "ak_" + secrets.token_urlsafe(24)
    row = db.execute(
        text(
            "insert into projects (name, sdk_key, admin_key_hash) "
            "values (:name, :sdk_key, :h) returning id, created_at"
        ),
        {"name": body.name, "sdk_key": sdk_key, "h": _hash_key(admin_key)},
    ).fetchone()
    db.commit()
    return {
        "id": str(row[0]),
        "name": body.name,
        "sdk_key": sdk_key,
        "admin_key": admin_key,   # save this now -- it is not shown again
        "created_at": row[1].isoformat(),
    }


@app.get("/v1/projects")
def list_projects(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        text("select id, name, sdk_key, created_at from projects "
             "order by created_at desc")
    ).fetchall()
    return [
        {"id": str(r[0]), "name": r[1], "sdk_key": r[2],
         "created_at": r[3].isoformat()}
        for r in rows
    ]
