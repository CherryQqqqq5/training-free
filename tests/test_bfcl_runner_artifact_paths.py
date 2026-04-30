from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script_name", ["run_bfcl_v4_baseline.sh", "run_bfcl_v4_patch.sh"])
def test_bfcl_runners_keep_repairs_out_of_compact_artifact_dir(script_name: str) -> None:
    script = (REPO_ROOT / "scripts" / script_name).read_text(encoding="utf-8")

    assert 'REPAIRS_OUT="${GRC_BFCL_REPAIRS_OUT:-${RUN_ROOT}/diagnostics/repairs.jsonl}"' in script
    assert 'mkdir -p "$(dirname "${REPAIRS_OUT}")"' in script
    assert '--repairs-out "${REPAIRS_OUT}"' in script
    assert '--repairs-out "${ARTIFACT_DIR}/repairs.jsonl"' not in script
