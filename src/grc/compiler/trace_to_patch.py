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
    ToolGuardSpec,
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


def _guard_action_for_failure_ir(failure_ir: FailureIR) -> str:
    error_types = set(failure_ir.error_types)
    if "wrong_tool_name" in error_types:
        return "drop"
    if "empty_tool_call" in error_types:
        return "assistant_message"
    return "record"


def _fallback_for_failure_ir(failure_ir: FailureIR) -> FallbackRoutingSpec:
    error_types = set(failure_ir.error_types)
    if "wrong_tool_name" in error_types:
        return FallbackRoutingSpec(
            strategy="assistant_message",
            assistant_message="Tool call removed because it did not match any tool exposed in the request.",
            on_issue_kinds=["tool_guard_violation", "wrong_tool_name"],
        )
    if "empty_tool_call" in error_types:
        return FallbackRoutingSpec(
            strategy="assistant_message",
            assistant_message="No valid tool call was emitted for the available tool set.",
            on_issue_kinds=["empty_tool_call"],
        )
    if "hallucinated_completion" in error_types:
        return FallbackRoutingSpec(
            strategy="assistant_message",
            assistant_message="No tool call was emitted. Emit the required tool call before claiming progress.",
            on_issue_kinds=["hallucinated_completion"],
        )
    if {"invalid_json_args", "non_object_args"} & error_types:
        return FallbackRoutingSpec(
            strategy="drop_tool_call",
            on_issue_kinds=["invalid_json_args", "non_object_args"],
        )
    if {"missing_required", "type_mismatch", "unknown_field"} & error_types:
        return FallbackRoutingSpec(
            strategy="drop_tool_call",
            on_issue_kinds=["missing_required", "type_mismatch", "unknown_field", "repair_budget_exceeded"],
        )
    return FallbackRoutingSpec(strategy="record_only", on_issue_kinds=sorted(error_types))


def _verification_contract_for_failure_ir(failure_ir: FailureIR) -> VerificationContract:
    error_types = set(failure_ir.error_types)
    contract = VerificationContract()
    if "wrong_tool_name" in error_types:
        contract.require_known_tool = True
    if "non_object_args" in error_types:
        contract.require_object_args = True
    if "missing_required" in error_types:
        contract.require_required_fields = True
    if "unknown_field" in error_types:
        contract.require_known_fields = True
    if "type_mismatch" in error_types:
        contract.require_type_match = True
    if {"invalid_json_args", "non_object_args", "type_mismatch", "unknown_field"} & error_types:
        contract.max_repairs = 2
    return contract


def _prompt_fragments(tool_name: str, failure_ir: FailureIR) -> List[str]:
    fragments = [
        (
            f"When calling `{tool_name}`, emit a JSON object with only schema-defined fields. "
            "Prefer exact required fields and schema-compatible scalar types."
        )
    ]
    error_types = set(failure_ir.error_types)
    if "missing_required" in error_types:
        fragments.append(f"For `{tool_name}`, always include all required fields before emitting the tool call.")
    if "type_mismatch" in error_types:
        fragments.append(f"For `{tool_name}`, match scalar JSON types exactly instead of relying on coercion.")
    if "unknown_field" in error_types:
        fragments.append(f"For `{tool_name}`, do not invent extra keys outside the declared schema.")
    return fragments


def _global_prompt_fragments(failure_ir: FailureIR) -> List[str]:
    error_types = set(failure_ir.error_types)
    fragments: List[str] = []
    if "hallucinated_completion" in error_types:
        fragments.append(
            "Do not claim that work has already started or completed unless you emit the corresponding tool call in the same response."
        )
        fragments.append(
            "If a tool is required, emit the tool call directly instead of promising results that have not been requested yet."
        )
    return fragments


def _build_global_guard_rule(grouped: DefaultDict[str, List[FailureCase]]) -> Rule | None:
    global_failures = grouped.get("__none__", [])
    if not global_failures:
        return None

    error_types = sorted({case.error_type for case in global_failures})
    categories = sorted({case.category for case in global_failures if case.category})
    failure_ir = FailureIR(
        failure_id="failure_ir_global_tool_guard",
        tool_name="__none__",
        error_types=error_types,
        field_names=[],
        expected_types={},
        categories=categories,
        evidence_count=len(global_failures),
        trace_ids=sorted({case.trace_id for case in global_failures}),
    )
    guard_action = _guard_action_for_failure_ir(failure_ir)
    fallback = _fallback_for_failure_ir(failure_ir)
    prompt_fragments = _global_prompt_fragments(failure_ir)

    return Rule(
        rule_id="rule_global_tool_guard_v1",
        priority=100,
        enabled=True,
        trigger=MatchSpec(error_types=error_types, category_patterns=categories),
        scope=PatchScope(tool_names=[], patch_sites=["tool_guard", "verification_hook", "fallback_router"]),
        action=RuleAction(
            prompt_fragments=prompt_fragments,
            prompt_injection=PromptInjectionSpec(fragments=prompt_fragments),
            tool_guard=ToolGuardSpec(
                enabled=True,
                on_violation=guard_action,
                on_unknown_tool=guard_action,
                on_empty_tool_call="assistant_message" if "empty_tool_call" in error_types else "record",
                assistant_message=fallback.assistant_message or "Invalid tool emission removed by guard.",
            ),
            verification=_verification_contract_for_failure_ir(failure_ir),
            fallback_router=fallback,
        ),
        validation_contract=_verification_contract_for_failure_ir(failure_ir),
    )


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
    global_guard_rule = _build_global_guard_rule(grouped)
    if global_guard_rule is not None:
        rules.append(global_guard_rule)

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
        prompt_fragments = _prompt_fragments(tool_name, failure_ir)
        guard_action = _guard_action_for_failure_ir(failure_ir)
        fallback = _fallback_for_failure_ir(failure_ir)
        verification = _verification_contract_for_failure_ir(failure_ir)
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
                    tool_guard=ToolGuardSpec(
                        enabled=True,
                        on_violation=guard_action,
                        on_unknown_tool=guard_action,
                        on_empty_tool_call="record",
                        assistant_message=fallback.assistant_message,
                    ),
                    arg_sanitizer={tool_name: spec},
                    verification=verification,
                    fallback_router=fallback,
                ),
                validation_contract=verification,
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
