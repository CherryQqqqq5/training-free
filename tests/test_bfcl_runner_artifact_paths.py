from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_baseline_runner_keeps_repairs_out_of_compact_artifact_dir() -> None:
    script = (REPO_ROOT / "scripts" / "run_bfcl_v4_baseline.sh").read_text(encoding="utf-8")

    assert 'REPAIRS_OUT="${GRC_BFCL_REPAIRS_OUT:-${RUN_ROOT}/diagnostics/repairs.jsonl}"' in script
    assert 'mkdir -p "$(dirname "${REPAIRS_OUT}")"' in script
    assert '--repairs-out "${REPAIRS_OUT}"' in script
    assert '--repairs-out "${ARTIFACT_DIR}/repairs.jsonl"' not in script
