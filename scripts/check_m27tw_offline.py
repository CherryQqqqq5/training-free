#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
HOLD = Path("outputs/artifacts/bfcl_ctspc_holdout30_v1")
SRC = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
OUT = ROOT / "m27tw_offline_summary.json"
MD = ROOT / "m27tw_offline_summary.md"


def _j(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _holdout_ready(manifest: dict[str, Any]) -> bool:
    return bool(manifest.get("m27tw_holdout_manifest_ready")) and int(manifest.get("selected_case_count") or 0) >= 20 and int(manifest.get("candidate_generatable_count") or 0) >= 15 and not (manifest.get("overlap_with_dev_case_ids") or [])


def evaluate(root: Path = ROOT, holdout: Path = HOLD, source: Path = SRC) -> dict[str, Any]:
    source_manifest = _j(source / "source_collection_manifest.json", {}) or {}
    holdout_manifest = _j(holdout / "holdout_manifest.json", {}) or {}
    u = _j(root / "m27u_tool_ranking.json", {}) or {}
    v = _j(root / "m27v_arg_realization.json", {}) or {}
    w = _j(root / "m27w_rule_retention.json", {}) or {}
    checks = {
        "m27t_source_pool_ready": bool(source_manifest.get("m27t_source_pool_ready")),
        "m27tw_holdout_manifest_ready": _holdout_ready(holdout_manifest),
        "m27u_tool_ranking_passed": bool(u.get("m27u_tool_ranking_passed")),
        "m27v_arg_realization_passed": bool(v.get("m27v_arg_realization_passed")),
        "m27w_rule_retention_passed": bool(w.get("m27w_rule_retention_passed")),
    }
    return {
        "report_scope": "m2_7tw_offline_summary",
        **checks,
        "m2_7tw_offline_passed": all(checks.values()),
        "source_pool": {key: source_manifest.get(key) for key in ["m27t_source_pool_ready", "planned_source_collection_commands", "candidate_commands"]},
        "holdout": {key: holdout_manifest.get(key) for key in ["selected_case_count", "candidate_generatable_count", "overlap_with_dev_case_ids", "planned_commands"]},
        "tool_ranking": {key: u.get(key) for key in ["tool_mismatch_before_arg_realization_count", "offline_recommended_tool_match_proxy", "dominant_selected_next_tool_rate", "last_scorer_tool_match_rate"]},
        "arg_realization": {key: v.get(key) for key in ["raw_arg_match_rate_proxy", "emitted_arg_wrong_or_guidance_not_followed_count", "canonical_arg_validation_coverage", "last_scorer_raw_arg_match_rate"]},
        "rule_retention": {key: w.get(key) for key in ["decision_distribution", "holdout_manifest_ready", "holdout_scorer_evidence_available", "offline_u_v_readiness_passed"]},
        "diagnostic": {
            "offline_readiness_only": True,
            "last_scorer_metrics_retained_for_postmortem_only": True,
            "no_bfcl_rerun": True,
            "no_100_case": True,
            "no_m2_8": True,
            "no_full_bfcl": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# M2.7tw Offline Summary", "", f"- Passed: `{report['m2_7tw_offline_passed']}`", "", "| Check | Passed |", "| --- | ---: |"]
    for key in ["m27t_source_pool_ready", "m27tw_holdout_manifest_ready", "m27u_tool_ranking_passed", "m27v_arg_realization_passed", "m27w_rule_retention_passed"]:
        lines.append(f"| `{key}` | `{report[key]}` |")
    lines.extend(["", "This summary is an offline readiness gate only. It does not authorize performance claims or 100-case/full BFCL.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--holdout-root", type=Path, default=HOLD)
    parser.add_argument("--source-pool-root", type=Path, default=SRC)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root, args.holdout_root, args.source_pool_root)
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in ["m2_7tw_offline_passed", "m27t_source_pool_ready", "m27tw_holdout_manifest_ready", "m27u_tool_ranking_passed", "m27v_arg_realization_passed", "m27w_rule_retention_passed"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
