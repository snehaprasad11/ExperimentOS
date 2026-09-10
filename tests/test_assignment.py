"""Tests for deterministic variant assignment.

Covers the FNV-1a test vectors (the exact target the JS SDK must match) and
the four properties the assignment must have: stability, independence,
proportionality, and input validation.
"""

from collections import Counter

import pytest
from scipy.stats import chi2_contingency, chisquare

from assignment import BUCKETS, assign, bucket_of, fnv1a_32

TWO_WAY = [("control", 50.0), ("treatment", 50.0)]
UNEVEN = [("control", 80.0), ("treatment", 20.0)]
THREE_WAY = [("a", 34.0), ("b", 33.0), ("c", 33.0)]


# --------------------------------------------------------------------------
# FNV-1a known test vectors -- these lock the hash cross-language.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("", 0x811C9DC5),
    ("a", 0xE40C292C),
    ("foobar", 0xBF9CF968),
])
def test_fnv1a_known_vectors(text, expected):
    assert fnv1a_32(text) == expected


def test_bucket_in_range():
    for i in range(1000):
        b = bucket_of("exp_1", f"user_{i}")
        assert 0 <= b < BUCKETS


# --------------------------------------------------------------------------
# 1. Stability: same user + experiment -> always the same variant.
# --------------------------------------------------------------------------
def test_assignment_is_stable():
    for i in range(500):
        uid = f"user_{i}"
        first = assign("exp_1", uid, TWO_WAY)
        for _ in range(5):
            assert assign("exp_1", uid, TWO_WAY) == first


# --------------------------------------------------------------------------
# 2. Proportionality: over many users, shares match the allocation.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("variants", [TWO_WAY, UNEVEN, THREE_WAY])
def test_proportional_allocation(variants):
    n = 50_000
    counts = Counter(assign("exp_alloc", f"user_{i}", variants) for i in range(n))
    observed = [counts[key] for key, _ in variants]
    expected = [pct / 100.0 * n for _, pct in variants]
    _, p = chisquare(f_obs=observed, f_exp=expected)
    # Strict threshold: only a real distribution problem should fail.
    assert p > 0.001, f"allocation off: observed={observed} expected={expected}"


# --------------------------------------------------------------------------
# 3. Independence: assignment in one experiment is uncorrelated with another.
# --------------------------------------------------------------------------
def test_independent_across_experiments():
    n = 50_000
    table = [[0, 0], [0, 0]]
    idx = {"control": 0, "treatment": 1}
    for i in range(n):
        uid = f"user_{i}"
        a = assign("exp_A", uid, TWO_WAY)
        b = assign("exp_B", uid, TWO_WAY)
        table[idx[a]][idx[b]] += 1
    _, p, _, _ = chi2_contingency(table)
    # High p => no detectable association between the two experiments.
    assert p > 0.001, f"experiments look correlated: {table}"


def test_reordering_variants_is_still_valid():
    # Whatever the order, allocations must still sum-check and assign.
    v = assign("exp_x", "user_42", [("treatment", 50.0), ("control", 50.0)])
    assert v in {"control", "treatment"}


# --------------------------------------------------------------------------
# 4. Validation: allocations must sum to 100.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("variants", [
    [("control", 60.0), ("treatment", 50.0)],   # sums to 110
    [("control", 50.0), ("treatment", 40.0)],   # sums to 90
])
def test_bad_allocation_raises(variants):
    with pytest.raises(ValueError):
        assign("exp_1", "user_1", variants)
