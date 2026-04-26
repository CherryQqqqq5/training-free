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

from scripts.scan_bfcl_ctspc_opportunities import scan_opportunities, summarize_opportunities

DEFAULT_DEV_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUT_ROOT = Path("outputs/artifacts/bfcl_ctspc_holdout30_v1")
FILE_PATH_TOOLS = {"cat", "cd", "cp", "diff", "echo", "find", "grep", "ls", "mkdir", "mv", "sort", "tail", "touch"}


def _read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def select_holdout(rows: list[dict[str, Any]], *, excluded_ids: set[str], max_cases: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row.get("case_id"))
        if case_id in excluded_ids:
            continue
        if not row.get("baseline_wrong"):
            continue
        tools = set(str(tool) for tool in row.get("target_action_tools_present") or [])
        if not row.get("schema_local") or not tools.intersection(FILE_PATH_TOOLS):
            continue
        selected.append(row)
        if len(selected) >= max_cases:
            break
    return selected


def build_holdout_manifest(dev_root: Path = DEFAULT_DEV_ROOT, out_root: Path = DEFAULT_OUT_ROOT, *, max_cases: int = 30) -> dict[str, Any]:
    dev_manifest = _read_json(dev_root / "paired_subset_manifest.json")
    category = str(dev_manifest.get("category") or "multi_turn_miss_param")
    source_run_root = Path(str(dev_manifest.get("source_run_root") or ""))
    dev_ids = set(str(case_id) for case_id in dev_manifest.get("selected_case_ids") or [])
    rows = scan_opportunities(source_run_root, category)
    selected = select_holdout(rows, excluded_ids=dev_ids, max_cases=max_cases)
    summary = summarize_opportunities(rows, selected)
    selected_ids = [str(row.get("case_id")) for row in selected]
    overlap = sorted(dev_ids.intersection(selected_ids))
    manifest = {
        "report_scope": "m2_7r_holdout_manifest",
        "holdout_subset_id": out_root.name,
        "dev_subset_root": str(dev_root),
        "source_run_root": str(source_run_root),
        "category": category,
        "requested_case_count": max_cases,
        "selected_case_count": len(selected_ids),
        "selected_case_ids": selected_ids,
        "excluded_dev_case_count": len(dev_ids),
        "excluded_dev_case_ids": sorted(dev_ids),
        "overlap_with_dev_case_ids": overlap,
        "selection_criteria": {
            "exclude_dev_subset": True,
            "require_baseline_wrong": True,
            "require_schema_local": True,
            "require_file_path_tool": True,
            "no_bfcl_planned_commands": True,
        },
        "opportunity_summary": summary,
        "planned_commands": [],
        "minimum_viable_case_count": 20,
        "minimum_viable_holdout_ready": len(selected_ids) >= 20 and not overlap,
        "m27r_holdout_manifest_ready": len(selected_ids) == max_cases and not overlap,
        "diagnostic": {"no_bfcl_rerun": True, "manifest_only": True},
    }
    return manifest


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7r Holdout Manifest",
        "",
        f"- Holdout subset: `{report.get('holdout_subset_id')}`",
        f"- Ready: `{report.get('m27r_holdout_manifest_ready')}`",
        f"- Selected cases: `{report.get('selected_case_count')}` / `{report.get('requested_case_count')}`",
        f"- Dev overlap: `{report.get('overlap_with_dev_case_ids')}`",
        f"- Planned commands: `{report.get('planned_commands')}`",
        "",
        "## Selected Cases",
        "",
    ]
    lines.extend(f"- `{case_id}`" for case_id in report.get("selected_case_ids") or [])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build M2.7r holdout manifest without BFCL execution commands.")
    parser.add_argument("--dev-root", type=Path, default=DEFAULT_DEV_ROOT)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--max-cases", type=int, default=30)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = build_holdout_manifest(args.dev_root, args.out_root, max_cases=args.max_cases)
    args.out_root.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_root / "holdout_manifest.json", report)
    (args.out_root / "holdout_manifest.md").write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "selected_case_count": report.get("selected_case_count"),
            "overlap_with_dev_case_ids": report.get("overlap_with_dev_case_ids"),
            "planned_commands": report.get("planned_commands"),
            "minimum_viable_holdout_ready": report.get("minimum_viable_holdout_ready"),
            "m27r_holdout_manifest_ready": report.get("m27r_holdout_manifest_ready"),
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
