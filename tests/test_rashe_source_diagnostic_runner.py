import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_source_real_trace_approved import APPROVED_CATEGORIES, FAILURE_BUCKETS
from scripts.run_rashe_source_diagnostic_compact import SIGNED_PUBLISH_FIELDS

SCRIPT = Path("scripts/run_rashe_source_diagnostic_compact.py")
SIGNED_ARGS = [
    sys.executable,
    str(SCRIPT),
    "--provider-profile",
    "Chuangzhi/Novacode",
    "--model",
    "gpt-5.2",
    "--categories",
    ",".join(APPROVED_CATEGORIES),
    "--min-cases-per-category",
    "20",
    "--max-cases-per-category",
    "50",
    "--max-total-cases",
    "200",
    "--output-root",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/",
    "--schema",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json",
    "--compact-sanitized-only",
    "--publish-fields",
    ",".join(SIGNED_PUBLISH_FIELDS),
    "--no-raw-trace",
    "--no-raw-payload",
    "--no-candidate-jsonl",
    "--no-scorer",
    "--dry-run",
    "--compact",
    "--strict",
]


def run_runner(*extra_args: str, replace: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    args = list(SIGNED_ARGS)
    if replace:
        for flag, value in replace.items():
            idx = args.index(flag)
            args[idx + 1] = value
    args.extend(extra_args)
    env = os.environ.copy()
    env["CHUANGZHI_API_KEY"] = "must-not-be-read"
    env["NOVACODE_API_KEY"] = "must-not-be-read"
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, env=env)


def load_summary(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.stdout, result.stderr
    return json.loads(result.stdout)


def test_dry_run_signed_plan_does_not_call_provider_or_read_api_key():
    result = run_runner()
    assert result.returncode == 0, result.stdout + result.stderr
    summary = load_summary(result)
    assert summary["rashe_source_diagnostic_compact_plan_passed"] is True
    assert summary["dry_run"] is True
    assert summary["provider_call_executed"] is False
    assert summary["api_key_read"] is False
    assert summary["diagnostic_written"] is False
    assert summary["approved_source_checker_passed"] is True
    assert summary["after_source_matrix_checker_passed"] is True
    assert summary["categories"] == list(APPROVED_CATEGORIES)
    assert summary["planned_case_count_per_category"] == 25
    assert len(summary["compact_artifact_plan"]) == len(APPROVED_CATEGORIES)

    for artifact in summary["compact_artifact_plan"]:
        assert set(artifact) == {
            "schema_version",
            "category",
            "case_count",
            "provider_call_count",
            "raw_payload_tracked_count",
            "forbidden_field_violation_count",
            "failure_bucket_counts",
            "candidate_generation_authorized",
            "scorer_authorized",
            "performance_evidence",
        }
        assert artifact["schema_version"] == "rashe_source_diagnostic_compact_v0"
        assert artifact["category"] in APPROVED_CATEGORIES
        assert artifact["case_count"] == 25
        assert artifact["provider_call_count"] == 0
        assert artifact["raw_payload_tracked_count"] == 0
        assert artifact["forbidden_field_violation_count"] == 0
        assert artifact["candidate_generation_authorized"] is False
        assert artifact["scorer_authorized"] is False
        assert artifact["performance_evidence"] is False
        assert set(artifact["failure_bucket_counts"]) == set(FAILURE_BUCKETS)
        assert all(count == 0 for count in artifact["failure_bucket_counts"].values())


def test_rejects_unsigned_provider_model_and_category():
    provider_result = run_runner(replace={"--provider-profile": "UnsignedProvider"})
    assert provider_result.returncode != 0
    provider_summary = load_summary(provider_result)
    assert "signed_provider_profile_invalid:'UnsignedProvider'" in provider_summary["blockers"]

    model_result = run_runner(replace={"--model": "gpt-4.1"})
    assert model_result.returncode != 0
    model_summary = load_summary(model_result)
    assert "signed_model_invalid:'gpt-4.1'" in model_summary["blockers"]

    category_result = run_runner(replace={"--categories": "agentic_web_search,not_signed"})
    assert category_result.returncode != 0
    category_summary = load_summary(category_result)
    assert "category_not_signed:not_signed" in category_summary["blockers"]


def test_rejects_case_count_bounds_outside_signed_range():
    min_result = run_runner(replace={"--min-cases-per-category": "19"})
    assert min_result.returncode != 0
    assert "min_cases_per_category_out_of_bounds:19" in load_summary(min_result)["blockers"]

    max_result = run_runner(replace={"--max-cases-per-category": "51"})
    assert max_result.returncode != 0
    assert "max_cases_per_category_out_of_bounds:51" in load_summary(max_result)["blockers"]

    total_result = run_runner(replace={"--max-total-cases": "99"})
    assert total_result.returncode != 0
    assert "max_total_cases_out_of_bounds:99" in load_summary(total_result)["blockers"]


def test_rejects_raw_output_path_and_forbidden_publish_fields():
    path_result = run_runner(replace={"--output-root": "outputs/artifacts/stage1_bfcl_acceptance/raw_trace/"})
    assert path_result.returncode != 0
    path_blockers = load_summary(path_result)["blockers"]
    assert any(blocker.startswith("output_root_not_signed:") for blocker in path_blockers)
    assert "raw_path_indicator_in_output_root:raw_trace" in path_blockers

    fields = ",".join([*SIGNED_PUBLISH_FIELDS, "gold"])
    field_result = run_runner(replace={"--publish-fields": fields})
    assert field_result.returncode != 0
    field_blockers = load_summary(field_result)["blockers"]
    assert "publish_fields_do_not_match_signed_schema" in field_blockers
    assert "forbidden_publish_field:gold" in field_blockers


def test_execute_switch_without_dry_run_still_refuses_execution():
    args = [item for item in SIGNED_ARGS if item != "--dry-run"]
    args.append("--execute-approved-source")
    env = os.environ.copy()
    env["CHUANGZHI_API_KEY"] = "must-not-be-read"
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, env=env)
    assert result.returncode != 0
    summary = load_summary(result)
    assert summary["execute_requested"] is True
    assert summary["provider_call_executed"] is False
    assert summary["api_key_read"] is False
    assert summary["diagnostic_written"] is False
    assert "execution_path_not_implemented_in_this_commit" in summary["blockers"]
