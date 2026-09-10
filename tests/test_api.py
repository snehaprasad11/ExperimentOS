"""Tests for the pure (no-DB) API endpoints.

These import the app and exercise it with FastAPI's TestClient without any
database, so they run anywhere including CI. DB-backed endpoints are covered
by manual smoke tests against Supabase.
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_calculator_matches_stats_core():
    r = client.post("/v1/calculator/sample-size",
                    json={"baseline_rate": 0.20, "mde": 0.05})
    assert r.status_code == 200
    body = r.json()
    assert body["per_variant_n"] == 1094      # same as the stats-core textbook case
    assert body["total_n"] == 2188
    assert body["target_rate"] == 0.25


def test_calculator_relative_mde():
    r = client.post("/v1/calculator/sample-size",
                    json={"baseline_rate": 0.10, "mde": 0.20,
                          "mde_type": "relative"})
    assert r.status_code == 200
    assert abs(r.json()["target_rate"] - 0.12) < 1e-9


def test_calculator_rejects_bad_input():
    # baseline_rate out of (0,1) -> pydantic validation -> 422
    r = client.post("/v1/calculator/sample-size",
                    json={"baseline_rate": 1.5, "mde": 0.05})
    assert r.status_code == 422
