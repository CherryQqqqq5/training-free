#!/usr/bin/env python3
"""Build M2.7ae low-risk slice scan manifest.

Offline-only. Scans existing source/holdout opportunity artifacts and records
candidate low-risk slices for future planning. It does not emit scorer commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.scan_bfcl_ctspc_opportunities import scan_opportunities

DEFAULT_DEV_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_SOURCE_POOL = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
DEFAULT_HOLDOUT = Path("outputs/artifacts/bfcl_ctspc_holdout30_v1")
DEFAULT_OUT = Path("outputs/artifacts/bfcl_ctspc_low_risk_slices_v1/low_risk_slice_manifest.json")
DEFAULT_MD = Path("outputs/artifacts/bfcl_ctspc_low_risk_slices_v1/low_risk_slice_manifest.md")
DEFAULT_CATEGORIES = ["multi_turn_miss_param", "multi_turn_base", "multi_turn_miss_func", "multi_turn_long_context"]
DETERMINISTIC_TOOLS = {"echo", "grep", "find", "diff", "cp", "mv", "touch", "mkdir", "cat"}
LOWER_TRAJECTORY_RISK_TOOLS = {"echo", "grep", "find", "diff"}


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _has_source(root: Path, category: str) -> bool:
    return bool(list((root / "bfcl").glob(f"**/BFCL_v4_{category}_score.json")))


def _available_categories(root: Path) -> list[str]:
    discovered = set(DEFAULT_CATEGORIES)
    for path in (root / "bfcl").glob("**/BFCL_v4_*_score.json"):
        name = path.name
        if name.startswith("BFCL_v4_") and name.endswith("_score.json"):
            discovered.add(name[len("BFCL_v4_") : -len("_score.json")])
    return sorted(discovered)


def _source_roots(dev_root: Path, source_pool: Path) -> list[Path]:
    dev = _read_json(dev_root / "paired_subset_manifest.json", {}) or {}
    roots = [Path(str(dev.get("source_run_root") or ""))]
    roots.extend(sorted(source_pool.glob("*/baseline")))
    return [root for root in dict.fromkeys(roots) if str(root)]


def _classify_slice(row: dict[str, Any]) -> list[str]:
    tools = {str(t) for t in row.get("target_action_tools_present") or []}
    labels = {str(t) for t in row.get("failure_labels") or []}
    slices: list[str] = []
    if row.get("schema_local") and len(tools) == 1:
        slices.append("single_step_function_tool_selection")
    if tools & {"echo", "touch", "mkdir", "cp", "mv"} and row.get("schema_local"):
        slices.append("explicit_required_arg_literal")
    if tools & {"cat", "grep", "find", "diff"} and row.get("schema_local"):
        slices.append("wrong_arg_key_alias_repair")
    if row.get("schema_local") and tools & LOWER_TRAJECTORY_RISK_TOOLS:
        slices.append("deterministic_schema_local_non_live_repair")
    if not slices and row.get("schema_local") and tools & DETERMINISTIC_TOOLS:
        slices.append("schema_local_file_path_candidate")
    return sorted(set(slices))


def build_manifest(dev_root: Path = DEFAULT_DEV_ROOT, source_pool: Path = DEFAULT_SOURCE_POOL, holdout_root: Path = DEFAULT_HOLDOUT, max_cases_per_slice: int = 40) -> dict[str, Any]:
    dev = _read_json(dev_root / "paired_subset_manifest.json", {}) or {}
    holdout = _read_json(holdout_root / "holdout_manifest.json", {}) or {}
    excluded = {str(x) for x in dev.get("selected_case_ids") or []}
    excluded.update(str(x) for x in holdout.get("selected_case_ids") or [])
    slice_cases: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scan_summary: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in _source_roots(dev_root, source_pool):
        for category in _available_categories(root):
            available = _has_source(root, category)
            before = sum(len(v) for v in slice_cases.values())
            if available:
                try:
                    rows = scan_opportunities(root, category)
                except Exception:
                    rows = []
                for row in rows:
                    case_id = str(row.get("case_id") or "")
                    if not case_id or case_id in excluded or case_id in seen:
                        continue
                    slices = _classify_slice(row)
                    if not slices:
                        continue
                    seen.add(case_id)
                    record = {
                        "case_id": case_id,
                        "category": category,
                        "source_run_root": str(root),
                        "schema_local": bool(row.get("schema_local")),
                        "target_action_tools_present": row.get("target_action_tools_present") or [],
                        "candidate_generatable": bool(row.get("candidate_generatable") or row.get("compiler_candidate_generatable") or row.get("candidate_rule_generatable")),
                        "low_risk_slices": slices,
                    }
                    for slice_name in slices:
                        if len(slice_cases[slice_name]) < max_cases_per_slice:
                            slice_cases[slice_name].append(record)
            after = sum(len(v) for v in slice_cases.values())
            scan_summary.append({"source_run_root": str(root), "category": category, "available": available, "selected_low_risk_records": after - before})
    counts = {key: len(value) for key, value in sorted(slice_cases.items())}
    priority = [
        "explicit_required_arg_literal",
        "wrong_arg_key_alias_repair",
        "deterministic_schema_local_non_live_repair",
        "single_step_function_tool_selection",
        "schema_local_file_path_candidate",
    ]
    recommended = next((name for name in priority if counts.get(name, 0) >= 5), max(counts, key=counts.get) if counts else None)
    return {
        "report_scope": "m2_7ae_low_risk_slice_manifest",
        "dev_subset_root": str(dev_root),
        "holdout_root": str(holdout_root),
        "source_pool_root": str(source_pool),
        "offline_manifest_only": True,
        "no_bfcl_or_model_call": True,
        "planned_commands": [],
        "candidate_commands": [],
        "excluded_dev_and_holdout_case_count": len(excluded),
        "slice_counts": counts,
        "recommended_slice": recommended,
        "slice_cases": slice_cases,
        "source_scan_summary": scan_summary,
        "m27ae_low_risk_slice_scan_ready": bool(recommended),
        "diagnostic": {
            "does_not_use_holdout_scorer_feedback": True,
            "does_not_authorize_scorer": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7ae Low-Risk Slice Manifest",
        "",
        f"- Ready: `{report['m27ae_low_risk_slice_scan_ready']}`",
        f"- Recommended slice: `{report['recommended_slice']}`",
        f"- Slice counts: `{report['slice_counts']}`",
        "",
        "This manifest is offline-only and emits no BFCL scorer commands.",
        "",
    ]
    return "\n".join(lines)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-root", type=Path, default=DEFAULT_DEV_ROOT)
    parser.add_argument("--source-pool-root", type=Path, default=DEFAULT_SOURCE_POOL)
    parser.add_argument("--holdout-root", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--max-cases-per-slice", type=int, default=40)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = build_manifest(args.dev_root, args.source_pool_root, args.holdout_root, max_cases_per_slice=args.max_cases_per_slice)
    _write_json(args.output, report)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "m27ae_low_risk_slice_scan_ready": report.get("m27ae_low_risk_slice_scan_ready"),
            "recommended_slice": report.get("recommended_slice"),
            "slice_counts": report.get("slice_counts"),
            "planned_commands": report.get("planned_commands"),
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
