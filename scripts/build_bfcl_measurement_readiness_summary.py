#!/usr/bin/env python3
"""Build compact BFCL measurement-readiness summary from the pending gate packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_measurement_readiness_gate import DEFAULT_PACKET, check

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_readiness_summary.json")
DEFAULT_MD_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_readiness_summary.md")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = _load(packet_path)
    gate = check(packet_path)
    return {
        "artifact_kind": "bfcl_measurement_readiness_summary",
        "source_packet": str(packet_path),
        "readiness_gate_passed": bool(gate.get("bfcl_measurement_readiness_gate_passed")),
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "target_commit_for_measurement": packet.get("target_commit_for_measurement"),
        "target_commit_current_head_mismatch_justification": packet.get("target_commit_current_head_mismatch_justification"),
        "route_profile": packet.get("route_profile"),
        "route_model": packet.get("route_model"),
        "fallback_allowed": packet.get("fallback_allowed"),
        "gpt_4o_fallback_allowed": packet.get("gpt_4o_fallback_allowed"),
        "openrouter_allowed": packet.get("openrouter_allowed"),
        "gpt_5_2_active": packet.get("gpt_5_2_active"),
        "candidates_inert": packet.get("candidates_inert"),
        "candidate_specs_activated": packet.get("candidate_specs_activated"),
        "evaluator_package": packet.get("evaluator_package"),
        "bfcl_evaluator_checkout": packet.get("bfcl_evaluator_checkout"),
        "bfcl_version": packet.get("bfcl_version"),
        "bfcl_data_version": packet.get("bfcl_data_version"),
        "config_files": packet.get("config_files"),
        "stop_gates": packet.get("stop_gates"),
        "provider_call_authorized": packet.get("provider_call_authorized"),
        "bfcl_generate_authorized": packet.get("bfcl_generate_authorized"),
        "bfcl_evaluate_authorized": packet.get("bfcl_evaluate_authorized"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "full_baseline_authorized": packet.get("full_baseline_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "sota_3pp_claim_ready": packet.get("sota_3pp_claim_ready"),
        "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
        "blockers": gate.get("blockers", []),
    }


def write_summary(summary: dict[str, Any], output: Path = DEFAULT_OUTPUT, md_output: Path = DEFAULT_MD_OUTPUT) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = (
        "# BFCL Measurement Readiness Summary\n\n"
        f"- Gate passed: `{str(summary['readiness_gate_passed']).lower()}`\n"
        f"- Approval status: `{summary['approval_status']}`\n"
        f"- Target commit: `{summary['target_commit_for_measurement']}`\n"
        f"- Route: `{summary['route_profile']}/{summary['route_model']}`\n"
        "- Execution authorized: `false`\n"
        "- Measurement evidence: `false`\n"
        "- Performance/+3pp/Huawei claim ready: `false`\n"
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
    summary = build(args.packet)
    write_summary(summary, args.output, args.md_output)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and (not summary.get("readiness_gate_passed") or summary.get("authorized") is not False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
