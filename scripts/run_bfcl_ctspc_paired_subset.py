#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_phase2_target_subset import write_test_case_ids
from scripts.scan_bfcl_ctspc_opportunities import scan_opportunities, select_opportunities, summarize_opportunities


def build_planned_commands(
    *,
    repo_root: Path,
    out_root: Path,
    category: str,
    runtime_config: Path,
    candidate_rules_dir: Path,
    baseline_port: int,
    candidate_port: int,
    model_alias: str,
) -> list[str]:
    runtime = runtime_config if runtime_config.is_absolute() else repo_root / runtime_config
    baseline = [
        "bash",
        str(repo_root / "scripts/run_bfcl_v4_baseline.sh"),
        model_alias,
        str(out_root / "baseline"),
        str(baseline_port),
        category,
        str(runtime),
    ]
    candidate = [
        "bash",
        str(repo_root / "scripts/run_bfcl_v4_patch.sh"),
        model_alias,
        str(out_root / "candidate"),
        str(candidate_port),
        category,
        str(runtime),
        str(candidate_rules_dir),
        str(out_root / "candidate" / "traces"),
        str(out_root / "candidate" / "artifacts"),
        str(out_root / "baseline" / "artifacts" / "metrics.json"),
    ]
    return [" ".join(baseline), " ".join(candidate)]


def write_manifest(out_root: Path, manifest: dict[str, Any]) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "paired_subset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or run a paired BFCL CTSPC subset.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-run-root", type=Path, required=True)
    parser.add_argument("--category", default="multi_turn_miss_param")
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--candidate-rules-dir", type=Path, required=True)
    parser.add_argument("--runtime-config", type=Path, default=Path("configs/runtime_bfcl_structured.yaml"))
    parser.add_argument("--max-cases", type=int, default=30)
    parser.add_argument("--min-selected-cases", type=int, default=30)
    parser.add_argument("--min-candidate-generatable-cases", type=int, default=20)
    parser.add_argument("--baseline-port", type=int, default=8060)
    parser.add_argument("--candidate-port", type=int, default=8061)
    parser.add_argument("--model-alias", default="gpt-4o-mini-2024-07-18-FC")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    out_root = args.out_root
    out_root.mkdir(parents=True, exist_ok=True)
    rows = scan_opportunities(args.source_run_root, args.category)
    selected = select_opportunities(rows, max_cases=args.max_cases)
    summary = summarize_opportunities(rows, selected)
    selected_ids = [str(row["case_id"]) for row in selected]
    for run_name in ("baseline", "candidate"):
        write_test_case_ids(out_root / run_name / "bfcl" / "test_case_ids_to_generate.json", args.category, selected_ids)

    selection_gate_passed = (
        len(selected_ids) >= args.min_selected_cases
        and sum(row.get("candidate_generatable") is True for row in selected) >= args.min_candidate_generatable_cases
    )
    candidate_rules_available = args.candidate_rules_dir.exists() and (args.candidate_rules_dir / "rule.yaml").exists()
    gate_passed = selection_gate_passed and candidate_rules_available
    commands = []
    if gate_passed:
        commands = build_planned_commands(
            repo_root=repo,
            out_root=out_root,
            category=args.category,
            runtime_config=args.runtime_config,
            candidate_rules_dir=args.candidate_rules_dir,
            baseline_port=args.baseline_port,
            candidate_port=args.candidate_port,
            model_alias=args.model_alias,
        )
    manifest = {
        "source_run_root": str(args.source_run_root),
        "category": args.category,
        "selected_case_ids": selected_ids,
        "max_cases": args.max_cases,
        "candidate_rules_dir": str(args.candidate_rules_dir),
        "runtime_config": str(args.runtime_config),
        "dry_run": True,
        "gate_passed": gate_passed,
        "selection_gate_passed": selection_gate_passed,
        "candidate_rules_available": candidate_rules_available,
        "gate_requirements": {
            "min_selected_cases": args.min_selected_cases,
            "min_candidate_generatable_cases": args.min_candidate_generatable_cases,
            "candidate_rules_must_exist": True,
        },
        "opportunity_summary": summary,
        "planned_commands": commands,
    }
    write_manifest(out_root, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
