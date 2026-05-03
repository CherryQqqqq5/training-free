#!/usr/bin/env python3
"""Dry-run or execute compact static proxy-vs-direct upstream shape diff."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_live_provider_preflight_gate import SIGNED_API_KEY_ENVS, SIGNED_BASE_URL_ENVS
from scripts.check_bfcl_proxy_vs_direct_upstream_shape_diff_artifact import check as check_artifact
from scripts.check_bfcl_proxy_vs_direct_upstream_shape_diff_gate import DEFAULT_PACKET, REQUIRED_COMPACT_FIELDS, check as check_packet

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_vs_direct_upstream_shape_diff_compact.json")
RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
PROXY_SOURCE = Path("src/grc/runtime/proxy.py")
LIVE_RUNNER_SOURCE = Path("scripts/run_bfcl_live_provider_preflight.py")


def _base_record(*, command_executed: bool = False) -> dict[str, Any]:
    return {
        "preflight_command_executed": command_executed,
        "direct_selected_api_key_env_label": "unknown",
        "proxy_selected_api_key_env_label": "unknown",
        "api_key_env_match": False,
        "direct_selected_base_url_env_label": "unknown",
        "proxy_selected_base_url_env_label": "unknown",
        "base_url_env_match": False,
        "model_label_match": False,
        "tool_choice_shape_label": "unknown",
        "tools_shape_label": "unknown",
        "messages_shape_label": "unknown",
        "token_field_shape_label": "unknown",
        "runtime_patch_label": "unknown",
        "suspected_mismatch_label": "unknown",
        "provider_call_started": False,
        "proxy_live_request_started": False,
        "profile_sourced": False,
        "bfcl_generate_started": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "full_baseline_executed": False,
        "candidate_specs_inert": True,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "performance_evidence": False,
        "raw_outputs_committed": False,
        "stop_gate_triggered": "none" if not command_executed else "stopped_after_static_shape_diff",
        "preflight_failed_check_label": "none_observed",
    }


def _extract_profile_value(config_text: str, profile: str, key: str) -> str:
    lines = config_text.splitlines()
    in_profile = False
    profile_indent = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if stripped == f"{profile}:":
            in_profile = True
            profile_indent = indent
            continue
        if in_profile and indent <= profile_indent and stripped.endswith(":"):
            break
        if in_profile and stripped.startswith(f"{key}:"):
            return stripped.split(":", 1)[1].strip().strip('"\'')
    return "unknown"


def _extract_top_level_upstream_value(config_text: str, key: str) -> str:
    lines = config_text.splitlines()
    in_upstream = False
    upstream_indent = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if stripped == "upstream:":
            in_upstream = True
            upstream_indent = indent
            continue
        if in_upstream and indent <= upstream_indent and stripped.endswith(":"):
            break
        if in_upstream and indent == upstream_indent + 2 and stripped.startswith(f"{key}:"):
            return stripped.split(":", 1)[1].strip().strip('"\'')
    return "unknown"


def _proxy_base_url_env_label(proxy_source: str, config_text: str) -> str:
    if 'os.environ.get("GRC_UPSTREAM_BASE_URL")' in proxy_source or "os.environ.get('GRC_UPSTREAM_BASE_URL')" in proxy_source:
        return "GRC_UPSTREAM_BASE_URL"
    label = _extract_profile_value(config_text, "novacode", "base_url_env")
    return label if label else "unknown"


def _label_tool_choice(live_source: str, proxy_source: str) -> str:
    direct_function = '"tool_choice": {"type": "function", "function": {"name": TOY_TOOL_NAME}}' in live_source
    proxy_function = "return tool_choice" in proxy_source and "isinstance(tool_choice, (str, dict))" in proxy_source
    if direct_function and proxy_function:
        return "function_object_aligned"
    if direct_function:
        return "direct_function_proxy_other"
    return "unknown"


def _label_tools_shape(proxy_source: str, live_source: str) -> str:
    direct_chat = '"type": "function"' in live_source and '"function": {' in live_source
    proxy_chat = '"function": {' in proxy_source and "_responses_tools_to_chat_tools" in proxy_source
    return "chat_function_tools_aligned" if direct_chat and proxy_chat else "mismatch"


def _label_messages_shape(config_text: str, proxy_source: str) -> str:
    developer = "_responses_instructions_to_messages" in proxy_source
    inject_system = "inject_structured_tool_guidance: true" in config_text or "inject_context_literal_hints: true" in config_text
    if developer and inject_system:
        return "direct_user_only_proxy_system_developer_user"
    if developer:
        return "direct_user_only_proxy_developer_user"
    return "unknown"


def _label_token_field(proxy_source: str, live_source: str) -> str:
    direct_max_tokens = '"max_tokens": 16' in live_source
    proxy_maps_max_output = 'elif "max_output_tokens" in request_json:' in proxy_source and 'forwarded["max_tokens"]' in proxy_source
    return "max_tokens_aligned" if direct_max_tokens and proxy_maps_max_output else "mismatch"


def _label_runtime_patch(config_text: str) -> str:
    if "inject_structured_tool_guidance: true" in config_text or "inject_context_literal_hints: true" in config_text:
        return "nonzero_runtime_request_patch"
    return "zero_runtime_request_patch"


def build_diff_record() -> dict[str, Any]:
    config_text = (REPO_ROOT / RUNTIME_CONFIG).read_text(encoding="utf-8")
    proxy_source = (REPO_ROOT / PROXY_SOURCE).read_text(encoding="utf-8")
    live_source = (REPO_ROOT / LIVE_RUNNER_SOURCE).read_text(encoding="utf-8")
    record = _base_record(command_executed=True)
    direct_api = SIGNED_API_KEY_ENVS[0] if SIGNED_API_KEY_ENVS else "unknown"
    proxy_api = _extract_profile_value(config_text, "novacode", "api_key_env")
    direct_base = SIGNED_BASE_URL_ENVS[0] if SIGNED_BASE_URL_ENVS else "unknown"
    proxy_base = _proxy_base_url_env_label(proxy_source, config_text)
    direct_model = "gpt-4.1" if '"model": "gpt-4.1"' in live_source else "unknown"
    proxy_model = _extract_profile_value(config_text, "novacode", "model") or _extract_top_level_upstream_value(config_text, "model")
    record.update(
        {
            "direct_selected_api_key_env_label": direct_api,
            "proxy_selected_api_key_env_label": proxy_api,
            "api_key_env_match": direct_api == proxy_api,
            "direct_selected_base_url_env_label": direct_base,
            "proxy_selected_base_url_env_label": proxy_base,
            "base_url_env_match": direct_base == proxy_base,
            "model_label_match": direct_model == proxy_model == "gpt-4.1",
            "tool_choice_shape_label": _label_tool_choice(live_source, proxy_source),
            "tools_shape_label": _label_tools_shape(proxy_source, live_source),
            "messages_shape_label": _label_messages_shape(config_text, proxy_source),
            "token_field_shape_label": _label_token_field(proxy_source, live_source),
            "runtime_patch_label": _label_runtime_patch(config_text),
        }
    )
    if not record["api_key_env_match"]:
        record["suspected_mismatch_label"] = "api_key_env_mismatch"
    elif not record["base_url_env_match"]:
        record["suspected_mismatch_label"] = "base_url_env_mismatch"
    elif record["messages_shape_label"] != "aligned" or record["runtime_patch_label"] != "zero_runtime_request_patch":
        record["suspected_mismatch_label"] = "payload_shape_drift"
    else:
        record["suspected_mismatch_label"] = "none_observed"
    return record


def _write_artifact(record: dict[str, Any], output_artifact: Path) -> None:
    payload = {
        "artifact_kind": "bfcl_proxy_vs_direct_upstream_shape_diff_compact",
        "compact_schema_version": "proxy_vs_direct_upstream_shape_diff_v1",
        "measurement_kind": "compact_static_proxy_vs_direct_upstream_shape_diff",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
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
        "report_scope": "bfcl_proxy_vs_direct_upstream_shape_diff_plan",
        "packet_path": str(packet_path),
        "output_artifact_planned": str(output_artifact),
        "approval_status": packet_summary.get("approval_status"),
        "authorized": packet_summary.get("authorized"),
        "provider_request_authorized": packet_summary.get("provider_request_authorized"),
        "proxy_live_request_authorized": packet_summary.get("proxy_live_request_authorized"),
        "profile_source_authorized": packet_summary.get("profile_source_authorized"),
        "compact_only": True,
        "static_no_provider_only": True,
        "env_profile_sourced": False,
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        **_base_record(command_executed=False),
        "blockers": list(packet_summary.get("blockers", [])),
    }


def execute_shape_diff(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_proxy_vs_direct_upstream_shape_diff_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("shape_diff_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return {
            "report_scope": "bfcl_proxy_vs_direct_upstream_shape_diff_execute",
            **_base_record(command_executed=False),
            "env_profile_sourced": False,
            "output_artifact": None,
            "blockers": sorted(set(blockers)),
        }
    record = build_diff_record()
    _write_artifact(record, output_artifact)
    artifact_summary = check_artifact(output_artifact)
    if not artifact_summary.get("bfcl_proxy_vs_direct_upstream_shape_diff_artifact_passed"):
        blockers.extend(str(blocker) for blocker in artifact_summary.get("blockers", []))
    return {
        "report_scope": "bfcl_proxy_vs_direct_upstream_shape_diff_execute",
        **record,
        "env_profile_sourced": False,
        "output_artifact": str(output_artifact),
        "blockers": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-shape-diff", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_shape_diff:
        summary = execute_shape_diff(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
