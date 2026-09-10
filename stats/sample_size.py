"""Sample-size / MDE calculator: the "plan before you run" tool.

Before starting an experiment you must know how many users you need to
detect the effect you care about. Guessing leads to the two classic sins:
underpowered tests (can't detect a real effect) and peeking (stopping the
moment the number looks good). This module computes the required sample
size up front, so the platform can say "you need N users, come back in D
days" instead of showing a tempting early p-value.

Method: the standard two-proportion sample-size formula (normal
approximation), using a pooled variance under the null and the actual
variances under the alternative. Cross-checked against statsmodels.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt

from scipy.stats import norm


@dataclass(frozen=True)
class SampleSizeResult:
    baseline_rate: float      # p0, the control conversion rate you expect
    target_rate: float        # p1 = the rate you want to be able to detect
    absolute_mde: float       # p1 - p0, in rate points
    relative_mde: float       # absolute_mde / p0
    alpha: float
    power: float
    per_variant_n: int        # users needed in EACH group (rounded up)
    total_n: int              # per_variant_n * 2


def required_sample_size(
    baseline_rate: float,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.80,
    mde_type: str = "absolute",
    two_sided: bool = True,
) -> SampleSizeResult:
    """Required sample size per variant for a two-proportion test.

    Args:
        baseline_rate: expected control conversion rate p0, in (0, 1)
        mde:           minimum detectable effect. If mde_type='absolute',
                       this is in rate points (0.02 = detect a 2pp change).
                       If 'relative', it's a fraction of the baseline
                       (0.10 = detect a 10% relative change).
        alpha:         significance level (false-positive rate)
        power:         desired power (1 - false-negative rate)
        mde_type:      'absolute' or 'relative'
        two_sided:     two-sided test (recommended) vs one-sided

    Returns:
        SampleSizeResult with per-variant and total sample size.
    """
    if not (0 < baseline_rate < 1):
        raise ValueError("baseline_rate must be in (0, 1)")
    if not (0 < alpha < 1) or not (0 < power < 1):
        raise ValueError("alpha and power must be in (0, 1)")
    if mde <= 0:
        raise ValueError("mde must be positive")
    if mde_type not in ("absolute", "relative"):
        raise ValueError("mde_type must be 'absolute' or 'relative'")

    p0 = baseline_rate
    absolute_mde = mde if mde_type == "absolute" else p0 * mde
    p1 = p0 + absolute_mde
    if not (0 < p1 < 1):
        raise ValueError(f"target rate {p1} out of (0, 1) -- mde too large")

    z_alpha = norm.ppf(1 - alpha / 2) if two_sided else norm.ppf(1 - alpha)
    z_beta = norm.ppf(power)

    p_bar = (p0 + p1) / 2
    # SE under H0 (pooled, equal rates) and under H1 (actual rates)
    se_null = sqrt(2 * p_bar * (1 - p_bar))
    se_alt = sqrt(p0 * (1 - p0) + p1 * (1 - p1))

    n = (z_alpha * se_null + z_beta * se_alt) ** 2 / absolute_mde ** 2
    per_variant = ceil(n)

    return SampleSizeResult(
        baseline_rate=p0,
        target_rate=p1,
        absolute_mde=absolute_mde,
        relative_mde=absolute_mde / p0,
        alpha=alpha,
        power=power,
        per_variant_n=per_variant,
        total_n=per_variant * 2,
    )


def achieved_power(
    baseline_rate: float,
    target_rate: float,
    per_variant_n: int,
    alpha: float = 0.05,
    two_sided: bool = True,
) -> float:
    """Power actually achieved at a given per-variant sample size.

    This is the inverse of `required_sample_size`, and we use it to
    self-check the calculator: the n it returns must reach the target power.
    """
    p0, p1 = baseline_rate, target_rate
    z_alpha = norm.ppf(1 - alpha / 2) if two_sided else norm.ppf(1 - alpha)
    p_bar = (p0 + p1) / 2
    se_null = sqrt(2 * p_bar * (1 - p_bar))
    se_alt = sqrt(p0 * (1 - p0) + p1 * (1 - p1))
    z_beta = (abs(p1 - p0) * sqrt(per_variant_n) - z_alpha * se_null) / se_alt
    return float(norm.cdf(z_beta))


def estimate_duration_days(total_n: int, daily_traffic: float) -> float:
    """How long the experiment must run, given daily eligible traffic."""
    if daily_traffic <= 0:
        raise ValueError("daily_traffic must be positive")
    return total_n / daily_traffic


if __name__ == "__main__":
    # Baseline 20% conversion, want to detect a 5-point absolute lift to 25%.
    r = required_sample_size(baseline_rate=0.20, mde=0.05,
                             alpha=0.05, power=0.80)
    print(f"baseline rate      : {r.baseline_rate:.2%}")
    print(f"target rate        : {r.target_rate:.2%}")
    print(f"absolute MDE       : {r.absolute_mde:.2%}  ({r.relative_mde:+.1%} relative)")
    print(f"alpha / power      : {r.alpha} / {r.power}")
    print(f"users PER variant  : {r.per_variant_n:,}")
    print(f"users TOTAL        : {r.total_n:,}")
    ap = achieved_power(r.baseline_rate, r.target_rate, r.per_variant_n)
    print(f"achieved power     : {ap:.4f}  (>= {r.power} target)")
    days = estimate_duration_days(r.total_n, daily_traffic=500)
    print(f"duration @ 500/day : {days:.1f} days")
