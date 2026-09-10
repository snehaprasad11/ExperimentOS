"""Two-proportion comparison: the core A/B-test statistic.

Given a control group and a treatment group, each summarised as
(n = users exposed, x = users who converted), this module answers:

    "Is the difference in conversion rate real, or could it be luck?"

It returns three things every honest A/B readout needs:
  - the effect      -> absolute lift and relative lift
  - the uncertainty -> a confidence interval on the absolute lift
  - the evidence     -> a two-sided p-value

One subtlety is deliberate (see SE_pooled vs SE_unpooled below):
the p-value and the confidence interval use *different* standard errors.
That is not a bug; it is the correct textbook treatment.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from scipy.stats import norm


@dataclass(frozen=True)
class TwoProportionResult:
    """Everything you need to report an A/B result on a conversion rate."""

    control_rate: float       # x_c / n_c
    treatment_rate: float     # x_t / n_t
    absolute_lift: float      # treatment_rate - control_rate  (in rate points)
    relative_lift: float      # absolute_lift / control_rate   (e.g. 0.20 = +20%)
    ci_low: float             # confidence interval on absolute_lift
    ci_high: float
    p_value: float            # two-sided
    z_stat: float
    significant: bool         # p_value < alpha
    alpha: float


def two_proportion_test(
    control_n: int,
    control_x: int,
    treatment_n: int,
    treatment_x: int,
    alpha: float = 0.05,
) -> TwoProportionResult:
    """Compare two conversion rates.

    Args:
        control_n:   users in control
        control_x:   conversions in control   (0 <= control_x <= control_n)
        treatment_n: users in treatment
        treatment_x: conversions in treatment
        alpha:       significance level (0.05 -> 95% confidence)

    Returns:
        TwoProportionResult with lift, CI, and p-value.
    """
    # --- guardrails: bad inputs should fail loudly, not silently mislead ---
    if control_n <= 0 or treatment_n <= 0:
        raise ValueError("group sizes must be positive")
    if not (0 <= control_x <= control_n) or not (0 <= treatment_x <= treatment_n):
        raise ValueError("conversions must satisfy 0 <= x <= n")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be in (0, 1)")

    p_c = control_x / control_n
    p_t = treatment_x / treatment_n
    absolute_lift = p_t - p_c

    # --- the p-value: POOLED standard error --------------------------------
    # The null hypothesis is "the two true rates are equal". To test it, we
    # act as if they ARE equal and pool both groups into one best estimate of
    # that shared rate, then ask how surprising the observed gap is under it.
    p_pool = (control_x + treatment_x) / (control_n + treatment_n)
    se_pooled = sqrt(p_pool * (1 - p_pool) * (1 / control_n + 1 / treatment_n))

    if se_pooled == 0:
        # Degenerate case: nobody converted anywhere (or everybody did).
        # There is no evidence of a difference.
        z = 0.0
        p_value = 1.0
    else:
        z = absolute_lift / se_pooled
        # two-sided: probability of a |z| this large in EITHER direction
        p_value = 2 * norm.sf(abs(z))

    # --- the confidence interval: UNPOOLED standard error ------------------
    # The CI describes the difference we actually observed, so we do NOT
    # assume the rates are equal here -- we use each group's own variance.
    se_unpooled = sqrt(
        p_c * (1 - p_c) / control_n + p_t * (1 - p_t) / treatment_n
    )
    z_crit = norm.ppf(1 - alpha / 2)  # e.g. 1.959964 for alpha=0.05
    margin = z_crit * se_unpooled

    # relative lift is undefined if the control rate is zero
    relative_lift = absolute_lift / p_c if p_c > 0 else float("nan")

    # Cast to native Python types: scipy hands back numpy scalars, and we
    # want a plain-float / plain-bool result that serialises cleanly to JSON
    # (the API layer stores these) and behaves under `is` identity checks.
    return TwoProportionResult(
        control_rate=float(p_c),
        treatment_rate=float(p_t),
        absolute_lift=float(absolute_lift),
        relative_lift=float(relative_lift),
        ci_low=float(absolute_lift - margin),
        ci_high=float(absolute_lift + margin),
        p_value=float(p_value),
        z_stat=float(z),
        significant=bool(p_value < alpha),
        alpha=float(alpha),
    )


if __name__ == "__main__":
    # A quick, human-readable demo. Control 10% (100/1000) vs treatment 12%.
    r = two_proportion_test(control_n=1000, control_x=100,
                            treatment_n=1000, treatment_x=120)
    print(f"control rate    : {r.control_rate:.4f}")
    print(f"treatment rate  : {r.treatment_rate:.4f}")
    print(f"absolute lift   : {r.absolute_lift:+.4f}  (rate points)")
    print(f"relative lift   : {r.relative_lift:+.2%}")
    print(f"95% CI on lift  : [{r.ci_low:+.4f}, {r.ci_high:+.4f}]")
    print(f"z-stat          : {r.z_stat:.4f}")
    print(f"p-value         : {r.p_value:.4f}")
    print(f"significant?    : {r.significant}")
