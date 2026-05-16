#!/usr/bin/env python3
"""Gate executable ABHE-v0 BFCL dev smoke readiness.

Readiness is stricter than approval. A valid approval packet may exist while this
checker still fails closed because provider env/preflight, runtime config, runner
implementation, or candidate execution adapters are unavailable.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_v0_bfcl_dev_smoke_approval_packet import check as check_approval_packet
from scripts.check_abhe_v0_bfcl_dev_smoke_approval_request import check as check_request
from scripts.check_abhe_v0_bfcl_fresh_dev_slice import check as check_fresh_slice
from scripts.check_abhe_v0_bfcl_fresh_slice_review import check as check_fresh_slice_review
from scripts.check_abhe_v0_candidate_materialization_plan import check as check_candidate_plan
from scripts.check_abhe_v0_materialized_candidates import check as check_materialized_candidates

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_execution_readiness.json")
DEFAULT_APPROVAL_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json")
DEFAULT_RUNNER = Path("scripts/run_abhe_v0_bfcl_dev_smoke.py")
EXPECTED_PROVIDER = "Chuangzhi/Novacode"
EXPECTED_PROFILE = "novacode"
EXPECTED_MODEL = "gpt-5.2"
EXPECTED_PROTOCOL = "bfcl_v4_abhe_v0_bounded_paired_dev_smoke"
EXPECTED_ROUTE_POLICY = "chuangzhi_novacode_only_openrouter_disabled"
API_KEY_ENV = "NOVACODE_API_KEY"
ENDPOINT_ENVS = ["NOVACODE_BASE_URL", "NOVACODE_ENDPOINT", "CHUANGZHI_NOVACODE_ENDPOINT"]
FAIL_CLOSED_ALLOWED_BLOCKERS = {
    "dev_smoke_approval_missing",
    "provider_model_protocol_not_approved",
    "runtime_config_not_selected",
    "scorer_authorization_false",
    "source_exclusion_proof_not_computed",
    "bfcl_fresh_dev_slice_not_materialized",
    "candidate_materialization_not_approved",
    "candidate_not_materialized",
    "provider_api_key_env_missing",
    "provider_endpoint_env_missing",
    "provider_preflight_not_run_env_missing",
    "bfcl_eval_package_missing",
    "real_execution_runner_not_implemented",
    "candidate_artifact_not_executable_without_runner_adapter",
    "runtime_config_path_missing",
    "dev_smoke_approval_packet_missing",
}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _provider_env_status() -> Dict[str, Any]:
    endpoint_status = {name: bool(os.environ.get(name)) for name in ENDPOINT_ENVS}
    api_key_set = bool(os.environ.get(API_KEY_ENV))
    endpoint_set = any(endpoint_status.values())
    return {
        "expected_api_key_env": API_KEY_ENV,
        "api_key_env_set": api_key_set,
        "endpoint_env_candidates": ENDPOINT_ENVS,
        "endpoint_env_status": endpoint_status,
        "endpoint_env_set": endpoint_set,
        "provider_preflight_status": "not_run_env_missing" if not (api_key_set and endpoint_set) else "ready_for_preflight",
    }


def _runner_status() -> Dict[str, Any]:
    if not DEFAULT_RUNNER.exists():
        return {"runner_present": False, "real_execution_implemented": False, "runner_blocker": "runner_missing"}
    text = DEFAULT_RUNNER.read_text(encoding="utf-8")
    real_implemented = "real_execution_not_implemented_in_gate_commit" not in text
    return {
        "runner_present": True,
        "real_execution_implemented": real_implemented,
        "runner_blocker": None if real_implemented else "real_execution_runner_not_implemented",
    }


def _approval_static_blockers(approval: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if not approval:
        return blockers
    if approval.get("approved_provider") != EXPECTED_PROVIDER or approval.get("approved_profile") != EXPECTED_PROFILE or approval.get("approved_model") != EXPECTED_MODEL or approval.get("approved_protocol") != EXPECTED_PROTOCOL or approval.get("approved_provider_route_policy") != EXPECTED_ROUTE_POLICY:
        blockers.append("provider_model_protocol_not_approved")
    runtime_config = approval.get("approved_runtime_config_path")
    if not runtime_config:
        blockers.append("runtime_config_not_selected")
    elif not Path(str(runtime_config)).exists():
        blockers.append("runtime_config_path_missing")
    if approval.get("scorer_authorized") is not True or approval.get("scorer_authorization_scope") != "bounded_dev_smoke_only":
        blockers.append("scorer_authorization_false")
    return blockers


def build_report(approval_packet: Path = DEFAULT_APPROVAL_PACKET) -> Dict[str, Any]:
    fresh = check_fresh_slice()
    fresh_review = check_fresh_slice_review()
    cand_plan = check_candidate_plan()
    cand = check_materialized_candidates()
    req = check_request()
    approval_check = check_approval_packet(approval_packet)
    provider_env = _provider_env_status()
    runner = _runner_status()
    bfcl_eval_present = importlib.util.find_spec("bfcl_eval") is not None

    blockers: List[str] = []
    approval: Dict[str, Any] = {}
    if not fresh.get("abhe_v0_bfcl_fresh_dev_slice_check_passed"):
        blockers += ["fresh_slice:%s" % x for x in fresh.get("blockers", [])]
    if fresh.get("fresh_dev_slice_materialized") is not True:
        blockers.append("bfcl_fresh_dev_slice_not_materialized")
    if not fresh_review.get("abhe_v0_bfcl_fresh_slice_review_passed"):
        blockers += ["fresh_slice_review:%s" % x for x in fresh_review.get("blockers", [])]
    if "source_exclusion_proof_not_computed" in fresh_review.get("execution_ready_blockers", []):
        blockers.append("source_exclusion_proof_not_computed")
    if not cand_plan.get("abhe_v0_candidate_materialization_plan_check_passed"):
        blockers += ["candidate_plan:%s" % x for x in cand_plan.get("blockers", [])]
    if not cand.get("abhe_v0_materialized_candidates_check_passed"):
        blockers += ["materialized_candidates:%s" % x for x in cand.get("blockers", [])]
    if cand.get("candidate_materialization_approved") is not True:
        blockers.append("candidate_materialization_not_approved")
    if cand.get("candidate_materialized") is not True:
        blockers.append("candidate_not_materialized")
    if not req.get("abhe_v0_bfcl_dev_smoke_approval_request_passed"):
        blockers += ["approval_request:%s" % x for x in req.get("blockers", [])]
    if not approval_packet.exists():
        blockers += ["dev_smoke_approval_missing", "provider_model_protocol_not_approved", "runtime_config_not_selected", "scorer_authorization_false"]
    else:
        approval = _load(approval_packet)
        if not approval_check.get("approval_packet_passed"):
            blockers += ["approval_packet:%s" % x for x in approval_check.get("blockers", [])]
        blockers += _approval_static_blockers(approval)
    if not provider_env["api_key_env_set"]:
        blockers.append("provider_api_key_env_missing")
    if not provider_env["endpoint_env_set"]:
        blockers.append("provider_endpoint_env_missing")
    if provider_env["provider_preflight_status"] != "ready_for_preflight":
        blockers.append("provider_preflight_not_run_env_missing")
    if not bfcl_eval_present:
        blockers.append("bfcl_eval_package_missing")
    if runner.get("runner_blocker"):
        blockers.append(str(runner["runner_blocker"]))
    if runner.get("real_execution_implemented") is not True:
        blockers.append("candidate_artifact_not_executable_without_runner_adapter")

    blockers = sorted(set(blockers))
    ready = not blockers
    check_passed = ready or set(blockers).issubset(FAIL_CLOSED_ALLOWED_BLOCKERS | {b for b in blockers if ":" in b})
    return {
        "report_scope": "abhe_v0_bfcl_execution_readiness",
        "artifact_kind": "abhe_v0_bfcl_execution_readiness",
        "schema_version": "abhe_v0_bfcl_execution_readiness_v0",
        "abhe_v0_bfcl_execution_ready": ready,
        "execution_readiness_check_passed": check_passed,
        "approval_packet_path": str(approval_packet),
        "approval_packet_present": approval_packet.exists(),
        "approval_packet_passed": approval_check.get("approval_packet_passed") is True,
        "fresh_dev_slice_materialized": fresh.get("fresh_dev_slice_materialized") is True,
        "candidate_materialization_approved": cand.get("candidate_materialization_approved") is True,
        "candidate_materialized": cand.get("candidate_materialized") is True,
        "provider_env_status": provider_env,
        "runner_status": runner,
        "bfcl_eval_package_present": bfcl_eval_present,
        "approved_provider": approval.get("approved_provider"),
        "approved_profile": approval.get("approved_profile"),
        "approved_model": approval.get("approved_model"),
        "approved_protocol": approval.get("approved_protocol"),
        "approved_runtime_config_path": approval.get("approved_runtime_config_path"),
        "approval_scorer_authorized": approval.get("scorer_authorized") is True,
        "execution_authorized": ready and approval.get("authorized") is True,
        "provider_calls_authorized": ready and approval.get("provider_calls_authorized") is True,
        "bfcl_generate_authorized": ready and approval.get("bfcl_generate_authorized") is True,
        "bfcl_evaluate_authorized": ready and approval.get("bfcl_evaluate_authorized") is True,
        "scorer_authorized": ready and approval.get("scorer_authorized") is True,
        "performance_evidence": False,
        "component_summaries": {
            "fresh_slice": fresh,
            "fresh_slice_review": fresh_review,
            "candidate_materialization_plan": cand_plan,
            "materialized_candidates": cand,
            "approval_request": req,
            "approval_packet": approval_check,
        },
        "blockers": blockers,
        "next_required_action": "restore_provider_env_and_materialize_real_runner_adapter_before_execution" if blockers else "run_approved_paired_bfcl_dev_smoke",
    }


def write_report(output: Path, report: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-packet", type=Path, default=DEFAULT_APPROVAL_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.approval_packet)
        if args.write:
            write_report(args.output, report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {
            "report_scope": "abhe_v0_bfcl_execution_readiness",
            "abhe_v0_bfcl_execution_ready": False,
            "execution_readiness_check_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report.get("execution_readiness_check_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
