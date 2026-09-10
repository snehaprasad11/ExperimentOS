"""Sample Ratio Mismatch (SRM) -- a first-class validity check.

If users were meant to split 50/50 but the observed exposure counts are, say,
52/48 with large n, something is broken: the randomisation, the logging, or a
filter that drops one variant more than the other. When that happens, every
downstream metric is suspect. SRM is a chi-square goodness-of-fit test of the
observed counts against the configured allocation.

The threshold is deliberately strict (default p < 0.001): with large samples
even a tiny, harmless imbalance is "significant" at 0.05, so a naive threshold
cries wolf. This ships in the MVP because an experiment platform without an
SRM check is dangerous.
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import chisquare


@dataclass(frozen=True)
class SRMResult:
    chi2: float
    p_value: float
    flagged: bool
    observed: dict[str, int]
    expected: dict[str, float]


def srm_test(
    observed: dict[str, int],
    allocation: dict[str, float],
    threshold: float = 0.001,
) -> SRMResult:
    """Test observed per-variant counts against the configured allocation.

    Args:
        observed:   {variant_key: exposed_count}
        allocation: {variant_key: allocation_pct} (pcts sum to ~100)
        threshold:  p-value below which SRM is flagged
    """
    keys = list(observed.keys())
    total = sum(observed.values())
    expected = {k: allocation.get(k, 0.0) / 100.0 * total for k in keys}

    if total == 0 or any(e == 0 for e in expected.values()):
        # Not enough data (or a zero-allocation variant) -> can't test.
        return SRMResult(0.0, 1.0, False, dict(observed), expected)

    chi2, p = chisquare(
        f_obs=[observed[k] for k in keys],
        f_exp=[expected[k] for k in keys],
    )
    return SRMResult(float(chi2), float(p), bool(p < threshold),
                     dict(observed), expected)
