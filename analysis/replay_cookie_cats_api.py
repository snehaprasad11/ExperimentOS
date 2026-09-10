"""Replay the real Cookie Cats experiment through the full API pipeline.

Unlike analysis/cookie_cats.py (which calls the stats engine directly), this
drives the actual HTTP API end to end:

    create project -> create experiment -> ingest ~107k real events -> results

and shows the results endpoint reproduces the known published finding
(gate_40 significantly hurts 7-day retention, p = 0.0016). It is the
end-to-end proof that the platform -- not just the statistics -- is correct.

Prereqs: DATABASE_URL in .env, and data/raw/cookie_cats.csv (python data/download.py).
Note: writes ~107k rows to the configured database and takes a few minutes
over a remote connection. Idempotent -- re-running re-ingests as duplicates.

Run (from repo root):  python -m analysis.replay_cookie_cats_api
"""

import time
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app

DATA = Path(__file__).resolve().parent.parent / "data" / "raw" / "cookie_cats.csv"


def main() -> None:
    client = TestClient(app)
    df = pd.read_csv(DATA)
    print(f"loaded {len(df):,} players")

    project = client.post("/v1/projects",
                          json={"name": "Cookie Cats (API replay)"}).json()
    sdk_key, admin_key = project["sdk_key"], project["admin_key"]
    auth = {"Authorization": f"Bearer {admin_key}"}

    exp = client.post("/v1/experiments", headers=auth, json={
        "key": "cookie_cats_gate",
        "hypothesis": "Moving the gate from level 30 to 40 changes retention",
        "planned_sample_size": 80000,
        "variants": [
            {"key": "gate_30", "allocation_pct": 50, "is_control": True},
            {"key": "gate_40", "allocation_pct": 50},
        ],
    }).json()
    exp_id = exp["id"]
    client.patch(f"/v1/experiments/{exp_id}/status", headers=auth,
                 json={"status": "running"})
    print("experiment running:", exp["key"])

    # one exposure per user + a retention_7 metric event for retained users
    events = []
    for uid, version, ret7 in zip(df["userid"], df["version"], df["retention_7"]):
        events.append({"event_id": f"exp_{uid}", "type": "exposure",
                       "experiment_key": "cookie_cats_gate",
                       "variant_key": version, "user_id": str(uid)})
        if bool(ret7):
            events.append({"event_id": f"met_{uid}", "type": "metric",
                           "metric_key": "retention_7", "user_id": str(uid)})
    print(f"prepared {len(events):,} events")

    t0 = time.time()
    totals = {"accepted": 0, "duplicates": 0, "rejected": 0}
    for i in range(0, len(events), 10000):
        r = client.post("/v1/events", headers={"X-SDK-Key": sdk_key},
                        json={"events": events[i:i + 10000]}).json()
        for k in totals:
            totals[k] += r[k]
    print(f"ingested in {time.time() - t0:.0f}s -> {totals}")

    res = client.get(f"/v1/experiments/{exp_id}/results",
                     params={"metric": "retention_7"}).json()
    print("\n=== RESULTS (through the full API) ===")
    print(f"total exposed: {res['total_exposed']:,}  "
          f"reached plan: {res['reached_planned_sample_size']}")
    srm = res["srm"]
    print(f"SRM: chi2={srm['chi2']:.3f} p={srm['p_value']:.4f} "
          f"flagged={srm['flagged']}  observed={srm['observed']}")
    for v in res["variants"]:
        print(f"  {v['key']}: n={v['n']:,} conv={v['conversions']:,} "
              f"rate={v['rate']:.4%}")
    for cmp in res["comparisons"]:
        print(f"  {cmp['variant']} vs {cmp['vs']}: "
              f"lift={cmp['absolute_lift']:+.4%} p={cmp['p_value']:.4f} "
              f"significant={cmp['significant']}")
    print("VERDICT:", res["verdict"])


if __name__ == "__main__":
    main()
