"""Tests for exposure tracking and the quality signals it produces."""

from datetime import datetime, timedelta

import pytest

from assignment import assign
from tracking import ExposureEvent, ExposureTracker

T0 = datetime(2026, 1, 1, 12, 0, 0)
EXP = "pricing_page_v2"
VARIANTS = [("control", 50.0), ("treatment", 50.0)]


def ev(user_id, variant, event_id, offset_secs=0):
    return ExposureEvent(
        experiment_id=EXP, user_id=user_id, variant_key=variant,
        event_id=event_id, exposed_at=T0 + timedelta(seconds=offset_secs),
    )


# --------------------------------------------------------------------------
# 1. Idempotency: a repeated event_id is ignored.
# --------------------------------------------------------------------------
def test_duplicate_event_id_ignored():
    t = ExposureTracker()
    assert t.record(ev("u1", "control", "e1")) == "accepted"
    assert t.record(ev("u1", "control", "e1")) == "duplicate"   # same event
    assert t.exposed_counts(EXP)["control"] == 1


# --------------------------------------------------------------------------
# 2. First exposure wins -- including out-of-order arrival.
# --------------------------------------------------------------------------
def test_first_exposure_wins_by_time():
    t = ExposureTracker()
    t.record(ev("u1", "control", "e1", offset_secs=10))
    # different variant, LATER in time -> leakage, but control still canonical
    assert t.record(ev("u1", "treatment", "e2", offset_secs=20)) == "leaked"
    assert t.canonical_variant(EXP, "u1") == "control"


def test_out_of_order_earlier_event_becomes_canonical():
    t = ExposureTracker()
    t.record(ev("u1", "treatment", "e1", offset_secs=20))       # arrives first
    # an earlier-timestamped exposure arrives late -> it wins
    assert t.record(ev("u1", "control", "e2", offset_secs=10)) == "leaked"
    assert t.canonical_variant(EXP, "u1") == "control"


# --------------------------------------------------------------------------
# 3. Leakage detection: users in multiple variants.
# --------------------------------------------------------------------------
def test_leakage_flagged_as_quality_finding():
    t = ExposureTracker()
    t.record(ev("u1", "control", "e1"))
    t.record(ev("u1", "treatment", "e2", offset_secs=5))   # leaked
    t.record(ev("u2", "control", "e3"))                    # clean

    assert t.leaked_users(EXP) == ["u1"]
    findings = t.quality_findings(EXP)
    assert len(findings) == 1
    assert findings[0].kind == "multi_variant_user"
    assert findings[0].severity == "critical"
    assert findings[0].detail["variants_seen"] == ["control", "treatment"]


def test_clean_log_has_no_findings():
    t = ExposureTracker()
    for i in range(100):
        uid = f"u{i}"
        t.record(ev(uid, assign(EXP, uid, VARIANTS), f"e{i}"))
    assert t.quality_findings(EXP) == []
    assert t.exposed_users(EXP) == 100


# --------------------------------------------------------------------------
# 4. Assignment audit: backend re-derives what the SDK should have assigned.
# --------------------------------------------------------------------------
def test_audit_passes_when_exposures_match_assignment():
    t = ExposureTracker()
    for i in range(500):
        uid = f"u{i}"
        # exposures generated with the correct deterministic assignment
        t.record(ev(uid, assign(EXP, uid, VARIANTS), f"e{i}"))
    assert t.audit_assignments(EXP, VARIANTS) == []


def test_audit_detects_wrong_variant():
    t = ExposureTracker()
    uid = "u1"
    correct = assign(EXP, uid, VARIANTS)
    wrong = "treatment" if correct == "control" else "control"
    t.record(ev(uid, wrong, "e1"))   # SDK/config drift: exposed to wrong variant

    findings = t.audit_assignments(EXP, VARIANTS)
    assert len(findings) == 1
    assert findings[0].kind == "assignment_mismatch"
    assert findings[0].detail["exposed_variant"] == wrong
    assert findings[0].detail["expected_variant"] == correct
