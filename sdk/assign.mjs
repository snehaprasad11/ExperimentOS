// Deterministic variant assignment -- JS SDK side.
//
// This is the exact counterpart of assignment/core.py. Same FNV-1a 32-bit
// hash, same bucket mapping, so the SDK (browser) and the backend (Python)
// always agree on which variant a user gets. Parity is verified against a
// shared golden fixture in tests/fixtures/assignment_golden.json.
//
// No dependencies, no network call: assignment is a local hash.

export const BUCKETS = 10000;
const FNV_OFFSET = 0x811c9dc5; // FNV-1a 32-bit offset basis
const FNV_PRIME = 0x01000193; // FNV-1a 32-bit prime

/** FNV-1a 32-bit hash of a string's UTF-8 bytes (unsigned 32-bit). */
export function fnv1a32(text) {
  const bytes = new TextEncoder().encode(text); // UTF-8, matches Python
  let h = FNV_OFFSET;
  for (let i = 0; i < bytes.length; i++) {
    h ^= bytes[i];
    h = Math.imul(h, FNV_PRIME) >>> 0; // 32-bit multiply, keep unsigned
  }
  return h >>> 0;
}

/** Bucket 0..BUCKETS-1 for this (experiment, user). */
export function bucketOf(experimentId, userId) {
  return fnv1a32(`${experimentId}:${userId}`) % BUCKETS;
}

/**
 * Assign a user to a variant.
 * @param {string} experimentId
 * @param {string} userId
 * @param {[string, number][]} variants ordered [key, allocationPct], sum 100
 * @returns {string} the assigned variant key
 */
export function assign(experimentId, userId, variants) {
  const total = variants.reduce((s, [, pct]) => s + pct, 0);
  if (Math.abs(total - 100) > 1e-6) {
    throw new Error(`allocations must sum to 100, got ${total}`);
  }
  const b = bucketOf(experimentId, userId);
  let cumulative = 0;
  for (const [key, pct] of variants) {
    cumulative += (pct / 100) * BUCKETS;
    if (b < cumulative) return key;
  }
  return variants[variants.length - 1][0]; // float safety net
}
