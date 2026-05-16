#!/usr/bin/env python3
"""Extract sanitized ABHE-v0 BFCL real trace cards from approved bounded dev smoke traces."""
from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_OUTPUT = ARTIFACT_ROOT / "abhe_v0_bfcl_real_trace_analysis.json"
DEFAULT_BASELINE_TRACE_ROOT = Path("/tmp/abhe_v0_bfcl_dev_smoke/baseline/traces")
DEFAULT_CANDIDATE_TRACE_ROOT = Path("/tmp/abhe_v0_bfcl_dev_smoke/candidate/traces")
EXPECTED_HASH = "sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f"


def _hash_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _load_trace(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _status_class(status: Any) -> str:
    if isinstance(status, int):
        return f"{status // 100}xx"
    return "unknown"


def _latency_bucket(ms: Any) -> str:
    if not isinstance(ms, (int, float)):
        return "unknown"
    if ms < 1000:
        return "lt_1s"
    if ms < 2500:
        return "1s_to_2_5s"
    if ms < 5000:
        return "2_5s_to_5s"
    return "ge_5s"


def _entry_from_patches(patches: List[str]) -> str:
    joined = " ".join(patches)
    if "hallucination_abstain_v0" in joined:
        return "hallucination_abstain_v0"
    if "state_tracking_v0" in joined:
        return "state_tracking_v0"
    return "state_tracking_v0"


def _pattern(entry_id: str, issues: List[Dict[str, Any]], patches: List[str]) -> str:
    kinds = {str(item.get("kind")) for item in issues if isinstance(item, dict)}
    if "post_tool_prose_summary" in kinds:
        return "post_tool_prose_summary_after_tool_observation"
    if any("no_tool_boundary" in patch for patch in patches):
        return "irrelevance_no_tool_boundary_applied"
    if entry_id == "hallucination_abstain_v0":
        return "answerability_boundary_checked_without_proxy_issue"
    return "state_tracking_guidance_applied_without_proxy_issue"


def _card(arm: str, path: Path, data: Dict[str, Any]) -> Dict[str, Any]:
    validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
    patches = [str(item) for item in (validation.get("request_patches") or [])]
    issues = [item for item in (validation.get("issues") or []) if isinstance(item, dict)]
    labels = [str(item) for item in (validation.get("failure_labels") or [])]
    entry_id = _entry_from_patches(patches)
    source_hash = _hash_bytes(path.read_bytes())
    pattern = _pattern(entry_id, issues, patches)
    tool_schema = data.get("tool_schema_snapshot") if isinstance(data.get("tool_schema_snapshot"), dict) else {}
    compact = {
        "trace_card_id": f"abhe_v0_{arm}_{_short_hash(source_hash)}",
        "source_hash": source_hash,
        "entry_id": entry_id,
        "behavior_cluster": entry_id.removesuffix("_v0"),
        "observed_failure_pattern": pattern,
        "turn_span_summary": "sanitized_server_trace_single_provider_exchange_or_multiturn_subexchange",
        "allowed_compact_evidence": [
            f"arm={arm}",
            f"status_code_class={_status_class(data.get('status_code'))}",
            f"latency_bucket={_latency_bucket(data.get('latency_ms'))}",
            f"tool_schema_count={len(tool_schema)}",
            f"issue_kinds={','.join(sorted({str(i.get('kind')) for i in issues})) or 'none'}",
            f"failure_label_count={len(labels)}",
            f"candidate_patch_count={len([p for p in patches if p.startswith('abhe_v0_runtime_candidate_adapter')])}",
            f"no_tool_boundary_applied={any('no_tool_boundary' in p for p in patches)}",
        ],
        "forbidden_fields_absent": True,
    }
    if entry_id == "state_tracking_v0":
        compact["state_variable_lost"] = "not_raw_extracted_proxy_issue_or_scorer_unit_state_mismatch"
    if entry_id == "hallucination_abstain_v0":
        compact["answerability_failure_kind"] = "irrelevance_or_relevance_boundary_compact"
    return compact


def _selected_cards(cards: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    def score(card: Dict[str, Any]) -> tuple[int, str]:
        evidence = " ".join(card.get("allowed_compact_evidence", []))
        important = 0
        if "post_tool_prose_summary" in evidence:
            important += 3
        if "no_tool_boundary_applied=True" in evidence:
            important += 2
        if card.get("entry_id") == "hallucination_abstain_v0":
            important += 1
        return (-important, str(card.get("trace_card_id")))
    return sorted(cards, key=score)[:limit]


def build_analysis(
    *,
    baseline_trace_root: Path = DEFAULT_BASELINE_TRACE_ROOT,
    candidate_trace_root: Path = DEFAULT_CANDIDATE_TRACE_ROOT,
    max_cards: int = 12,
) -> Dict[str, Any]:
    blockers: List[str] = []
    all_cards: List[Dict[str, Any]] = []
    trace_counts: Dict[str, int] = {}
    for arm, root in [("baseline", baseline_trace_root), ("candidate", candidate_trace_root)]:
        if not root.exists():
            blockers.append(f"trace_root_missing:{arm}")
            trace_counts[arm] = 0
            continue
        paths = sorted(root.glob("*.json"))
        trace_counts[arm] = len(paths)
        for path in paths:
            try:
                all_cards.append(_card(arm, path, _load_trace(path)))
            except Exception:
                blockers.append(f"trace_parse_failed:{arm}:{path.name}")
    selected = _selected_cards(all_cards, max_cards)
    pattern_counts: Dict[str, int] = {}
    entry_counts: Dict[str, int] = {}
    no_tool_boundary_count = 0
    for card in all_cards:
        pattern_counts[card["observed_failure_pattern"]] = pattern_counts.get(card["observed_failure_pattern"], 0) + 1
        entry_counts[card["entry_id"]] = entry_counts.get(card["entry_id"], 0) + 1
        if any(item == "no_tool_boundary_applied=True" for item in card.get("allowed_compact_evidence", [])):
            no_tool_boundary_count += 1
    analysis = {
        "artifact_kind": "abhe_v0_bfcl_real_trace_analysis",
        "schema_version": "abhe_v0_bfcl_real_trace_analysis_v0",
        "selected_case_ids_hash": EXPECTED_HASH,
        "bounded_dev_smoke_only": True,
        "trace_source_scope": "server_tmp_bounded_dev_smoke_traces_sanitized",
        "trace_counts_by_arm": trace_counts,
        "sanitized_trace_card_count": len(selected),
        "all_trace_pattern_counts": pattern_counts,
        "all_trace_entry_counts": entry_counts,
        "no_tool_boundary_trace_count": no_tool_boundary_count,
        "cards": selected,
        "diagnosis_summary": {
            "post_tool_prose_summary_present": pattern_counts.get("post_tool_prose_summary_after_tool_observation", 0) > 0,
            "irrelevance_no_tool_boundary_observed": no_tool_boundary_count > 0,
            "raw_material_absent": True,
            "performance_evidence": False,
        },
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "performance_evidence": False,
        "blockers": sorted(set(blockers)),
        "next_required_action": "use_sanitized_trace_patterns_for_candidate_refinement_only",
    }
    analysis["blockers"] = sorted(set(analysis["blockers"] + scan_value(analysis, label="abhe_v0_bfcl_real_trace_analysis")))
    analysis["abhe_v0_bfcl_real_trace_analysis_passed"] = not analysis["blockers"]
    return analysis


def write_analysis(path: Path, analysis: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-trace-root", type=Path, default=DEFAULT_BASELINE_TRACE_ROOT)
    parser.add_argument("--candidate-trace-root", type=Path, default=DEFAULT_CANDIDATE_TRACE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-cards", type=int, default=12)
    parser.add_argument("--selected-case-ids-hash", default=EXPECTED_HASH)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        analysis = build_analysis(
            baseline_trace_root=args.baseline_trace_root,
            candidate_trace_root=args.candidate_trace_root,
            max_cards=args.max_cards,
        )
        analysis["selected_case_ids_hash"] = args.selected_case_ids_hash
        if args.write:
            write_analysis(args.output, analysis)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        analysis = {
            "artifact_kind": "abhe_v0_bfcl_real_trace_analysis",
            "abhe_v0_bfcl_real_trace_analysis_passed": False,
            "raw_material_absent": True,
            "performance_evidence": False,
            "blockers": [f"load_failed:{exc.__class__.__name__}"],
        }
    print(json.dumps(analysis, sort_keys=True) if args.compact else json.dumps(analysis, indent=2, sort_keys=True))
    return 1 if args.strict and not analysis.get("abhe_v0_bfcl_real_trace_analysis_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
