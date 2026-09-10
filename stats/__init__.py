"""ExperimentOS statistics core.

A pure, dependency-light package: given experiment data, compute the
effect, the uncertainty, and the evidence -- correctly. Everything here
is independently unit-tested and cross-checked against statsmodels.
"""

from .proportions import TwoProportionResult, two_proportion_test

__all__ = ["TwoProportionResult", "two_proportion_test"]
