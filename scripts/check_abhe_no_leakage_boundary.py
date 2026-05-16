#!/usr/bin/env python3
"""Check ABHE artifacts for forbidden raw or scorer-derived material."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

DEFAULT_PATHS = [
    Path("abhe_archive/archive_index.json"),
    Path("abhe_archive/opportunity_table.json"),
    Path("abhe_archive/policy_config.yaml"),
    Path("abhe_archive/state_transitions.jsonl"),
    Path("abhe_archive/behavior_taxonomy_v0.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_next_evolution_plan.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_policy_score.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_simple_candidate_specs.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_synthetic_fresh_dev_slice_manifest.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_synthetic_dev_feedback.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_archive_transition_plan.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_plan.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_manifest.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_review.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_selection.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_category_review.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_review.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_source_exclusion_proof.json"),
    Path("docs/stage1_abhe_v0_bfcl_fresh_slice_review_memo.md"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_plan.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_approval_packet.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_materialized_candidates.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_request.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_execution_readiness.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_dry_run_manifest.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_execution_failure.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_candidate_adapter.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_provider_preflight.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_baseline_arm_compact.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_candidate_arm_compact.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_result.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_case_delta_analysis.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_real_trace_analysis.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.schema.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_archive_transition_plan.json"),
    Path("docs/stage1_abhe_v0_bfcl_fresh_dev_slice.md"),
    Path("docs/stage1_abhe_v0_candidate_materialization.md"),
    Path("docs/stage1_abhe_v0_bfcl_dev_smoke_request.md"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_planning_ready.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_execution_readiness.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_review_bundle.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_approval_chain.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_review_request.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_execution_approval.schema.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_extraction_approval.schema.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_fresh_dev_slice_approval.schema.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_fresh_dev_slice_approval_packet.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_candidate_spec_approval.schema.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_fresh_dev_slice_request.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_dev_smoke_dry_run_manifest.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_temporary_trace_extraction_packet.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_bounded_dev_smoke_execution_packet.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_card.schema.json"),
    Path("docs/stage1_abhe_method_overview.md"),
    Path("docs/stage1_abhe_approval_lanes.md"),
    Path("docs/stage1_abhe_review_bundle.md"),
    Path("docs/stage1_abhe_v0_simple_closed_loop.md"),
    Path("docs/stage1_abhe_transition_from_rashe.md"),
    Path("docs/stage1_abhe_archive_policy.md"),
    Path("docs/stage1_abhe_trace_packet_boundary.md"),
    Path("docs/stage1_abhe_trace_card_contract.md"),
    Path("docs/stage1_abhe_fresh_dev_slice_boundary.md"),
    Path("docs/stage1_abhe_state_tracking_candidate_sketch.md"),
    Path("docs/stage1_abhe_hallucination_abstain_candidate_sketch.md"),
    Path("docs/stage1_abhe_state_tracking_candidate_spec_draft.md"),
    Path("docs/stage1_abhe_hallucination_abstain_candidate_spec_draft.md"),
    Path("docs/stage1_abhe_post_dev_update_contract.md"),
    Path("docs/stage1_abhe_search_memory_watch_split_proposal.md"),
    Path("tests/fixtures/abhe_dev_feedback/dev_passed.json"),
    Path("tests/fixtures/abhe_dev_feedback/narrow_router_requested.json"),
    Path("tests/fixtures/abhe_dev_feedback/split_requested.json"),
    Path("tests/fixtures/abhe_dev_feedback/demoted_no_mechanism_signal.json"),
    Path("tests/fixtures/abhe_dev_feedback/demoted_regression_not_controlled.json"),
    Path("tests/fixtures/abhe_dev_feedback/rejected_boundary_failure.json"),
]

ALLOWED_KEY_NAMES = {
    "selected_case_ids_hash",
    "selected_compact_case_identifiers",
    "selected_dataset_path",
    "proposed_selected_case_ids_hash",
    "source_file_hash",
    "case_row_index_hash",
    "case_stable_hash",
    "case_identifier_hash",
    "forbidden_fields",
    "forbidden_mainline_next_steps",
    "raw_material_persisted",
    "candidate_pool_ready",
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_activation_authorized",
    "source_evidence_count",
    "source_evidence_role",
    "raw_prompt_allowed",
    "raw_trace_allowed",
    "raw_payload_allowed",
    "raw_case_id_allowed",
    "gold_expected_allowed",
    "gold_expected_persisted",
    "scorer_diff_allowed",
    "scorer_diff_persisted",
    "candidate_output_allowed",
    "raw_material_absent",
    "approved_fresh_dev_slice_hash",
    "approved_runner_manifest_hash",
    "approved_candidate_spec_hash",
    "fresh_dev_slice_hash",
    "dev_run_id_hash",
    "expected_missing_approval_blockers",
    "raw_outputs_committed",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
    "approved_candidate_artifact",
    "approved_fresh_slice_manifest",
    "approved_runtime_config_path",
    "scorer_authorization_scope",
    "provider_env_status",
    "api_key_env_set",
    "expected_api_key_env",
    "profile_loaded",
    "profile_source_checked",
    "endpoint_env_present",
    "api_key_env_present",
    "endpoint_env_status",
    "endpoint_env_candidates",
    "provider_api_key_env_missing",
    "adapter_ready",
    "scorer_called",
    "bfcl_evaluate_called",
    "bfcl_generate_called",
    "provider_calls_made",
    "runtime_config_path",
    "fresh_slice_manifest_path",
    "candidate_artifact_path",
    "provider_preflight_path",
    "provider_preflight_passed",
    "provider_preflight_summary",
    "candidate_jsonl_generated",
    "candidate_yaml_generated",
    "candidate_rule_generated",
    "runtime_projection",
    "entry_specific_activation_required",
    "fallback_global_activation_allowed",
    "runtime_context_source",
    "candidate_activation_telemetry",
    "case_hash",
    "scorer_unit_hash",
    "scorer_unit_hashes",
    "strict_per_compact_case_paired_available",
    "aggregate_feedback_fixed_count_is_scaled_category_delta",
    "runtime_guidance_fragment_id",
    "preflight_status_code_class",
    "preflight_error_class",
    "endpoint_env_status_redacted",
    "endpoint_value_persisted",
    "secret_values_persisted",
    "provider_endpoint_env_missing",
    "raw_material_absent",
}

OPTIONAL_DEFAULT_PATHS = {
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_baseline_arm_compact.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_candidate_arm_compact.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_result.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_case_delta_analysis.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_real_trace_analysis.json"),
}

FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_(?:prompt|trace|payload|provider|request|response|header|body|case_id)|"
    r"prompt_text|trace_text|provider_exchange|case_id|gold|expected|reference|"
    r"tool_args?|tool_arguments?|scorer_diff|candidate_output|api_key|bearer_token|"
    r"endpoint_value)(_|$)",
    re.I,
)

NEGATIVE_BOUNDARY_CUES = (
    "forbidden",
    "must not",
    "do not",
    "does not",
    "not allowed",
    "not authorize",
    "not include",
    "not contain",
    "absent",
    "excluded",
    "false",
    "fail-closed",
    "no raw",
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|bearer\s+|api key|secret|raw prompt|raw trace|"
     r"raw payload|provider exchange|case id|gold answer|expected answer|reference answer|"
     r"tool argument values|scorer diff|candidate output text|endpoint value"),
    re.I,
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> List[Any]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError("%s:%d invalid jsonl: %s" % (path, line_no, exc))
    return rows


def _load_yamlish(path: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    stack: List[Tuple[int, Any]] = [(-1, data)]
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if stripped.startswith("- "):
            if not isinstance(parent, list):
                continue
            parent.append(stripped[2:].strip())
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            child: Any = []
            if isinstance(parent, dict):
                parent[key] = child
            stack.append((indent, child))
        else:
            if value.lower() == "true":
                parsed: Any = True
            elif value.lower() == "false":
                parsed = False
            else:
                parsed = value
            if isinstance(parent, dict):
                parent[key] = parsed
    return data


def load_path(path: Path) -> Any:
    if path.suffix == ".json":
        return _load_json(path)
    if path.suffix == ".jsonl":
        return _load_jsonl(path)
    if path.suffix in {".yaml", ".yml"}:
        return _load_yamlish(path)
    if path.suffix == ".md":
        return {
            "markdown_lines": [
                {"line_number": line_no, "text": line}
                for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
            ]
        }
    return path.read_text(encoding="utf-8")


def _walk(value: Any, path: Tuple[str, ...] = ()) -> Iterable[Tuple[Tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            for item in _walk(child, path + (str(key),)):
                yield item
    elif isinstance(value, list):
        for index, child in enumerate(value):
            for item in _walk(child, path + (str(index),)):
                yield item


def scan_value(value: Any, *, label: str) -> List[str]:
    blockers: List[str] = []
    for path, child in _walk(value):
        key = path[-1] if path else ""
        dotted = ".".join(path)
        if key and key not in ALLOWED_KEY_NAMES and FORBIDDEN_KEY_RE.search(key):
            blockers.append("%s_forbidden_key:%s" % (label, dotted))
        if isinstance(child, str) and FORBIDDEN_VALUE_RE.search(child):
            if len(path) >= 2 and path[-2] in {"forbidden_fields", "risk_flags"}:
                continue
            if path and path[-1] == "text" and any(cue in child.lower() for cue in NEGATIVE_BOUNDARY_CUES):
                continue
            blockers.append("%s_forbidden_value:%s" % (label, dotted))
    return sorted(set(blockers))


def check_paths(paths: List[Path]) -> Dict[str, Any]:
    blockers: List[str] = []
    checked = []
    for path in paths:
        if not path.exists():
            if path.name == "abhe_next_evolution_plan.json" or path in OPTIONAL_DEFAULT_PATHS:
                continue
            blockers.append("missing_path:%s" % path)
            continue
        checked.append(str(path))
        try:
            data = load_path(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            blockers.append("load_failed:%s:%s" % (path, exc))
            continue
        blockers.extend(scan_value(data, label=str(path)))
    return {
        "report_scope": "abhe_no_leakage_boundary_check",
        "checked_paths": checked,
        "abhe_no_leakage_boundary_passed": not blockers,
        "blockers": sorted(set(blockers)),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    paths = args.paths or DEFAULT_PATHS
    summary = check_paths(paths)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_no_leakage_boundary_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
