#!/usr/bin/env python3
"""Skeleton builder for the explicit-literal candidate pool.

This is an offline-only command-line surface for the future extractor. The
current skeleton does not parse raw BFCL outputs and does not call a provider,
BFCL, a model, or a scorer. It fails closed until source inputs are present and
the extractor implementation is enabled in a later patch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_MANIFEST = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_manifest.json")
DEFAULT_OUT_ROOT = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1")
DEFAULT_CANDIDATES = DEFAULT_OUT_ROOT / "candidate_rules.jsonl"
DEFAULT_DEV = DEFAULT_OUT_ROOT / "explicit_required_arg_literal_dev20_manifest.json"
DEFAULT_HOLDOUT = DEFAULT_OUT_ROOT / "explicit_required_arg_literal_holdout20_manifest.json"
DEFAULT_SUMMARY = DEFAULT_OUT_ROOT / "explicit_literal_candidate_pool_build_summary.json"
DEFAULT_MD = DEFAULT_OUT_ROOT / "explicit_literal_candidate_pool_build_summary.md"


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _manifest(path: Path, *, name: str, selected_case_ids: list[str], candidate_jsonl: Path) -> dict[str, Any]:
    return {
        "manifest_name": name,
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_rules_type": "explicit_required_arg_literal_completion",
        "candidate_jsonl": str(candidate_jsonl),
        "selected_case_count": len(selected_case_ids),
        "selected_case_ids": selected_case_ids,
        "unique_selected_case_count": len(set(selected_case_ids)),
        "duplicate_selected_case_ids": [],
        "planned_commands": [],
        "candidate_commands": [],
        "no_next_tool_intervention": True,
        "exact_tool_choice": False,
    }


def build(
    *,
    source_manifest: Path = DEFAULT_SOURCE_MANIFEST,
    out_candidates: Path = DEFAULT_CANDIDATES,
    dev_manifest: Path = DEFAULT_DEV,
    holdout_manifest: Path = DEFAULT_HOLDOUT,
    summary_output: Path = DEFAULT_SUMMARY,
    markdown_output: Path = DEFAULT_MD,
    min_eligible: int = 35,
    dev_count: int = 20,
    holdout_count: int = 20,
) -> dict[str, Any]:
    source = _read_json(source_manifest, {}) or {}
    source_present = source_manifest.exists()
    source_categories = [
        str(item.get("category"))
        for item in source.get("category_status") or []
        if isinstance(item, dict) and item.get("category")
    ]
    blockers: list[str] = []
    if not source_present:
        blockers.append("source_collection_manifest_missing")
    if not source_categories:
        blockers.append("source_collection_categories_missing")
    blockers.append("extractor_implementation_not_enabled")

    _write_jsonl(out_candidates, [])
    _write_json(dev_manifest, _manifest(dev_manifest, name="explicit_required_arg_literal_dev20", selected_case_ids=[], candidate_jsonl=out_candidates))
    _write_json(holdout_manifest, _manifest(holdout_manifest, name="explicit_required_arg_literal_holdout20", selected_case_ids=[], candidate_jsonl=out_candidates))

    report = {
        "report_scope": "explicit_literal_candidate_pool_build",
        "offline_only": True,
        "does_not_call_provider": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "extractor_skeleton_only": True,
        "source_manifest": str(source_manifest),
        "source_manifest_present": source_present,
        "source_categories": source_categories,
        "out_candidates": str(out_candidates),
        "dev_manifest": str(dev_manifest),
        "holdout_manifest": str(holdout_manifest),
        "candidate_record_count": 0,
        "eligible_count": 0,
        "min_eligible": min_eligible,
        "dev_required_count": dev_count,
        "holdout_required_count": holdout_count,
        "dev_selected_case_count": 0,
        "holdout_selected_case_count": 0,
        "candidate_pool_build_passed": False,
        "blockers": blockers,
        "next_required_action": "implement_offline_extractor_then_rebuild_candidate_pool",
    }
    _write_json(summary_output, report)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Explicit Literal Candidate Pool Build",
        "",
        f"- Passed: `{report['candidate_pool_build_passed']}`",
        f"- Skeleton only: `{report['extractor_skeleton_only']}`",
        f"- Candidate records: `{report['candidate_record_count']}`",
        f"- Eligible count: `{report['eligible_count']}` / `{report['min_eligible']}`",
        f"- Dev selected: `{report['dev_selected_case_count']}` / `{report['dev_required_count']}`",
        f"- Holdout selected: `{report['holdout_selected_case_count']}` / `{report['holdout_required_count']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "Offline-only skeleton. This command does not call a provider, BFCL, a model, or a scorer.",
        "",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the explicit-literal candidate pool from offline source artifacts.")
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--out-candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--dev-manifest", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--holdout-manifest", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--min-eligible", type=int, default=35)
    parser.add_argument("--dev-count", type=int, default=20)
    parser.add_argument("--holdout-count", type=int, default=20)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = build(
        source_manifest=args.source_manifest,
        out_candidates=args.out_candidates,
        dev_manifest=args.dev_manifest,
        holdout_manifest=args.holdout_manifest,
        summary_output=args.summary_output,
        markdown_output=args.markdown_output,
        min_eligible=args.min_eligible,
        dev_count=args.dev_count,
        holdout_count=args.holdout_count,
    )
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "candidate_pool_build_passed",
            "extractor_skeleton_only",
            "candidate_record_count",
            "eligible_count",
            "blockers",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    if args.strict and not report["candidate_pool_build_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
