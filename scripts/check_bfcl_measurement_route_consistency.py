#!/usr/bin/env python3
"""Check active BFCL measurement route consistency."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATHS = {
    "runtime": Path("configs/runtime.yaml"),
    "runtime_bfcl_structured": Path("configs/runtime_bfcl_structured.yaml"),
    "bfcl_eval_protocol": Path("configs/bfcl_eval_protocol.yaml"),
    "bfcl_v4_phase1_env": Path("configs/bfcl_v4_phase1.env"),
}
ROUTE_METADATA = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_route_consistency.json")
ROUTE_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_route_update_approval_packet.json")
SIGNED_MODEL = "gpt-4.1"
SIGNED_PROFILE = "novacode"
SIGNED_PROVIDER_PROFILE = "Chuangzhi/Novacode"
HISTORICAL_GPT_5_2_KEYS = {"old_signed_model", "old_signed_model_status"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _walk_json(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk_json(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk_json(child, path + (str(index),)))
    return items


def _check_no_active_gpt_5_2(name: str, data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk_json(data):
        if value != "gpt-5.2":
            continue
        if path and path[-1] in HISTORICAL_GPT_5_2_KEYS:
            continue
        if any(part in {"historical", "superseded", "old_route", "old_route_evidence"} for part in path):
            continue
        blockers.append(f"{name}_active_gpt_5_2:{'.'.join(path)}")
    return blockers


def _check_no_gpt_4o_fallback(name: str, data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk_json(data):
        key = path[-1] if path else ""
        if key in {"gpt_4o_fallback_allowed", "gpt-4o_fallback_allowed", "fallback_allowed"} and value is True:
            blockers.append(f"{name}_fallback_allowed_true:{'.'.join(path)}")
        if key in {"fallback_model", "fallback_route", "active_fallback_model"} and isinstance(value, str) and "gpt-4o" in value:
            blockers.append(f"{name}_gpt_4o_fallback_route:{'.'.join(path)}")
    return blockers


def _check_runtime(name: str, path: Path, blockers: list[str]) -> None:
    data = load_yaml(path)
    upstream = data.get("upstream") if isinstance(data.get("upstream"), dict) else {}
    if upstream.get("active_profile") != SIGNED_PROFILE:
        blockers.append(f"{name}_active_profile_invalid:{upstream.get('active_profile')!r}")
    if upstream.get("model") != SIGNED_MODEL:
        blockers.append(f"{name}_upstream_model_invalid:{upstream.get('model')!r}")
    if upstream.get("fallback_allowed") is not False:
        blockers.append(f"{name}_fallback_allowed_not_false:{upstream.get('fallback_allowed')!r}")
    if upstream.get("gpt_4o_fallback_allowed") is not False:
        blockers.append(f"{name}_gpt_4o_fallback_allowed_not_false:{upstream.get('gpt_4o_fallback_allowed')!r}")
    profiles = upstream.get("profiles") if isinstance(upstream.get("profiles"), dict) else {}
    novacode = profiles.get("novacode") if isinstance(profiles.get("novacode"), dict) else {}
    if novacode.get("model") != SIGNED_MODEL:
        blockers.append(f"{name}_novacode_model_invalid:{novacode.get('model')!r}")
    if novacode.get("provider_profile") != SIGNED_PROVIDER_PROFILE:
        blockers.append(f"{name}_provider_profile_invalid:{novacode.get('provider_profile')!r}")
    if "openrouter" in profiles:
        blockers.append(f"{name}_openrouter_profile_present")
    blockers.extend(_check_no_active_gpt_5_2(name, data))
    blockers.extend(_check_no_gpt_4o_fallback(name, data))


def _check_protocol(path: Path, blockers: list[str]) -> None:
    data = load_yaml(path)
    model = data.get("model") if isinstance(data.get("model"), dict) else {}
    if model.get("upstream_profile") != SIGNED_PROFILE:
        blockers.append(f"bfcl_eval_protocol_upstream_profile_invalid:{model.get('upstream_profile')!r}")
    if model.get("provider_profile") != SIGNED_PROVIDER_PROFILE:
        blockers.append(f"bfcl_eval_protocol_provider_profile_invalid:{model.get('provider_profile')!r}")
    if model.get("upstream_model_route") != SIGNED_MODEL:
        blockers.append(f"bfcl_eval_protocol_upstream_model_route_invalid:{model.get('upstream_model_route')!r}")
    if model.get("fallback_allowed") is not False:
        blockers.append(f"bfcl_eval_protocol_fallback_allowed_not_false:{model.get('fallback_allowed')!r}")
    if model.get("gpt_4o_fallback_allowed") is not False:
        blockers.append(f"bfcl_eval_protocol_gpt_4o_fallback_allowed_not_false:{model.get('gpt_4o_fallback_allowed')!r}")
    blockers.extend(_check_no_active_gpt_5_2("bfcl_eval_protocol", data))
    blockers.extend(_check_no_gpt_4o_fallback("bfcl_eval_protocol", data))


def _env_default_model(text: str) -> str | None:
    match = re.search(r'export\s+GRC_UPSTREAM_MODEL="([^"]+)"', text)
    return match.group(1) if match else None


def _check_env(path: Path, blockers: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    if 'export GRC_UPSTREAM_PROFILE="${GRC_UPSTREAM_PROFILE:-novacode}"' not in text:
        blockers.append("bfcl_v4_phase1_env_default_profile_not_novacode")
    if 'export GRC_UPSTREAM_MODEL="gpt-4.1"' not in text:
        blockers.append(f"bfcl_v4_phase1_env_default_model_not_gpt_4_1:{_env_default_model(text)!r}")
    if 'OpenRouter upstream is disabled for Stage-1 BFCL measurement readiness' not in text:
        blockers.append("bfcl_v4_phase1_env_openrouter_not_fail_closed")
    if 'export GRC_UPSTREAM_MODEL="gpt-5.2"' in text or "GRC_UPSTREAM_MODEL='gpt-5.2'" in text:
        blockers.append("bfcl_v4_phase1_env_active_gpt_5_2")
    if 'export GRC_UPSTREAM_PROFILE="${GRC_UPSTREAM_PROFILE:-openrouter}"' in text:
        blockers.append("bfcl_v4_phase1_env_openrouter_default_active")
    if re.search(r'openrouter\)\s*\n\s*export\s+GRC_UPSTREAM_MODEL=', text):
        blockers.append("bfcl_v4_phase1_env_openrouter_exports_model")
    if "gpt-4o" in text and "GRC_BFCL_MODEL" not in text:
        blockers.append("bfcl_v4_phase1_env_gpt_4o_active_or_fallback")


def _check_route_metadata(path: Path, blockers: list[str]) -> None:
    data = load_json(path)
    expected = {
        "artifact_kind": "bfcl_measurement_route_consistency",
        "provider_profile": SIGNED_PROVIDER_PROFILE,
        "active_profile": SIGNED_PROFILE,
        "route_model": SIGNED_MODEL,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "old_signed_model": "gpt-5.2",
        "old_signed_model_status": "historical_superseded_inactive",
        "candidate_specs_inert": True,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "scorer_authorized": False,
        "provider_call_authorized": False,
        "phase_b_rerun_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"route_metadata_{key}_invalid:{data.get(key)!r}")
    blockers.extend(_check_no_active_gpt_5_2("route_metadata", data))
    blockers.extend(_check_no_gpt_4o_fallback("route_metadata", data))


def _check_route_packet(path: Path, blockers: list[str]) -> None:
    data = load_json(path)
    if data.get("new_signed_model") != SIGNED_MODEL:
        blockers.append(f"route_packet_new_signed_model_invalid:{data.get('new_signed_model')!r}")
    if data.get("old_signed_model") != "gpt-5.2" or data.get("old_signed_model_active") is not False:
        blockers.append("route_packet_old_signed_model_not_historical_inactive")
    if data.get("gpt_4o_fallback_allowed") is not False or data.get("fallback_allowed") is not False:
        blockers.append("route_packet_fallback_allowed_not_false")


def check(repo_root: Path = Path(".")) -> dict[str, Any]:
    blockers: list[str] = []
    _check_runtime("runtime_yaml", repo_root / CONFIG_PATHS["runtime"], blockers)
    _check_runtime("runtime_bfcl_structured_yaml", repo_root / CONFIG_PATHS["runtime_bfcl_structured"], blockers)
    _check_protocol(repo_root / CONFIG_PATHS["bfcl_eval_protocol"], blockers)
    _check_env(repo_root / CONFIG_PATHS["bfcl_v4_phase1_env"], blockers)
    _check_route_metadata(repo_root / ROUTE_METADATA, blockers)
    _check_route_packet(repo_root / ROUTE_PACKET, blockers)
    return {
        "report_scope": "bfcl_measurement_route_consistency_check",
        "route_model": SIGNED_MODEL,
        "provider_profile": SIGNED_PROVIDER_PROFILE,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "checked_paths": [str(path) for path in CONFIG_PATHS.values()] + [str(ROUTE_METADATA), str(ROUTE_PACKET)],
        "bfcl_measurement_route_consistency_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.repo_root)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        summary = {
            "report_scope": "bfcl_measurement_route_consistency_check",
            "bfcl_measurement_route_consistency_passed": False,
            "blockers": [f"bfcl_measurement_route_consistency_check_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_measurement_route_consistency_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
