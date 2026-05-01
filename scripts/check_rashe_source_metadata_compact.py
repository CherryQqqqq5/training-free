#!/usr/bin/env python3
"""Check approved sanitized compact source metadata root."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

APPROVED_CATEGORIES = (
    "agentic_web_search",
    "agentic_memory",
    "multi_turn_base",
    "multi_turn_long_context",
    "multi_turn_miss_param",
    "multi_turn_miss_func",
    "hallucination",
    "irrelevance",
)
PROMPT_FAMILY_TAXONOMY = {
    "web_search_required",
    "memory_retrieval_required",
    "multi_turn_state_tracking",
    "long_context_state_tracking",
    "multi_turn_missing_parameter",
    "multi_turn_missing_function",
    "hallucination_abstention",
    "irrelevance_abstention",
}
CATEGORY_PROMPT_FAMILY = {
    "agentic_web_search": "web_search_required",
    "agentic_memory": "memory_retrieval_required",
    "multi_turn_base": "multi_turn_state_tracking",
    "multi_turn_long_context": "long_context_state_tracking",
    "multi_turn_miss_param": "multi_turn_missing_parameter",
    "multi_turn_miss_func": "multi_turn_missing_function",
    "hallucination": "hallucination_abstention",
    "irrelevance": "irrelevance_abstention",
}
SOURCE_FAMILY_ID_TAXONOMY = {
    "agentic_web",
    "agentic_memory",
    "multi_turn_workflow",
    "abstention_safety",
}
CATEGORY_SOURCE_FAMILY_ID = {
    "agentic_web_search": "agentic_web",
    "agentic_memory": "agentic_memory",
    "multi_turn_base": "multi_turn_workflow",
    "multi_turn_long_context": "multi_turn_workflow",
    "multi_turn_miss_param": "multi_turn_workflow",
    "multi_turn_miss_func": "multi_turn_workflow",
    "hallucination": "abstention_safety",
    "irrelevance": "abstention_safety",
}
SIGNED_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/approved_source_metadata_compact/")
SIGNED_CASES_PER_CATEGORY = 20
ALLOWED_FIELDS = {"category", "ordinal", "prompt_family", "source_nonce", "source_family_id"}
NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{32,}$|^[0-9a-fA-F]{32,}$")
FORBIDDEN_FIELD_NAMES = {
    "raw_case_id",
    "case_id",
    "case id",
    "raw_prompt",
    "prompt",
    "prompt_text",
    "task_text",
    "tool_trace",
    "trace_path",
    "raw_trace",
    "raw_provider_payload",
    "provider_payload",
    "provider_response",
    "raw_payload",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "candidate_output",
    "repair_output",
    "feedback",
    "holdout_feedback",
    "full_suite_feedback",
    "dev_manifest",
    "holdout_manifest",
    "full_manifest",
    "candidate_jsonl",
    "performance_metric",
}
RAW_VALUE_INDICATORS = (
    "raw_trace",
    "raw-trace",
    "raw_payload",
    "raw-payload",
    "raw_prompt",
    "raw-prompt",
    "case_id",
    "case-id",
    "case id",
    "provider_payload",
    "provider-payload",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "candidate_output",
    "repair_output",
    "holdout_feedback",
    "full_suite_feedback",
)


def _field_name(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def forbidden_hits(value: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            name = _field_name(str(key))
            path = f"{prefix}.{key}" if prefix else str(key)
            if name in FORBIDDEN_FIELD_NAMES:
                hits.append(path)
            hits.extend(forbidden_hits(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(forbidden_hits(child, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        for indicator in RAW_VALUE_INDICATORS:
            if indicator in lowered:
                hits.append(f"{prefix}:raw_indicator:{indicator}")
    return hits


def load_records(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        text = path.read_text(encoding="utf-8")
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    except OSError as exc:
        return [], [f"source_metadata_read_failed:{path}:{exc}"]
    except json.JSONDecodeError as exc:
        return [], [f"source_metadata_json_invalid:{path}:{exc}"]
    if not all(isinstance(record, dict) for record in records):
        return [], [f"source_metadata_record_not_object:{path}"]
    return records, []


def check_record(record: dict[str, Any], category: str, ordinal: int) -> list[str]:
    blockers: list[str] = []
    if set(record) != ALLOWED_FIELDS:
        blockers.append("source_metadata_fields_do_not_match_allowlist")
    extra = set(record) - ALLOWED_FIELDS
    if extra:
        blockers.append("source_metadata_extra_field:" + ",".join(sorted(extra)))
    hits = forbidden_hits(record)
    if hits:
        blockers.extend(f"source_metadata_forbidden_field:{hit}" for hit in hits)
    if record.get("category") != category:
        blockers.append(f"source_metadata_category_mismatch:{record.get('category')!r}:{category}")
    if record.get("ordinal") != ordinal:
        blockers.append(f"source_metadata_ordinal_not_continuous:{category}:{record.get('ordinal')!r}:{ordinal}")
    prompt_family = record.get("prompt_family")
    if prompt_family not in PROMPT_FAMILY_TAXONOMY:
        blockers.append(f"source_metadata_prompt_family_not_taxonomy:{prompt_family!r}")
    elif prompt_family != CATEGORY_PROMPT_FAMILY[category]:
        blockers.append(f"source_metadata_prompt_family_not_signed:{category}:{prompt_family!r}")
    source_family_id = record.get("source_family_id")
    if source_family_id not in SOURCE_FAMILY_ID_TAXONOMY:
        blockers.append(f"source_metadata_source_family_id_not_taxonomy:{source_family_id!r}")
    elif source_family_id != CATEGORY_SOURCE_FAMILY_ID[category]:
        blockers.append(f"source_metadata_source_family_id_not_signed:{category}:{source_family_id!r}")
    source_nonce = record.get("source_nonce")
    if not isinstance(source_nonce, str) or not NONCE_RE.match(source_nonce):
        blockers.append(f"source_metadata_nonce_format_invalid:{category}:{ordinal}")
    elif forbidden_hits({"source_nonce": source_nonce}):
        blockers.append(f"source_metadata_nonce_forbidden:{category}:{ordinal}")
    return blockers


def check_root(root: Path) -> dict[str, Any]:
    blockers: list[str] = []
    category_counts: dict[str, int] = {}
    if not root.exists():
        return {"category_counts": category_counts, "blockers": [f"approved_bfcl_source_metadata_missing:{root}"]}
    for category in APPROVED_CATEGORIES:
        path = root / f"{category}.jsonl"
        if not path.exists():
            blockers.append(f"source_metadata_category_missing:{category}:{path}")
            category_counts[category] = 0
            continue
        records, load_blockers = load_records(path)
        blockers.extend(load_blockers)
        category_counts[category] = len(records)
        if len(records) != SIGNED_CASES_PER_CATEGORY:
            blockers.append(f"source_metadata_count_not_signed:{category}:{len(records)}")
        for ordinal, record in enumerate(records):
            blockers.extend(check_record(record, category, ordinal))
    extra_files = sorted(p.name for p in root.iterdir() if p.is_file() and p.name not in {f"{category}.jsonl" for category in APPROVED_CATEGORIES})
    if extra_files:
        blockers.append("source_metadata_extra_file:" + ",".join(extra_files))
    return {"category_counts": category_counts, "blockers": blockers}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=SIGNED_ROOT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = check_root(args.root)
    blockers = result["blockers"]
    total_records = sum(result["category_counts"].values())
    summary = {
        "report_scope": "rashe_source_metadata_compact_check",
        "root": str(args.root),
        "categories": list(APPROVED_CATEGORIES),
        "category_counts": result["category_counts"],
        "records_per_category": SIGNED_CASES_PER_CATEGORY,
        "total_records": total_records,
        "allowed_fields": sorted(ALLOWED_FIELDS),
        "prompt_family_taxonomy": sorted(PROMPT_FAMILY_TAXONOMY),
        "source_family_id_taxonomy": sorted(SOURCE_FAMILY_ID_TAXONOMY),
        "rashe_source_metadata_compact_passed": not blockers,
        "blockers": blockers,
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and blockers:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
