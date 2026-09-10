"""Cross-language assignment parity.

Two guards:
  1. Python must reproduce every case in the shared golden fixture.
  2. The JS SDK (via node) must reproduce the same fixture -- this is what
     proves the browser and the backend agree on every assignment.

The JS check is skipped (not failed) if node isn't installed, so the Python
suite still runs anywhere; CI runs node so parity is always enforced there.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from assignment import assign

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "fixtures" / "assignment_golden.json"


@pytest.fixture(scope="module")
def cases():
    if not GOLDEN.exists():
        pytest.skip("golden fixture missing -- run scripts.generate_parity_fixture")
    return json.loads(GOLDEN.read_text())


def test_python_reproduces_golden(cases):
    for c in cases:
        variants = [(k, p) for k, p in c["variants"]]
        assert assign(c["experiment_id"], c["user_id"], variants) == c["expected"]


def test_js_sdk_matches_golden():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed -- JS parity checked in CI")
    result = subprocess.run(
        [node, str(ROOT / "sdk" / "verify_parity.mjs")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"JS parity failed:\n{result.stdout}\n{result.stderr}"
    assert "PARITY OK" in result.stdout
