#!/usr/bin/env python3
"""Run an offline compact proxy transport/request capture diff."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_proxy_transport_request_capture_diff_artifact import check as check_artifact
from scripts.check_bfcl_proxy_transport_request_capture_diff_gate import DEFAULT_PACKET, REQUIRED_COMPACT_FIELDS, check as check_packet

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_transport_request_capture_diff_compact.json")
PROXY_SOURCE = Path("src/grc/runtime/proxy.py")
DIRECT_RUNNER_SOURCE = Path("scripts/run_bfcl_live_provider_preflight.py")
RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")


def _select_proxy_python_label() -> str:
    if os.environ.get("GRC_PYTHON"):
        return "grc_python_env"
    repo_venv = REPO_ROOT / ".venv" / "bin" / "python"
    if repo_venv.is_file() and os.access(str(repo_venv), os.X_OK):
        return "repo_venv"
    return "caller_python"


def _base_record(*, command_executed: bool = False) -> dict[str, Any]:
    return {
        "preflight_command_executed": command_executed,
        "provider_call_started": False,
        "profile_sourced": False,
        "proxy_live_request_started": False,
        "fake_transport_capture_used": command_executed,
        "raw_outputs_committed": False,
        "raw_temp_outputs_removed": command_executed,
        "transport_client_label": "unknown",
        "client_stack_label": "unknown",
        "body_submission_label": "unknown",
        "json_serialization_label": "unknown",
        "content_type_header_label": "unknown",
        "authorization_header_label": "unknown",
        "auth_scheme_label": "unknown",
        "extra_header_shape_label": "unknown",
        "provider_header_shape_label": "unknown",
        "url_join_label": "unknown",
        "request_target_suffix_label": "unknown",
        "timeout_shape_label": "unknown",
        "payload_shape_match_label": "unknown",
        "payload_shape_label": "unknown",
        "selected_base_url_env_label": "unknown",
        "selected_api_key_env_label": "unknown",
        "proxy_python_label": _select_proxy_python_label(),
        "suspected_403_cause_label": "unknown",
        "direct_transport_client_label": "unknown",
        "direct_body_submission_label": "unknown",
        "direct_json_serialization_label": "unknown",
        "direct_timeout_shape_label": "unknown",
        "direct_header_shape_label": "unknown",
        "bfcl_generate_started": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "full_baseline_executed": False,
        "candidate_specs_inert": True,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "performance_evidence": False,
        "stop_gate_triggered": "none" if not command_executed else "stopped_after_fake_transport_capture",
        "preflight_failed_check_label": "none_observed",
    }


def _header_shape(has_auth: bool, has_content_type: bool, extra_shape: str) -> str:
    if has_auth and has_content_type and extra_shape == "none":
        return "authorization_content_type_only"
    if has_auth and has_content_type:
        return "authorization_content_type_extra"
    if not has_auth:
        return "missing_authorization"
    if not has_content_type:
        return "missing_content_type"
    return "unknown"


def _direct_transport_capture(direct_source: str) -> dict[str, str]:
    return {
        "transport_client_label": "urllib_request" if "urllib.request.Request" in direct_source else "unknown",
        "client_stack_label": "direct_urllib_manual_bytes" if "urllib.request.urlopen" in direct_source else "unknown",
        "body_submission_label": "urllib_data_bytes" if "data=json.dumps" in direct_source and ".encode(\"utf-8\")" in direct_source else "unknown",
        "json_serialization_label": "manual_json_compact_bytes" if "separators=(\",\", \":\")" in direct_source or "separators=(\",\",\":\")" in direct_source else "manual_json_compact_bytes",
        "content_type_header_label": "present" if "Content-Type" in direct_source else "unknown",
        "authorization_header_label": "present" if "Authorization" in direct_source else "unknown",
        "auth_scheme_label": "bearer" if "Bearer" in direct_source else "unknown",
        "extra_header_shape_label": "none",
        "provider_header_shape_label": "authorization_content_type_only",
        "url_join_label": "direct_target_url_supplied",
        "request_target_suffix_label": "chat_completions_suffix",
        "timeout_shape_label": "urllib_timeout_30" if "timeout=30" in direct_source else "unknown",
        "payload_shape_label": "chat_tool_direct_aligned" if "_chat_tool_payload" in direct_source and "max_tokens" in direct_source else "unknown",
    }


def _proxy_transport_capture(proxy_source: str, config_text: str) -> dict[str, str]:
    has_httpx_post = "httpx.AsyncClient" in proxy_source and ".post(" in proxy_source
    has_json_kwarg = "json=req_json" in proxy_source
    has_headers_kwarg = "headers=headers" in proxy_source
    has_auth = '"Authorization"' in proxy_source
    has_content_type = '"Content-Type"' in proxy_source
    extra_header_shape = "referer_or_title_possible" if "HTTP-Referer" in proxy_source or "X-Title" in proxy_source else "none"
    # Current committed config has no default title and the diagnostic boundary does not source env values.
    if "default_title" not in config_text:
        extra_header_shape = "none"
    selected_base = "GRC_UPSTREAM_BASE_URL_then_NOVACODE_BASE_URL" if "GRC_UPSTREAM_BASE_URL" in proxy_source and "base_url_env: NOVACODE_BASE_URL" in config_text else "unknown"
    selected_api = "CHUANGZHI_API_KEY" if "GRC_UPSTREAM_API_KEY_ENV" in proxy_source else "NOVACODE_API_KEY"
    return {
        "transport_client_label": "httpx_async_client_post" if has_httpx_post else "unknown",
        "client_stack_label": "proxy_httpx_json_kwarg" if has_httpx_post and has_json_kwarg else "unknown",
        "body_submission_label": "httpx_json_kwarg" if has_json_kwarg else "unknown",
        "json_serialization_label": "httpx_json_parameter" if has_json_kwarg else "unknown",
        "content_type_header_label": "present" if has_content_type else "missing",
        "authorization_header_label": "present" if has_auth and has_headers_kwarg else "missing",
        "auth_scheme_label": "bearer" if "Bearer" in proxy_source else "unknown",
        "extra_header_shape_label": extra_header_shape,
        "provider_header_shape_label": _header_shape(has_auth, has_content_type, extra_header_shape),
        "url_join_label": "base_url_chat_completions_appended" if "/chat/completions" in proxy_source else "unknown",
        "request_target_suffix_label": "chat_completions_suffix" if "/chat/completions" in proxy_source else "unknown",
        "timeout_shape_label": "config_timeout_sec" if "timeout=timeout_sec" in proxy_source else "unknown",
        "payload_shape_label": "chat_tool_direct_aligned" if "GRC_PROXY_RESPONSES_TOOL_SHAPE_DIRECT_ALIGNMENT" in proxy_source else "unknown",
        "selected_base_url_env_label": selected_base,
        "selected_api_key_env_label": selected_api,
    }


def _payload_match_label(direct: dict[str, str], proxy: dict[str, str]) -> str:
    if direct.get("payload_shape_label") == proxy.get("payload_shape_label") == "chat_tool_direct_aligned":
        return "matched_direct_chat_tool_shape"
    if proxy.get("payload_shape_label") == "unknown":
        return "transport_only_payload_not_compared"
    return "mismatch"


def _suspected_cause(direct: dict[str, str], proxy: dict[str, str], payload_match: str) -> str:
    if proxy.get("provider_header_shape_label") != direct.get("provider_header_shape_label"):
        return "header_shape_drift"
    if payload_match not in {"matched_direct_chat_tool_shape", "transport_only_payload_not_compared"}:
        return "payload_shape_drift"
    if proxy.get("url_join_label") != "base_url_chat_completions_appended":
        return "url_join_or_provider_policy"
    if proxy.get("transport_client_label") != direct.get("transport_client_label") or proxy.get("json_serialization_label") != direct.get("json_serialization_label"):
        return "transport_stack_or_serialization_drift"
    return "none_observed"


def build_diff_record() -> dict[str, Any]:
    proxy_source = (REPO_ROOT / PROXY_SOURCE).read_text(encoding="utf-8")
    direct_source = (REPO_ROOT / DIRECT_RUNNER_SOURCE).read_text(encoding="utf-8")
    config_text = (REPO_ROOT / RUNTIME_CONFIG).read_text(encoding="utf-8")
    direct = _direct_transport_capture(direct_source)
    proxy = _proxy_transport_capture(proxy_source, config_text)
    payload_match = _payload_match_label(direct, proxy)
    record = _base_record(command_executed=True)
    record.update(
        {
            "transport_client_label": proxy["transport_client_label"],
            "client_stack_label": proxy["client_stack_label"],
            "body_submission_label": proxy["body_submission_label"],
            "json_serialization_label": proxy["json_serialization_label"],
            "content_type_header_label": proxy["content_type_header_label"],
            "authorization_header_label": proxy["authorization_header_label"],
            "auth_scheme_label": proxy["auth_scheme_label"],
            "extra_header_shape_label": proxy["extra_header_shape_label"],
            "provider_header_shape_label": proxy["provider_header_shape_label"],
            "url_join_label": proxy["url_join_label"],
            "request_target_suffix_label": proxy["request_target_suffix_label"],
            "timeout_shape_label": proxy["timeout_shape_label"],
            "payload_shape_match_label": payload_match,
            "payload_shape_label": proxy["payload_shape_label"],
            "selected_base_url_env_label": proxy["selected_base_url_env_label"],
            "selected_api_key_env_label": proxy["selected_api_key_env_label"],
            "direct_transport_client_label": direct["transport_client_label"],
            "direct_body_submission_label": direct["body_submission_label"],
            "direct_json_serialization_label": direct["json_serialization_label"],
            "direct_timeout_shape_label": direct["timeout_shape_label"],
            "direct_header_shape_label": direct["provider_header_shape_label"],
        }
    )
    record["suspected_403_cause_label"] = _suspected_cause(direct, proxy, payload_match)
    return record


def _write_artifact(record: dict[str, Any], output_artifact: Path) -> None:
    payload = {
        "artifact_kind": "bfcl_proxy_transport_request_capture_diff_compact",
        "compact_schema_version": "proxy_transport_request_capture_diff_v1",
        "measurement_kind": "compact_offline_proxy_transport_request_capture_diff",
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
        "report_scope": "bfcl_proxy_transport_request_capture_diff_plan",
        "packet_path": str(packet_path),
        "output_artifact_planned": str(output_artifact),
        "approval_status": packet_summary.get("approval_status"),
        "authorized": packet_summary.get("authorized"),
        "provider_request_authorized": packet_summary.get("provider_request_authorized"),
        "proxy_live_request_authorized": packet_summary.get("proxy_live_request_authorized"),
        "profile_source_authorized": packet_summary.get("profile_source_authorized"),
        "compact_only": True,
        "offline_no_provider_only": True,
        "fake_transport_capture_required": True,
        "env_profile_sourced": False,
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        **_base_record(command_executed=False),
        "blockers": list(packet_summary.get("blockers", [])),
    }


def execute_transport_capture_diff(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_proxy_transport_request_capture_diff_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("transport_capture_diff_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return {
            "report_scope": "bfcl_proxy_transport_request_capture_diff_execute",
            **_base_record(command_executed=False),
            "env_profile_sourced": False,
            "output_artifact": None,
            "blockers": sorted(set(blockers)),
        }
    record = build_diff_record()
    _write_artifact(record, output_artifact)
    artifact_summary = check_artifact(output_artifact)
    if not artifact_summary.get("bfcl_proxy_transport_request_capture_diff_artifact_passed"):
        blockers.extend(str(blocker) for blocker in artifact_summary.get("blockers", []))
    return {
        "report_scope": "bfcl_proxy_transport_request_capture_diff_execute",
        **record,
        "env_profile_sourced": False,
        "output_artifact": str(output_artifact),
        "blockers": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute-transport-capture-diff", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_transport_capture_diff and args.dry_run:
        summary = {"report_scope": "bfcl_proxy_transport_request_capture_diff_execute", "blockers": ["dry_run_and_execute_both_set"]}
    elif args.execute_transport_capture_diff:
        summary = execute_transport_capture_diff(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
