#!/usr/bin/env python3
"""Build signed compact RASHE source-input manifests.

This builder never writes raw BFCL prompts, case IDs, provider payloads, scorer
material, candidate material, or performance evidence. It only accepts approved
source metadata records that are already compact and sanitized, then derives an
irreversible compact_source_hash from a source nonce plus category/ordinal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
SIGNED_CASES_PER_CATEGORY = 20
SIGNED_OUTPUT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/")
ALLOWED_SOURCE_METADATA_FIELDS = {
    "category",
    "ordinal",
    "prompt_family",
    "source_nonce",
    "source_family_id",
}
ALLOWED_MANIFEST_FIELDS = {"category", "ordinal", "prompt_family", "compact_source_hash"}
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


class CompactSourceInputBuildError(RuntimeError):
    """Fail-closed builder error whose message is an auditable blocker."""


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


def load_records(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CompactSourceInputBuildError(f"approved_source_input_read_failed:{path}:{exc}") from exc
    try:
        if path.suffix == ".jsonl":
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows = payload.get("records") or payload.get("cases") or []
            else:
                rows = payload
    except json.JSONDecodeError as exc:
        raise CompactSourceInputBuildError(f"approved_source_input_json_invalid:{path}:{exc}") from exc
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise CompactSourceInputBuildError(f"approved_source_input_records_not_list:{path}")
    return rows


def metadata_path(root: Path, category: str) -> Path:
    for suffix in (".jsonl", ".json"):
        path = root / f"{category}{suffix}"
        if path.exists():
            return path
    raise CompactSourceInputBuildError(f"approved_source_input_category_missing:{category}")


def validate_metadata_record(record: dict[str, Any], category: str, ordinal: int) -> None:
    hits = forbidden_hits(record)
    if hits:
        raise CompactSourceInputBuildError("approved_source_input_forbidden_field:" + ";".join(hits))
    extra = set(record) - ALLOWED_SOURCE_METADATA_FIELDS
    if extra:
        raise CompactSourceInputBuildError("approved_source_input_extra_field:" + ",".join(sorted(extra)))
    if record.get("category") != category:
        raise CompactSourceInputBuildError(f"approved_source_input_category_mismatch:{record.get('category')!r}:{category}")
    if record.get("ordinal") != ordinal:
        raise CompactSourceInputBuildError(f"approved_source_input_ordinal_not_signed:{category}:{record.get('ordinal')!r}:{ordinal}")
    prompt_family = record.get("prompt_family")
    if prompt_family != CATEGORY_PROMPT_FAMILY[category]:
        raise CompactSourceInputBuildError(f"approved_source_input_prompt_family_not_signed:{category}:{prompt_family!r}")
    source_nonce = record.get("source_nonce")
    if not isinstance(source_nonce, str) or len(source_nonce) < 16:
        raise CompactSourceInputBuildError(f"approved_source_input_nonce_invalid:{category}:{ordinal}")
    if forbidden_hits({"source_nonce": source_nonce}):
        raise CompactSourceInputBuildError(f"approved_source_input_nonce_forbidden:{category}:{ordinal}")


def compact_hash(category: str, ordinal: int, prompt_family: str, source_nonce: str) -> str:
    material = json.dumps(
        {
            "namespace": "rashe_compact_source_input_v1",
            "category": category,
            "ordinal": ordinal,
            "prompt_family": prompt_family,
            "source_nonce_sha256": hashlib.sha256(source_nonce.encode("utf-8")).hexdigest(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_category_records(source_root: Path, category: str) -> list[dict[str, Any]]:
    path = metadata_path(source_root, category)
    rows = load_records(path)
    if len(rows) != SIGNED_CASES_PER_CATEGORY:
        raise CompactSourceInputBuildError(f"approved_source_input_count_not_signed:{category}:{len(rows)}")
    outputs: list[dict[str, Any]] = []
    for ordinal, record in enumerate(rows):
        validate_metadata_record(record, category, ordinal)
        prompt_family = str(record["prompt_family"])
        output = {
            "category": category,
            "ordinal": ordinal,
            "prompt_family": prompt_family,
            "compact_source_hash": compact_hash(category, ordinal, prompt_family, str(record["source_nonce"])),
        }
        if set(output) != ALLOWED_MANIFEST_FIELDS:
            raise CompactSourceInputBuildError("compact_source_input_output_schema_invalid")
        outputs.append(output)
    return outputs


def write_manifests(source_root: Path, output_root: Path) -> list[str]:
    if not source_root.exists():
        raise CompactSourceInputBuildError(f"approved_source_input_root_missing:{source_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for category in APPROVED_CATEGORIES:
        records = build_category_records(source_root, category)
        path = output_root / f"{category}.jsonl"
        path.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")
        written.append(str(path))
    return written


def check_plan(source_root: Path) -> list[str]:
    blockers: list[str] = []
    if not source_root.exists():
        return [f"approved_source_input_root_missing:{source_root}"]
    for category in APPROVED_CATEGORIES:
        try:
            build_category_records(source_root, category)
        except CompactSourceInputBuildError as exc:
            blockers.append(str(exc))
    return blockers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True, help="Approved compact source metadata root; raw BFCL roots are not accepted.")
    parser.add_argument("--output-root", type=Path, default=SIGNED_OUTPUT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    blockers = check_plan(args.source_root)
    written: list[str] = []
    if not blockers and not args.dry_run:
        try:
            written = write_manifests(args.source_root, args.output_root)
        except CompactSourceInputBuildError as exc:
            blockers.append(str(exc))
    summary = {
        "report_scope": "rashe_source_inputs_compact_builder",
        "source_root": str(args.source_root),
        "output_root": str(args.output_root),
        "dry_run": args.dry_run,
        "categories": list(APPROVED_CATEGORIES),
        "case_count_per_category": SIGNED_CASES_PER_CATEGORY,
        "planned_total_cases": len(APPROVED_CATEGORIES) * SIGNED_CASES_PER_CATEGORY,
        "written_manifests": written,
        "rashe_source_inputs_compact_builder_passed": not blockers,
        "blockers": blockers,
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and blockers:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
