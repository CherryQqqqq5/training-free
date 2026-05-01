import json
import os
import subprocess
import sys
from pathlib import Path

import scripts.run_rashe_source_diagnostic_compact as runner
import scripts.rashe_source_diagnostic_compact_adapter as signed_adapter
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
    "20",
    "--max-total-cases",
    "160",
    "--output-root",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/",
    "--schema",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json",
    "--source-input-root",
    "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/",
    "--compact-sanitized-only",
    "--publish-fields",
    ",".join(SIGNED_PUBLISH_FIELDS),
    "--no-raw-trace",
    "--no-raw-payload",
    "--no-candidate-jsonl",
    "--no-scorer",
    "--execution-adapter",
    "scripts.rashe_source_diagnostic_compact_adapter:run_compact_source_diagnostic",
    "--provider-client-factory",
    "scripts.rashe_source_provider_client:build_chuangzhi_novacode_source_provider_client",
    "--source-case-provider",
    "scripts.rashe_source_case_provider:build_signed_source_case_provider",
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


def signed_execute_args() -> object:
    args = [item for item in SIGNED_ARGS if item not in {"--dry-run", "--compact", "--strict"}]
    args.extend(["--execute-approved-source", "--skip-preflight-checks"])
    return runner.build_parser().parse_args(args[2:])


def compact_artifact(category: str, *, provider_call_count: int = 0, **overrides) -> dict:
    artifact = {
        "schema_version": "rashe_source_diagnostic_compact_v0",
        "category": category,
        "case_count": 20,
        "provider_call_count": provider_call_count,
        "raw_payload_tracked_count": 0,
        "forbidden_field_violation_count": 0,
        "failure_bucket_counts": {bucket: 0 for bucket in FAILURE_BUCKETS},
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }
    artifact.update(overrides)
    return artifact


def test_dry_run_signed_plan_does_not_call_provider_or_read_api_key():
    result = run_runner()
    assert result.returncode == 0, result.stdout + result.stderr
    summary = load_summary(result)
    assert summary["rashe_source_diagnostic_compact_plan_passed"] is True
    assert summary["dry_run"] is True
    assert summary["provider_call_executed"] is False
    assert summary["api_key_read"] is False
    assert summary["diagnostic_written"] is False
    assert summary["execution_adapter_status"] == "loadable"
    assert summary["provider_client_factory_status"] == "loadable"
    assert summary["source_case_provider_status"] == "loadable"
    assert summary["source_case_provider_injected"] is False
    assert summary["provider_client_injected"] is False
    assert summary["approved_source_checker_passed"] is True
    assert summary["after_source_matrix_checker_passed"] is True
    assert summary["categories"] == list(APPROVED_CATEGORIES)
    assert summary["planned_case_count_per_category"] == 20
    assert summary["planned_total_cases"] == 160
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
        assert artifact["case_count"] == 20
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
    assert "categories_do_not_match_signed_runbook" in category_summary["blockers"]
    assert "category_not_signed:not_signed" in category_summary["blockers"]


def test_rejects_counts_outside_signed_8x20_scope():
    min_result = run_runner(replace={"--min-cases-per-category": "19"})
    assert min_result.returncode != 0
    assert "min_cases_per_category_not_signed:19" in load_summary(min_result)["blockers"]

    max_result = run_runner(replace={"--max-cases-per-category": "50"})
    assert max_result.returncode != 0
    assert "max_cases_per_category_not_signed:50" in load_summary(max_result)["blockers"]

    twenty_five_result = run_runner(replace={"--max-cases-per-category": "25"})
    assert twenty_five_result.returncode != 0
    assert "max_cases_per_category_not_signed:25" in load_summary(twenty_five_result)["blockers"]

    total_result = run_runner(replace={"--max-total-cases": "200"})
    assert total_result.returncode != 0
    assert "max_total_cases_not_signed:200" in load_summary(total_result)["blockers"]


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


def test_signed_execute_adapter_boundary_reports_missing_provider_transport_without_key_read():
    args = signed_execute_args()
    schema = runner.load_json(args.schema)
    execution = runner.execute_approved_source(
        args,
        list(APPROVED_CATEGORIES),
        20,
        schema,
        write_artifacts=False,
    )
    assert execution["execution_adapter_status"] == "provider_transport_missing"
    assert execution["provider_call_executed"] is False
    assert execution["api_key_read"] is False
    assert execution["diagnostic_written"] is False
    assert "provider_transport_missing" in execution["blockers"]
    assert "execution_path_not_implemented_in_this_commit" not in execution["blockers"]


def test_invalid_execution_adapter_function_has_explicit_blocker():
    result = run_runner(replace={"--execution-adapter": "scripts.rashe_source_diagnostic_compact_adapter:not_a_function"})
    assert result.returncode != 0
    blockers = load_summary(result)["blockers"]
    assert "execution_adapter_not_signed:'scripts.rashe_source_diagnostic_compact_adapter:not_a_function'" in blockers
    assert "source_execution_adapter_callable_missing" in blockers


def test_invalid_provider_client_factory_has_explicit_blocker():
    result = run_runner(replace={"--provider-client-factory": "scripts.rashe_source_provider_client:not_a_factory"})
    assert result.returncode != 0
    blockers = load_summary(result)["blockers"]
    assert "provider_client_factory_not_signed:'scripts.rashe_source_provider_client:not_a_factory'" in blockers
    assert "provider_client_factory_callable_missing" in blockers


def test_invalid_source_case_provider_has_explicit_blocker():
    result = run_runner(replace={"--source-case-provider": "scripts.rashe_source_case_provider:not_a_provider"})
    assert result.returncode != 0
    blockers = load_summary(result)["blockers"]
    assert "source_case_provider_not_signed:'scripts.rashe_source_case_provider:not_a_provider'" in blockers
    assert "source_case_provider_callable_missing" in blockers


def test_signed_adapter_builds_schema_bound_artifacts_from_sanitized_counters():
    args = signed_execute_args()
    request = runner.build_adapter_request(args, list(APPROVED_CATEGORIES), 20)
    records = [
        {
            "category": category,
            "case_count": 20,
            "provider_call_count": 20,
            "raw_payload_tracked_count": 0,
            "forbidden_field_violation_count": 0,
            "failure_bucket_counts": {bucket: 0 for bucket in FAILURE_BUCKETS},
            "candidate_generation_authorized": False,
            "scorer_authorized": False,
            "performance_evidence": False,
        }
        for category in APPROVED_CATEGORIES
    ]
    artifacts = signed_adapter.build_compact_artifacts_from_sanitized_counters(records, request)
    assert [artifact["category"] for artifact in artifacts] == list(APPROVED_CATEGORIES)
    assert sum(artifact["case_count"] for artifact in artifacts) == 160
    for artifact in artifacts:
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
        assert artifact["case_count"] == 20
        assert artifact["provider_call_count"] == 20
        assert artifact["raw_payload_tracked_count"] == 0
        assert artifact["forbidden_field_violation_count"] == 0
        assert artifact["candidate_generation_authorized"] is False
        assert artifact["scorer_authorized"] is False
        assert artifact["performance_evidence"] is False


def test_signed_adapter_rejects_raw_or_forbidden_counter_fields():
    args = signed_execute_args()
    request = runner.build_adapter_request(args, list(APPROVED_CATEGORIES), 20)
    records = [
        {
            "category": category,
            "case_count": 20,
            "provider_call_count": 20,
            "raw_payload_tracked_count": 0,
            "forbidden_field_violation_count": 0,
            "failure_bucket_counts": {bucket: 0 for bucket in FAILURE_BUCKETS},
            "candidate_generation_authorized": False,
            "scorer_authorized": False,
            "performance_evidence": False,
        }
        for category in APPROVED_CATEGORIES
    ]
    records[0]["case_id"] = "raw-case-id"
    try:
        signed_adapter.build_compact_artifacts_from_sanitized_counters(records, request)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("adapter accepted raw case_id")
    assert "adapter_counter_extra_field:case_id" in message
    assert "adapter_forbidden_counter_field:case_id" in message


def test_execute_path_accepts_mock_adapter_without_real_provider_or_key_read():
    args = signed_execute_args()
    schema = runner.load_json(args.schema)
    calls = []

    def fake_adapter(request: dict) -> list[dict]:
        calls.append(request)
        assert "provider_client" in request
        assert "api_key" not in " ".join(str(key).lower() for key in request)
        assert request["case_count_per_category"] == 20
        assert request["max_total_cases"] == 160
        assert request["candidate_generation_authorized"] is False
        assert request["scorer_authorized"] is False
        assert request["performance_evidence"] is False
        return [compact_artifact(category, provider_call_count=0) for category in APPROVED_CATEGORIES]

    execution = runner.execute_approved_source(
        args,
        list(APPROVED_CATEGORIES),
        20,
        schema,
        adapter_func=fake_adapter,
        write_artifacts=False,
    )
    assert calls
    assert execution["blockers"] == []
    assert execution["execution_adapter_status"] == "loaded"
    assert execution["provider_call_executed"] is False
    assert execution["api_key_read"] is False
    assert execution["diagnostic_written"] is False
    assert execution["written_artifacts"] == []
    assert len(execution["executed_artifacts"]) == len(APPROVED_CATEGORIES)


def test_execute_path_rejects_forbidden_fields_and_true_downstream_flags():
    args = signed_execute_args()
    schema = runner.load_json(args.schema)

    def bad_adapter(_: dict) -> list[dict]:
        artifacts = [compact_artifact(category) for category in APPROVED_CATEGORIES]
        artifacts[0]["gold"] = "raw forbidden answer"
        artifacts[1]["candidate_generation_authorized"] = True
        artifacts[2]["scorer_authorized"] = True
        artifacts[3]["performance_evidence"] = True
        artifacts[4]["raw_payload_tracked_count"] = 1
        artifacts[5]["forbidden_field_violation_count"] = 1
        return artifacts

    execution = runner.execute_approved_source(
        args,
        list(APPROVED_CATEGORIES),
        20,
        schema,
        adapter_func=bad_adapter,
        write_artifacts=False,
    )
    blockers = execution["blockers"]
    assert "compact_artifact_fields_do_not_match_schema_required" in blockers
    assert "forbidden_artifact_field:gold" in blockers
    assert "compact_artifact_candidate_generation_authorized_not_false:True" in blockers
    assert "compact_artifact_scorer_authorized_not_false:True" in blockers
    assert "compact_artifact_performance_evidence_not_false:True" in blockers
    assert "compact_artifact_raw_payload_tracked_count_not_zero:1" in blockers
    assert "compact_artifact_forbidden_field_violation_count_not_zero:1" in blockers
    assert execution["diagnostic_written"] is False


def test_execute_path_rejects_adapter_category_and_count_mismatch():
    args = signed_execute_args()
    schema = runner.load_json(args.schema)

    def bad_adapter(_: dict) -> list[dict]:
        artifacts = [compact_artifact(category) for category in APPROVED_CATEGORIES]
        artifacts[0]["case_count"] = 25
        artifacts[1]["provider_call_count"] = 21
        artifacts[-1]["category"] = "not_signed"
        return artifacts

    execution = runner.execute_approved_source(
        args,
        list(APPROVED_CATEGORIES),
        20,
        schema,
        adapter_func=bad_adapter,
        write_artifacts=False,
    )
    blockers = execution["blockers"]
    assert "source_execution_adapter_categories_mismatch" in blockers
    assert "compact_artifact_case_count_not_signed:25" in blockers
    assert "compact_artifact_provider_call_count_invalid:21" in blockers
    assert "compact_artifact_category_not_signed:not_signed" in blockers
    assert execution["diagnostic_written"] is False


def test_execute_path_with_mock_provider_factory_validates_and_writes_temp_compact_artifacts(tmp_path):
    args = signed_execute_args()
    args.output_root = tmp_path
    schema = runner.load_json(args.schema)

    def fake_adapter(request: dict) -> list[dict]:
        assert callable(request["provider_client"])
        return [compact_artifact(category, provider_call_count=20) for category in APPROVED_CATEGORIES]

    def fake_factory(request: dict):
        assert request["case_count_per_category"] == 20
        assert request["max_total_cases"] == 160

        def client(_: dict) -> dict:
            raise AssertionError("fake adapter should not call provider client")

        return client

    execution = runner.execute_approved_source(
        args,
        list(APPROVED_CATEGORIES),
        20,
        schema,
        adapter_func=fake_adapter,
        provider_client_factory=fake_factory,
        write_artifacts=True,
    )
    assert execution["blockers"] == []
    assert execution["provider_call_executed"] is True
    assert execution["api_key_read"] is False
    assert execution["diagnostic_written"] is True
    files = sorted(tmp_path.glob("*.json"))
    assert len(files) == 8
    secret = "mock-secret-must-not-leak"
    for path in files:
        text = path.read_text()
        assert secret not in text
        payload = json.loads(text)
        assert set(payload) == {
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
        assert payload["case_count"] == 20
        assert payload["provider_call_count"] == 20
        assert payload["raw_payload_tracked_count"] == 0
        assert payload["candidate_generation_authorized"] is False
        assert payload["scorer_authorized"] is False
        assert payload["performance_evidence"] is False


def test_execute_path_with_real_adapter_and_mock_provider_factory_no_write():
    args = signed_execute_args()
    schema = runner.load_json(args.schema)

    def fake_factory(_: dict):
        def client(category_request: dict) -> dict:
            return {
                "category": category_request["category"],
                "case_count": 20,
                "provider_call_count": 20,
                "failure_bucket_counts": {bucket: 0 for bucket in FAILURE_BUCKETS},
                "raw_payload_tracked_count": 0,
                "forbidden_field_violation_count": 0,
                "candidate_generation_authorized": False,
                "scorer_authorized": False,
                "performance_evidence": False,
            }

        return client

    execution = runner.execute_approved_source(
        args,
        list(APPROVED_CATEGORIES),
        20,
        schema,
        provider_client_factory=fake_factory,
        write_artifacts=False,
    )
    assert execution["blockers"] == []
    assert execution["provider_call_executed"] is True
    assert execution["api_key_read"] is False
    assert execution["diagnostic_written"] is False
    assert len(execution["executed_artifacts"]) == 8
    assert sum(item["provider_call_count"] for item in execution["executed_artifacts"]) == 160
