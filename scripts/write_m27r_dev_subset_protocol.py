#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUTPUT = DEFAULT_ROOT / "m27r_dev_subset_protocol.json"
DEFAULT_MD = DEFAULT_ROOT / "m27r_dev_subset_protocol.md"


def _read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_protocol(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    manifest = _read_json(root / "paired_subset_manifest.json", default={})
    summary = _read_json(root / "subset_summary.json", default={})
    postmortem = _read_json(root / "m27q_postmortem.json", default={})
    selected_ids = [str(case_id) for case_id in manifest.get("selected_case_ids") or []]
    frozen = bool(selected_ids)
    report = {
        "report_scope": "m2_7r_dev_subset_protocol",
        "artifact_root": str(root),
        "dev_subset_id": root.name,
        "subset_role": "dev_subset",
        "frozen_dev_subset": frozen,
        "selected_case_count": len(selected_ids),
        "selected_case_ids": selected_ids,
        "category": manifest.get("category"),
        "generalization_claim_allowed": False,
        "dev_only_scorer_rerun_allowed": False,
        "next_required_stage": "m2_7s_offline_gate_before_any_new_scorer_run",
        "evidence_status": postmortem.get("evidence_status"),
        "case_report_trace_mapping": summary.get("case_report_trace_mapping"),
        "case_level_gate_allowed": summary.get("case_level_gate_allowed"),
        "baseline_accuracy": summary.get("baseline_accuracy"),
        "candidate_accuracy": summary.get("candidate_accuracy"),
        "case_fixed_count": summary.get("case_fixed_count"),
        "case_regressed_count": summary.get("case_regressed_count"),
        "net_case_gain": summary.get("net_case_gain"),
        "recommended_tool_match_rate_among_activated": summary.get("recommended_tool_match_rate_among_activated"),
        "raw_normalized_arg_match_rate_among_activated": summary.get("raw_normalized_arg_match_rate_among_activated"),
        "freeze_reasons": [
            "subset_used_for_multiple_trace_mapping_guard_ranking_guidance_compiler_iterations",
            "latest_durable_result_failed_m2_7f_gate",
            "future_claims_require_holdout_or_larger_subset_validation",
        ],
        "m27r_dev_subset_protocol_ready": frozen and len(selected_ids) == 30,
        "diagnostic": {
            "no_bfcl_rerun": True,
            "no_100_case": True,
            "no_m2_8": True,
            "no_full_bfcl": True,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7r Dev Subset Protocol",
        "",
        f"- Dev subset: `{report['dev_subset_id']}`",
        f"- Frozen: `{report['frozen_dev_subset']}`",
        f"- Selected cases: `{report['selected_case_count']}`",
        f"- Generalization claim allowed: `{report['generalization_claim_allowed']}`",
        f"- Dev-only scorer rerun allowed: `{report['dev_only_scorer_rerun_allowed']}`",
        f"- Next required stage: `{report['next_required_stage']}`",
        "",
        "## Latest Durable Metrics",
        "",
        f"- Baseline accuracy: `{report.get('baseline_accuracy')}`",
        f"- Candidate accuracy: `{report.get('candidate_accuracy')}`",
        f"- Fixed/regressed/net: `{report.get('case_fixed_count')}` / `{report.get('case_regressed_count')}` / `{report.get('net_case_gain')}`",
        f"- Tool match rate: `{report.get('recommended_tool_match_rate_among_activated')}`",
        f"- Raw arg match rate: `{report.get('raw_normalized_arg_match_rate_among_activated')}`",
        "",
        "## Freeze Reasons",
        "",
    ]
    lines.extend(f"- `{reason}`" for reason in report.get("freeze_reasons") or [])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Write M2.7r dev subset protocol artifact.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = build_protocol(args.root)
    _write_json(args.output, report)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "dev_subset_id": report.get("dev_subset_id"),
            "selected_case_count": report.get("selected_case_count"),
            "frozen_dev_subset": report.get("frozen_dev_subset"),
            "generalization_claim_allowed": report.get("generalization_claim_allowed"),
            "dev_only_scorer_rerun_allowed": report.get("dev_only_scorer_rerun_allowed"),
            "m27r_dev_subset_protocol_ready": report.get("m27r_dev_subset_protocol_ready"),
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
