from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List

import yaml

from grc.types import (
    DecisionPolicySpec,
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


def _compile_status_path(out_path: str, candidate_dir: str | None) -> Path:
    if candidate_dir:
        return Path(candidate_dir) / "compile_status.json"
    return Path(out_path).with_name("compile_status.json")


def _is_actionable_rule(rule: Rule) -> bool:
    if rule.trigger.request_predicates:
        return True
    if rule.action.prompt_fragments or rule.action.prompt_injection.fragments:
        return True
    if rule.action.arg_sanitizer:
        return True
    verification = rule.action.verification
    if any(
        [
            verification.require_known_tool,
            verification.require_object_args,
            verification.require_required_fields,
            verification.require_known_fields,
            verification.require_type_match,
            verification.max_repairs is not None,
            bool(verification.forbidden_terminations),
            bool(verification.evidence_requirements),
        ]
    ):
        return True
    fallback = rule.action.fallback_router
    if fallback.strategy != "record_only" or fallback.assistant_message:
        return True
    guard = rule.action.tool_guard
    if any(
        [
            guard.on_violation != "record",
            guard.on_unknown_tool != "record",
            guard.on_empty_tool_call != "record",
            bool(guard.assistant_message),
        ]
    ):
        return True
    return False


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
            groups: DefaultDict[tuple[str, tuple[str, ...]], List[FailureCase]] = defaultdict(list)
            for case in failures:
                predicates = tuple(sorted(case.request_predicates)) if case.error_type == "actionable_no_tool_decision" else ()
                groups[(case.error_type, predicates)].append(case)
            for (error_type, request_predicates), scoped_failures in sorted(groups.items()):
                failure_irs.append(
                    FailureIR(
                        failure_id=(
                            f"failure_ir_global_{error_type}"
                            if not request_predicates
                            else f"failure_ir_global_{error_type}_{'_'.join(request_predicates)}"
                        ),
                        tool_name="__none__",
                        error_types=[error_type],
                        field_names=[],
                        expected_types={},
                        categories=sorted({case.category for case in scoped_failures if case.category}),
                        evidence_count=len(scoped_failures),
                        trace_ids=sorted({case.trace_id for case in scoped_failures}),
                        request_predicates=list(request_predicates),
                        request_literals=sorted(
                            {
                                literal
                                for case in scoped_failures
                                for literal in case.request_literals
                                if isinstance(literal, str) and literal.strip()
                            }
                        )[:8],
                    )
                )
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
                request_predicates=sorted({predicate for case in failures for predicate in case.request_predicates}),
                request_literals=sorted(
                    {
                        literal
                        for case in failures
                        for literal in case.request_literals
                        if isinstance(literal, str) and literal.strip()
                    }
                )[:8],
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
    if "empty_tool_call" in error_types:
        fragments.append(
            "When tools are available and the request is actionable from the current conversation state, emit the next tool call instead of replying with explanatory prose."
        )
        fragments.append(
            "Do not ask the user to repeat or reconfirm information that is already available from prior turns, tool outputs, or the current working state."
        )
    if "natural_language_termination" in error_types:
        fragments.append(
            "Do not end the turn with a natural-language completion if additional tool actions are still required to satisfy the request."
        )
    if "hallucinated_completion" in error_types:
        fragments.append(
            "Do not claim that work has already started or completed unless you emit the corresponding tool call in the same response."
        )
        fragments.append(
            "If a tool is required, emit the tool call directly instead of promising results that have not been requested yet."
        )
    if "redundant_clarification_request" in error_types:
        fragments.append(
            "Before asking the user for missing details, inspect prior user turns, tool outputs, and current state for explicit values that were already provided."
        )
        fragments.append(
            "If a file name, path, identifier, or previously confirmed target already appears in the conversation or tool state, reuse it and emit the next tool call instead of asking again."
        )
    if "unsupported_request" in error_types:
        fragments.append(
            "Before concluding that a request is unsupported, verify whether the available tools and current conversation state already provide a valid next action."
        )
    if {"empty_tool_call", "natural_language_termination", "hallucinated_completion"} & error_types:
        fragments.append(
            "If you emit tool calls in a response, keep the response focused on those tool calls and avoid adding a free-form status summary in the same message."
        )
    return fragments


def _actionable_no_tool_prompt_fragments(failure_ir: FailureIR) -> List[str]:
    fragments = [
        "When tools are available and the current request already contains enough local evidence to continue, emit the next tool call instead of ending the turn with explanatory prose.",
        "Do not end a tool-enabled turn with prose-only status updates when the next action can be grounded from the current request, prior explicit literals, or prior tool outputs.",
    ]
    predicates = set(failure_ir.request_predicates)
    if "prior_explicit_literals_present" in predicates:
        fragments.append(
            "Reuse explicit file names, paths, identifiers, or quoted literals already present in the request context before asking for clarification or stopping."
        )
    if "prior_tool_outputs_present" in predicates:
        fragments.append(
            "Use prior tool outputs as grounding for the next tool call instead of switching into natural-language explanation."
        )
    return fragments


def _global_decision_policy_for_failure_ir(failure_ir: FailureIR) -> DecisionPolicySpec:
    error_types = set(failure_ir.error_types)
    predicates = list(failure_ir.request_predicates)
    policy = DecisionPolicySpec(request_predicates=predicates)

    if "actionable_no_tool_decision" in error_types:
        policy.forbidden_terminations = ["prose_only_no_tool_termination"]
        policy.evidence_requirements = list(predicates)
        policy.continue_condition = "tools remain available and locally grounded evidence supports another tool action"
        policy.stop_condition = "do not stop with prose-only narration while the matched local continuation evidence still holds"
        return policy

    if "empty_tool_call" in error_types:
        policy.continue_condition = "a tool-enabled turn produced no tool call and should continue with a concrete tool action"
        policy.stop_condition = "only stop without a tool call when the request is genuinely non-actionable from the current local state"
        return policy

    if "natural_language_termination" in error_types:
        policy.forbidden_terminations = ["natural_language_completion_without_required_tool"]
        policy.continue_condition = "do not close the turn in natural language while a next tool action is still locally grounded"
        policy.stop_condition = "natural-language completion is admissible only after tool use is no longer required"
        return policy

    if "hallucinated_completion" in error_types:
        policy.forbidden_terminations = ["claim_progress_without_corresponding_tool_call"]
        policy.continue_condition = "emit the concrete tool call before describing progress or completion"
        policy.stop_condition = "progress claims are only admissible after the corresponding tool action has actually been emitted"
        return policy

    if "redundant_clarification_request" in error_types:
        policy.evidence_requirements = ["prior_explicit_literals_present"]
        policy.continue_condition = "reuse already available explicit literals before asking the user to restate them"
        policy.stop_condition = "clarification is only admissible when the required explicit literal is not already present in local context"
        return policy

    if "unsupported_request" in error_types:
        policy.continue_condition = "check the available tools and current state before concluding that a request is unsupported"
        policy.stop_condition = "an unsupported conclusion is only admissible after local tool/state checks fail to reveal a valid next action"
        return policy

    return policy


def _no_tool_verification_contract() -> VerificationContract:
    return VerificationContract(
        require_known_tool=False,
        require_object_args=False,
        require_required_fields=False,
        require_known_fields=False,
        require_type_match=False,
        max_repairs=None,
    )


def _build_global_guard_rules(grouped: DefaultDict[str, List[FailureCase]]) -> List[Rule]:
    global_failures = grouped.get("__none__", [])
    if not global_failures:
        return []

    rules: List[Rule] = []
    groups: DefaultDict[tuple[str, tuple[str, ...]], List[FailureCase]] = defaultdict(list)
    for case in global_failures:
        predicates = tuple(sorted(case.request_predicates)) if case.error_type == "actionable_no_tool_decision" else ()
        groups[(case.error_type, predicates)].append(case)

    for (error_type, request_predicates), scoped_failures in sorted(groups.items()):
        categories = sorted({case.category for case in scoped_failures if case.category})
        failure_ir = FailureIR(
            failure_id=(
                f"failure_ir_global_{error_type}"
                if not request_predicates
                else f"failure_ir_global_{error_type}_{'_'.join(request_predicates)}"
            ),
            tool_name="__none__",
            error_types=[error_type],
            field_names=[],
            expected_types={},
            categories=categories,
            evidence_count=len(scoped_failures),
            trace_ids=sorted({case.trace_id for case in scoped_failures}),
            request_predicates=list(request_predicates),
            request_literals=sorted(
                {
                    literal
                    for case in scoped_failures
                    for literal in case.request_literals
                    if isinstance(literal, str) and literal.strip()
                }
            )[:8],
        )
        prompt_fragments = (
            _actionable_no_tool_prompt_fragments(failure_ir)
            if error_type == "actionable_no_tool_decision"
            else _global_prompt_fragments(failure_ir)
        )
        verification = _no_tool_verification_contract()
        decision_policy = _global_decision_policy_for_failure_ir(failure_ir)
        policy_first = error_type == "actionable_no_tool_decision"
        if policy_first:
            patch_sites = ["prompt_injector", "policy_executor"]
            tool_guard = ToolGuardSpec(
                enabled=False,
                on_violation="record",
                on_unknown_tool="record",
                on_empty_tool_call="record",
            )
            fallback_router = FallbackRoutingSpec(strategy="record_only")
            validation_contract = VerificationContract()
        else:
            patch_sites = ["tool_guard", "verification_hook", "fallback_router"]
            tool_guard = ToolGuardSpec(
                enabled=True,
                on_violation="record",
                on_unknown_tool="record",
                on_empty_tool_call="record",
            )
            fallback_router = FallbackRoutingSpec(
                strategy="record_only",
                on_issue_kinds=[error_type],
            )
            validation_contract = verification

        rules.append(
            Rule(
                rule_id=(
                    f"rule_global_no_tool_{error_type}_v1"
                    if not request_predicates
                    else f"rule_global_no_tool_{error_type}_{'_'.join(request_predicates)}_v1"
                ),
                priority=100,
                enabled=True,
                trigger=MatchSpec(
                    error_types=[error_type],
                    category_patterns=categories,
                    request_predicates=list(request_predicates),
                ),
                scope=PatchScope(
                    tool_names=[],
                    patch_sites=patch_sites,
                ),
                action=RuleAction(
                    prompt_fragments=prompt_fragments,
                    prompt_injection=PromptInjectionSpec(
                        fragments=prompt_fragments if policy_first else []
                    ),
                    decision_policy=decision_policy,
                    tool_guard=tool_guard,
                    verification=verification,
                    fallback_router=fallback_router,
                ),
                validation_contract=validation_contract,
            )
        )

    return rules


def compile_patch(
    failure_jsonl: str,
    out_path: str,
    patch_id: str = "patch_auto_001",
    candidate_dir: str | None = None,
) -> Dict[str, object]:
    grouped: DefaultDict[str, List[FailureCase]] = defaultdict(list)
    failures = _load_failures(failure_jsonl)
    for item in failures:
        grouped[item.tool_name].append(item)

    rules: List[Rule] = []
    failure_irs = _build_failure_ir(grouped)
    failure_ir_map = {item.tool_name: item for item in failure_irs}
    rules.extend(_build_global_guard_rules(grouped))

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

    high_value_error_types = sorted({item.error_type for item in failures if item.error_type})
    source_failure_count = len(failures)
    failure_ir_count = len(failure_irs)
    rule_count = len(rules)
    actionable_rule_count = sum(1 for rule in rules if _is_actionable_rule(rule))
    if source_failure_count <= 0:
        status = "no_failure_evidence"
        reason = "mine produced zero failure evidence"
    elif failure_ir_count <= 0 or rule_count <= 0 or actionable_rule_count <= 0:
        status = "uncompilable_failure_evidence"
        reason = "failure evidence exists but compiler did not synthesize a non-empty actionable rule set"
    else:
        status = "actionable_patch"
        reason = "compiler synthesized a non-empty actionable patch"

    compile_status = {
        "status": status,
        "patch_id": patch_id,
        "source_failure_count": source_failure_count,
        "failure_ir_count": failure_ir_count,
        "rule_count": rule_count,
        "actionable_rule_count": actionable_rule_count,
        "high_value_error_types": high_value_error_types,
        "reason": reason,
    }
    status_path = _compile_status_path(out_path, candidate_dir)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(compile_status, ensure_ascii=False, indent=2), encoding="utf-8")

    if candidate_dir:
        candidate_path = Path(candidate_dir)
        candidate_path.mkdir(parents=True, exist_ok=True)
        (candidate_path / "rule.yaml").write_text(out_file.read_text(encoding="utf-8"), encoding="utf-8")
        (candidate_path / "failure_summary.json").write_text(
            json.dumps(_failure_summary(failure_irs, len(failures), patch_id), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return compile_status
