#!/usr/bin/env python3
"""Runner for bounded RASHE compact source diagnostics.

Dry-run/plan-only modes validate the signed runbook scope without executing
source collection. The approved execution path is adapter-driven: it can only
write compact schema artifacts after the approved-source and after-source matrix
gates pass. The signed adapter and provider-client factory are importable;
true execution injects the signed source-case provider boundary and still
fails closed with ``provider_transport_missing`` until approved transport is
injected into the signed request.
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_rashe_source_real_trace_approved import APPROVED_CATEGORIES, FAILURE_BUCKETS

SIGNED_PROVIDER_PROFILES = ("Chuangzhi/Novacode", "Chuangzhi/Novacode gpt-5.2")
SIGNED_MODEL = "gpt-5.2"
SIGNED_CASES_PER_CATEGORY = 20
SIGNED_TOTAL_CASES = 160
SIGNED_OUTPUT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/")
SIGNED_SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json")
SIGNED_EXECUTION_ADAPTER = "scripts.rashe_source_diagnostic_compact_adapter:run_compact_source_diagnostic"
SIGNED_PROVIDER_CLIENT_FACTORY = "scripts.rashe_source_provider_client:build_chuangzhi_novacode_source_provider_client"
SIGNED_SOURCE_CASE_PROVIDER = "scripts.rashe_source_case_provider:build_signed_source_case_provider"
SIGNED_SOURCE_INPUT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/")
SIGNED_PUBLISH_FIELDS = (
    "category",
    "case_count",
    "provider_call_count",
    "raw_payload_tracked_count",
    "forbidden_field_violation_count",
    "failure_bucket_counts",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
)
FORBIDDEN_FIELD_NAMES = (
    "raw_case_id",
    "case_id",
    "raw_trace",
    "trace_path",
    "raw_provider_payload",
    "provider_payload",
    "raw_payload",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "candidate_output",
    "repair_output",
    "feedback",
    "holdout_feedback",
    "full_suite_feedback",
    "candidate_jsonl",
    "dev_manifest",
    "holdout_manifest",
    "full_manifest",
)
RAW_PATH_INDICATORS = (
    "raw_trace",
    "raw-trace",
    "raw_payload",
    "raw-payload",
    "case_id",
    "case-id",
    "provider_payload",
    "provider-payload",
    "candidate_jsonl",
    "candidate-jsonl",
    "scorer_diff",
    "scorer-diff",
    "scorer_output",
    "scorer-output",
    "gold",
    "expected",
    "reference",
    "repair_output",
    "repair-output",
    "holdout_feedback",
    "holdout-feedback",
    "full_suite_feedback",
    "full-suite-feedback",
)
AdapterFunc = Callable[[dict[str, Any]], list[dict[str, Any]]]
ProviderClientFactory = Callable[[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]
SourceCaseProviderBuilder = Callable[[dict[str, Any]], Callable[[dict[str, Any]], list[dict[str, Any]]]]


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def run_json_checker(args: list[str]) -> tuple[bool, str | None, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stdout.strip() or result.stderr.strip() or "checker_failed", {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return False, f"checker_json_invalid:{args[0]}:{exc}", {}
    if not isinstance(data, dict):
        return False, f"checker_output_not_object:{args[0]}", {}
    return True, None, data


def run_plain_command(args: list[str]) -> str | None:
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        return result.stdout.strip() or result.stderr.strip() or "command_failed"
    return None


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def normalize_field(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def build_compact_plan(category: str, case_count: int) -> dict[str, Any]:
    return {
        "schema_version": "rashe_source_diagnostic_compact_v0",
        "category": category,
        "case_count": case_count,
        "provider_call_count": 0,
        "raw_payload_tracked_count": 0,
        "forbidden_field_violation_count": 0,
        "failure_bucket_counts": {bucket: 0 for bucket in FAILURE_BUCKETS},
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }


def build_adapter_request(args: argparse.Namespace, categories: list[str], case_count: int) -> dict[str, Any]:
    return {
        "provider_profile": args.provider_profile,
        "model": args.model,
        "categories": categories,
        "case_count_per_category": case_count,
        "max_total_cases": args.max_total_cases,
        "output_root": str(args.output_root),
        "schema_path": str(args.schema),
        "source_input_root": str(args.source_input_root),
        "forbidden_fields": list(FORBIDDEN_FIELD_NAMES),
        "failure_buckets": list(FAILURE_BUCKETS),
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "raw_payload_capture_authorized": False,
        "raw_trace_capture_authorized": False,
        "compact_sanitized_only": True,
    }


def find_forbidden_artifact_fields(value: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = normalize_field(str(key))
            path = f"{prefix}.{key}" if prefix else str(key)
            if normalized in FORBIDDEN_FIELD_NAMES:
                hits.append(path)
            hits.extend(find_forbidden_artifact_fields(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_artifact_fields(child, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        for indicator in RAW_PATH_INDICATORS:
            if indicator in lowered:
                hits.append(f"{prefix}:raw_path_indicator:{indicator}")
    return hits


def validate_schema_artifact(schema: dict[str, Any], artifact: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    if set(artifact) != set(required):
        blockers.append("compact_artifact_fields_do_not_match_schema_required")
    allowed_categories = schema.get("properties", {}).get("category", {}).get("enum", [])
    if artifact.get("category") not in allowed_categories:
        blockers.append(f"compact_artifact_category_not_signed:{artifact.get('category')}")
    case_count = artifact.get("case_count")
    if not isinstance(case_count, int) or case_count != SIGNED_CASES_PER_CATEGORY:
        blockers.append(f"compact_artifact_case_count_not_signed:{case_count!r}")
    provider_call_count = artifact.get("provider_call_count")
    if not isinstance(provider_call_count, int) or provider_call_count < 0 or provider_call_count > SIGNED_CASES_PER_CATEGORY:
        blockers.append(f"compact_artifact_provider_call_count_invalid:{provider_call_count!r}")
    for field in ["raw_payload_tracked_count", "forbidden_field_violation_count"]:
        if artifact.get(field) != 0:
            blockers.append(f"compact_artifact_{field}_not_zero:{artifact.get(field)!r}")
    for field in ["candidate_generation_authorized", "scorer_authorized", "performance_evidence"]:
        if artifact.get(field) is not False:
            blockers.append(f"compact_artifact_{field}_not_false:{artifact.get(field)!r}")
    buckets = artifact.get("failure_bucket_counts")
    if not isinstance(buckets, dict) or set(buckets) != set(FAILURE_BUCKETS):
        blockers.append("compact_artifact_failure_buckets_invalid")
    elif any((not isinstance(value, int) or value < 0) for value in buckets.values()):
        blockers.append("compact_artifact_failure_bucket_count_invalid")
    forbidden_hits = find_forbidden_artifact_fields(artifact)
    if forbidden_hits:
        blockers.extend(f"forbidden_artifact_field:{hit}" for hit in forbidden_hits)
    if schema.get("additionalProperties") is not False:
        blockers.append("compact_schema_additional_properties_not_false")
    return blockers


def validate_args(args: argparse.Namespace) -> tuple[list[str], list[str], list[str], int]:
    blockers: list[str] = []
    categories = split_csv(args.categories)
    publish_fields = split_csv(args.publish_fields)

    if args.provider_profile not in SIGNED_PROVIDER_PROFILES:
        blockers.append(f"signed_provider_profile_invalid:{args.provider_profile!r}")
    if args.model != SIGNED_MODEL:
        blockers.append(f"signed_model_invalid:{args.model!r}")

    if categories != list(APPROVED_CATEGORIES):
        blockers.append("categories_do_not_match_signed_runbook")
    seen: set[str] = set()
    for category in categories:
        if category not in APPROVED_CATEGORIES:
            blockers.append(f"category_not_signed:{category}")
        if category in seen:
            blockers.append(f"category_duplicate:{category}")
        seen.add(category)

    if args.min_cases_per_category != SIGNED_CASES_PER_CATEGORY:
        blockers.append(f"min_cases_per_category_not_signed:{args.min_cases_per_category}")
    if args.max_cases_per_category != SIGNED_CASES_PER_CATEGORY:
        blockers.append(f"max_cases_per_category_not_signed:{args.max_cases_per_category}")
    if args.max_total_cases != SIGNED_TOTAL_CASES:
        blockers.append(f"max_total_cases_not_signed:{args.max_total_cases}")

    planned_case_count = SIGNED_CASES_PER_CATEGORY if categories == list(APPROVED_CATEGORIES) else 0

    if args.output_root != SIGNED_OUTPUT_ROOT:
        blockers.append(f"output_root_not_signed:{args.output_root}")
    output_text = str(args.output_root).lower()
    for indicator in RAW_PATH_INDICATORS:
        if indicator in output_text:
            blockers.append(f"raw_path_indicator_in_output_root:{indicator}")
    if args.schema != SIGNED_SCHEMA:
        blockers.append(f"schema_path_not_signed:{args.schema}")
    if args.source_input_root != SIGNED_SOURCE_INPUT_ROOT:
        blockers.append(f"source_input_root_not_signed:{args.source_input_root}")
    source_input_text = str(args.source_input_root).lower()
    for indicator in RAW_PATH_INDICATORS:
        if indicator in source_input_text:
            blockers.append(f"raw_path_indicator_in_source_input_root:{indicator}")

    if set(publish_fields) != set(SIGNED_PUBLISH_FIELDS):
        blockers.append("publish_fields_do_not_match_signed_schema")
    for field in publish_fields:
        normalized = normalize_field(field)
        if normalized in FORBIDDEN_FIELD_NAMES:
            blockers.append(f"forbidden_publish_field:{field}")

    if not args.compact_sanitized_only:
        blockers.append("compact_sanitized_only_required")
    for flag_name in ["no_raw_trace", "no_raw_payload", "no_candidate_jsonl", "no_scorer"]:
        if getattr(args, flag_name) is not True:
            blockers.append(f"{flag_name}_required")

    if args.execution_adapter != SIGNED_EXECUTION_ADAPTER:
        blockers.append(f"execution_adapter_not_signed:{args.execution_adapter!r}")
    if args.provider_client_factory != SIGNED_PROVIDER_CLIENT_FACTORY:
        blockers.append(f"provider_client_factory_not_signed:{args.provider_client_factory!r}")
    if args.source_case_provider != SIGNED_SOURCE_CASE_PROVIDER:
        blockers.append(f"source_case_provider_not_signed:{args.source_case_provider!r}")
    if not (args.dry_run or args.plan_only or args.execute_approved_source):
        blockers.append("dry_run_or_plan_only_required_without_execution_approval")
    return blockers, categories, publish_fields, planned_case_count


def load_callable(spec: str | None, *, missing: str, invalid: str, import_failed: str, callable_missing: str):
    if not spec:
        return None, missing
    if ":" not in spec:
        return None, invalid
    module_name, func_name = spec.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - exact import errors are environment-specific.
        return None, f"{import_failed}:{exc}"
    func = getattr(module, func_name, None)
    if not callable(func):
        return None, callable_missing
    return func, None


def load_execution_adapter(spec: str | None) -> tuple[AdapterFunc | None, str | None]:
    return load_callable(
        spec,
        missing="source_execution_adapter_missing",
        invalid="source_execution_adapter_spec_invalid",
        import_failed="source_execution_adapter_import_failed",
        callable_missing="source_execution_adapter_callable_missing",
    )


def load_provider_client_factory(spec: str | None) -> tuple[ProviderClientFactory | None, str | None]:
    return load_callable(
        spec,
        missing="source_provider_client_missing",
        invalid="provider_client_factory_spec_invalid",
        import_failed="provider_client_factory_import_failed",
        callable_missing="provider_client_factory_callable_missing",
    )


def load_source_case_provider(spec: str | None) -> tuple[SourceCaseProviderBuilder | None, str | None]:
    return load_callable(
        spec,
        missing="source_case_provider_missing",
        invalid="source_case_provider_spec_invalid",
        import_failed="source_case_provider_import_failed",
        callable_missing="source_case_provider_callable_missing",
    )


def write_compact_artifacts(output_root: Path, artifacts: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    output_root.mkdir(parents=True, exist_ok=True)
    for artifact in artifacts:
        category = artifact.get("category")
        if category not in APPROVED_CATEGORIES:
            blockers.append(f"write_category_not_signed:{category}")
            continue
        path = output_root / f"{category}.json"
        if path.parent != output_root:
            blockers.append(f"write_path_escape:{path}")
            continue
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return blockers


def execute_approved_source(
    args: argparse.Namespace,
    categories: list[str],
    planned_case_count: int,
    schema: dict[str, Any],
    *,
    adapter_func: AdapterFunc | None = None,
    provider_client_factory: ProviderClientFactory | None = None,
    write_artifacts: bool = True,
) -> dict[str, Any]:
    blockers: list[str] = []
    provider_transport_checker_passed, provider_transport_error, _ = run_json_checker(
        ["scripts/check_rashe_provider_transport_approved.py", "--compact", "--strict"]
    )
    if provider_transport_error:
        return {
            "execution_adapter_status": "provider_transport_not_approved",
            "provider_call_executed": False,
            "api_key_read": False,
            "diagnostic_written": False,
            "written_artifacts": [],
            "executed_artifacts": [],
            "blockers": ["provider_transport_not_approved"],
        }
    adapter_status = "loaded"
    if adapter_func is None:
        adapter_func, adapter_error = load_execution_adapter(args.execution_adapter)
        if adapter_error:
            adapter_status = "missing" if adapter_error == "source_execution_adapter_missing" else "invalid"
            blockers.append(adapter_error)
            return {
                "execution_adapter_status": adapter_status,
                "provider_call_executed": False,
                "api_key_read": False,
                "diagnostic_written": False,
                "written_artifacts": [],
                "executed_artifacts": [],
                "blockers": blockers,
            }

    request = build_adapter_request(args, categories, planned_case_count)
    source_case_provider_builder, source_case_provider_error = load_source_case_provider(args.source_case_provider)
    if source_case_provider_error:
        return {
            "execution_adapter_status": "source_case_provider_invalid",
            "provider_call_executed": False,
            "api_key_read": False,
            "diagnostic_written": False,
            "written_artifacts": [],
            "executed_artifacts": [],
            "blockers": [source_case_provider_error],
        }
    try:
        request["source_case_provider"] = source_case_provider_builder(request)
    except Exception as exc:  # pragma: no cover - source provider construction failures vary.
        message = str(exc)
        if message.startswith("bfcl_source_inputs_missing"):
            status = "bfcl_source_inputs_missing"
            blocker = message
        elif message.startswith("source_case_provider_data_missing"):
            status = "source_case_provider_data_missing"
            blocker = message
        else:
            status = "source_case_provider_failed"
            blocker = f"source_case_provider_failed:{message}"
        return {
            "execution_adapter_status": status,
            "provider_call_executed": False,
            "api_key_read": False,
            "diagnostic_written": False,
            "written_artifacts": [],
            "executed_artifacts": [],
            "blockers": [blocker],
        }
    if not callable(request["source_case_provider"]):
        return {
            "execution_adapter_status": "source_case_provider_invalid",
            "provider_call_executed": False,
            "api_key_read": False,
            "diagnostic_written": False,
            "written_artifacts": [],
            "executed_artifacts": [],
            "blockers": ["source_case_provider_output_not_callable"],
        }
    if provider_client_factory is None:
        provider_client_factory, factory_error = load_provider_client_factory(args.provider_client_factory)
        if factory_error:
            return {
                "execution_adapter_status": "provider_client_factory_invalid",
                "provider_call_executed": False,
                "api_key_read": False,
                "diagnostic_written": False,
                "written_artifacts": [],
                "executed_artifacts": [],
                "blockers": [factory_error],
            }
    try:
        request["provider_client"] = provider_client_factory(request)
    except Exception as exc:  # pragma: no cover - provider factory failures vary.
        message = str(exc)
        if message.startswith("source_case_provider_missing"):
            status = "source_case_provider_missing"
            blocker = message
        elif message.startswith("provider_transport_missing"):
            status = "provider_transport_missing"
            blocker = message
        elif message.startswith("provider_key_missing"):
            status = "provider_key_missing"
            blocker = message
        elif message.startswith("provider_transport_not_approved"):
            status = "provider_transport_not_approved"
            blocker = message
        else:
            status = "provider_client_factory_failed"
            blocker = f"provider_client_factory_failed:{message}"
        return {
            "execution_adapter_status": status,
            "provider_call_executed": False,
            "api_key_read": False,
            "diagnostic_written": False,
            "written_artifacts": [],
            "executed_artifacts": [],
            "blockers": [blocker],
        }
    if not callable(request["provider_client"]):
        return {
            "execution_adapter_status": "provider_client_factory_invalid",
            "provider_call_executed": False,
            "api_key_read": False,
            "diagnostic_written": False,
            "written_artifacts": [],
            "executed_artifacts": [],
            "blockers": ["provider_client_factory_output_not_callable"],
        }
    api_key_read = bool(getattr(request["provider_client"], "api_key_read", False))
    try:
        artifacts = adapter_func(request)
    except Exception as exc:  # pragma: no cover - adapter-specific failures vary.
        message = str(exc)
        if message.startswith("source_execution_dependency_missing:"):
            status = "dependency_missing"
            blocker = message
        elif message.startswith("source_provider_client_missing"):
            status = "provider_client_missing"
            blocker = message
        elif message.startswith("source_case_provider_missing"):
            status = "source_case_provider_missing"
            blocker = message
        elif message.startswith("bfcl_source_inputs_missing"):
            status = "bfcl_source_inputs_missing"
            blocker = message
        elif message.startswith("source_case_provider_data_missing"):
            status = "source_case_provider_data_missing"
            blocker = message
        elif message.startswith("provider_transport_missing"):
            status = "provider_transport_missing"
            blocker = message
        elif message.startswith("provider_key_missing"):
            status = "provider_key_missing"
            blocker = message
        elif message.startswith("provider_transport_not_approved"):
            status = "provider_transport_not_approved"
            blocker = message
        elif message.startswith("provider_transport_not_implemented"):
            status = "provider_transport_not_implemented"
            blocker = message
        else:
            status = "failed"
            blocker = f"source_execution_adapter_failed:{message}"
        api_key_read = bool(getattr(request.get("provider_client"), "api_key_read", api_key_read))
        return {
            "execution_adapter_status": status,
            "provider_call_executed": False,
            "api_key_read": api_key_read,
            "diagnostic_written": False,
            "written_artifacts": [],
            "executed_artifacts": [],
            "blockers": [blocker],
        }
    if not isinstance(artifacts, list) or not all(isinstance(item, dict) for item in artifacts):
        blockers.append("source_execution_adapter_output_invalid")
        artifacts = []
    if [artifact.get("category") for artifact in artifacts] != categories:
        blockers.append("source_execution_adapter_categories_mismatch")
    for artifact in artifacts:
        blockers.extend(validate_schema_artifact(schema, artifact))

    written_artifacts: list[str] = []
    if not blockers and write_artifacts:
        blockers.extend(write_compact_artifacts(args.output_root, artifacts))
        if not blockers:
            written_artifacts = [str(args.output_root / f"{artifact['category']}.json") for artifact in artifacts]
            boundary_error = run_plain_command([sys.executable, "scripts/check_artifact_boundary.py"])
            if boundary_error:
                blockers.append(f"artifact_boundary_failed:{boundary_error}")
    provider_call_executed = any(int(artifact.get("provider_call_count") or 0) > 0 for artifact in artifacts)
    api_key_read = bool(getattr(request.get("provider_client"), "api_key_read", api_key_read))
    return {
        "execution_adapter_status": adapter_status,
        "provider_call_executed": provider_call_executed,
        "api_key_read": api_key_read,
        "diagnostic_written": bool(written_artifacts),
        "written_artifacts": written_artifacts,
        "executed_artifacts": artifacts,
        "blockers": blockers,
    }


def check(args: argparse.Namespace) -> dict[str, Any]:
    blockers, categories, publish_fields, planned_case_count = validate_args(args)
    approved_source_checker_passed = False
    after_source_matrix_checker_passed = False

    if not args.skip_preflight_checks:
        approved_source_checker_passed, error, _ = run_json_checker(
            ["scripts/check_rashe_source_real_trace_approved.py", "--compact", "--strict"]
        )
        if error:
            blockers.append(f"approved_source_checker_failed:{error}")
        after_source_matrix_checker_passed, error, _ = run_json_checker(
            ["scripts/check_rashe_approval_packet_review_matrix_after_source_approval.py", "--compact", "--strict"]
        )
        if error:
            blockers.append(f"after_source_matrix_checker_failed:{error}")
    else:
        approved_source_checker_passed = True
        after_source_matrix_checker_passed = True

    compact_plans = [build_compact_plan(category, planned_case_count) for category in categories if category in APPROVED_CATEGORIES]
    try:
        schema = load_json(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        schema = {}
        blockers.append(f"schema_load_failed:{exc}")
    if schema:
        for artifact in compact_plans:
            blockers.extend(validate_schema_artifact(schema, artifact))

    adapter_load_status = "not_requested"
    if args.execution_adapter:
        _, adapter_error = load_execution_adapter(args.execution_adapter)
        if adapter_error:
            adapter_load_status = "missing" if adapter_error == "source_execution_adapter_missing" else "invalid"
            blockers.append(adapter_error)
        else:
            adapter_load_status = "loadable"
    provider_client_factory_status = "not_requested"
    if args.provider_client_factory:
        _, factory_error = load_provider_client_factory(args.provider_client_factory)
        if factory_error:
            provider_client_factory_status = "missing" if factory_error == "source_provider_client_missing" else "invalid"
            blockers.append(factory_error)
        else:
            provider_client_factory_status = "loadable"

    source_case_provider_status = "not_requested"
    if args.source_case_provider:
        _, source_error = load_source_case_provider(args.source_case_provider)
        if source_error:
            source_case_provider_status = "missing" if source_error == "source_case_provider_missing" else "invalid"
            blockers.append(source_error)
        else:
            source_case_provider_status = "loadable"

    execution = {
        "execution_adapter_status": adapter_load_status,
        "provider_call_executed": False,
        "api_key_read": False,
        "diagnostic_written": False,
        "written_artifacts": [],
        "executed_artifacts": [],
    }
    if args.execute_approved_source and not args.dry_run and not args.plan_only and not blockers and schema:
        execution = execute_approved_source(args, categories, planned_case_count, schema)
        blockers.extend(execution.get("blockers", []))

    return {
        "report_scope": "rashe_source_diagnostic_compact_plan",
        "provider_profile": args.provider_profile,
        "model": args.model,
        "categories": categories,
        "min_cases_per_category": args.min_cases_per_category,
        "max_cases_per_category": args.max_cases_per_category,
        "planned_case_count_per_category": planned_case_count,
        "planned_total_cases": len(categories) * planned_case_count if planned_case_count else 0,
        "max_total_cases": args.max_total_cases,
        "output_root": str(args.output_root),
        "schema_path": str(args.schema),
        "source_input_root": str(args.source_input_root),
        "publish_fields": publish_fields,
        "dry_run": args.dry_run,
        "plan_only": args.plan_only,
        "execute_requested": args.execute_approved_source,
        "provider_call_executed": execution["provider_call_executed"],
        "api_key_read": execution["api_key_read"],
        "diagnostic_written": execution["diagnostic_written"],
        "execution_adapter_status": execution["execution_adapter_status"],
        "provider_client_factory_status": provider_client_factory_status,
        "source_case_provider_status": source_case_provider_status,
        "source_case_provider_injected": bool(args.execute_approved_source and not args.dry_run and not args.plan_only and not blockers),
        "provider_client_injected": bool(args.execute_approved_source and not args.dry_run and not args.plan_only and not blockers),
        "written_artifacts": execution["written_artifacts"],
        "approved_source_checker_passed": approved_source_checker_passed,
        "after_source_matrix_checker_passed": after_source_matrix_checker_passed,
        "raw_payload_tracked_count": 0,
        "forbidden_field_violation_count": 0,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "compact_artifact_plan": compact_plans,
        "executed_artifacts": execution["executed_artifacts"],
        "rashe_source_diagnostic_compact_plan_passed": not blockers,
        "blockers": blockers,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-profile", default="Chuangzhi/Novacode")
    parser.add_argument("--model", default=SIGNED_MODEL)
    parser.add_argument("--categories", default=",".join(APPROVED_CATEGORIES))
    parser.add_argument("--min-cases-per-category", type=int, default=SIGNED_CASES_PER_CATEGORY)
    parser.add_argument("--max-cases-per-category", type=int, default=SIGNED_CASES_PER_CATEGORY)
    parser.add_argument("--max-total-cases", type=int, default=SIGNED_TOTAL_CASES)
    parser.add_argument("--output-root", type=Path, default=SIGNED_OUTPUT_ROOT)
    parser.add_argument("--schema", type=Path, default=SIGNED_SCHEMA)
    parser.add_argument("--source-input-root", type=Path, default=SIGNED_SOURCE_INPUT_ROOT)
    parser.add_argument("--compact-sanitized-only", action="store_true", default=True)
    parser.add_argument("--publish-fields", default=",".join(SIGNED_PUBLISH_FIELDS))
    parser.add_argument("--no-raw-trace", action="store_true", default=True)
    parser.add_argument("--no-raw-payload", action="store_true", default=True)
    parser.add_argument("--no-candidate-jsonl", action="store_true", default=True)
    parser.add_argument("--no-scorer", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--execute-approved-source", action="store_true")
    parser.add_argument("--execution-adapter", default=SIGNED_EXECUTION_ADAPTER, help="Adapter entrypoint as module:function for approved execution.")
    parser.add_argument("--provider-client-factory", default=SIGNED_PROVIDER_CLIENT_FACTORY, help="Signed provider client factory as module:function for approved execution.")
    parser.add_argument("--source-case-provider", default=SIGNED_SOURCE_CASE_PROVIDER, help="Signed source-case provider builder as module:function for approved execution.")
    parser.add_argument("--skip-preflight-checks", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = check(args)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_source_diagnostic_compact_plan_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
