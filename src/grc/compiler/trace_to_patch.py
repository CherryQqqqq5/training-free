from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List

import yaml

from grc.types import (
    FailureCase,
    FailureIR,
    FieldConstraint,
    FallbackRoutingSpec,
    MatchSpec,
    PatchBundle,
    PatchScope,
    PromptInjectionSpec,
    Rule,
    RuleAction,
    ToolSanitizerSpec,
    VerificationContract,
)

PATCH_SITES = [
    "prompt_injector",
    "tool_guard",
    "arg_sanitizer",
    "verification_hook",
    "fallback_router",
]


def _load_failures(failure_jsonl: str) -> List[FailureCase]:
    failures: List[FailureCase] = []
    with open(failure_jsonl, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            failures.append(FailureCase(**json.loads(line)))
    return failures


def _build_failure_ir(grouped: DefaultDict[str, List[FailureCase]]) -> List[FailureIR]:
    failure_irs: List[FailureIR] = []
    for tool_name, failures in grouped.items():
        if tool_name == "__none__":
            continue

        expected_types: Dict[str, str] = {}
        field_names = sorted({case.field_name for case in failures if case.field_name})
        error_types = sorted({case.error_type for case in failures})
        categories = sorted({case.category for case in failures if case.category})
        trace_ids = sorted({case.trace_id for case in failures})

        for case in failures:
            if case.field_name and case.expected_type:
                expected_types[case.field_name] = case.expected_type

        failure_irs.append(
            FailureIR(
                failure_id=f"failure_ir_{tool_name}",
                tool_name=tool_name,
                error_types=error_types,
                field_names=field_names,
                expected_types=expected_types,
                categories=categories,
                evidence_count=len(failures),
                trace_ids=trace_ids,
            )
        )

    return failure_irs


def _failure_summary(failure_irs: List[FailureIR], total_failures: int, patch_id: str) -> Dict[str, object]:
    return {
        "patch_id": patch_id,
        "source_failure_count": total_failures,
        "failure_ir_count": len(failure_irs),
        "tools": [
            {
                "tool_name": item.tool_name,
                "evidence_count": item.evidence_count,
                "error_types": item.error_types,
                "field_names": item.field_names,
            }
            for item in failure_irs
        ],
    }


def compile_patch(
    failure_jsonl: str,
    out_path: str,
    patch_id: str = "patch_auto_001",
    candidate_dir: str | None = None,
) -> None:
    grouped: DefaultDict[str, List[FailureCase]] = defaultdict(list)
    failures = _load_failures(failure_jsonl)
    for item in failures:
        grouped[item.tool_name].append(item)

    rules: List[Rule] = []
    failure_irs = _build_failure_ir(grouped)
    failure_ir_map = {item.tool_name: item for item in failure_irs}

    for tool_name, failures in grouped.items():
        if tool_name == "__none__":
            continue

        fields: Dict[str, FieldConstraint] = {}
        for case in failures:
            if not case.field_name:
                continue
            field_constraint = fields.get(case.field_name, FieldConstraint())
            if case.expected_type:
                field_constraint.type = case.expected_type
            if case.error_type == "missing_required":
                field_constraint.required = True
            fields[case.field_name] = field_constraint

        spec = ToolSanitizerSpec(
            repair_json=True,
            coerce_types=True,
            strip_unknown_keys=True,
            fill_defaults=True,
            fields=fields,
        )

        failure_ir = failure_ir_map[tool_name]
        prompt_fragments = [
            (
                f"When calling `{tool_name}`, emit a JSON object with only schema-defined fields. "
                "Prefer exact required fields and schema-compatible scalar types."
            )
        ]
        rules.append(
            Rule(
                rule_id=f"rule_{tool_name}_arg_sanitizer_v1",
                priority=10,
                enabled=True,
                trigger=MatchSpec(
                    tool_names=[tool_name],
                    error_types=failure_ir.error_types,
                    category_patterns=failure_ir.categories,
                ),
                scope=PatchScope(tool_names=[tool_name], patch_sites=PATCH_SITES),
                action=RuleAction(
                    prompt_fragments=prompt_fragments,
                    prompt_injection=PromptInjectionSpec(fragments=prompt_fragments),
                    arg_sanitizer={tool_name: spec},
                    verification=VerificationContract(),
                    fallback_router=FallbackRoutingSpec(strategy="record_only"),
                ),
                validation_contract=VerificationContract(),
            )
        )

    bundle = PatchBundle(
        patch_id=patch_id,
        rules=rules,
        failure_ir=failure_irs,
        source_failure_count=len(failures),
        metadata={
            "compiler": "trace_to_patch",
            "failure_jsonl": str(Path(failure_jsonl)),
            "candidate_dir": candidate_dir,
        },
    )
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        yaml.safe_dump(bundle.model_dump(mode="python"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    if candidate_dir:
        candidate_path = Path(candidate_dir)
        candidate_path.mkdir(parents=True, exist_ok=True)
        (candidate_path / "rule.yaml").write_text(out_file.read_text(encoding="utf-8"), encoding="utf-8")
        (candidate_path / "failure_summary.json").write_text(
            json.dumps(_failure_summary(failure_irs, len(failures), patch_id), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
