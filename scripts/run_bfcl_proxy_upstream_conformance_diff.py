#!/usr/bin/env python3
"""Run an offline compact proxy upstream conformance/header/policy diff."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_proxy_upstream_conformance_diff_artifact import check as check_artifact
from scripts.check_bfcl_proxy_upstream_conformance_diff_gate import DEFAULT_PACKET, REQUIRED_COMPACT_FIELDS, check as check_packet

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_upstream_conformance_diff_compact.json")
RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
ROUTE_MODEL = "gpt-4.1"


def _base_record(*, command_executed: bool = False) -> dict[str, Any]:
    return {
        "preflight_command_executed": command_executed,
        "provider_call_started": False,
        "profile_sourced": False,
        "proxy_live_request_started": False,
        "fake_upstream_capture_used": command_executed,
        "raw_outputs_committed": False,
        "raw_temp_outputs_removed": command_executed,
        "provider_facing_header_shape_label": "unknown",
        "authorization_header_presence_label": "unknown",
        "content_type_header_label": "unknown",
        "extra_provider_header_shape_label": "unknown",
        "messages_role_sequence_label": "unknown",
        "system_injection_label": "unknown",
        "developer_instruction_label": "unknown",
        "temperature_field_label": "unknown",
        "token_field_label": "unknown",
        "tool_choice_shape_label": "unknown",
        "tools_shape_label": "unknown",
        "model_label": "unknown",
        "runtime_patch_label": "unknown",
        "responses_to_chat_adapter_label": "unknown",
        "suspected_403_cause_label": "unknown",
        "direct_proxy_conformance_label": "unknown",
        "bfcl_generate_started": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "full_baseline_executed": False,
        "candidate_specs_inert": True,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "performance_evidence": False,
        "stop_gate_triggered": "none" if not command_executed else "stopped_after_fake_upstream_capture",
        "preflight_failed_check_label": "none_observed",
    }


def _runtime_policy_flags(config_text: str) -> tuple[bool, bool]:
    structured = "inject_structured_tool_guidance: true" in config_text
    literal_hints = "inject_context_literal_hints: true" in config_text
    return structured, literal_hints


def _responses_probe_shape() -> dict[str, Any]:
    return {
        "model": ROUTE_MODEL,
        "instructions_present": False,
        "input_roles": ["user"],
        "tools_shape": "responses_function_schema",
        "tool_choice_shape": "responses_function_object",
        "max_output_tokens_present": True,
        "temperature_present": True,
        "temperature_zero": True,
    }


def _adapt_responses_to_chat_shape(responses_shape: dict[str, Any], *, inject_system: bool) -> dict[str, Any]:
    roles = []
    if inject_system:
        roles.append("system")
    if responses_shape.get("instructions_present"):
        roles.append("developer")
    roles.extend(str(role) for role in responses_shape.get("input_roles", []))
    return {
        "model": responses_shape.get("model"),
        "message_roles": roles,
        "tools_shape": "chat_function_schema" if responses_shape.get("tools_shape") == "responses_function_schema" else "malformed",
        "tool_choice_shape": "chat_function_object" if responses_shape.get("tool_choice_shape") == "responses_function_object" else "malformed",
        "max_tokens_present": bool(responses_shape.get("max_output_tokens_present")),
        "temperature_present": bool(responses_shape.get("temperature_present")),
        "temperature_zero": bool(responses_shape.get("temperature_zero")),
    }


def _fake_upstream_capture(chat_shape: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_header_names": ["Authorization", "Content-Type"],
        "provider_message_roles": list(chat_shape.get("message_roles", [])),
        "provider_tools_shape": chat_shape.get("tools_shape"),
        "provider_tool_choice_shape": chat_shape.get("tool_choice_shape"),
        "provider_model": chat_shape.get("model"),
        "provider_max_tokens_present": bool(chat_shape.get("max_tokens_present")),
        "provider_temperature_present": bool(chat_shape.get("temperature_present")),
        "provider_temperature_zero": bool(chat_shape.get("temperature_zero")),
    }


def _label_headers(names: list[str]) -> tuple[str, str, str, str]:
    name_set = set(names)
    authorization = "present" if "Authorization" in name_set else "missing"
    content_type = "present" if "Content-Type" in name_set else "missing"
    extra = name_set - {"Authorization", "Content-Type"}
    if not extra:
        extra_label = "none"
    elif extra.intersection({"HTTP-Referer", "X-Title"}):
        extra_label = "referer_or_title_present"
    else:
        extra_label = "other_extra"
    if authorization == "present" and content_type == "present" and extra_label == "none":
        shape = "authorization_content_type_only"
    elif authorization == "present" and content_type == "present":
        shape = "authorization_content_type_extra"
    elif authorization == "missing":
        shape = "missing_authorization"
    elif content_type == "missing":
        shape = "missing_content_type"
    else:
        shape = "unknown"
    return shape, authorization, content_type, extra_label


def _label_roles(roles: list[str]) -> str:
    joined = "_".join(roles)
    return joined if joined in {"user", "developer_user", "system_developer_user", "system_user"} else "malformed"


def _label_temperature(capture: dict[str, Any]) -> str:
    if not capture.get("provider_temperature_present"):
        return "missing"
    if capture.get("provider_temperature_zero"):
        return "present_zero"
    return "present_nonzero"


def _label_model(model: Any) -> str:
    if model == ROUTE_MODEL:
        return "gpt_4_1"
    if not model:
        return "missing"
    return "other"


def _suspected_cause(record: dict[str, Any]) -> str:
    if record["provider_facing_header_shape_label"] != "authorization_content_type_only":
        return "header_shape_drift"
    if record["model_label"] != "gpt_4_1":
        return "model_drift"
    if record["runtime_patch_label"] == "nonzero_policy_patch" and record["temperature_field_label"] == "missing":
        return "temperature_missing_with_policy_drift"
    if record["runtime_patch_label"] == "nonzero_policy_patch" or record["messages_role_sequence_label"] != "user":
        return "policy_message_shape_drift"
    return "none_observed"


def _conformance_label(record: dict[str, Any]) -> str:
    if record["provider_facing_header_shape_label"] != "authorization_content_type_only":
        return "header_drift"
    if record["model_label"] != "gpt_4_1":
        return "model_drift"
    if record["messages_role_sequence_label"] == "user" and record["temperature_field_label"] == "present_zero":
        return "matched_direct_chat_tool_shape"
    return "partial_drift_headers_aligned"


def build_diff_record() -> dict[str, Any]:
    config_text = (REPO_ROOT / RUNTIME_CONFIG).read_text(encoding="utf-8")
    structured, literal_hints = _runtime_policy_flags(config_text)
    responses_shape = _responses_probe_shape()
    diagnostic_direct_alignment = True
    chat_shape = _adapt_responses_to_chat_shape(
        responses_shape,
        inject_system=(structured or literal_hints) and not diagnostic_direct_alignment,
    )
    capture = _fake_upstream_capture(chat_shape)
    header_shape, authorization, content_type, extra_header = _label_headers(capture["provider_header_names"])
    roles_label = _label_roles(capture["provider_message_roles"])
    record = _base_record(command_executed=True)
    record.update(
        {
            "provider_facing_header_shape_label": header_shape,
            "authorization_header_presence_label": authorization,
            "content_type_header_label": content_type,
            "extra_provider_header_shape_label": extra_header,
            "messages_role_sequence_label": roles_label,
            "system_injection_label": "present" if "system" in capture["provider_message_roles"] else "absent",
            "developer_instruction_label": "present" if "developer" in capture["provider_message_roles"] else "absent",
            "temperature_field_label": _label_temperature(capture),
            "token_field_label": "max_output_tokens_mapped_to_max_tokens" if capture.get("provider_max_tokens_present") else "missing",
            "tool_choice_shape_label": str(capture.get("provider_tool_choice_shape") or "unknown"),
            "tools_shape_label": str(capture.get("provider_tools_shape") or "unknown"),
            "model_label": _label_model(capture.get("provider_model")),
            "runtime_patch_label": "zero_policy_patch" if diagnostic_direct_alignment else ("nonzero_policy_patch" if structured or literal_hints else "zero_policy_patch"),
            "responses_to_chat_adapter_label": "responses_to_chat_applied",
        }
    )
    record["suspected_403_cause_label"] = _suspected_cause(record)
    record["direct_proxy_conformance_label"] = _conformance_label(record)
    return record


def _write_artifact(record: dict[str, Any], output_artifact: Path) -> None:
    payload = {
        "artifact_kind": "bfcl_proxy_upstream_conformance_diff_compact",
        "compact_schema_version": "proxy_upstream_conformance_diff_v1",
        "measurement_kind": "compact_offline_proxy_upstream_conformance_header_policy_diff",
        "route_profile": "novacode",
        "route_model": ROUTE_MODEL,
        "provider_call_executed": False,
        "proxy_live_request_executed": False,
        "profile_sourced_summary": False,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_outputs_committed": False,
        "records": [{field: record.get(field) for field in REQUIRED_COMPACT_FIELDS}],
    }
    output_artifact.parent.mkdir(parents=True, exist_ok=True)
    output_artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_proxy_upstream_conformance_diff_plan",
        "packet_path": str(packet_path),
        "output_artifact_planned": str(output_artifact),
        "approval_status": packet_summary.get("approval_status"),
        "authorized": packet_summary.get("authorized"),
        "provider_request_authorized": packet_summary.get("provider_request_authorized"),
        "proxy_live_request_authorized": packet_summary.get("proxy_live_request_authorized"),
        "profile_source_authorized": packet_summary.get("profile_source_authorized"),
        "compact_only": True,
        "offline_no_provider_only": True,
        "fake_upstream_capture_required": True,
        "env_profile_sourced": False,
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        **_base_record(command_executed=False),
        "blockers": list(packet_summary.get("blockers", [])),
    }


def execute_conformance_diff(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_proxy_upstream_conformance_diff_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("conformance_diff_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return {
            "report_scope": "bfcl_proxy_upstream_conformance_diff_execute",
            **_base_record(command_executed=False),
            "env_profile_sourced": False,
            "output_artifact": None,
            "blockers": sorted(set(blockers)),
        }
    record = build_diff_record()
    _write_artifact(record, output_artifact)
    artifact_summary = check_artifact(output_artifact)
    if not artifact_summary.get("bfcl_proxy_upstream_conformance_diff_artifact_passed"):
        blockers.extend(str(blocker) for blocker in artifact_summary.get("blockers", []))
    return {
        "report_scope": "bfcl_proxy_upstream_conformance_diff_execute",
        **record,
        "env_profile_sourced": False,
        "output_artifact": str(output_artifact),
        "blockers": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute-conformance-diff", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_conformance_diff and args.dry_run:
        summary = {"report_scope": "bfcl_proxy_upstream_conformance_diff_execute", "blockers": ["dry_run_and_execute_both_set"]}
    elif args.execute_conformance_diff:
        summary = execute_conformance_diff(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
