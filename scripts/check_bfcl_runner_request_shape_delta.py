#!/usr/bin/env python3
"""Check no-provider BFCL runner/request-shape delta packet and artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_runner_request_shape_delta_packet.json")
DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_runner_request_shape_delta.json")
SIGNED_ROUTE = "gpt-4.1"
SIGNED_PROFILE = "novacode"
REQUIRED_FALSE_PACKET = (
    "authorized",
    "provider_request_authorized",
    "bfcl_smoke_authorized",
    "bfcl_scorer_authorized",
    "full_baseline_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "provider_request_executed",
    "bfcl_smoke_executed",
    "scorer_executed",
    "full_baseline_executed",
    "endpoint_value_committed",
    "api_key_value_committed",
    "raw_material_persisted",
)
REQUIRED_FALSE_ARTIFACT = (
    "provider_request_executed",
    "bfcl_smoke_executed",
    "scorer_executed",
    "full_baseline_executed",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "raw_prompt_persisted",
    "raw_case_content_persisted",
    "raw_provider_payload_persisted",
    "raw_log_persisted",
    "raw_trace_persisted",
    "endpoint_or_key_committed",
)
FORBIDDEN_KEY_RE = re.compile(r"(raw_(?:prompt|case|provider|payload|log|trace|response)|case_id|gold|reference|expected|scorer_diff|candidate_output|endpoint_value|api_key_value)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|apicz|boyuerichdata|raw prompt|raw case|provider payload|scorer diff|gold/reference/expected|candidate output)", re.IGNORECASE)
LOOPBACK_REDACTED_OK = "loopback_proxy_v1_redacted"
ALLOWED_FALSE_KEYS = set(REQUIRED_FALSE_ARTIFACT) | set(REQUIRED_FALSE_PACKET)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain object")
    return data


def _walk(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, path + (str(index),)))
    return items


def _scan_forbidden(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        if path:
            key = path[-1]
            if FORBIDDEN_KEY_RE.search(key) and key not in ALLOWED_FALSE_KEYS:
                blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str):
            if value == LOOPBACK_REDACTED_OK:
                continue
            if FORBIDDEN_VALUE_RE.search(value):
                blockers.append(f"forbidden_value:{'.'.join(path)}")
            if "http://" in value or "https://" in value:
                blockers.append(f"url_literal:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_runner_request_shape_delta_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"packet_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_model") != SIGNED_ROUTE or data.get("active_profile") != SIGNED_PROFILE:
        blockers.append("packet_route_drift")
    if data.get("fallback_allowed") is not False or data.get("gpt_4o_fallback_allowed") is not False or data.get("openrouter_allowed") is not False:
        blockers.append("packet_fallback_or_openrouter_enabled")
    for key in REQUIRED_FALSE_PACKET:
        if data.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{data.get(key)!r}")
    for key in ("candidate_specs_inert", "endpoint_env_only", "api_key_env_only", "compact_shape_only"):
        if data.get(key) is not True:
            blockers.append(f"packet_{key}_not_true:{data.get(key)!r}")
    blockers.extend(f"packet_{item}" for item in _scan_forbidden(data))
    return blockers


def validate_artifact(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_runner_request_shape_delta":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("route_model") != SIGNED_ROUTE or data.get("active_profile") != SIGNED_PROFILE:
        blockers.append("artifact_route_drift")
    for key in REQUIRED_FALSE_ARTIFACT:
        if data.get(key) is not False:
            blockers.append(f"artifact_{key}_not_false:{data.get(key)!r}")
    if not data.get("suspected_gap"):
        blockers.append("artifact_suspected_gap_missing")
    if not isinstance(data.get("shape_deltas"), list):
        blockers.append("artifact_shape_deltas_not_list")
    for section in ("telemetry_shape", "bfcl_runner_shape"):
        if not isinstance(data.get(section), dict):
            blockers.append(f"artifact_{section}_missing")
    blockers.extend(f"artifact_{item}" for item in _scan_forbidden(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, artifact_path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    packet = _load(packet_path)
    artifact = _load(artifact_path)
    blockers = validate_packet(packet) + validate_artifact(artifact)
    return {
        "report_scope": "bfcl_runner_request_shape_delta_check",
        "packet_path": str(packet_path),
        "artifact_path": str(artifact_path),
        "bfcl_runner_request_shape_delta_passed": not blockers,
        "suspected_gap": artifact.get("suspected_gap"),
        "shape_deltas": artifact.get("shape_deltas"),
        "blockers": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_runner_request_shape_delta_check", "bfcl_runner_request_shape_delta_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_runner_request_shape_delta_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
