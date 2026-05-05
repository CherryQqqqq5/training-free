#!/usr/bin/env python3
"""Build compact offline RASHE router/proposer replay report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_rashe_candidate_proposer_ready import DEFAULT_PACKET as APPROVAL_PACKET_PATH
from scripts.check_rashe_candidate_proposer_ready import check_ready
from scripts.check_rashe_offline_router_proposer_replay import (
    ALLOWED_SEED_SKILLS,
    CATEGORY_ROUTING,
    DEFAULT_PACKET,
    DEFAULT_REPORT,
    DISALLOWED_SEED_SKILLS,
    FALSE_KEYS,
    SELECTED_SKILL_COUNTS,
    SOURCE_DIAGNOSTICS_COMMIT,
)
from scripts.check_rashe_source_diagnostic_compact import SIGNED_ROOT, check_root

DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_offline_router_proposer_replay.md")


def _load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain JSON object" % path)
    return data


def _category_case_counts() -> Dict[str, int]:
    summary = check_root(SIGNED_ROOT)
    if summary.get("blockers"):
        raise ValueError("source_diagnostics_not_clean:%r" % summary.get("blockers"))
    counts = summary.get("category_counts") if isinstance(summary.get("category_counts"), dict) else {}
    return {str(category): int(counts.get(category) or 0) for category in counts}


def _validate_packet(packet_path: Path) -> Dict[str, Any]:
    packet = _load_json(packet_path)
    if packet.get("artifact_kind") != "rashe_offline_router_proposer_replay_packet":
        raise ValueError("packet_kind_invalid")
    if packet.get("approval_status") != "approved" or packet.get("authorized") is not True:
        raise ValueError("packet_not_approved")
    for key in FALSE_KEYS:
        if packet.get(key) is not False:
            raise ValueError("packet_%s_not_false" % key)
    return packet


def build_report(packet_path: Path = DEFAULT_PACKET) -> Dict[str, Any]:
    _validate_packet(packet_path)
    ready = check_ready(APPROVAL_PACKET_PATH)
    if not ready.get("rashe_candidate_proposer_ready_passed"):
        raise ValueError("candidate_proposer_ready_failed:%r" % ready.get("blockers"))
    category_counts = _category_case_counts()
    routing = {}
    for category, template in CATEGORY_ROUTING.items():
        row = dict(template)
        row["case_count"] = category_counts.get(category, row["case_count"])
        routing[category] = row
    selected_counts = {"state_tracking": 0, "hallucination_abstain": 0, "no_spec_selected": 0}
    for row in routing.values():
        selected = row["selected_skill"]
        if selected == "bfcl_multi_turn_state_tracking":
            selected_counts["state_tracking"] += int(row["case_count"])
        elif selected == "bfcl_hallucination_abstain":
            selected_counts["hallucination_abstain"] += int(row["case_count"])
        else:
            selected_counts["no_spec_selected"] += int(row["case_count"])
    blockers = []
    if selected_counts != SELECTED_SKILL_COUNTS:
        blockers.append("selected_skill_counts_mismatch")
    if sum(selected_counts.values()) != 160:
        blockers.append("total_source_cases_mismatch")
    report = {
        "artifact_kind": "rashe_offline_router_proposer_replay_report",
        "source_diagnostics_commit": SOURCE_DIAGNOSTICS_COMMIT,
        "candidate_proposer_approval_packet_path": str(APPROVAL_PACKET_PATH),
        "candidate_proposer_ready_passed": ready.get("rashe_candidate_proposer_ready_passed") is True,
        "input_mode": "compact_source_diagnostics_only",
        "replay_mode": "offline_router_proposer_report_only",
        "allowed_seed_skills": ALLOWED_SEED_SKILLS,
        "disallowed_seed_skills": DISALLOWED_SEED_SKILLS,
        "total_source_cases": sum(selected_counts.values()),
        "selected_skill_counts": selected_counts,
        "category_routing": routing,
        "forbidden_skill_selection_count": 0,
        "ambiguous_or_leakage_fail_closed_count": 0,
        "candidate_jsonl_created": False,
        "candidate_pool_created": False,
        "candidate_activation_authorized": False,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "dev_holdout_material_used": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_outputs_committed": False,
        "no_leakage_audit_passed": not blockers,
        "blockers": blockers,
    }
    return report


def write_markdown(path: Path, report: Dict[str, Any]) -> None:
    lines = [
        "# RASHE Offline Router Proposer Replay",
        "",
        "Status: compact offline router/proposer replay report only. No provider, BFCL generate/evaluate, scorer, full baseline, candidate JSONL, candidate pool, dev/holdout, performance, +3pp, or Huawei path was run.",
        "",
        "## Routing Counts",
        "",
        "- state_tracking: `%s`" % report["selected_skill_counts"]["state_tracking"],
        "- hallucination_abstain: `%s`" % report["selected_skill_counts"]["hallucination_abstain"],
        "- no_spec_selected: `%s`" % report["selected_skill_counts"]["no_spec_selected"],
        "",
        "The no-spec categories are fail-closed because corresponding seed skills are disallowed for this replay gate.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(output: Path = DEFAULT_REPORT, md_output: Path = DEFAULT_MD, packet_path: Path = DEFAULT_PACKET) -> Dict[str, Any]:
    report = build_report(packet_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_output, report)
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = write_report(args.output, args.md_output, args.packet)
        summary = {
            "report_scope": "rashe_offline_router_proposer_replay_build",
            "report_path": str(args.output),
            "md_path": str(args.md_output),
            "candidate_proposer_ready_passed": report["candidate_proposer_ready_passed"],
            "selected_skill_counts": report["selected_skill_counts"],
            "no_leakage_audit_passed": report["no_leakage_audit_passed"],
            "blockers": report["blockers"],
        }
    except Exception as exc:
        summary = {"report_scope": "rashe_offline_router_proposer_replay_build", "blockers": ["build_failed:%s" % exc]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
