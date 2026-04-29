from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_explicit_literal_candidate_pool import build


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_explicit_literal_candidate_pool.py"


def test_build_explicit_literal_candidate_pool_help() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "--source-manifest" in result.stdout
    assert "--out-candidates" in result.stdout


def test_build_explicit_literal_candidate_pool_empty_input_fails_closed(tmp_path: Path) -> None:
    report = build(
        source_manifest=tmp_path / "missing_source_manifest.json",
        out_candidates=tmp_path / "candidate_rules.jsonl",
        dev_manifest=tmp_path / "dev20.json",
        holdout_manifest=tmp_path / "holdout20.json",
        summary_output=tmp_path / "summary.json",
        markdown_output=tmp_path / "summary.md",
    )

    assert report["candidate_pool_build_passed"] is False
    assert report["offline_only"] is True
    assert report["does_not_call_provider"] is True
    assert report["does_not_call_bfcl_or_model"] is True
    assert report["does_not_authorize_scorer"] is True
    assert "source_collection_manifest_missing" in report["blockers"]
    assert "extractor_implementation_not_enabled" in report["blockers"]
    assert (tmp_path / "candidate_rules.jsonl").read_text(encoding="utf-8") == ""
    dev = json.loads((tmp_path / "dev20.json").read_text(encoding="utf-8"))
    holdout = json.loads((tmp_path / "holdout20.json").read_text(encoding="utf-8"))
    assert dev["selected_case_ids"] == []
    assert holdout["selected_case_ids"] == []
