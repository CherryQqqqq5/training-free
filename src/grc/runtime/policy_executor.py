from __future__ import annotations

from typing import Callable, Dict, List

from grc.types import DecisionPolicySpec, Rule, ValidationIssue, VerificationContract
from grc.runtime.validator import validate_termination_admissibility
from grc.utils.text_tool_calls import classify_no_tool_call_content


def rule_decision_policy(rule: Rule) -> DecisionPolicySpec | None:
    policy = getattr(rule.action, "decision_policy", None)
    if policy is None:
        return None
    if any(
        [
            bool(getattr(policy, "request_predicates", []) or []),
            bool(getattr(policy, "recommended_tools", []) or []),
            bool(getattr(policy, "continue_condition", None)),
            bool(getattr(policy, "stop_condition", None)),
            bool(getattr(policy, "forbidden_terminations", []) or []),
            bool(getattr(policy, "evidence_requirements", []) or []),
        ]
    ):
        return policy
    return None


def is_policy_rule(rule: Rule) -> bool:
    return rule_decision_policy(rule) is not None


def partition_matching_rules(rule_hits: List[Rule]) -> tuple[List[Rule], List[Rule]]:
    policy_rule_hits = [rule for rule in rule_hits if is_policy_rule(rule)]
    compatibility_rule_hits = [rule for rule in rule_hits if not is_policy_rule(rule)]
    return policy_rule_hits, compatibility_rule_hits


def is_post_tool_prose_summary(
    base_kind: str,
    text: str,
    observed_predicates: List[str],
    last_observed_role: str | None,
) -> bool:
    if base_kind not in {"empty_tool_call", "hallucinated_completion", "natural_language_termination"}:
        return False
    if not text:
        return False
    if "prior_tool_outputs_present" not in observed_predicates:
        return False
    if last_observed_role != "tool":
        return False
    stripped = text.strip()
    if "?" in stripped:
        return False
    if stripped.startswith(("{", "[")):
        return False
    return True


def classify_no_tool_policy_issue(
    content: str,
    tool_schema_map: Dict[str, Dict[str, object]],
    observed_predicates: List[str],
    last_observed_role: str | None,
    *,
    base_kind: str | None = None,
) -> str:
    base_kind = base_kind or classify_no_tool_call_content(content, tool_schema_map)
    text = content.strip() if isinstance(content, str) else ""
    actionable_bases = {
        "empty_tool_call",
        "hallucinated_completion",
        "natural_language_termination",
        "malformed_output",
    }
    if is_post_tool_prose_summary(base_kind, text, observed_predicates, last_observed_role):
        return "post_tool_prose_summary"
    if (
        base_kind in actionable_bases
        and text
        and "tools_available" in observed_predicates
        and (
            "prior_explicit_literals_present" in observed_predicates
            or "prior_tool_outputs_present" in observed_predicates
        )
    ):
        return "actionable_no_tool_decision"
    return base_kind


def build_policy_contract(
    policy_rule_hits: List[Rule],
    rule_contract_resolver: Callable[[Rule], VerificationContract],
) -> VerificationContract:
    if not policy_rule_hits:
        return VerificationContract()
    return rule_contract_resolver(policy_rule_hits[0])


def evaluate_no_tool_policy(
    issue_kind: str,
    observed_predicates: List[str],
    policy_rule_hits: List[Rule],
    rule_contract_resolver: Callable[[Rule], VerificationContract],
) -> List[ValidationIssue]:
    issue_messages = {
        "natural_language_termination": "assistant ended turn with natural language without tool call",
        "clarification_request": "assistant requested missing user parameters before tool invocation",
        "clarification_no_tool": "assistant requested clarification instead of continuing with the available tool context",
        "unsupported_request": "assistant refused because request appears unsupported by available tools",
        "unsupported_no_tool": "assistant treated the request as unsupported instead of using the available tools",
        "hallucinated_completion": "assistant claimed progress or completion without emitting a tool call",
        "malformed_output": "assistant emitted malformed content instead of a tool call",
        "empty_tool_call": "no tool call emitted for tool-enabled request",
        "empty_completion": "provider returned an empty assistant completion without tool calls for a tool-enabled request",
        "post_tool_prose_summary": "assistant emitted a prose-only summary immediately after a successful tool result instead of continuing structurally",
        "actionable_no_tool_decision": "assistant ended a tool-enabled turn with prose instead of the next locally grounded tool action",
    }
    issues = [ValidationIssue(kind=issue_kind, message=issue_messages[issue_kind])]
    if policy_rule_hits:
        contract = build_policy_contract(policy_rule_hits, rule_contract_resolver)
        issues.extend(validate_termination_admissibility(issue_kind, contract, observed_predicates))
    return issues
