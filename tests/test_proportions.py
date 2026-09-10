"""Tests for the two-proportion test.

Two kinds of check, exactly as the spec's v0.1 demands:

  1. TEXTBOOK FIXTURES -- hand-computed values we can verify with a
     calculator, so the module is correct in absolute terms, not just
     "consistent with another library that could share our bug".

  2. STATSMODELS CROSS-CHECK -- our z-statistic and p-value must match
     statsmodels' `proportions_ztest` (pooled, two-sided) across a range
     of inputs. This is the "second opinion" that catches subtle errors.
"""

import math

import numpy as np
import pytest
from statsmodels.stats.proportion import proportions_ztest

from stats.proportions import two_proportion_test


# --------------------------------------------------------------------------
# 1. Textbook fixture: control 100/1000 (10%) vs treatment 120/1000 (12%).
#    Hand-computed:
#      pooled p   = 220/2000 = 0.11
#      SE_pooled  = sqrt(0.11 * 0.89 * (1/1000 + 1/1000)) = 0.0139929
#      z          = 0.02 / 0.0139929                       = 1.42927
#      p_value    = 2 * P(Z > 1.42927)                     = 0.15289
# --------------------------------------------------------------------------
def test_textbook_fixture_10_vs_12_percent():
    r = two_proportion_test(control_n=1000, control_x=100,
                            treatment_n=1000, treatment_x=120)

    assert r.control_rate == pytest.approx(0.10)
    assert r.treatment_rate == pytest.approx(0.12)
    assert r.absolute_lift == pytest.approx(0.02)
    assert r.relative_lift == pytest.approx(0.20)          # +20% relative
    assert r.z_stat == pytest.approx(1.42927, abs=1e-4)
    assert r.p_value == pytest.approx(0.15289, abs=1e-4)
    assert r.significant is False                           # p > 0.05

    # The 95% CI on the absolute lift straddles zero, consistent with
    # a non-significant result. Hand-computed: [-0.00741, 0.04741].
    assert r.ci_low == pytest.approx(-0.00741, abs=1e-4)
    assert r.ci_high == pytest.approx(0.04741, abs=1e-4)


# --------------------------------------------------------------------------
# 2. Cross-check against statsmodels over many cases.
# --------------------------------------------------------------------------
CASES = [
    # (control_n, control_x, treatment_n, treatment_x)
    (1000, 100, 1000, 120),
    (500, 50, 500, 80),
    (2000, 300, 2000, 300),     # identical rates -> z ~ 0, p ~ 1
    (10000, 500, 10000, 650),   # large n, small effect
    (300, 30, 320, 60),         # unequal group sizes
]


@pytest.mark.parametrize("n_c, x_c, n_t, x_t", CASES)
def test_matches_statsmodels(n_c, x_c, n_t, x_t):
    ours = two_proportion_test(n_c, x_c, n_t, x_t)

    # statsmodels: order [treatment, control] so the sign of z matches
    # our convention (treatment_rate - control_rate).
    sm_z, sm_p = proportions_ztest([x_t, x_c], [n_t, n_c])

    assert ours.z_stat == pytest.approx(sm_z, rel=1e-9, abs=1e-9)
    assert ours.p_value == pytest.approx(sm_p, rel=1e-9, abs=1e-9)


def test_identical_rates_give_no_evidence():
    r = two_proportion_test(2000, 300, 2000, 300)
    assert r.z_stat == pytest.approx(0.0)
    assert r.p_value == pytest.approx(1.0)
    assert r.significant is False


def test_ci_contains_point_estimate():
    r = two_proportion_test(1000, 100, 1000, 150)
    assert r.ci_low < r.absolute_lift < r.ci_high


# --------------------------------------------------------------------------
# 3. Input validation: bad inputs must fail loudly.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("args", [
    (0, 0, 100, 10),        # zero group size
    (100, 200, 100, 10),    # x > n
    (100, -5, 100, 10),     # negative conversions
])
def test_bad_inputs_raise(args):
    with pytest.raises(ValueError):
        two_proportion_test(*args)


def test_bad_alpha_raises():
    with pytest.raises(ValueError):
        two_proportion_test(1000, 100, 1000, 120, alpha=1.5)


def test_degenerate_nobody_converts():
    # No conversions anywhere: no evidence of a difference, no crash.
    r = two_proportion_test(1000, 0, 1000, 0)
    assert r.p_value == pytest.approx(1.0)
    assert math.isnan(r.relative_lift)   # 0/0 is undefined
