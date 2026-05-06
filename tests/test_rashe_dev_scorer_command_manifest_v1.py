from __future__ import annotations

import json
from pathlib import Path

from scripts.check_rashe_dev_scorer_command_manifest_v1 import DEFAULT_MANIFEST, validate_manifest, check


def _manifest() -> dict:
    return json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))


def test_command_manifest_is_pending_and_fail_closed() -> None:
    manifest = _manifest()
    assert validate_manifest(manifest) == []
    assert manifest["approval_status"] == "pending"
    assert manifest["authorized"] is False
    assert manifest["execution_started"] is False
    assert manifest["one_attempt_only"] is True
    assert manifest["dev_smoke_only"] is True
    assert manifest["max_dev_cases"] == 12
    assert manifest["performance_evidence"] is False
    assert manifest["huawei_acceptance_ready"] is False


def test_command_manifest_rejects_authorized_or_started() -> None:
    for key in ("authorized", "execution_started", "performance_evidence", "performance_claim_allowed", "sota_3pp_claim_ready", "huawei_acceptance_ready", "raw_outputs_committed"):
        manifest = _manifest()
        manifest[key] = True
        blockers = validate_manifest(manifest, check_existing_outputs=False)
        assert any(key in blocker for blocker in blockers)


def test_command_manifest_rejects_forbidden_command_drift() -> None:
    manifest = _manifest()
    manifest["allowed_command_patterns"].append("PYTHONPATH=.:src .venv/bin/python scripts/check_stage1_bfcl_performance_ready.py --compact --strict")
    blockers = validate_manifest(manifest, check_existing_outputs=False)
    assert "allowed_command_patterns_invalid" in blockers or "allowed_command_patterns_include_forbidden" in blockers

    manifest = _manifest()
    manifest["command_templates"]["baseline_dev_smoke"]["template"].append("holdout")
    blockers = validate_manifest(manifest, check_existing_outputs=False)
    assert "forbidden_command_pattern:baseline_dev_smoke" in blockers


def test_command_manifest_rejects_raw_leakage_fields() -> None:
    for key in ("prompt_text", "raw_trace", "provider_exchange", "case_id", "gold", "expected", "tool_args", "scorer_diff", "candidate_output"):
        manifest = _manifest()
        manifest[key] = "redacted"
        blockers = validate_manifest(manifest, check_existing_outputs=False)
        assert any("forbidden_key" in blocker for blocker in blockers)


def test_command_manifest_require_report_mode(tmp_path: Path) -> None:
    missing = tmp_path / "missing_cost_latency_report.json"
    summary = check(DEFAULT_MANIFEST, require_report=missing)
    assert summary["rashe_dev_scorer_command_manifest_v1_passed"] is False
    assert any("required_report_missing" in blocker for blocker in summary["blockers"])
