"""Generate the cross-language assignment parity fixture.

Writes tests/fixtures/assignment_golden.json: a list of assignment cases
that BOTH the Python core and the JS SDK must reproduce exactly. Python is
already pinned to the known FNV-1a vectors, so it defines the contract here;
the JS SDK is then verified against the same file.

Run:  python -m scripts.generate_parity_fixture
"""

import json
from pathlib import Path

from assignment import assign

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "assignment_golden.json"

VARIANT_SETS = {
    "two_way": [["control", 50.0], ["treatment", 50.0]],
    "uneven": [["control", 80.0], ["treatment", 20.0]],
    "three_way": [["a", 34.0], ["b", 33.0], ["c", 33.0]],
}


def main() -> None:
    cases = []
    for exp in ["pricing_page_v2", "checkout_flow", "onboarding_2026"]:
        for vname, variants in VARIANT_SETS.items():
            for i in range(200):
                uid = f"user_{i}"
                cases.append({
                    "experiment_id": exp,
                    "user_id": uid,
                    "variant_set": vname,
                    "variants": variants,
                    "expected": assign(exp, uid, [(k, p) for k, p in variants]),
                })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cases, indent=2))
    print(f"wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
