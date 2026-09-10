"""Run the ExperimentOS engine on a REAL published A/B test.

Dataset: Cookie Cats (mobile game). The team moved a progression gate from
level 30 to level 40 and measured player retention. This is a real
experiment with a known, published result -- so it doubles as a third
validation of our statistics core (textbook + statsmodels + real result).

  control   = gate_30   (the original)
  treatment = gate_40   (the change)
  metrics   = retention_1 (came back day 1), retention_7 (came back day 7)

Run (from repo root):  python -m analysis.cookie_cats
  (first fetch the data: python data/download.py)
"""

from pathlib import Path

import pandas as pd
from scipy.stats import chisquare

from stats.proportions import two_proportion_test

DATA = Path(__file__).resolve().parent.parent / "data" / "raw" / "cookie_cats.csv"


def srm_check(n_control: int, n_treatment: int) -> None:
    """Sample Ratio Mismatch: did users actually split ~50/50 as intended?

    A significant mismatch means the randomisation or logging is broken, and
    every downstream metric is suspect. We test observed counts against the
    expected 50/50 with a chi-square goodness-of-fit test.
    """
    total = n_control + n_treatment
    expected = [total / 2, total / 2]
    stat, p = chisquare(f_obs=[n_control, n_treatment], f_exp=expected)
    verdict = "OK" if p > 0.001 else "SRM DETECTED -- results untrustworthy"
    print("Sample Ratio Mismatch (SRM) check")
    print(f"  observed : control={n_control}  treatment={n_treatment}")
    print(f"  expected : 50 / 50")
    print(f"  chi2={stat:.3f}  p={p:.4f}  -> {verdict}\n")


def analyse(df: pd.DataFrame, metric: str) -> None:
    control = df[df["version"] == "gate_30"][metric]
    treatment = df[df["version"] == "gate_40"][metric]

    r = two_proportion_test(
        control_n=len(control), control_x=int(control.sum()),
        treatment_n=len(treatment), treatment_x=int(treatment.sum()),
    )

    print(f"Metric: {metric}   (gate_30 control vs gate_40 treatment)")
    print(f"  control rate    : {r.control_rate:.4%}")
    print(f"  treatment rate  : {r.treatment_rate:.4%}")
    print(f"  absolute lift   : {r.absolute_lift:+.4%}")
    print(f"  relative lift   : {r.relative_lift:+.2%}")
    print(f"  95% CI on lift  : [{r.ci_low:+.4%}, {r.ci_high:+.4%}]")
    print(f"  p-value         : {r.p_value:.4f}")
    print(f"  significant?    : {r.significant}")
    verdict = ("moving the gate to 40 HURT retention"
               if r.significant and r.absolute_lift < 0
               else "moving the gate to 40 HELPED retention"
               if r.significant else "no significant difference")
    print(f"  -> {verdict}\n")


def main() -> None:
    df = pd.read_csv(DATA)
    print(f"Loaded {len(df):,} players from the Cookie Cats experiment.\n")
    n_c = int((df["version"] == "gate_30").sum())
    n_t = int((df["version"] == "gate_40").sum())
    srm_check(n_c, n_t)
    analyse(df, "retention_1")
    analyse(df, "retention_7")


if __name__ == "__main__":
    main()
