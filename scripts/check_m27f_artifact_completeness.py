from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.run_phase2_target_subset import (
    _read_jsonl,
    _result_failure_reasons,
    _result_json_path,
    _result_rows_by_case,
    _score_header,
    _score_json_path,
    _score_rows_by_case,
    _trace_paths_by_case_from_prompt_prefix_with_diagnostics,
)


DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")


def _ordered_missing(selected_ids: list[str], ids: set[str]) -> list[str]:
    return [case_id for case_id in selected_ids if case_id not in ids]


def _score_case_ids(run_root: Path, category: str) -> list[str]:
    path = _score_json_path(run_root, category)
    if not path:
        return []
    return [str(row["id"]) for row in _read_jsonl(path) if isinstance(row.get("id"), str)]


def _effective_score_case_ids(run_root: Path, category: str, selected_ids: list[str]) -> tuple[list[str], bool]:
    selected = set(selected_ids)
    score_ids = set(_score_rows_by_case(run_root, category))
    result_ids = set(_result_rows_by_case(run_root, category))
    header = _score_header(run_root, category)
    total_count = header.get("total_count")
    failure_only_score_rows = isinstance(total_count, (int, float)) and int(total_count) <= len(result_ids)
    if failure_only_score_rows:
        return [case_id for case_id in selected_ids if case_id in result_ids], True
    return [case_id for case_id in selected_ids if case_id in score_ids], False


def _run_report(run_root: Path, category: str, selected_ids: list[str], *, require_prompt_traces: bool) -> dict[str, Any]:
    score_ids = _score_case_ids(run_root, category)
    result_rows = _result_rows_by_case(run_root, category)
    result_ids = list(result_rows)
    trace_groups, trace_mapping_diagnostic = _trace_paths_by_case_from_prompt_prefix_with_diagnostics(
        source_run_root=run_root,
        category=category,
        selected_ids=selected_ids,
    )
    trace_ids = [case_id for case_id in selected_ids if trace_groups.get(case_id)]
    effective_score_ids, scorer_coverage_explained = _effective_score_case_ids(run_root, category, selected_ids)
    missing_result_ids = _ordered_missing(selected_ids, set(result_ids))
    missing_trace_ids = _ordered_missing(selected_ids, set(trace_ids))
    missing_effective_score_ids = _ordered_missing(selected_ids, set(effective_score_ids))
    prompt_prefix_ambiguity_unresolved = bool(trace_mapping_diagnostic.get("unresolved_ambiguity"))
    prompt_prefix_count_mismatch = list(trace_mapping_diagnostic.get("count_mismatch") or [])
    gate_passed = (
        not missing_result_ids
        and not missing_effective_score_ids
        and (not require_prompt_traces or not missing_trace_ids)
        and (not require_prompt_traces or not prompt_prefix_ambiguity_unresolved)
        and (not require_prompt_traces or not prompt_prefix_count_mismatch)
    )
    return {
        "run_root": str(run_root),
        "score_path": str(_score_json_path(run_root, category)) if _score_json_path(run_root, category) else None,
        "result_path": str(_result_json_path(run_root, category)) if _result_json_path(run_root, category) else None,
        "score_header": _score_header(run_root, category),
        "score_case_ids": score_ids,
        "result_case_ids": [case_id for case_id in selected_ids if case_id in set(result_ids)],
        "trace_case_ids_by_prompt_prefix": trace_ids,
        "effective_score_case_ids": effective_score_ids,
        "missing_score_ids": _ordered_missing(selected_ids, set(score_ids)),
        "missing_result_ids": missing_result_ids,
        "missing_trace_ids": missing_trace_ids,
        "missing_effective_score_ids": missing_effective_score_ids,
        "prompt_prefix_ambiguity_unresolved": prompt_prefix_ambiguity_unresolved,
        "prompt_prefix_count_mismatch": prompt_prefix_count_mismatch,
        "prompt_prefix_mapping_diagnostic": trace_mapping_diagnostic,
        "result_exception_ids": [case_id for case_id in selected_ids if case_id in _result_failure_reasons(run_root, category)],
        "prompt_prefix_traces_required": require_prompt_traces,
        "scorer_coverage_explained_by_failure_only_rows": scorer_coverage_explained,
        "gate_passed": gate_passed,
    }


def evaluate_artifact_completeness(
    root: Path = DEFAULT_ROOT,
    *,
    require_baseline_prompt_traces: bool = False,
    require_candidate_prompt_traces: bool = True,
) -> dict[str, Any]:
    manifest = json.loads((root / "paired_subset_manifest.json").read_text(encoding="utf-8"))
    selected_ids = [str(case_id) for case_id in manifest.get("selected_case_ids") or []]
    category = str(manifest.get("category") or "multi_turn_miss_param")
    runs = {
        "baseline": _run_report(
            root / "baseline",
            category,
            selected_ids,
            require_prompt_traces=require_baseline_prompt_traces,
        ),
        "candidate": _run_report(
            root / "candidate",
            category,
            selected_ids,
            require_prompt_traces=require_candidate_prompt_traces,
        ),
    }
    gate_passed = bool(selected_ids) and all(run["gate_passed"] for run in runs.values())
    return {
        "artifact_root": str(root),
        "category": category,
        "selected_case_ids": selected_ids,
        "selected_case_count": len(selected_ids),
        "m2_7f_artifact_completeness_passed": gate_passed,
        "require_baseline_prompt_traces": require_baseline_prompt_traces,
        "require_candidate_prompt_traces": require_candidate_prompt_traces,
        "case_level_gate_allowed": gate_passed,
        "runs": runs,
        "diagnostic": {
            "first_failed_run": next((name for name, run in runs.items() if not run["gate_passed"]), None),
            "do_not_rerun_m2_7f_until_passed": not gate_passed,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check M2.7f selected-case artifact completeness before rerun.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--require-baseline-prompt-traces", action="store_true")
    parser.add_argument("--allow-missing-candidate-prompt-traces", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_artifact_completeness(
        args.root,
        require_baseline_prompt_traces=args.require_baseline_prompt_traces,
        require_candidate_prompt_traces=not args.allow_missing_candidate_prompt_traces,
    )
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if report["m2_7f_artifact_completeness_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
