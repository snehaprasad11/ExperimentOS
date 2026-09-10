"""Tests for the sample-size / MDE calculator.

Validated three ways, matching the spec's v0.1 requirement:
  1. TEXTBOOK FIXTURE  -- a hand-computable standard example.
  2. SELF-CONSISTENCY  -- the n returned must reach the target power, and
     one fewer user must fall short (proves the rounding is right).
  3. STATSMODELS       -- statsmodels' power at our n must match the target.
"""

import pytest
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from stats.sample_size import (
    achieved_power,
    estimate_duration_days,
    required_sample_size,
)


# --------------------------------------------------------------------------
# 1. Textbook fixture: baseline 20%, detect +5pp to 25%, alpha 0.05, power 0.80.
#    Standard two-proportion formula gives 1094 per variant (hand-computed).
# --------------------------------------------------------------------------
def test_textbook_20_to_25_percent():
    r = required_sample_size(baseline_rate=0.20, mde=0.05,
                             alpha=0.05, power=0.80)
    assert r.target_rate == pytest.approx(0.25)
    assert r.absolute_mde == pytest.approx(0.05)
    assert r.relative_mde == pytest.approx(0.25)
    assert r.per_variant_n == 1094
    assert r.total_n == 2188


# --------------------------------------------------------------------------
# 2. Self-consistency: n reaches target power, n-1 does not.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("p0, mde, power", [
    (0.20, 0.05, 0.80),
    (0.10, 0.02, 0.80),
    (0.50, 0.05, 0.90),
    (0.03, 0.01, 0.80),
])
def test_sample_size_reaches_target_power(p0, mde, power):
    r = required_sample_size(p0, mde, power=power)
    assert achieved_power(r.baseline_rate, r.target_rate, r.per_variant_n) >= power
    # one fewer user should fall just short -> confirms we round up correctly
    assert achieved_power(r.baseline_rate, r.target_rate, r.per_variant_n - 1) < power


# --------------------------------------------------------------------------
# 3. Cross-check against statsmodels: power at our n must hit the target.
#    (statsmodels uses the arcsine effect size, so allow a small tolerance.)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("p0, mde, power", [
    (0.20, 0.05, 0.80),
    (0.10, 0.03, 0.80),
    (0.30, 0.05, 0.90),
])
def test_matches_statsmodels_power(p0, mde, power):
    r = required_sample_size(p0, mde, power=power)
    h = proportion_effectsize(r.target_rate, r.baseline_rate)
    sm_power = NormalIndPower().power(
        effect_size=abs(h), nobs1=r.per_variant_n,
        alpha=r.alpha, ratio=1.0, alternative="two-sided",
    )
    assert sm_power == pytest.approx(power, abs=0.03)


# --------------------------------------------------------------------------
# Behaviour: relative MDE, monotonicity, duration.
# --------------------------------------------------------------------------
def test_relative_mde():
    # detect a 20% relative lift on a 10% baseline -> 12%
    r = required_sample_size(0.10, 0.20, mde_type="relative")
    assert r.target_rate == pytest.approx(0.12)
    assert r.absolute_mde == pytest.approx(0.02)


def test_smaller_effect_needs_more_users():
    big_effect = required_sample_size(0.20, 0.10)
    small_effect = required_sample_size(0.20, 0.02)
    assert small_effect.per_variant_n > big_effect.per_variant_n


def test_higher_power_needs_more_users():
    p80 = required_sample_size(0.20, 0.05, power=0.80)
    p90 = required_sample_size(0.20, 0.05, power=0.90)
    assert p90.per_variant_n > p80.per_variant_n


def test_duration_estimate():
    assert estimate_duration_days(total_n=2188, daily_traffic=500) == pytest.approx(4.376)


# --------------------------------------------------------------------------
# Input validation: bad inputs fail loudly.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("kwargs", [
    dict(baseline_rate=0.0, mde=0.05),      # baseline out of (0,1)
    dict(baseline_rate=1.2, mde=0.05),      # baseline out of (0,1)
    dict(baseline_rate=0.20, mde=0.0),      # non-positive mde
    dict(baseline_rate=0.20, mde=0.90),     # target rate > 1
    dict(baseline_rate=0.20, mde=0.05, alpha=1.5),   # bad alpha
    dict(baseline_rate=0.20, mde=0.05, power=0.0),   # bad power
    dict(baseline_rate=0.20, mde=0.05, mde_type="x"),  # bad mde_type
])
def test_bad_inputs_raise(kwargs):
    with pytest.raises(ValueError):
        required_sample_size(**kwargs)
