"""Deterministic variant assignment -- the heart of ExperimentOS.

A user is assigned to a variant by hashing (experiment_id + ":" + user_id)
into a bucket 0..9999, then mapping that bucket to a variant by cumulative
allocation. This is PURE and LOCAL: no network call, no server state,
perfectly reproducible.

The identical function is implemented in the JS SDK and verified to produce
the same assignments -- that cross-language parity is what lets the backend
audit the SDK's decisions.

Properties (spec FR4):
  - stable:       same user + experiment  -> always the same variant
  - independent:  assignment in one experiment is uncorrelated with another
  - proportional: over many users, variant shares match the allocation

Why FNV-1a (32-bit): it is trivially reimplementable identically in Python
and JavaScript -- no library, no 64-bit math -- so both sides agree exactly.
"""

from __future__ import annotations

BUCKETS = 10_000
_FNV_OFFSET = 0x811C9DC5      # FNV-1a 32-bit offset basis
_FNV_PRIME = 0x01000193       # FNV-1a 32-bit prime
_UINT32 = 0xFFFFFFFF


def fnv1a_32(text: str) -> int:
    """FNV-1a 32-bit hash of a string's UTF-8 bytes.

    Known test vectors (locked in tests, and the target for the JS SDK):
      ""        -> 0x811C9DC5
      "a"       -> 0xE40C292C
      "foobar"  -> 0xBF9CF968
    """
    h = _FNV_OFFSET
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * _FNV_PRIME) & _UINT32   # keep it 32-bit, exactly like JS
    return h


def bucket_of(experiment_id: str, user_id: str) -> int:
    """The user's bucket 0..BUCKETS-1 for this experiment."""
    return fnv1a_32(f"{experiment_id}:{user_id}") % BUCKETS


def assign(
    experiment_id: str,
    user_id: str,
    variants: list[tuple[str, float]],
) -> str:
    """Assign a user to a variant.

    Args:
        experiment_id: stable experiment key used in the hash
        user_id:       stable user identifier
        variants:      ordered list of (variant_key, allocation_pct), where
                       allocation_pct is in [0, 100] and the pcts sum to 100.

    Returns:
        the assigned variant_key.
    """
    total = sum(pct for _, pct in variants)
    if abs(total - 100.0) > 1e-6:
        raise ValueError(f"allocations must sum to 100, got {total}")

    b = bucket_of(experiment_id, user_id)
    cumulative = 0.0
    for key, pct in variants:
        cumulative += pct / 100.0 * BUCKETS
        if b < cumulative:
            return key
    return variants[-1][0]   # floating-point safety net for the last bucket
