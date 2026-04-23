from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _path_exists(path: Path | None) -> bool:
    return path is not None and path.exists()


def _candidate_dirs(proposal_summary_path: Path, max_candidates: int) -> list[Path]:
    if not proposal_summary_path.exists():
        return []
    data = json.loads(proposal_summary_path.read_text(encoding="utf-8"))
    proposals = data.get("proposals") or []
    return [Path(item["candidate_dir"]) for item in proposals[:max_candidates] if isinstance(item, dict) and item.get("candidate_dir")]


def _parse_optional_run(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("optional rerun must be LABEL=PATH")
    label, raw = value.split("=", 1)
    return label.strip(), Path(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or plan one minimal Phase-2 evolution iteration.")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--target-category", default="multi_turn_miss_param")
    parser.add_argument("--holdout-category", default="simple_python")
    parser.add_argument("--baseline-run-root", required=True)
    parser.add_argument("--target-run-root", required=True)
    parser.add_argument("--holdout-run-root")
    parser.add_argument("--history", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--optional-rerun-root", action="append", default=[], type=_parse_optional_run)
    parser.add_argument("--allow-missing-rerun", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=1)
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    baseline_root = Path(args.baseline_run_root)
    target_root = Path(args.target_run_root)
    holdout_root = Path(args.holdout_run_root) if args.holdout_run_root else None
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    if not baseline_root.exists():
        raise SystemExit(f"missing baseline run root: {baseline_root}")
    if not target_root.exists():
        raise SystemExit(f"missing target run root: {target_root}")
    if args.execute and not _path_exists(holdout_root):
        raise SystemExit("executable mode requires --holdout-run-root")
    if args.execute and args.holdout_category != "simple_python":
        raise SystemExit("executable mode currently requires simple_python as the clean holdout")

    skipped_optional: list[dict[str, Any]] = []
    for label, path in args.optional_rerun_root:
        if path.exists():
            continue
        if args.allow_missing_rerun:
            skipped_optional.append({"run": label, "status": "skipped_missing", "path": str(path)})
            continue
        raise SystemExit(f"missing optional rerun root without --allow-missing-rerun: {label} -> {path}")

    failures_path = out_root / "failures.jsonl"
    proposal_root = out_root / "proposals"
    proposal_summary_path = proposal_root / "proposal_summary.json"
    taxonomy_json = out_root / "taxonomy_report.json"
    taxonomy_md = out_root / "taxonomy_report.md"

    planned_commands = [
        f"cd {repo_root} && PYTHONPATH=src python scripts/build_phase2_taxonomy_report.py --run baseline={baseline_root / 'traces'} --run primary_v4={target_root / 'traces'} --out-json {taxonomy_json} --out-md {taxonomy_md}",
        f"cd {repo_root} && PYTHONPATH=src python -m grc.cli mine --trace-dir {target_root / 'traces'} --out {failures_path}",
        f"cd {repo_root} && PYTHONPATH=src python -m grc.cli propose --failures {failures_path} --history {args.history} --out-dir {proposal_root} --top-k-signatures 3 --target-category {args.target_category} --holdout-category {args.holdout_category}",
        f"cd {repo_root} && bash scripts/run_bfcl_v4_patch.sh \"$GRC_BFCL_MODEL\" {out_root / 'candidate_run'} 8022 {args.target_category} {repo_root / 'configs/runtime_bfcl_structured.yaml'} {repo_root / 'outputs/phase2_targeted_v2'} {out_root / 'candidate_run/traces'} {out_root / 'candidate_run/artifacts'}",
        f"cd {repo_root} && bash scripts/run_bfcl_v4_baseline.sh \"$GRC_BFCL_MODEL\" {out_root / 'holdout_run'} 8012 {args.holdout_category} {repo_root / 'configs/runtime_bfcl_structured.yaml'} {repo_root / 'outputs/phase2_targeted_v2'} {out_root / 'holdout_run/traces'} {out_root / 'holdout_run/artifacts'}",
        f"cd {repo_root} && PYTHONPATH=src python scripts/assess_paired_rerun.py --baseline-metrics {baseline_root / 'artifacts/metrics.json'} --candidate-metrics {out_root / 'candidate_run/artifacts/metrics.json'} --out {out_root / 'candidate_run/artifacts/paired_rerun.json'}",
        f"cd {repo_root} && PYTHONPATH=src python -m grc.cli select --baseline-metrics {baseline_root / 'artifacts/metrics.json'} --candidate-metrics {out_root / 'candidate_run/artifacts/metrics.json'} --candidate-dir {out_root / 'candidate_run/artifacts'} --out {out_root / 'candidate_run/artifacts/accept.json'}",
    ]

    summary = {
        "mode": "execute" if args.execute else "dry-run",
        "target_category": args.target_category,
        "holdout_category": args.holdout_category,
        "planned_commands": planned_commands,
        "failure_rate_by_label": {},
        "top_failure_signatures": [],
        "proposal_count_by_mode": {},
        "history_reuse_count": 0,
        "new_policy_count": 0,
        "accepted_count": 0,
        "retained_count": 0,
        "rejected_count": 0,
        "target_delta": None,
        "holdout_delta": None,
        "clean_slice_regression": None,
        "skipped_optional_runs": skipped_optional,
    }

    if args.dry_run and not args.execute:
        _json_dump(out_root / "evolution_iteration_summary.json", summary)
        (out_root / "evolution_iteration_summary.md").write_text(
            "# Evolution Iteration Summary\n\n## Planned Commands\n\n" + "\n".join(f"- `{cmd}`" for cmd in planned_commands) + "\n",
            encoding="utf-8",
        )
        return

    raise SystemExit("execute mode wiring is intentionally deferred until the dry-run summary is reviewed")


if __name__ == "__main__":
    main()
