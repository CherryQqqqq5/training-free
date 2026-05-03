#!/usr/bin/env python3
"""Dry-run or execute compact proxy Responses tool-shape preflight."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_proxy_responses_tool_shape_artifact import check as check_artifact
from scripts.check_bfcl_proxy_responses_tool_shape_gate import DEFAULT_PACKET, REQUIRED_COMPACT_FIELDS, check as check_packet

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_responses_tool_shape_compact.json")
TOOL_NAME = "synthetic_proxy_responses_tool_shape_ping"
Probe = Callable[..., dict]


def _base_record(*, command_executed: bool = False) -> dict[str, Any]:
    return {
        "preflight_command_executed": command_executed,
        "proxy_started": False,
        "local_proxy_request_executed": False,
        "local_responses_path_selected": False,
        "proxy_python_label": _select_proxy_python()[1],
        "proxy_start_failure_label": "none_observed",
        "upstream_provider_request_authorized": False,
        "upstream_provider_call_started": False,
        "upstream_chat_route_label": "not_reached",
        "http_status_class": "not_observed",
        "provider_http_status_label": "not_observed",
        "response_body_read": False,
        "response_body_persisted": False,
        "response_json_parse_label": "not_read",
        "responses_envelope_shape_label": "not_checked",
        "function_call_present": False,
        "function_name_match": False,
        "trace_emission_label": "not_observed",
        "trace_count_class": "not_observed",
        "raw_temp_outputs_removed": True,
        "raw_outputs_committed": False,
        "bfcl_generate_started": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "full_baseline_executed": False,
        "candidate_specs_inert": True,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "performance_evidence": False,
        "stop_gate_triggered": "none",
        "preflight_failed_check_label": "none_observed",
        "suspected_failure_stage": "not_executed" if not command_executed else "pending",
    }


def _http_status_class(status: int | None) -> str:
    if status is None:
        return "transport_error"
    if 200 <= status <= 299:
        return "2xx"
    if 300 <= status <= 399:
        return "3xx"
    if 400 <= status <= 499:
        return "4xx"
    if 500 <= status <= 599:
        return "5xx"
    return "unknown"


def _provider_http_status_label(status: int | None) -> str:
    if status is None:
        return "transport_error"
    if status in {400, 401, 403, 404, 405, 415, 422, 429}:
        return f"status_{status}"
    if 400 <= status <= 499:
        return "other_4xx"
    if 500 <= status <= 599:
        return "status_5xx"
    return "unknown"


def _trace_count_class(count: int | None) -> str:
    if count is None:
        return "not_observed"
    if count <= 0:
        return "zero"
    if count == 1:
        return "one"
    return "multiple"


def _set_failure(record: dict[str, Any], label: str, stage: str) -> None:
    record["preflight_failed_check_label"] = label
    record["stop_gate_triggered"] = label
    record["suspected_failure_stage"] = stage



def _select_proxy_python() -> tuple[str, str]:
    grc_python = os.environ.get("GRC_PYTHON")
    if grc_python:
        return grc_python, "grc_python_env"
    repo_venv = REPO_ROOT / ".venv" / "bin" / "python"
    if repo_venv.is_file() and os.access(str(repo_venv), os.X_OK):
        return str(repo_venv), "repo_venv"
    return sys.executable, "caller_python"


def _proxy_config_start_failure_label(env: dict[str, str]) -> str:
    if env.get("GRC_UPSTREAM_BASE_URL") or env.get("NOVACODE_BASE_URL"):
        return "none_observed"
    return "proxy_config_startup_failed"

def _responses_payload() -> dict[str, Any]:
    return {
        "model": "gpt-4.1",
        "instructions": "Synthetic proxy Responses tool-shape preflight. Use the tool when required.",
        "input": [{"role": "user", "content": "Run synthetic proxy Responses shape preflight."}],
        "tools": [
            {
                "type": "function",
                "name": TOOL_NAME,
                "description": "Synthetic proxy Responses shape tool carrying no BFCL case data.",
                "parameters": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "max_output_tokens": 16,
    }


def _post_json(url: str, payload: dict[str, Any]) -> tuple[int | None, dict[str, Any], str]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer synthetic-local-proxy-key"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = int(response.status)
            body = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read()
    except Exception:
        return None, {}, "not_read"
    if not body:
        return status, {}, "empty_body"
    try:
        payload_json = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, {}, "invalid_json"
    return status, payload_json if isinstance(payload_json, dict) else {}, "parsed_json"


def _classify_responses_envelope(payload: Any) -> tuple[str, bool, bool]:
    if not isinstance(payload, dict):
        return "malformed", False, False
    output = payload.get("output")
    if not isinstance(output, list):
        return "no_output", False, False
    if not output:
        return "responses_empty_output", False, False
    has_message = False
    has_function_call = False
    name_match = False
    for item in output:
        if not isinstance(item, dict):
            return "malformed", False, False
        item_type = item.get("type")
        if item_type == "function_call":
            has_function_call = True
            if item.get("name") == TOOL_NAME:
                name_match = True
        elif item_type == "message":
            has_message = True
    if has_function_call:
        return "responses_function_call", True, name_match
    if has_message:
        return "responses_message_text", False, False
    return "malformed", False, False


def _write_artifact(record: dict[str, Any], output_artifact: Path) -> None:
    payload = {
        "artifact_kind": "bfcl_proxy_responses_tool_shape_compact",
        "compact_schema_version": "proxy_responses_tool_shape_v1",
        "measurement_kind": "compact_synthetic_proxy_responses_tool_shape_preflight",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
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


def _blocked_summary(blockers: list[str]) -> dict[str, Any]:
    return {
        "report_scope": "bfcl_proxy_responses_tool_shape_execute",
        **_base_record(command_executed=False),
        "env_profile_sourced": False,
        "output_artifact": None,
        "blockers": sorted(set(blockers)),
    }


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_proxy_responses_tool_shape_plan",
        "packet_path": str(packet_path),
        "output_artifact_planned": str(output_artifact),
        "approval_status": packet_summary.get("approval_status"),
        "authorized": packet_summary.get("authorized"),
        "proxy_responses_tool_shape_authorized": packet_summary.get("proxy_responses_tool_shape_authorized"),
        "local_proxy_request_authorized": packet_summary.get("local_proxy_request_authorized"),
        "provider_request_authorized": packet_summary.get("provider_request_authorized"),
        "planned_attempt_count": 1,
        "planned_local_request_path_label": "local_proxy_responses_path",
        "planned_upstream_route_label": "local_proxy_responses_to_upstream_chat_completions",
        "compact_only": True,
        "synthetic_probe_only": True,
        "env_profile_sourced": False,
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        **_base_record(command_executed=False),
        "blockers": list(packet_summary.get("blockers", [])),
    }


def _default_proxy_probe(temp_root: Path) -> dict[str, Any]:
    trace_dir = temp_root / "traces"
    proxy_log = temp_root / "proxy.log"
    trace_dir.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("GRC_PROXY_RESPONSES_TOOL_SHAPE_PORT", "8139"))
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else str(REPO_ROOT / "src")
    proxy_python, proxy_python_label = _select_proxy_python()
    config_start_failure_label = _proxy_config_start_failure_label(env)
    if config_start_failure_label != "none_observed":
        return {
            "proxy_started": False,
            "status": None,
            "payload": {},
            "parse_label": "not_read",
            "trace_count": 0,
            "proxy_python_label": proxy_python_label,
            "proxy_start_failure_label": config_start_failure_label,
        }
    command = [
        proxy_python,
        "-m",
        "grc.cli",
        "serve",
        "--config",
        "configs/runtime_bfcl_structured.yaml",
        "--rules-dir",
        "rules/baseline_empty",
        "--trace-dir",
        str(trace_dir),
        "--port",
        str(port),
    ]
    with proxy_log.open("w", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(command, cwd=str(REPO_ROOT), env=env, stdout=log_handle, stderr=subprocess.STDOUT)
        try:
            for _ in range(60):
                if proc.poll() is not None:
                    return {
                        "proxy_started": False,
                        "status": None,
                        "payload": {},
                        "parse_label": "not_read",
                        "trace_count": 0,
                        "proxy_python_label": proxy_python_label,
                        "proxy_start_failure_label": "proxy_import_or_process_exit",
                    }
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1).read()
                    break
                except Exception:
                    time.sleep(0.2)
            else:
                return {
                    "proxy_started": False,
                    "status": None,
                    "payload": {},
                    "parse_label": "not_read",
                    "trace_count": 0,
                    "proxy_python_label": proxy_python_label,
                    "proxy_start_failure_label": "proxy_health_timeout",
                }
            status, payload, parse_label = _post_json(f"http://127.0.0.1:{port}/v1/responses", _responses_payload())
            return {
                "proxy_started": True,
                "status": status,
                "payload": payload,
                "parse_label": parse_label,
                "trace_count": len(list(trace_dir.glob("*.json"))),
                "proxy_python_label": proxy_python_label,
                "proxy_start_failure_label": "none_observed",
            }
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


def execute_proxy_responses_tool_shape(
    packet_path: Path = DEFAULT_PACKET,
    output_artifact: Path = DEFAULT_OUTPUT,
    *,
    proxy_probe: Probe | None = None,
) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_proxy_responses_tool_shape_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("proxy_responses_tool_shape_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return _blocked_summary(blockers)

    record = _base_record(command_executed=True)
    record["upstream_provider_request_authorized"] = True
    temp_root = Path(tempfile.mkdtemp(prefix="bfcl_proxy_responses_tool_shape_"))
    selected_probe = proxy_probe or _default_proxy_probe
    cleanup_removed = False
    try:
        try:
            observation = selected_probe(temp_root=temp_root)
        except TypeError:
            observation = selected_probe(temp_root)
        except Exception:
            observation = {
                "proxy_started": False,
                "status": None,
                "payload": {},
                "parse_label": "not_read",
                "trace_count": 0,
                "probe_exception": True,
                "proxy_python_label": record["proxy_python_label"],
                "proxy_start_failure_label": "unknown",
            }
        proxy_python_label = observation.get("proxy_python_label")
        if proxy_python_label in {"grc_python_env", "repo_venv", "caller_python"}:
            record["proxy_python_label"] = str(proxy_python_label)
        proxy_start_failure_label = observation.get("proxy_start_failure_label")
        if proxy_start_failure_label in {"proxy_import_or_process_exit", "proxy_config_startup_failed", "proxy_health_timeout", "none_observed", "unknown"}:
            record["proxy_start_failure_label"] = str(proxy_start_failure_label)
        record["proxy_started"] = bool(observation.get("proxy_started"))
        if not record["proxy_started"]:
            if record["proxy_start_failure_label"] == "none_observed":
                record["proxy_start_failure_label"] = "unknown"
            _set_failure(record, "proxy_start_failed", "proxy_start_failed")
            blockers.append("proxy_start_failed")
        else:
            record["local_proxy_request_executed"] = True
            record["local_responses_path_selected"] = True
            record["upstream_provider_call_started"] = True
            record["upstream_chat_route_label"] = "local_proxy_responses_to_upstream_chat_completions"
            status = observation.get("status") if isinstance(observation.get("status"), int) else None
            payload = observation.get("payload") if isinstance(observation.get("payload"), dict) else {}
            parse_label = str(observation.get("parse_label") or "not_read")
            record["http_status_class"] = _http_status_class(status)
            record["provider_http_status_label"] = _provider_http_status_label(status)
            record["response_body_read"] = parse_label != "not_read"
            record["response_json_parse_label"] = parse_label if parse_label in {"parsed_json", "invalid_json", "empty_body", "not_read"} else "invalid_json"
            trace_count = observation.get("trace_count") if isinstance(observation.get("trace_count"), int) else None
            record["trace_count_class"] = _trace_count_class(trace_count)
            record["trace_emission_label"] = "trace_emitted" if isinstance(trace_count, int) and trace_count > 0 else "trace_missing"
            if status is None:
                _set_failure(record, "provider_transport_error", "provider_transport_error")
                blockers.append("provider_transport_error")
            elif record["http_status_class"] != "2xx":
                record["responses_envelope_shape_label"] = "non_2xx"
                _set_failure(record, "provider_non_2xx", "provider_non_2xx")
                blockers.append("provider_non_2xx")
            elif record["response_json_parse_label"] != "parsed_json":
                record["responses_envelope_shape_label"] = "invalid_json" if record["response_json_parse_label"] == "invalid_json" else "malformed"
                _set_failure(record, "responses_envelope_malformed", "responses_envelope_malformed")
                blockers.append("responses_envelope_malformed")
            else:
                shape_label, function_present, name_match = _classify_responses_envelope(payload)
                record["responses_envelope_shape_label"] = shape_label
                record["function_call_present"] = function_present
                record["function_name_match"] = name_match
                if shape_label != "responses_function_call":
                    _set_failure(record, "responses_envelope_malformed", "responses_envelope_malformed")
                    blockers.append("responses_envelope_malformed")
                elif not name_match:
                    _set_failure(record, "responses_function_call_missing", "responses_function_call_missing")
                    blockers.append("responses_function_call_missing")
    finally:
        shutil.rmtree(str(temp_root), ignore_errors=True)
        cleanup_removed = not temp_root.exists()
    record["raw_temp_outputs_removed"] = cleanup_removed
    if not cleanup_removed:
        _set_failure(record, "temp_raw_cleanup_failed", "temp_raw_cleanup_failed")
        blockers.append("temp_raw_cleanup_failed")
    if not blockers:
        record["preflight_failed_check_label"] = "none_observed"
        record["stop_gate_triggered"] = "stopped_after_proxy_responses_tool_shape"
        record["suspected_failure_stage"] = "responses_tool_shape_classified_without_raw_persistence"
    _write_artifact(record, output_artifact)
    artifact_summary = check_artifact(output_artifact)
    if not artifact_summary.get("bfcl_proxy_responses_tool_shape_artifact_passed"):
        blockers.extend(str(blocker) for blocker in artifact_summary.get("blockers", []))
    return {
        "report_scope": "bfcl_proxy_responses_tool_shape_execute",
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
    parser.add_argument("--execute-proxy-responses-tool-shape", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_proxy_responses_tool_shape:
        summary = execute_proxy_responses_tool_shape(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
