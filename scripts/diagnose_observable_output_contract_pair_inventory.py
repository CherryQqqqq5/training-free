#!/usr/bin/env python3
"""Inventory observable output-contract raw/repaired artifact pairs.

This is an offline discovery audit. It scans compact phase2 artifacts for
fields that can support output-contract preservation analysis, without calling
BFCL, models, or scorers.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/phase2")
DEFAULT_OUT = Path("outputs/artifacts/phase2/output_contract_preservation_v1/observable_output_contract_pair_inventory.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/output_contract_preservation_v1/observable_output_contract_pair_inventory.md")

PAIR_KEYS = {
    "old_coerce_no_tool_text_to_empty_count",
    "new_offline_replay_preserved_final_answer_count",
    "old_trace_repair_kinds",
    "new_offline_replay_content_preserved",
    "new_offline_replay_repair_kinds",
}


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _walk(obj: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        out.append(obj)
        for value in obj.values():
            out.extend(_walk(value))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_walk(item))
    return out


def _slice_from_path(path: Path) -> str:
    text = str(path)
    if "memory" in text:
        return "memory"
    if "postcondition" in text:
        return "multi_turn_postcondition"
    if "required_next_tool" in text:
        return "required_next_tool"
    return "unknown"


def _payload_kind(row: dict[str, Any], path: Path) -> str:
    if "final_answer" in str(path) or row.get("new_offline_replay_content_preserved") is not None:
        return "final_answer"
    if row.get("tool") or row.get("selected_tool"):
        return "tool_call"
    return "unknown"


def evaluate(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    artifact_records: list[dict[str, Any]] = []
    candidate_pair_records: list[dict[str, Any]] = []
    files_scanned = 0
    for path in sorted(root.rglob("*.json")) if root.exists() else []:
        if "/runs" in str(path) or "/dry_runs" in str(path):
            continue
        files_scanned += 1
        data = _load(path)
        if data is None:
            continue
        nodes = _walk(data)
        matched_nodes = []
        for node in nodes:
            keys = set(node)
            if keys & PAIR_KEYS:
                matched_nodes.append(node)
        if not matched_nodes:
            continue
        artifact_records.append({
            "source_artifact": str(path),
            "benchmark_slice": _slice_from_path(path),
            "matched_node_count": len(matched_nodes),
            "matched_keys": sorted(set().union(*(set(node) & PAIR_KEYS for node in matched_nodes))),
        })
        for idx, node in enumerate(matched_nodes):
            has_before = bool(node.get("old_coerce_no_tool_text_to_empty_count") or node.get("old_trace_repair_kinds"))
            has_after = bool(node.get("new_offline_replay_preserved_final_answer_count") or node.get("new_offline_replay_content_preserved") is not None or node.get("new_offline_replay_repair_kinds") is not None)
            if has_before and has_after:
                candidate_pair_records.append({
                    "record_id": node.get("trace_id") or f"{path.stem}:{idx}",
                    "source_artifact": str(path),
                    "benchmark_slice": _slice_from_path(path),
                    "payload_kind": _payload_kind(node, path),
                    "has_before_signal": has_before,
                    "has_after_signal": has_after,
                    "is_exact_memory_final_answer_pair": "memory_operation_final_answer_repair_audit" in str(path),
                })
    by_slice = Counter(row["benchmark_slice"] for row in candidate_pair_records)
    by_payload = Counter(row["payload_kind"] for row in candidate_pair_records)
    non_memory_pair_count = sum(1 for row in candidate_pair_records if row["benchmark_slice"] != "memory")
    return {
        "report_scope": "observable_output_contract_pair_inventory",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "artifact_root": str(root),
        "json_files_scanned": files_scanned,
        "artifact_with_pair_signal_count": len(artifact_records),
        "candidate_raw_repair_pair_count": len(candidate_pair_records),
        "non_memory_raw_repair_pair_count": non_memory_pair_count,
        "candidate_pairs_by_slice": dict(sorted(by_slice.items())),
        "candidate_pairs_by_payload_kind": dict(sorted(by_payload.items())),
        "cross_slice_pair_inventory_ready": non_memory_pair_count > 0 and len(by_slice) >= 2,
        "artifact_records_sample": artifact_records[:20],
        "candidate_pair_records_sample": candidate_pair_records[:20],
        "route_recommendation": "build_non_memory_output_contract_pairs" if non_memory_pair_count == 0 else "extend_output_contract_broader_audit_with_non_memory_pairs",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Observable Output Contract Pair Inventory",
        "",
        f"- JSON files scanned: `{report['json_files_scanned']}`",
        f"- Artifacts with pair signal: `{report['artifact_with_pair_signal_count']}`",
        f"- Candidate raw/repaired pairs: `{report['candidate_raw_repair_pair_count']}`",
        f"- Non-memory pairs: `{report['non_memory_raw_repair_pair_count']}`",
        f"- Pairs by slice: `{report['candidate_pairs_by_slice']}`",
        f"- Pairs by payload kind: `{report['candidate_pairs_by_payload_kind']}`",
        f"- Cross-slice inventory ready: `{report['cross_slice_pair_inventory_ready']}`",
        f"- Route recommendation: `{report['route_recommendation']}`",
        "",
        "Offline diagnostic only. It does not authorize BFCL/model/scorer runs.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "candidate_raw_repair_pair_count": report["candidate_raw_repair_pair_count"],
            "non_memory_raw_repair_pair_count": report["non_memory_raw_repair_pair_count"],
            "candidate_pairs_by_slice": report["candidate_pairs_by_slice"],
            "cross_slice_pair_inventory_ready": report["cross_slice_pair_inventory_ready"],
            "route_recommendation": report["route_recommendation"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
