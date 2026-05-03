#!/usr/bin/env python3
"""Build a compact no-execution plan for the BFCL current-system baseline gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_current_system_baseline_execution_gate import DEFAULT_PACKET, check  # noqa: E402

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_execution_plan.json")
DEFAULT_MD_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_execution_plan.md")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = _load(packet_path)
    gate = check(packet_path)
    return {
        "artifact_kind": "bfcl_current_system_baseline_execution_plan",
        "source_packet": str(packet_path),
        "gate_passed": bool(gate.get("bfcl_current_system_baseline_execution_gate_passed")),
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "measurement_kind": packet.get("measurement_kind"),
        "target_commit_for_measurement": packet.get("target_commit_for_measurement"),
        "route_profile": packet.get("route_profile"),
        "route_model": packet.get("route_model"),
        "evaluator_package": packet.get("evaluator_package"),
        "bfcl_version": packet.get("bfcl_version"),
        "bfcl_evaluator_checkout": packet.get("bfcl_evaluator_checkout"),
        "case_scope_protocol": packet.get("case_scope_protocol"),
        "runner_command_template": packet.get("runner_command_template"),
        "output_roots": packet.get("output_roots"),
        "compact_manifest_schema": packet.get("compact_manifest_schema"),
        "compact_metrics_schema": packet.get("compact_metrics_schema"),
        "provider_call_authorized": packet.get("provider_call_authorized"),
        "bfcl_generate_authorized": packet.get("bfcl_generate_authorized"),
        "bfcl_evaluate_authorized": packet.get("bfcl_evaluate_authorized"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "full_baseline_authorized": packet.get("full_baseline_authorized"),
        "candidate_runtime_activation_authorized": packet.get("candidate_runtime_activation_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "sota_3pp_claim_ready": packet.get("sota_3pp_claim_ready"),
        "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
        "stop_gates": packet.get("stop_gates"),
        "blockers": gate.get("blockers", []),
    }


def write_plan(plan: dict[str, Any], output: Path = DEFAULT_OUTPUT, md_output: Path = DEFAULT_MD_OUTPUT) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = (
        "# BFCL Current-System Baseline Execution Plan\n\n"
        f"- Gate passed: `{str(plan['gate_passed']).lower()}`\n"
        f"- Approval status: `{plan['approval_status']}`\n"
        f"- Execution authorized: `{str(plan['authorized']).lower()}`\n"
        f"- Measurement kind: `{plan['measurement_kind']}`\n"
        f"- Target commit: `{plan['target_commit_for_measurement']}`\n"
        f"- Route: `{plan['route_profile']}/{plan['route_model']}`\n"
        "- Provider/BFCL/scorer/full baseline authorized: `false`\n"
        "- Candidate/performance/+3pp/Huawei authorized: `false`\n"
    )
    md_output.write_text(md, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD_OUTPUT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    plan = build(args.packet)
    write_plan(plan, args.output, args.md_output)
    print(json.dumps(plan, sort_keys=True) if args.compact else json.dumps(plan, indent=2, sort_keys=True))
    if args.strict and (not plan.get("gate_passed") or plan.get("authorized") is not False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
