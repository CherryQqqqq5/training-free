#!/usr/bin/env python3
"""Validate the post-approval RASHE runtime-behavior boundary.

This checker is for the L1 runtime behavior approval only. It must not be used
as approval for provider calls, source collection, candidate generation, scorer
execution, performance evidence, or Huawei acceptance claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_runtime_behavior_approval_packet.json")
DEFAULT_CONFIG = Path("configs/runtime_bfcl_skills.yaml")

REQUIRED_PACKET_VALUES = {
    "approval_packet_kind": "runtime_behavior",
    "approval_status": "approved",
    "authorized": True,
    "runtime_behavior_authorized": True,
    "runtime_behavior_scope": "synthetic_default_disabled_only",
    "default_enabled_required_if_approved": False,
}

DOWNSTREAM_FALSE_FIELDS = (
    "provider_calls_authorized",
    "provider_scorer_side_effects_allowed",
    "source_collection_authorized",
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "proposer_execution_authorized",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "bfcl_performance_ready",
    "prompt_injection_authorized",
    "retry_authorized",
    "tool_path_mutation_authorized",
    "raw_trace_authorized",
    "raw_payload_capture_authorized",
    "dev_holdout_authorized",
    "paired_comparison_authorized",
)

NO_LEAKAGE_FALSE_FIELDS = (
    "gold_used",
    "expected_used",
    "scorer_diff_used",
    "candidate_output_used",
    "holdout_feedback_used",
    "full_suite_feedback_used",
    "raw_trace_committed",
    "case_id_specific_rules_allowed",
)

CONFIG_FALSE_FIELDS = (
    "enabled",
    "provider_calls_authorized",
    "source_collection_authorized",
    "scorer_authorized",
    "candidate_generation_authorized",
    "prompt_injection_authorized",
    "retry_authorized",
    "ruleengine_proxy_active_path_import_allowed",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        data: dict[str, Any] = {}
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            value = raw_value.strip()
            if value == "false":
                data[key.strip()] = False
            elif value == "true":
                data[key.strip()] = True
            elif value.isdigit():
                data[key.strip()] = int(value)
            else:
                data[key.strip()] = value
        return data
    loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return loaded


def validate(packet: dict[str, Any], config: dict[str, Any]) -> list[str]:
    blockers: list[str] = []

    for key, expected in REQUIRED_PACKET_VALUES.items():
        if packet.get(key) != expected:
            blockers.append(f"packet_{key}_invalid:{packet.get(key)!r}")

    for key in DOWNSTREAM_FALSE_FIELDS:
        if packet.get(key) is not False:
            blockers.append(f"packet_downstream_field_not_false:{key}")

    no_leakage = packet.get("no_leakage_required")
    if not isinstance(no_leakage, dict):
        blockers.append("packet_no_leakage_required_missing")
    else:
        for key in NO_LEAKAGE_FALSE_FIELDS:
            if no_leakage.get(key) is not False:
                blockers.append(f"packet_no_leakage_field_not_false:{key}")
        for key, value in no_leakage.items():
            if value is not False:
                blockers.append(f"packet_no_leakage_extra_field_not_false:{key}")

    for key in CONFIG_FALSE_FIELDS:
        if config.get(key) is not False:
            blockers.append(f"runtime_config_{key}_not_false")

    return blockers


def check(packet_path: Path = DEFAULT_PACKET, config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    packet = load_json(packet_path)
    config = load_yaml(config_path)
    blockers = validate(packet, config)
    downstream_false = {key: packet.get(key) for key in DOWNSTREAM_FALSE_FIELDS}
    config_defaults = {key: config.get(key) for key in CONFIG_FALSE_FIELDS}
    return {
        "report_scope": "rashe_runtime_behavior_approved_check",
        "packet_path": str(packet_path),
        "config_path": str(config_path),
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "runtime_behavior_authorized": packet.get("runtime_behavior_authorized"),
        "runtime_behavior_scope": packet.get("runtime_behavior_scope"),
        "default_enabled_required_if_approved": packet.get("default_enabled_required_if_approved"),
        "downstream_false_fields": downstream_false,
        "config_defaults": config_defaults,
        "rashe_runtime_behavior_approved_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "rashe_runtime_behavior_approved_check",
            "packet_path": str(args.packet),
            "config_path": str(args.config),
            "rashe_runtime_behavior_approved_passed": False,
            "blockers": [f"load_error:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_runtime_behavior_approved_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
