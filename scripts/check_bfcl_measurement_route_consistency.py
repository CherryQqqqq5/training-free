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
STAGE1_MEASUREMENT_ARTIFACTS = [
    Path("outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.md"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/performance_ready.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json"),
]
SIGNED_MODEL = "gpt-4.1"
SIGNED_PROFILE = "novacode"
SIGNED_PROVIDER_PROFILE = "Chuangzhi/Novacode"
HISTORICAL_GPT_5_2_KEYS = {"old_signed_model", "old_signed_model_status"}
SIGNED_ENDPOINT_ENVS = ["CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT"]
SIGNED_KEY_ENVS = ["CHUANGZHI_API_KEY", "NOVACODE_API_KEY"]
ENDPOINT_LITERAL_FRAGMENTS = ("apicz", "boyuerichdata", "http://", "https://")
KEY_LITERAL_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{16,}")


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


def _check_no_endpoint_or_key_literals(name: str, data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk_json(data):
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        for fragment in ENDPOINT_LITERAL_FRAGMENTS:
            if fragment in lowered:
                blockers.append(f"{name}_endpoint_literal_forbidden:{'.'.join(path)}")
                break
        if KEY_LITERAL_PATTERN.search(value):
            blockers.append(f"{name}_key_literal_forbidden:{'.'.join(path)}")
    return blockers


def _check_env_only_route(name: str, upstream: dict[str, Any], blockers: list[str]) -> None:
    if upstream.get("base_url_env") is None:
        blockers.append(f"{name}_base_url_env_missing")
    if upstream.get("api_key_env") is None:
        blockers.append(f"{name}_api_key_env_missing")
    if upstream.get("endpoint_env_only") is not True:
        blockers.append(f"{name}_endpoint_env_only_not_true:{upstream.get('endpoint_env_only')!r}")
    if upstream.get("api_key_env_only") is not True:
        blockers.append(f"{name}_api_key_env_only_not_true:{upstream.get('api_key_env_only')!r}")
    if upstream.get("endpoint_value_committed") is not False:
        blockers.append(f"{name}_endpoint_value_committed_not_false:{upstream.get('endpoint_value_committed')!r}")
    if upstream.get("api_key_value_committed") is not False:
        blockers.append(f"{name}_api_key_value_committed_not_false:{upstream.get('api_key_value_committed')!r}")


def _check_no_active_scorer_feedback(name: str, data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    runtime_policy = data.get("runtime_policy") if isinstance(data.get("runtime_policy"), dict) else {}
    enabled = runtime_policy.get("scorer_feedback_enabled")
    status = runtime_policy.get("scorer_feedback_status")
    if enabled is not False:
        blockers.append(f"{name}_scorer_feedback_enabled_not_false:{enabled!r}")
    if status != "disabled_inert_for_measurement_only":
        blockers.append(f"{name}_scorer_feedback_status_not_disabled_inert:{status!r}")
    for key in ("scorer_feedback_path", "feedback_path", "scorer_feedback_input", "feedback_input"):
        value = runtime_policy.get(key)
        if value not in (None, "", False):
            blockers.append(f"{name}_{key}_active:{value!r}")
    return blockers


def _check_runtime(name: str, path: Path, blockers: list[str]) -> None:
    data = load_yaml(path)
    upstream = data.get("upstream") if isinstance(data.get("upstream"), dict) else {}
    blockers.extend(_check_no_endpoint_or_key_literals(name, data))
    blockers.extend(_check_no_active_scorer_feedback(name, data))
    if upstream.get("active_profile") != SIGNED_PROFILE:
        blockers.append(f"{name}_active_profile_invalid:{upstream.get('active_profile')!r}")
    if upstream.get("model") != SIGNED_MODEL:
        blockers.append(f"{name}_upstream_model_invalid:{upstream.get('model')!r}")
    if upstream.get("fallback_allowed") is not False:
        blockers.append(f"{name}_fallback_allowed_not_false:{upstream.get('fallback_allowed')!r}")
    if upstream.get("gpt_4o_fallback_allowed") is not False:
        blockers.append(f"{name}_gpt_4o_fallback_allowed_not_false:{upstream.get('gpt_4o_fallback_allowed')!r}")
    _check_env_only_route(f"{name}_upstream", upstream, blockers)
    profiles = upstream.get("profiles") if isinstance(upstream.get("profiles"), dict) else {}
    novacode = profiles.get("novacode") if isinstance(profiles.get("novacode"), dict) else {}
    if novacode.get("model") != SIGNED_MODEL:
        blockers.append(f"{name}_novacode_model_invalid:{novacode.get('model')!r}")
    if novacode.get("provider_profile") != SIGNED_PROVIDER_PROFILE:
        blockers.append(f"{name}_provider_profile_invalid:{novacode.get('provider_profile')!r}")
    _check_env_only_route(f"{name}_novacode", novacode, blockers)
    if "openrouter" in profiles:
        blockers.append(f"{name}_openrouter_profile_present")
    blockers.extend(_check_no_active_gpt_5_2(name, data))
    blockers.extend(_check_no_gpt_4o_fallback(name, data))


def _check_protocol(path: Path, blockers: list[str]) -> None:
    data = load_yaml(path)
    model = data.get("model") if isinstance(data.get("model"), dict) else {}
    blockers.extend(_check_no_endpoint_or_key_literals("bfcl_eval_protocol", data))
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
    if any(fragment in text.lower() for fragment in ENDPOINT_LITERAL_FRAGMENTS):
        blockers.append("bfcl_v4_phase1_env_endpoint_literal_forbidden")
    if KEY_LITERAL_PATTERN.search(text):
        blockers.append("bfcl_v4_phase1_env_key_literal_forbidden")
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
    blockers.extend(_check_no_endpoint_or_key_literals("route_metadata", data))
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
        "endpoint_env_only": True,
        "api_key_env_only": True,
        "endpoint_value_committed": False,
        "api_key_value_committed": False,
        "signed_endpoint_env_vars": SIGNED_ENDPOINT_ENVS,
        "signed_api_key_env_vars": SIGNED_KEY_ENVS,
        "scorer_feedback_enabled": False,
        "scorer_feedback_status": "disabled_inert_for_measurement_only",
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


def _check_stage1_measurement_artifact(path: Path, blockers: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    if any(fragment in lowered for fragment in ENDPOINT_LITERAL_FRAGMENTS):
        blockers.append(f"stage1_artifact_endpoint_literal_forbidden:{path}")
    if KEY_LITERAL_PATTERN.search(text):
        blockers.append(f"stage1_artifact_key_literal_forbidden:{path}")
    if path.suffix == ".json":
        data = json.loads(text)
        blockers.extend(_check_no_endpoint_or_key_literals(f"stage1_artifact:{path.name}", data))


def check(repo_root: Path = Path(".")) -> dict[str, Any]:
    blockers: list[str] = []
    _check_runtime("runtime_yaml", repo_root / CONFIG_PATHS["runtime"], blockers)
    _check_runtime("runtime_bfcl_structured_yaml", repo_root / CONFIG_PATHS["runtime_bfcl_structured"], blockers)
    _check_protocol(repo_root / CONFIG_PATHS["bfcl_eval_protocol"], blockers)
    _check_env(repo_root / CONFIG_PATHS["bfcl_v4_phase1_env"], blockers)
    _check_route_metadata(repo_root / ROUTE_METADATA, blockers)
    _check_route_packet(repo_root / ROUTE_PACKET, blockers)
    for artifact_path in STAGE1_MEASUREMENT_ARTIFACTS:
        _check_stage1_measurement_artifact(repo_root / artifact_path, blockers)
    return {
        "report_scope": "bfcl_measurement_route_consistency_check",
        "route_model": SIGNED_MODEL,
        "provider_profile": SIGNED_PROVIDER_PROFILE,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "checked_paths": [str(path) for path in CONFIG_PATHS.values()] + [str(ROUTE_METADATA), str(ROUTE_PACKET)] + [str(path) for path in STAGE1_MEASUREMENT_ARTIFACTS],
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
