"""Tests for the SRM (sample ratio mismatch) check."""

import pytest

from quality import srm_test


def test_even_split_not_flagged():
    r = srm_test({"control": 5000, "treatment": 5000},
                 {"control": 50.0, "treatment": 50.0})
    assert r.flagged is False
    assert r.p_value == pytest.approx(1.0)


def test_clear_mismatch_flagged():
    # 60/40 observed against a 50/50 design, large n -> definitely SRM
    r = srm_test({"control": 6000, "treatment": 4000},
                 {"control": 50.0, "treatment": 50.0})
    assert r.flagged is True
    assert r.p_value < 0.001


def test_cookie_cats_borderline_not_flagged_at_strict_threshold():
    # The real Cookie Cats split: chi2=6.90, p=0.0086 -> NOT flagged at 0.001,
    # though it would trip a naive 0.05 alarm.
    r = srm_test({"gate_30": 44700, "gate_40": 45489},
                 {"gate_30": 50.0, "gate_40": 50.0})
    assert r.chi2 == pytest.approx(6.90, abs=0.05)
    assert r.flagged is False
    assert 0.001 < r.p_value < 0.05


def test_empty_counts_not_flagged():
    r = srm_test({"control": 0, "treatment": 0},
                 {"control": 50.0, "treatment": 50.0})
    assert r.flagged is False
