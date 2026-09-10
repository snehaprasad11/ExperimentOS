"""Exposure tracking -- the analysis population, and where validity is won.

The single most important distinction in ExperimentOS:

  ASSIGNMENT happens for every user the SDK evaluates.
  EXPOSURE   happens only when the user actually SEES the variant.

Analysing on assignment instead of exposure includes users who never reached
the feature, diluting every effect toward zero. So the analysis population is
the set of EXPOSED users, and this module owns it.

Three rules the spec insists on, all enforced here without a database (the
FastAPI + Postgres layer will later wrap this same logic):

  1. Idempotency      -- a repeated event_id is ignored (retries can't inflate
                         counts).
  2. First exposure wins -- a user belongs to exactly one variant: the one they
                         were first exposed to (earliest exposed_at).
  3. Leakage detection -- if the same user is exposed to a *different* variant,
                         that is a `multi_variant_user` quality signal, not a
                         silent overwrite.

It also supports an ASSIGNMENT AUDIT: given the experiment's allocation, the
backend re-derives each exposed user's variant with the same deterministic
hash the SDK used, and flags any exposure that disagrees.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from assignment import assign


@dataclass(frozen=True)
class ExposureEvent:
    experiment_id: str
    user_id: str
    variant_key: str
    event_id: str            # idempotency key
    exposed_at: datetime


@dataclass(frozen=True)
class QualityFinding:
    kind: str                # 'multi_variant_user' | 'assignment_mismatch'
    experiment_id: str
    user_id: str
    severity: str            # 'warn' | 'critical'
    detail: dict


@dataclass
class _Canonical:
    """The canonical (first) exposure for a user, plus every variant seen."""
    variant_key: str
    exposed_at: datetime
    event_id: str
    variants_seen: set[str] = field(default_factory=set)


class ExposureTracker:
    """Accumulates exposure events into the analysis population."""

    def __init__(self) -> None:
        # (experiment_id, user_id) -> canonical exposure
        self._canonical: dict[tuple[str, str], _Canonical] = {}
        self._seen_event_ids: set[str] = set()

    def record(self, e: ExposureEvent) -> str:
        """Record one exposure. Returns: 'accepted' | 'duplicate' | 'leaked'.

        'leaked' means this event was for a different variant than the user's
        canonical exposure -- the population is unchanged, but a leakage signal
        is now detectable via `quality_findings()`.
        """
        if e.event_id in self._seen_event_ids:
            return "duplicate"
        self._seen_event_ids.add(e.event_id)

        key = (e.experiment_id, e.user_id)
        canon = self._canonical.get(key)
        if canon is None:
            self._canonical[key] = _Canonical(
                variant_key=e.variant_key,
                exposed_at=e.exposed_at,
                event_id=e.event_id,
                variants_seen={e.variant_key},
            )
            return "accepted"

        canon.variants_seen.add(e.variant_key)
        # First exposure wins: keep the earliest exposed_at as canonical.
        if e.exposed_at < canon.exposed_at:
            canon.variant_key = e.variant_key
            canon.exposed_at = e.exposed_at
            canon.event_id = e.event_id

        return "leaked" if len(canon.variants_seen) > 1 else "accepted"

    # --- the analysis population -----------------------------------------
    def exposed_counts(self, experiment_id: str) -> Counter[str]:
        """First-exposure user counts per variant for one experiment."""
        counts: Counter[str] = Counter()
        for (exp, _uid), canon in self._canonical.items():
            if exp == experiment_id:
                counts[canon.variant_key] += 1
        return counts

    def exposed_users(self, experiment_id: str) -> int:
        return sum(1 for (exp, _u) in self._canonical if exp == experiment_id)

    def canonical_variant(self, experiment_id: str, user_id: str) -> str | None:
        canon = self._canonical.get((experiment_id, user_id))
        return canon.variant_key if canon else None

    # --- quality signals --------------------------------------------------
    def leaked_users(self, experiment_id: str) -> list[str]:
        """Users exposed to more than one variant (cross-variant leakage)."""
        return [
            uid for (exp, uid), canon in self._canonical.items()
            if exp == experiment_id and len(canon.variants_seen) > 1
        ]

    def quality_findings(self, experiment_id: str) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        for uid in self.leaked_users(experiment_id):
            canon = self._canonical[(experiment_id, uid)]
            findings.append(QualityFinding(
                kind="multi_variant_user",
                experiment_id=experiment_id,
                user_id=uid,
                severity="critical",
                detail={"variants_seen": sorted(canon.variants_seen)},
            ))
        return findings

    def audit_assignments(
        self,
        experiment_id: str,
        variants: list[tuple[str, float]],
    ) -> list[QualityFinding]:
        """Re-derive each exposed user's variant and flag disagreements.

        This is the independent backend audit described in the architecture:
        the SDK assigned the user client-side; here the backend recomputes the
        assignment from the same deterministic hash and checks the exposure
        matches. A mismatch means config drift, a stale SDK, or tampering.
        """
        findings: list[QualityFinding] = []
        for (exp, uid), canon in self._canonical.items():
            if exp != experiment_id:
                continue
            expected = assign(experiment_id, uid, variants)
            if expected != canon.variant_key:
                findings.append(QualityFinding(
                    kind="assignment_mismatch",
                    experiment_id=experiment_id,
                    user_id=uid,
                    severity="critical",
                    detail={"exposed_variant": canon.variant_key,
                            "expected_variant": expected},
                ))
        return findings
