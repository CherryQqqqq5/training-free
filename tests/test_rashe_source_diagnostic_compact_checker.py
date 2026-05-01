import json
import subprocess
import sys
from pathlib import Path

from scripts import check_rashe_source_diagnostic_compact as checker

RAW_SECRET = "raw provider payload must not leak"


def artifact(category: str, **overrides) -> dict:
    payload = {
        "schema_version": "rashe_source_diagnostic_compact_v0",
        "category": category,
        "case_count": 20,
        "provider_call_count": 20,
        "raw_payload_tracked_count": 0,
        "forbidden_field_violation_count": 0,
        "failure_bucket_counts": {bucket: 0 for bucket in checker.FAILURE_BUCKETS},
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }
    payload.update(overrides)
    return payload


def write_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for category in checker.APPROVED_CATEGORIES:
        (root / f"{category}.json").write_text(json.dumps(artifact(category), sort_keys=True) + "\n")


def test_source_diagnostic_compact_checker_passes_valid_fixture(tmp_path):
    root = tmp_path / "diag"
    write_root(root)

    summary = checker.check_root(root)

    assert summary["blockers"] == []
    assert summary["total_case_count"] == 160
    assert summary["category_counts"] == {category: 20 for category in checker.APPROVED_CATEGORIES}


def test_source_diagnostic_compact_checker_rejects_missing_and_extra_files(tmp_path):
    root = tmp_path / "diag"
    write_root(root)
    (root / "agentic_memory.json").unlink()
    (root / "extra.json").write_text("{}\n")

    blockers = checker.check_root(root)["blockers"]

    assert "source_diagnostic_files_not_exact_signed_set" in blockers
    assert "source_diagnostic_missing_file:agentic_memory.json" in blockers
    assert "source_diagnostic_extra_file:extra.json" in blockers


def test_source_diagnostic_compact_checker_rejects_raw_fields_and_downstream_flags(tmp_path):
    root = tmp_path / "diag"
    write_root(root)
    path = root / "agentic_web_search.json"
    payload = artifact(
        "agentic_web_search",
        case_id=RAW_SECRET,
        raw_payload_tracked_count=1,
        forbidden_field_violation_count=1,
        candidate_generation_authorized=True,
        scorer_authorized=True,
        performance_evidence=True,
    )
    path.write_text(json.dumps(payload, sort_keys=True) + "\n")

    blockers = checker.check_root(root)["blockers"]

    assert any("source_diagnostic_extra_field:agentic_web_search:case_id" in blocker for blocker in blockers)
    assert any("source_diagnostic_forbidden_field:agentic_web_search:case_id" in blocker for blocker in blockers)
    assert "source_diagnostic_raw_payload_tracked_count_not_zero:agentic_web_search:1" in blockers
    assert "source_diagnostic_forbidden_field_violation_count_not_zero:agentic_web_search:1" in blockers
    assert "source_diagnostic_candidate_generation_authorized_not_false:agentic_web_search:True" in blockers
    assert "source_diagnostic_scorer_authorized_not_false:agentic_web_search:True" in blockers
    assert "source_diagnostic_performance_evidence_not_false:agentic_web_search:True" in blockers
    assert all(RAW_SECRET not in blocker for blocker in blockers)


def test_source_diagnostic_compact_checker_rejects_bad_counts_and_bucket_taxonomy(tmp_path):
    root = tmp_path / "diag"
    write_root(root)
    payload = artifact("agentic_web_search", case_count=25, provider_call_count=21)
    payload["failure_bucket_counts"]["unsigned_bucket"] = 1
    (root / "agentic_web_search.json").write_text(json.dumps(payload, sort_keys=True) + "\n")

    blockers = checker.check_root(root)["blockers"]

    assert "source_diagnostic_case_count_not_signed:agentic_web_search:25" in blockers
    assert "source_diagnostic_provider_call_count_invalid:agentic_web_search:21" in blockers
    assert "source_diagnostic_failure_bucket_keys_invalid:agentic_web_search" in blockers


def test_source_diagnostic_compact_checker_cli_missing_default_root_is_precise():
    result = subprocess.run([sys.executable, "scripts/check_rashe_source_diagnostic_compact.py", "--compact"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)

    assert result.returncode == 0
    summary = json.loads(result.stdout)
    assert summary["rashe_source_diagnostic_compact_passed"] is False
    assert any(blocker.startswith("source_diagnostic_root_missing:") for blocker in summary["blockers"])


def test_source_diagnostic_compact_checker_cli_strict_passes_fixture(tmp_path):
    root = tmp_path / "diag"
    write_root(root)
    result = subprocess.run([sys.executable, "scripts/check_rashe_source_diagnostic_compact.py", "--root", str(root), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_source_diagnostic_compact_passed"] is True
    assert summary["total_case_count"] == 160
