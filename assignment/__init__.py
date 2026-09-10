"""Deterministic variant assignment (the ExperimentOS SDK core, Python side)."""

from .core import BUCKETS, assign, bucket_of, fnv1a_32

__all__ = ["BUCKETS", "assign", "bucket_of", "fnv1a_32"]
