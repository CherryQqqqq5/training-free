from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from grc.compiler.failure_taxonomy import classify_error_type
from grc.runtime.policy_executor import (
    classify_no_tool_policy_issue,
    evaluate_no_tool_policy,
    is_post_tool_structured_final_answer,
    is_policy_rule,
    partition_matching_rules,
)
from grc.runtime.sanitizer import sanitize_tool_call
from grc.runtime.validator import validate_tool_arguments
from grc.types import (
    DecisionPolicySpec,
    PatchBundle,
    Rule,
    ToolSanitizerSpec,
    ValidationIssue,
    ValidationRecord,
    VerificationContract,
)
from grc.utils.jsonfix import parse_loose_json
from grc.utils.text_tool_calls import parse_text_tool_calls
from grc.utils.tool_schema import tool_map_from_tools_payload


class RequestPatchList(list):
    def __init__(self, values: List[str] | None = None, *, next_tool_plan: Dict[str, Any] | None = None):
        super().__init__(values or [])
        self.next_tool_plan = next_tool_plan or {}


class RuleEngine:
    _EXACT_NEXT_TOOL_CHOICE_MODES = {"off", "guidance_only", "exact_tool_when_single_step_confident"}
    _DEFAULT_EXACT_TOOL_CHOICE_TRAJECTORY_SENSITIVE_TOOLS = {"cat", "touch", "mkdir"}
    _DEFAULT_EXACT_TOOL_CHOICE_ALLOWED_GUARD_REASONS = {
        "strong_explicit_literal_binding",
        "strong_prior_output_binding",
        "strong_prior_output_match_binding",
        "literal_arg_match",
    }
    _DEFAULT_EXACT_TOOL_CHOICE_UNSAFE_RISK_FLAGS = {
        "weak_arg_binding_evidence",
        "prior_output_state_unavailable",
        "weak_cwd_or_listing_binding",
        "cat_competing_intent",
        "write_intent_unconfirmed",
        "repeat_same_tool_without_new_evidence",
        "post_write_tool_intervention",
        "post_search_literal_cat_intervention",
        "postcondition_missing",
        "high_trajectory_risk",
    }
    _DEFAULT_HIGH_TRAJECTORY_RISK_THRESHOLD = 5

    def __init__(self, rules_dir: str, runtime_policy: Dict[str, Any] | None = None):
        self.rules_dir = Path(rules_dir)
        self.runtime_policy = dict(runtime_policy or {})
        configured_record_only = self.runtime_policy.get("record_only_no_tool_kinds")
        if isinstance(configured_record_only, list) and configured_record_only:
            self.record_only_no_tool_kinds = {str(item) for item in configured_record_only if str(item).strip()}
        else:
            self.record_only_no_tool_kinds = {
                "clarification_request",
                "unsupported_request",
                "hallucinated_completion",
                "malformed_output",
                "natural_language_termination",
            }
        configured_empty_coercion = self.runtime_policy.get("coerce_no_tool_response_to_empty_kinds")
        if isinstance(configured_empty_coercion, list) and configured_empty_coercion:
            self.coerce_no_tool_response_to_empty_kinds = {
                str(item) for item in configured_empty_coercion if str(item).strip()
            }
        else:
            self.coerce_no_tool_response_to_empty_kinds = set()
        self.inject_structured_tool_guidance = bool(self.runtime_policy.get("inject_structured_tool_guidance", False))
        self.inject_context_literal_hints = bool(self.runtime_policy.get("inject_context_literal_hints", False))
        self.resolve_contextual_string_args = bool(self.runtime_policy.get("resolve_contextual_string_args", False))
        self.force_actionable_tool_choice = bool(self.runtime_policy.get("force_actionable_tool_choice", True))
        self.enable_required_next_tool_choice = bool(
            self.runtime_policy.get("enable_required_next_tool_choice", False)
            or self.runtime_policy.get("required_next_tool_choice_enabled", False)
        )
        self.exact_next_tool_choice_mode = self._configured_exact_next_tool_choice_mode()
        self.enable_exact_next_tool_choice = self.exact_next_tool_choice_mode == "exact_tool_when_single_step_confident"
        configured_sensitive = self.runtime_policy.get("exact_tool_choice_trajectory_sensitive_tools")
        if isinstance(configured_sensitive, list):
            self.exact_tool_choice_trajectory_sensitive_tools = {str(item) for item in configured_sensitive if str(item).strip()}
        else:
            self.exact_tool_choice_trajectory_sensitive_tools = set(self._DEFAULT_EXACT_TOOL_CHOICE_TRAJECTORY_SENSITIVE_TOOLS)
        self.scorer_feedback_blocked_signatures = self._load_scorer_feedback_blocked_signatures()
        self.scorer_feedback_blocked_patterns = self._load_scorer_feedback_blocked_patterns()
        self.scorer_feedback_fallback_contexts = self._load_scorer_feedback_fallback_contexts()
        self.rules: List[Rule] = self._load_rules()

    _QUOTED_LITERAL_RE = re.compile(
        r"(?<![A-Za-z0-9])'([^'\n]{1,120})'(?![A-Za-z0-9])|\"([^\"\n]{1,120})\""
    )
    _FILE_TOKEN_RE = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9_.-]*\.[A-Za-z0-9]{1,8}\b")
    _PATH_TOKEN_RE = re.compile(r"\b(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)\b")
    _REFERENCE_VALUE_RE = re.compile(
        r"\b("
        r"it|this|that|the file|the directory|the folder|the one|same one|previously mentioned|earlier file|above file"
        r")\b",
        re.IGNORECASE,
    )



    @staticmethod
    def _scorer_feedback_tool_family(tool_name: str) -> str:
        return {
            "cat": "read_content",
            "touch": "create_file",
            "mkdir": "create_directory",
            "grep": "search",
            "find": "search",
            "cp": "move_or_copy",
            "mv": "move_or_copy",
            "echo": "write_content",
            "diff": "compare",
            "cd": "directory_navigation",
        }.get(str(tool_name or "").strip(), str(tool_name or "unknown").strip() or "unknown")

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    value = item.get("text") or item.get("content")
                    if value is not None:
                        parts.append(str(value))
            return "\n".join(parts)
        return str(content or "")

    @classmethod
    def _structured_final_answer_format_observable(cls, request_json: Dict[str, Any]) -> bool:
        texts: List[str] = []
        for message in request_json.get("messages") or []:
            if isinstance(message, dict):
                texts.append(cls._content_to_text(message.get("content")))
        input_payload = request_json.get("input")
        if isinstance(input_payload, list):
            for item in input_payload:
                if isinstance(item, dict):
                    texts.append(cls._content_to_text(item.get("content") or item.get("text")))
                else:
                    texts.append(str(item))
        elif input_payload is not None:
            texts.append(cls._content_to_text(input_payload))
        joined = "\n".join(texts).lower()
        return "final answer" in joined and "answer" in joined and "context" in joined

    def _load_scorer_feedback_payload(self) -> Dict[str, Any]:
        feedback = self.runtime_policy.get("scorer_feedback")
        path = self.runtime_policy.get("scorer_feedback_path")
        if not isinstance(feedback, dict) and isinstance(path, str) and path.strip():
            try:
                feedback = json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception:
                feedback = {}
        return feedback if isinstance(feedback, dict) else {}

    @staticmethod
    def _candidate_feedback_signature(tool_name: str, args: Dict[str, Any] | None) -> str:
        return json.dumps({"tool": tool_name, "args": args or {}}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _load_scorer_feedback_blocked_signatures(self) -> set[str]:
        feedback = self._load_scorer_feedback_payload()
        if not isinstance(feedback, dict) or not feedback.get("m27y_scorer_feedback_ready"):
            return set()
        signatures: set[str] = set()
        for item in feedback.get("blocked_candidate_signatures") or []:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool") or "").strip()
            args = item.get("args") if isinstance(item.get("args"), dict) else {}
            if tool_name:
                signatures.add(self._candidate_feedback_signature(tool_name, args))
        return signatures

    def _load_scorer_feedback_blocked_patterns(self) -> list[Dict[str, Any]]:
        feedback = self._load_scorer_feedback_payload()
        if not feedback.get("m27y_scorer_feedback_ready"):
            return []
        patterns: list[Dict[str, Any]] = []
        for item in feedback.get("blocked_regression_patterns") or []:
            if not isinstance(item, dict):
                continue
            selected_tool_family = str(item.get("selected_tool_family") or "").strip()
            postcondition_family = str(item.get("postcondition_family") or "").strip()
            binding_source = str(item.get("binding_source") or "").strip()
            if selected_tool_family or postcondition_family or binding_source:
                patterns.append(
                    {
                        "selected_tool_family": selected_tool_family,
                        "postcondition_family": postcondition_family,
                        "binding_source": binding_source,
                        "trajectory_risk_flags": sorted({str(flag) for flag in (item.get("trajectory_risk_flags") or []) if str(flag).strip()}),
                        "action": str(item.get("action") or "record_only"),
                        "regression_guard_key": item.get("regression_guard_key"),
                    }
                )
        return patterns


    def _load_scorer_feedback_fallback_contexts(self) -> list[Dict[str, Any]]:
        feedback = self._load_scorer_feedback_payload()
        if not feedback.get("m27y_scorer_feedback_ready"):
            return []
        contexts: list[Dict[str, Any]] = []
        for item in feedback.get("blocked_fallback_regression_contexts") or []:
            if not isinstance(item, dict):
                continue
            fallback_key = str(item.get("fallback_regression_guard_key") or "").strip()
            signature = item.get("fallback_signature") if isinstance(item.get("fallback_signature"), dict) else {}
            tool_name = str(signature.get("tool") or item.get("fallback_tool") or "").strip()
            args = signature.get("args") if isinstance(signature.get("args"), dict) else (item.get("fallback_args") if isinstance(item.get("fallback_args"), dict) else {})
            if not fallback_key or not tool_name:
                continue
            contexts.append(
                {
                    "source_regression_guard_key": item.get("source_regression_guard_key"),
                    "fallback_regression_guard_key": fallback_key,
                    "fallback_signature": self._candidate_feedback_signature(tool_name, args),
                    "match_mode": str(item.get("match_mode") or "signature"),
                    "action": str(item.get("action") or "record_only"),
                    "case_ids": sorted({str(case_id) for case_id in (item.get("case_ids") or []) if str(case_id).strip()}),
                    "reason": str(item.get("reason") or "post_feedback_fallback_candidate"),
                }
            )
        return contexts

    def _candidate_feedback_fallback_match(self, candidate: Dict[str, Any], matched_pattern: Dict[str, Any] | None) -> Dict[str, Any] | None:
        if not self.scorer_feedback_fallback_contexts or not matched_pattern:
            return None
        pattern_key = str(matched_pattern.get("regression_guard_key") or "").strip()
        if not pattern_key:
            return None
        tool_name = str(candidate.get("tool") or "").strip()
        args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
        signature = self._candidate_feedback_signature(tool_name, args)
        for context in self.scorer_feedback_fallback_contexts:
            if context.get("fallback_regression_guard_key") != pattern_key:
                continue
            if context.get("match_mode") == "pattern":
                return context
            if context.get("fallback_signature") == signature:
                return context
        return None

    def _candidate_feedback_pattern_match(self, candidate: Dict[str, Any]) -> Dict[str, Any] | None:
        if not self.scorer_feedback_blocked_patterns:
            return None
        candidate_tool_family = self._scorer_feedback_tool_family(str(candidate.get("tool") or ""))
        candidate_postcondition_family = self._postcondition_goal_family(candidate)
        candidate_binding_sources = set(self._candidate_binding_sources(candidate))
        candidate_binding_source = str(candidate.get("binding_source") or "").strip()
        if candidate_binding_source:
            candidate_binding_sources.add(candidate_binding_source)
        candidate_risk_flags = set(self._candidate_declared_risk_flags(candidate))
        if str(candidate.get("tool") or "").strip() in {"cat", "touch", "mkdir"}:
            candidate_risk_flags.add("trajectory_sensitive_tool")
        for pattern in self.scorer_feedback_blocked_patterns:
            expected_tool_family = pattern.get("selected_tool_family")
            if expected_tool_family and expected_tool_family != candidate_tool_family:
                continue
            expected_postcondition_family = pattern.get("postcondition_family")
            if expected_postcondition_family and expected_postcondition_family != "unknown" and expected_postcondition_family != candidate_postcondition_family:
                continue
            expected_binding_source = pattern.get("binding_source")
            if expected_binding_source and expected_binding_source != "unknown" and expected_binding_source not in candidate_binding_sources:
                continue
            expected_flags = set(pattern.get("trajectory_risk_flags") or [])
            if expected_flags and not expected_flags.issubset(candidate_risk_flags):
                continue
            return pattern
        return None

    def _candidate_feedback_pattern_matches(self, candidate: Dict[str, Any]) -> bool:
        return self._candidate_feedback_pattern_match(candidate) is not None

    def _apply_scorer_feedback_to_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = str(candidate.get("tool") or "").strip()
        args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
        signature_blocked = bool(tool_name and self._candidate_feedback_signature(tool_name, args) in self.scorer_feedback_blocked_signatures)
        matched_pattern = self._candidate_feedback_pattern_match(candidate)
        pattern_blocked = matched_pattern is not None
        fallback_context = self._candidate_feedback_fallback_match(candidate, matched_pattern)
        fallback_blocked = fallback_context is not None
        if not signature_blocked and not pattern_blocked and not fallback_blocked:
            return candidate
        patched = dict(candidate)
        action = str((matched_pattern or {}).get("action") or "record_only") if pattern_blocked else "record_only"
        fallback_action = str((fallback_context or {}).get("action") or "record_only") if fallback_blocked else None
        patched["scorer_feedback_pattern_matched"] = pattern_blocked
        patched["scorer_feedback_pattern_action"] = action if pattern_blocked else None
        patched["matched_regression_guard_key"] = (matched_pattern or {}).get("regression_guard_key")
        patched["scorer_feedback_fallback_guard_matched"] = fallback_blocked
        patched["matched_fallback_guard_key"] = (fallback_context or {}).get("source_regression_guard_key") if fallback_blocked else None
        patched["scorer_feedback_fallback_action"] = fallback_action
        if fallback_blocked:
            fallback_selection_class = "unsafe_fallback"
            fallback_selection_action = fallback_action or "record_only"
            fallback_selection_reason = "exact post-feedback fallback context matched"
        elif pattern_blocked and action == "record_only":
            fallback_selection_class = "unsafe_fallback"
            fallback_selection_action = action
            fallback_selection_reason = "high-confidence regression pattern matched"
        elif pattern_blocked:
            fallback_selection_class = "ambiguous_fallback"
            fallback_selection_action = action
            fallback_selection_reason = "diagnostic regression pattern overlap without hard block"
        else:
            fallback_selection_class = None
            fallback_selection_action = None
            fallback_selection_reason = None
        patched["fallback_selection_class"] = fallback_selection_class
        patched["fallback_selection_action"] = fallback_selection_action
        patched["fallback_selection_reason"] = fallback_selection_reason
        patched["fallback_selection_risk_score"] = patched.get("trajectory_risk_score")
        patched["scorer_feedback_action"] = fallback_action or action
        patched["scorer_feedback_reason"] = "m27ac_post_feedback_fallback_guard" if fallback_blocked else ("m27aa_pattern_regression_guard" if pattern_blocked else "m27y_scorer_gap_or_regression")
        if signature_blocked or fallback_action == "record_only" or action == "record_only":
            patched["intervention_mode"] = "record_only"
            flags = list(patched.get("trajectory_risk_flags") or [])
            if "scorer_feedback_record_only" not in flags:
                flags.append("scorer_feedback_record_only")
            if fallback_blocked and "scorer_feedback_fallback_record_only" not in flags:
                flags.append("scorer_feedback_fallback_record_only")
            patched["trajectory_risk_flags"] = flags
        return patched

    def _load_rules(self) -> List[Rule]:
        rules: List[Rule] = []
        if not self.rules_dir.exists():
            return rules

        for path in sorted(self.rules_dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if "rules" in data:
                bundle = PatchBundle(**data)
                rules.extend(bundle.rules)
            elif "policy_units" in data:
                # Candidate directories can include policy_unit.yaml next to rule.yaml.
                # Policy units are selector/compiler metadata, not runtime Rule docs.
                continue
            elif data:
                rules.append(Rule(**data))
        return sorted((rule for rule in rules if rule.enabled), key=lambda item: item.priority, reverse=True)

    def _configured_exact_next_tool_choice_mode(self) -> str:
        raw_mode = self.runtime_policy.get("exact_next_tool_choice_mode")
        if isinstance(raw_mode, str) and raw_mode.strip():
            mode = raw_mode.strip()
            if mode not in self._EXACT_NEXT_TOOL_CHOICE_MODES:
                raise ValueError(
                    "exact_next_tool_choice_mode must be one of "
                    + ", ".join(sorted(self._EXACT_NEXT_TOOL_CHOICE_MODES))
                )
            return mode
        legacy_enabled = bool(
            self.runtime_policy.get("enable_exact_next_tool_choice", False)
            or self.runtime_policy.get("exact_next_tool_choice_enabled", False)
        )
        if legacy_enabled:
            return "exact_tool_when_single_step_confident"
        return "guidance_only"

    def _action_specific_guidance_enabled(self) -> bool:
        return self.exact_next_tool_choice_mode in {"guidance_only", "exact_tool_when_single_step_confident"}

    def _exact_next_tool_choice_allowed(
        self,
        *,
        selected_tool: str | None,
        selected_action_candidate: Dict[str, Any] | None,
        next_tool_plan: Dict[str, Any],
    ) -> bool:
        if self.exact_next_tool_choice_mode != "exact_tool_when_single_step_confident":
            return False
        if not selected_tool or not isinstance(selected_action_candidate, dict):
            return False
        if str(selected_action_candidate.get("tool") or "").strip() != selected_tool:
            return False
        if selected_tool in self.exact_tool_choice_trajectory_sensitive_tools:
            return False
        guard = next_tool_plan.get("action_candidate_guard") if isinstance(next_tool_plan.get("action_candidate_guard"), dict) else {}
        reason = str(guard.get("reason") or "")
        configured_reasons = self.runtime_policy.get("exact_tool_choice_allowed_guard_reasons")
        if isinstance(configured_reasons, list) and configured_reasons:
            allowed_reasons = {str(item) for item in configured_reasons if str(item).strip()}
        else:
            allowed_reasons = set(self._DEFAULT_EXACT_TOOL_CHOICE_ALLOWED_GUARD_REASONS)
        if reason not in allowed_reasons:
            return False
        risk_flags = {str(item) for item in guard.get("risk_flags") or []}
        unsafe_flags = set(self._DEFAULT_EXACT_TOOL_CHOICE_UNSAFE_RISK_FLAGS)
        configured_unsafe = self.runtime_policy.get("exact_tool_choice_unsafe_risk_flags")
        if isinstance(configured_unsafe, list) and configured_unsafe:
            unsafe_flags = {str(item) for item in configured_unsafe if str(item).strip()}
        if risk_flags & unsafe_flags:
            return False
        try:
            json.dumps(selected_action_candidate.get("args") or {}, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return False
        return True

    def _tool_schema_map(self, request_json: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        return tool_map_from_tools_payload(request_json.get("tools", []))

    def _matched_sanitizer(self, tool_name: str) -> ToolSanitizerSpec | None:
        for rule in self.rules:
            names = rule.trigger.tool_names
            if not names or tool_name in names:
                spec = rule.action.arg_sanitizer.get(tool_name)
                if spec:
                    return spec
        return None

    def _has_prior_tool_outputs(self, request_json: Dict[str, Any]) -> bool:
        def visit(item: Any) -> bool:
            if isinstance(item, list):
                return any(visit(child) for child in item)
            if not isinstance(item, dict):
                return False
            if item.get("role") == "tool" or item.get("type") == "function_call_output":
                return True
            return any(visit(value) for key, value in item.items() if key not in {"id", "call_id", "name"})

        return any(
            visit(candidate)
            for candidate in (
                request_json.get("messages"),
                request_json.get("input"),
            )
        )

    def _observable_request_predicates(self, request_json: Dict[str, Any]) -> set[str]:
        predicates: set[str] = set()
        tool_names = set(self._tool_schema_map(request_json).keys())
        if tool_names:
            predicates.add("tools_available")
        lowered_tool_names = {name.lower() for name in tool_names}
        if any("memory" in name for name in lowered_tool_names):
            predicates.add("memory_tools_available")
        if self._collect_context_literals(request_json):
            predicates.add("prior_explicit_literals_present")
        if self._has_prior_tool_outputs(request_json):
            predicates.add("prior_tool_outputs_present")
        else:
            predicates.add("no_prior_tool_outputs_present")
        return predicates

    def _request_predicates_met(self, predicates: List[str], request_json: Dict[str, Any] | None) -> bool:
        if not predicates:
            return True
        if request_json is None:
            return False
        return set(predicates).issubset(self._observable_request_predicates(request_json))

    @staticmethod
    def _rule_request_predicates(rule: Rule) -> List[str]:
        policy = getattr(rule.action, "decision_policy", None)
        policy_predicates = list(getattr(policy, "request_predicates", []) or [])
        if policy_predicates:
            return policy_predicates
        return list(rule.trigger.request_predicates)

    @staticmethod
    def _rule_contract(rule: Rule) -> VerificationContract:
        contract = copy.deepcopy(rule.validation_contract or rule.action.verification)
        policy = RuleEngine._rule_decision_policy(rule)
        if policy is None:
            return contract
        forbidden = list(getattr(policy, "forbidden_terminations", []) or [])
        evidence = list(getattr(policy, "evidence_requirements", []) or [])
        if forbidden:
            contract.forbidden_terminations = forbidden
        if evidence:
            contract.evidence_requirements = evidence
        return contract

    @staticmethod
    def _rule_decision_policy(rule: Rule) -> DecisionPolicySpec | None:
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
                bool(getattr(policy, "action_candidates", []) or []),
                bool(getattr(getattr(policy, "next_tool_policy", None), "recommended_tools", []) or []),
                bool(getattr(getattr(policy, "next_tool_policy", None), "activation_predicates", []) or []),
            ]
        ):
            return policy
        return None

    def _is_policy_rule(self, rule: Rule) -> bool:
        return is_policy_rule(rule)

    def _matched_rules(
        self,
        tool_name: str | None = None,
        issue_kind: str | None = None,
        request_json: Dict[str, Any] | None = None,
    ) -> List[Rule]:
        matched: List[Rule] = []
        for rule in self.rules:
            names = rule.trigger.tool_names
            if not self._request_predicates_met(self._rule_request_predicates(rule), request_json):
                continue
            if tool_name is None and not names:
                if issue_kind and rule.trigger.error_types and issue_kind not in rule.trigger.error_types:
                    continue
                matched.append(rule)
            elif tool_name is not None and names and tool_name in names:
                if issue_kind and rule.trigger.error_types and issue_kind not in rule.trigger.error_types:
                    continue
                matched.append(rule)
        return matched

    def _matched_global_rules(
        self,
        issue_kind: str | None = None,
        request_json: Dict[str, Any] | None = None,
    ) -> List[Rule]:
        matched: List[Rule] = []
        for rule in self.rules:
            if rule.trigger.tool_names:
                continue
            if issue_kind and rule.trigger.error_types and issue_kind not in rule.trigger.error_types:
                continue
            if not self._request_predicates_met(self._rule_request_predicates(rule), request_json):
                continue
            matched.append(rule)
        return matched

    def _matched_policy_rules(
        self,
        issue_kind: str | None = None,
        request_json: Dict[str, Any] | None = None,
    ) -> List[Rule]:
        return partition_matching_rules(
            self._matched_global_rules(issue_kind=issue_kind, request_json=request_json)
        )[0]

    def _matched_compatibility_rules(
        self,
        issue_kind: str | None = None,
        request_json: Dict[str, Any] | None = None,
    ) -> List[Rule]:
        return partition_matching_rules(
            self._matched_global_rules(issue_kind=issue_kind, request_json=request_json)
        )[1]

    def _rule_prompt_fragments(self, rule: Rule) -> List[str]:
        injected = list(rule.action.prompt_injection.fragments)
        if injected:
            return injected
        return list(rule.action.prompt_fragments)

    def _collect_context_literals(self, request_json: Dict[str, Any]) -> List[str]:
        values: List[str] = []
        ignored_literals = {
            "current_working_directory",
            "current_directory_content",
            "matches",
            "result",
            "message",
            "messages",
            "error",
            "errors",
            "status",
            "sent_status",
            "added_status",
            "login_status",
            "user_id",
            "message_id",
            "new_id",
        }

        def looks_like_literal(value: str) -> bool:
            cleaned = value.strip()
            if not cleaned or len(cleaned) > 80:
                return False
            if "\n" in cleaned:
                return False
            if self._PATH_TOKEN_RE.fullmatch(cleaned) or self._FILE_TOKEN_RE.fullmatch(cleaned):
                return True
            if any(punct in cleaned for punct in ["!", "?", ";"]):
                return False
            if cleaned.count(",") > 0:
                return False
            tokens = [token for token in re.split(r"\s+", cleaned) if token]
            if not tokens or len(tokens) > 6:
                return False
            return all(re.fullmatch(r"[A-Za-z0-9_./:#-]+", token) for token in tokens)

        def add_value(value: str) -> None:
            cleaned = str(value).strip()
            if not looks_like_literal(cleaned):
                return
            if cleaned.lower() in ignored_literals:
                return
            if cleaned not in values:
                values.append(cleaned)

        def visit_jsonlike(value: Any) -> None:
            if isinstance(value, dict):
                for item in value.values():
                    visit_jsonlike(item)
            elif isinstance(value, list):
                for item in value:
                    visit_jsonlike(item)
            elif isinstance(value, str):
                add_value(value)

        for message in request_json.get("messages", [])[-12:]:
            if not isinstance(message, dict):
                continue
            if message.get("role") in {"system", "developer"}:
                continue
            content = message.get("content")
            if isinstance(content, str):
                try:
                    parsed = json.loads(content)
                except Exception:
                    parsed = None
                if parsed is not None:
                    visit_jsonlike(parsed)
                    continue
                for match in self._QUOTED_LITERAL_RE.finditer(content):
                    add_value(match.group(1) or match.group(2) or "")
                for token in self._PATH_TOKEN_RE.findall(content):
                    add_value(token)
                for token in self._FILE_TOKEN_RE.findall(content):
                    add_value(token)
        return values[:12]

    def _conversation_items(self, request_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        for key in ("messages", "input"):
            items = request_json.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    def _last_observed_role(self, request_json: Dict[str, Any]) -> str | None:
        for item in reversed(self._conversation_items(request_json)):
            role = item.get("role")
            if isinstance(role, str) and role:
                return role
            if item.get("type") == "function_call_output":
                return "tool"
        return None

    @staticmethod
    def _detect_no_tool_response_shape(
        message: Dict[str, Any],
        choice: Dict[str, Any],
        response_json: Dict[str, Any],
    ) -> str | None:
        if message.get("tool_calls"):
            return None
        content = message.get("content")
        finish_reason = choice.get("finish_reason")
        usage = response_json.get("usage", {})
        completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
        if content is None and completion_tokens == 0 and finish_reason in {None, "stop"}:
            return "empty_completion"
        if isinstance(content, str) and not content.strip():
            return "blank_no_tool_response"
        return None

    def _structured_tool_guidance_fragments(self, request_json: Dict[str, Any]) -> List[str]:
        if not request_json.get("tools") or not self.inject_structured_tool_guidance:
            return []

        fragments = [
            "For tool-enabled turns, emit the next tool call instead of explanatory prose whenever the next action is already supported by the available tools.",
            "Do not ask for values that are already explicit in prior user turns, tool outputs, or the current working state.",
            "Before using path-sensitive tools, ground the current working directory and existing file or directory names from prior tool outputs instead of assuming the root directory.",
            "When emitting tool calls, keep assistant content empty and avoid adding a free-form status summary in the same message.",
        ]

        if self.inject_context_literal_hints:
            literals = self._collect_context_literals(request_json)
            if literals:
                fragments.append(
                    "Known explicit context values you can reuse exactly if relevant: "
                    + ", ".join(literals[:8])
                )
        return fragments

    def _policy_recommended_tools(self, policy: DecisionPolicySpec) -> List[str]:
        recommended = list(getattr(policy, "recommended_tools", []) or [])
        for candidate in getattr(policy, "action_candidates", []) or []:
            if not isinstance(candidate, dict):
                continue
            for tool_name in candidate.get("recommended_tools") or [candidate.get("tool")]:
                if tool_name and tool_name not in recommended:
                    recommended.append(str(tool_name))
        next_tool_policy = getattr(policy, "next_tool_policy", None)
        for tool_name in getattr(next_tool_policy, "recommended_tools", []) or []:
            if tool_name not in recommended:
                recommended.append(tool_name)
        return recommended

    @staticmethod
    def _policy_action_candidates(policy: DecisionPolicySpec, selected_tool: str | None = None) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        for raw in getattr(policy, "action_candidates", []) or []:
            if not isinstance(raw, dict):
                continue
            tool_name = str(raw.get("tool") or "").strip()
            if not tool_name:
                recommended = raw.get("recommended_tools") or []
                tool_name = str(recommended[0]).strip() if recommended else ""
            if selected_tool and tool_name != selected_tool:
                continue
            candidate = dict(raw)
            if tool_name:
                candidate["tool"] = tool_name
            candidates.append(candidate)
        return candidates

    @staticmethod
    def _candidate_string_values(value: Any) -> List[str]:
        values: List[str] = []
        if isinstance(value, dict):
            for item in value.values():
                values.extend(RuleEngine._candidate_string_values(item))
        elif isinstance(value, list):
            for item in value:
                values.extend(RuleEngine._candidate_string_values(item))
        elif isinstance(value, str) and value.strip():
            values.append(value.strip())
        return values

    @staticmethod
    def _candidate_binding_values(candidate: Dict[str, Any]) -> List[str]:
        values = RuleEngine._candidate_string_values(candidate.get("args") or {})
        bindings = candidate.get("arg_bindings") or {}
        if isinstance(bindings, dict):
            for binding in bindings.values():
                if not isinstance(binding, dict):
                    continue
                value = binding.get("value")
                if isinstance(value, str) and value.strip():
                    values.append(value.strip())
        return values

    @staticmethod
    def _candidate_prior_output_keys(candidate: Dict[str, Any]) -> set[str]:
        keys: set[str] = set()

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                prior_keys = value.get("prior_output_keys")
                if isinstance(prior_keys, list):
                    keys.update(str(item) for item in prior_keys if str(item).strip())
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        visit(candidate.get("evidence") or {})
        bindings = candidate.get("arg_bindings") or {}
        if isinstance(bindings, dict):
            for binding in bindings.values():
                if isinstance(binding, dict):
                    visit(binding.get("evidence") or {})
        for source in RuleEngine._candidate_binding_sources(candidate):
            if source.startswith("prior_tool_output."):
                suffix = source[len("prior_tool_output.") :]
                key = suffix.split("[", 1)[0].split(".", 1)[0].split("|", 1)[0]
                if key == "cwd_or_listing":
                    keys.update({"current_working_directory", "current_directory_content"})
                elif key:
                    keys.add(key)
        return keys

    @staticmethod
    def _candidate_binding_sources(candidate: Dict[str, Any]) -> set[str]:
        sources: set[str] = set()
        binding_source = candidate.get("binding_source")
        if isinstance(binding_source, str) and binding_source.strip():
            sources.add(binding_source.strip())
        bindings = candidate.get("arg_bindings") or {}
        if isinstance(bindings, dict):
            for binding in bindings.values():
                if not isinstance(binding, dict):
                    continue
                source = binding.get("source")
                if isinstance(source, str) and source.strip():
                    sources.add(source.strip())
        return sources

    @staticmethod
    def _candidate_postcondition(candidate: Dict[str, Any]) -> Dict[str, Any]:
        postcondition = candidate.get("postcondition")
        if isinstance(postcondition, dict) and postcondition:
            return postcondition
        tool = str(candidate.get("tool") or "")
        args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
        target_arg = next(iter(args.keys()), "") if args else ""
        inferred = {
            "cat": ("file_content", "file_content"),
            "touch": ("file_exists", "current_directory_content"),
            "mkdir": ("directory_exists", "current_directory_content"),
            "grep": ("matches", "matches"),
            "find": ("matches", "matches"),
            "cp": ("target_path_changed", "current_directory_content"),
            "mv": ("target_path_changed", "current_directory_content"),
            "move_file": ("target_path_changed", "current_directory_content"),
            "copy_file": ("target_path_changed", "current_directory_content"),
            "echo": ("content_written", "file_content"),
            "diff": ("comparison_result", "diff"),
            "cd": ("current_directory_changed", "current_working_directory"),
        }.get(tool)
        if not inferred:
            return {}
        kind, expected_key = inferred
        return {"kind": kind, "expected_state_key": expected_key, "target_arg": target_arg, "confidence": 0.5, "inferred_from_legacy_candidate": True}

    @staticmethod
    def _candidate_declared_risk_flags(candidate: Dict[str, Any]) -> list[str]:
        flags = candidate.get("trajectory_risk_flags")
        if isinstance(flags, list):
            return [str(item) for item in flags if str(item).strip()]
        return []

    def _candidate_trajectory_risk_score(self, candidate: Dict[str, Any]) -> int:
        raw = candidate.get("trajectory_risk_score")
        try:
            score = int(raw)
        except (TypeError, ValueError):
            score = 0
        if not self._candidate_postcondition(candidate):
            score = max(score, 8)
        return score

    @staticmethod
    def _candidate_intervention_mode(candidate: Dict[str, Any]) -> str:
        mode = str(candidate.get("intervention_mode") or "").strip()
        return mode if mode in {"record_only", "weak_guidance", "guidance"} else "record_only"

    @staticmethod
    def _jsonlike_keys(value: Any) -> set[str]:
        keys: set[str] = set()
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(key, str) and key:
                    keys.add(key)
                keys.update(RuleEngine._jsonlike_keys(item))
        elif isinstance(value, list):
            for item in value:
                keys.update(RuleEngine._jsonlike_keys(item))
        elif isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception:
                parsed = None
            if parsed is not None:
                keys.update(RuleEngine._jsonlike_keys(parsed))
        return keys

    def _prior_tool_output_keys(self, request_json: Dict[str, Any]) -> set[str]:
        keys: set[str] = set()
        for item in self._conversation_items(request_json):
            if item.get("role") == "tool":
                keys.update(self._jsonlike_keys(item.get("content")))
            if item.get("type") == "function_call_output":
                keys.update(self._jsonlike_keys(item.get("output")))
        return keys

    def _last_prior_tool_name(self, request_json: Dict[str, Any]) -> str | None:
        for item in reversed(self._conversation_items(request_json)):
            if item.get("type") == "function_call":
                name = item.get("name")
                if isinstance(name, str) and name:
                    return name
            tool_calls = item.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls:
                for call in reversed(tool_calls):
                    if not isinstance(call, dict):
                        continue
                    fn = call.get("function") if isinstance(call.get("function"), dict) else {}
                    name = fn.get("name")
                    if isinstance(name, str) and name:
                        return name
        return None

    def _request_text_for_ranking(self, request_json: Dict[str, Any]) -> str:
        items = [
            item
            for item in self._conversation_items(request_json)
            if item.get("role") not in {"system", "developer"}
        ]
        return json.dumps(items[-12:], ensure_ascii=False).lower()

    def _request_intent_text_for_ranking(self, request_json: Dict[str, Any]) -> str:
        values: List[str] = []
        for item in self._conversation_items(request_json):
            if item.get("role") != "user":
                continue
            content = item.get("content")
            if isinstance(content, str):
                values.append(content)
            elif content is not None:
                try:
                    values.append(json.dumps(content, ensure_ascii=False))
                except Exception:
                    values.append(str(content))
        return "\n".join(values[-4:]).lower()

    @staticmethod
    def _request_intent_hits(request_text: str) -> Dict[str, int]:
        aliases = {
            "cat": ("read", "show", "display", "open", "view", "print contents", "show contents"),
            "grep": ("grep", "search", "match", "matches", "contains", "matching lines"),
            "find": ("find", "locate", "search for", "look for"),
            "mkdir": ("make directory", "make a directory", "create directory", "create a directory", "new directory", "new folder", "make folder", "create folder"),
            "touch": ("create file", "new file", "touch", "empty file"),
            "mv": ("move", "rename"),
            "cp": ("copy", "duplicate"),
            "diff": ("compare", "identical", "difference", "diff"),
            "echo": ("write", "put", "putting", "append", "replace", "insert", "modify", "update", "change"),
            "ls": ("list", "show files"),
            "tail": ("last lines", "tail"),
            "sort": ("sort", "ordered"),
        }
        return {tool: sum(1 for alias in values if alias in request_text) for tool, values in aliases.items()}

    def _tool_intent_score(self, tool_name: str, request_text: str) -> int:
        hits = self._request_intent_hits(request_text)
        score = hits.get(tool_name, 0)
        if tool_name == "cat":
            competing = sum(hits.get(tool, 0) for tool in ("mkdir", "touch", "mv", "cp", "grep", "find", "echo"))
            if competing:
                score -= min(4, competing)
        elif score:
            score += 2
        return score

    @staticmethod
    def _request_pending_goal_family(request_text: str) -> str:
        lowered = request_text.lower()
        if any(token in lowered for token in ("post", "send", "submit", "ticket", "email")):
            return "submit_or_send"
        if any(token in lowered for token in ("cd", "change directory", "go to", "navigate", "enter directory", "switch directory")) and any(token in lowered for token in ("directory", "folder", "dir", "cd")):
            return "directory_navigation"
        if any(token in lowered for token in ("move", "copy", "rename", "duplicate")):
            return "move_or_copy"
        if "compare" in lowered or "diff" in lowered:
            return "compare"
        if any(token in lowered for token in ("write", "modify", "replace", "update", "append", "put", "edit")):
            return "write_content"
        if any(token in lowered for token in ("create", "make", "add", "touch", "new file", "new directory", "new folder")):
            if any(token in lowered for token in ("directory", "folder", " dir")):
                return "create_directory"
            return "create_file"
        if any(token in lowered for token in ("read", "open", "show", "display", "contents", "content")):
            return "read_content"
        if any(token in lowered for token in ("search", "find", "grep", "locate", "match", "matches")):
            return "search"
        return "unknown"

    @staticmethod
    def _postcondition_goal_family(candidate: Dict[str, Any]) -> str:
        postcondition = RuleEngine._candidate_postcondition(candidate)
        return {
            "file_content": "read_content",
            "file_exists": "create_file",
            "directory_exists": "create_directory",
            "matches": "search",
            "target_path_changed": "move_or_copy",
            "content_written": "write_content",
            "comparison_result": "compare",
            "current_directory_changed": "directory_navigation",
        }.get(str(postcondition.get("kind") or ""), "unknown")

    def _action_candidate_score_components(
        self,
        candidate: Dict[str, Any],
        *,
        request_json: Dict[str, Any],
        request_tool_name_set: set[str],
        recommended: List[str],
        confidence: float,
        index: int,
    ) -> Dict[str, Any]:
        tool_name = str(candidate.get("tool") or "").strip()
        recommended_rank = recommended.index(tool_name) if tool_name in recommended else 999
        components: Dict[str, Any] = {
            "tool": tool_name,
            "schema_available": tool_name in request_tool_name_set,
            "literal_score": 0,
            "arg_binding_score": 0,
            "state_compatibility_score": 0,
            "intent_score": 0,
            "recommended_rank": recommended_rank,
            "confidence": confidence,
            "index": index,
            "prior_output_keys_required": sorted(self._candidate_prior_output_keys(candidate)),
            "prior_output_keys_observed": sorted(self._prior_tool_output_keys(request_json)),
            "binding_sources": sorted(self._candidate_binding_sources(candidate)),
            "postcondition": self._candidate_postcondition(candidate),
            "trajectory_risk_score": self._candidate_trajectory_risk_score(candidate),
            "trajectory_risk_flags": self._candidate_declared_risk_flags(candidate),
            "binding_type": str(candidate.get("binding_type") or "unknown"),
            "intervention_mode": self._candidate_intervention_mode(candidate),
            "score": -1000,
        }
        if tool_name not in request_tool_name_set:
            return components

        request_text = self._request_text_for_ranking(request_json)
        context_literals = [item.lower() for item in self._collect_context_literals(request_json)]
        values = self._candidate_binding_values(candidate)
        literal_score = 0
        for value in values:
            lowered = value.lower().strip()
            if not lowered:
                continue
            basename = lowered.rsplit("/", 1)[-1]
            if self._literal_present_in_text(lowered, request_text):
                literal_score += 10
            elif basename and self._literal_present_in_text(basename, request_text):
                literal_score += 8
            elif lowered in context_literals or basename in context_literals:
                literal_score += 6
            elif not self._looks_like_file_literal(lowered):
                tokens = set(self._normalize_literal_tokens(lowered))
                if tokens and tokens.issubset(set(self._normalize_literal_tokens(request_text))):
                    literal_score += 3
        components["literal_score"] = literal_score

        observed_prior_keys = set(components["prior_output_keys_observed"])
        required_prior_keys = set(components["prior_output_keys_required"])
        binding_sources = set(components["binding_sources"])
        needs_prior_output = bool(required_prior_keys) or any(source.startswith("prior_tool_output") for source in binding_sources)
        if needs_prior_output:
            overlap = required_prior_keys & observed_prior_keys
            if overlap:
                components["state_compatibility_score"] = 8 + min(6, len(overlap))
            else:
                components["state_compatibility_score"] = -18
        elif "explicit_literal" in binding_sources and literal_score > 0:
            components["state_compatibility_score"] = 8

        if binding_sources and literal_score > 0:
            components["arg_binding_score"] = 12 if "explicit_literal" in binding_sources else 8
        elif binding_sources and needs_prior_output and components["state_compatibility_score"] > 0:
            components["arg_binding_score"] = 6
        elif not binding_sources and literal_score > 0:
            components["arg_binding_score"] = 8

        intent_text = self._request_intent_text_for_ranking(request_json)
        request_pending_goal = self._request_pending_goal_family(intent_text)
        postcondition_goal = self._postcondition_goal_family(candidate)
        candidate_pending_goal = str(candidate.get("pending_goal_family") or "unknown")
        if request_pending_goal != "unknown":
            effective_pending_goal = request_pending_goal
            pending_goal_source = "request_text"
        elif candidate_pending_goal != "unknown":
            effective_pending_goal = candidate_pending_goal
            pending_goal_source = "candidate_policy"
        elif postcondition_goal != "unknown":
            effective_pending_goal = postcondition_goal
            pending_goal_source = "candidate_postcondition"
        else:
            effective_pending_goal = "unknown"
            pending_goal_source = "unknown"
        components["request_pending_goal_family"] = request_pending_goal
        components["candidate_pending_goal_family"] = candidate_pending_goal
        components["effective_pending_goal_family"] = effective_pending_goal
        components["pending_goal_source"] = pending_goal_source
        components["postcondition_goal_family"] = postcondition_goal
        components["postcondition_goal_matches_request"] = effective_pending_goal != "unknown" and postcondition_goal == effective_pending_goal
        components["intent_score"] = self._tool_intent_score(tool_name, intent_text)
        if components["postcondition_goal_matches_request"] is False:
            components["intent_score"] = int(components["intent_score"]) - (8 if effective_pending_goal == "unknown" else 18)
        if tool_name == "cat" and effective_pending_goal != "read_content":
            components["intent_score"] = int(components["intent_score"]) - 12
        components["score"] = (
            int(components["arg_binding_score"])
            + int(components["state_compatibility_score"])
            + int(components["literal_score"])
            + int(components["intent_score"])
        )
        return components

    @staticmethod
    def _rank_tuple_from_components(components: Dict[str, Any]) -> tuple[int, int, int, int, float, int, int]:
        if not components.get("schema_available"):
            return (-1000, -1000, -1000, -1000, float(components.get("confidence") or 0.0), -999, -int(components.get("index") or 0))
        recommended_rank = components.get("recommended_rank")
        if recommended_rank is None:
            recommended_rank = 999
        index = components.get("index")
        if index is None:
            index = 0
        return (
            int(components.get("score") or 0),
            int(components.get("arg_binding_score") or 0),
            int(components.get("state_compatibility_score") or 0),
            int(components.get("literal_score") or 0),
            float(components.get("confidence") or 0.0),
            -int(recommended_rank),
            -int(index),
        )

    def _action_candidate_rank(
        self,
        candidate: Dict[str, Any],
        *,
        request_json: Dict[str, Any],
        request_tool_name_set: set[str],
        recommended: List[str],
        confidence: float,
        index: int,
    ) -> tuple[int, int, int, int, float, int, int]:
        return self._rank_tuple_from_components(
            self._action_candidate_score_components(
                candidate,
                request_json=request_json,
                request_tool_name_set=request_tool_name_set,
                recommended=recommended,
                confidence=confidence,
                index=index,
            )
        )

    def _rank_action_candidates(
        self,
        candidates: List[Dict[str, Any]],
        *,
        request_json: Dict[str, Any],
        request_tool_name_set: set[str],
        recommended: List[str],
        confidence: float,
    ) -> List[tuple[tuple[int, int, int, int, float, int, int], Dict[str, Any]]]:
        ranked = [
            (
                self._action_candidate_rank(
                    candidate,
                    request_json=request_json,
                    request_tool_name_set=request_tool_name_set,
                    recommended=recommended,
                    confidence=confidence,
                    index=index,
                ),
                candidate,
            )
            for index, candidate in enumerate(candidates)
        ]
        return sorted(ranked, key=lambda item: item[0], reverse=True)

    def _action_candidate_guard_status(
        self,
        candidate: Dict[str, Any],
        components: Dict[str, Any],
        *,
        request_json: Dict[str, Any],
    ) -> Dict[str, Any]:
        tool_name = str(candidate.get("tool") or "").strip()
        binding_sources = set(components.get("binding_sources") or [])
        arg_score = int(components.get("arg_binding_score") or 0)
        literal_score = int(components.get("literal_score") or 0)
        state_score = int(components.get("state_compatibility_score") or 0)
        intent_score = int(components.get("intent_score") or 0)
        observed_prior_keys = set(components.get("prior_output_keys_observed") or [])
        context_literals = self._collect_context_literals(request_json)
        has_context_file_literal = any(self._looks_like_file_literal(str(item)) for item in context_literals)
        risk_flags: List[str] = list(components.get("trajectory_risk_flags") or [])
        trajectory_risk_score = int(components.get("trajectory_risk_score") or 0)
        intervention_mode = str(components.get("intervention_mode") or "record_only")
        postcondition = components.get("postcondition") if isinstance(components.get("postcondition"), dict) else {}
        if not components.get("schema_available"):
            return {"accepted": False, "reason": "schema_unavailable", "risk_flags": ["schema_unavailable"], "trajectory_risk_score": trajectory_risk_score, "intervention_mode": intervention_mode}
        if not postcondition:
            risk_flags.append("postcondition_missing")
            trajectory_risk_score = max(trajectory_risk_score, 8)
        if trajectory_risk_score >= self._DEFAULT_HIGH_TRAJECTORY_RISK_THRESHOLD:
            risk_flags.append("high_trajectory_risk")
        if intervention_mode != "guidance":
            risk_flags.append(f"intervention_mode_{intervention_mode}")
        if components.get("effective_pending_goal_family") == "unknown":
            risk_flags.append("unknown_pending_goal_for_guidance")
        if components.get("postcondition_goal_matches_request") is False:
            risk_flags.append("pending_goal_postcondition_request_mismatch")
        if tool_name == "cat" and components.get("effective_pending_goal_family") != "read_content":
            risk_flags.append("cat_request_goal_mismatch")
        if (
            tool_name == "cat"
            and components.get("request_pending_goal_family") != "read_content"
            and components.get("pending_goal_source") != "request_text"
            and literal_score <= 0
        ):
            risk_flags.append("cat_without_request_read_goal")
        generic_tools = {"cat", "touch", "mkdir"}
        needs_prior_output = any(source.startswith("prior_tool_output") for source in binding_sources) or bool(components.get("prior_output_keys_required"))
        if any(source.startswith("explicit_literal") for source in binding_sources) and literal_score <= 0:
            risk_flags.append("explicit_literal_not_in_current_state")
        if tool_name in generic_tools and arg_score < 8:
            risk_flags.append("weak_arg_binding_evidence")
        if needs_prior_output and state_score <= 0:
            risk_flags.append("prior_output_state_unavailable")
        if "prior_tool_output.cwd_or_listing" in binding_sources and literal_score <= 0:
            risk_flags.append("weak_cwd_or_listing_binding")
        if tool_name == "cat" and (intent_score < 0 or (intent_score <= 0 and "explicit_literal" in binding_sources)):
            risk_flags.append("cat_competing_intent")
        write_path_tools = {"mkdir", "touch"}
        if tool_name in write_path_tools and "explicit_literal" in binding_sources and intent_score <= 0:
            risk_flags.append("write_intent_unconfirmed")
        last_prior_tool = self._last_prior_tool_name(request_json)
        if tool_name in generic_tools and last_prior_tool == tool_name and binding_sources:
            risk_flags.append("repeat_same_tool_without_new_evidence")
        if tool_name in generic_tools and last_prior_tool in {"echo", "touch", "mkdir", "mv", "cp", "rm"} and "explicit_literal" in binding_sources:
            risk_flags.append("post_write_tool_intervention")
        if tool_name == "cat" and last_prior_tool in {"grep", "find"} and "explicit_literal" in binding_sources:
            risk_flags.append("post_search_literal_cat_intervention")
        if not self._candidate_required_pair_complete(candidate):
            risk_flags.append("required_arg_pair_incomplete")
        early_clean_cwd_listing = (
            tool_name in {"touch", "mkdir"}
            and "prior_tool_output.cwd_or_listing" in binding_sources
            and state_score >= 9
            and arg_score >= 6
            and "current_directory_content" in observed_prior_keys
            and observed_prior_keys.issubset({"current_directory_content", "current_working_directory"})
            and not (tool_name == "touch" and has_context_file_literal)
        )
        if early_clean_cwd_listing:
            risk_flags = [
                flag
                for flag in risk_flags
                if flag not in {"high_trajectory_risk", "intervention_mode_weak_guidance", "weak_cwd_or_listing_binding"}
            ]
            trajectory_risk_score = min(trajectory_risk_score, self._DEFAULT_HIGH_TRAJECTORY_RISK_THRESHOLD - 1)
            intervention_mode = "guidance"
        blocking_trajectory_flags = {
            "postcondition_missing",
            "high_trajectory_risk",
            "intervention_mode_record_only",
            "intervention_mode_weak_guidance",
            "explicit_literal_not_in_current_state",
            "unknown_pending_goal_for_guidance",
            "pending_goal_postcondition_request_mismatch",
            "cat_request_goal_mismatch",
            "cat_without_request_read_goal",
            "required_arg_pair_incomplete",
        }
        if any(flag in risk_flags for flag in blocking_trajectory_flags):
            return {
                "accepted": False,
                "reason": next(flag for flag in risk_flags if flag in blocking_trajectory_flags),
                "risk_flags": risk_flags,
                "trajectory_risk_score": trajectory_risk_score,
                "intervention_mode": intervention_mode,
            }
        match_keys = {"matches", "file_content"}
        strong_prior_match = (
            tool_name == "cat"
            and "prior_tool_output.matches[0]|basename" in binding_sources
            and state_score >= 9
            and arg_score >= 6
            and intent_score >= -1
            and bool(observed_prior_keys & match_keys)
        )
        clean_cwd_listing = (
            tool_name in {"touch", "mkdir"}
            and "prior_tool_output.cwd_or_listing" in binding_sources
            and state_score >= 9
            and arg_score >= 6
            and "current_directory_content" in observed_prior_keys
            and observed_prior_keys.issubset({"current_directory_content", "current_working_directory"})
            and not (tool_name == "touch" and has_context_file_literal)
        )
        strong_explicit = "explicit_literal" in binding_sources and arg_score >= 12 and literal_score > 0
        strong_prior = needs_prior_output and state_score >= 8 and arg_score >= 8 and literal_score > 0
        strong_literal_arg = not binding_sources and arg_score >= 8 and literal_score > 0
        if strong_explicit and not (tool_name == "cat" and "cat_competing_intent" in risk_flags) and "write_intent_unconfirmed" not in risk_flags and "repeat_same_tool_without_new_evidence" not in risk_flags and "post_write_tool_intervention" not in risk_flags and "post_search_literal_cat_intervention" not in risk_flags:
            return {"accepted": True, "reason": "strong_explicit_literal_binding", "risk_flags": risk_flags, "trajectory_risk_score": trajectory_risk_score, "intervention_mode": intervention_mode}
        if strong_prior and "weak_cwd_or_listing_binding" not in risk_flags:
            return {"accepted": True, "reason": "strong_prior_output_binding", "risk_flags": risk_flags, "trajectory_risk_score": trajectory_risk_score, "intervention_mode": intervention_mode}
        if strong_prior_match and "cat_competing_intent" not in risk_flags and "repeat_same_tool_without_new_evidence" not in risk_flags:
            return {"accepted": True, "reason": "strong_prior_output_match_binding", "risk_flags": risk_flags, "trajectory_risk_score": trajectory_risk_score, "intervention_mode": intervention_mode}
        if clean_cwd_listing:
            return {"accepted": True, "reason": "clean_cwd_listing_binding", "risk_flags": risk_flags, "trajectory_risk_score": trajectory_risk_score, "intervention_mode": intervention_mode}
        if strong_literal_arg and not (tool_name == "cat" and "cat_competing_intent" in risk_flags) and "write_intent_unconfirmed" not in risk_flags and "repeat_same_tool_without_new_evidence" not in risk_flags and "post_write_tool_intervention" not in risk_flags:
            return {"accepted": True, "reason": "literal_arg_match", "risk_flags": risk_flags, "trajectory_risk_score": trajectory_risk_score, "intervention_mode": intervention_mode}
        nonblocking_diagnostic_flags = {"trajectory_sensitive_tool", "weak_arg_binding_evidence"}
        blocking_residual_flags = [flag for flag in risk_flags if flag not in nonblocking_diagnostic_flags]
        if blocking_residual_flags:
            return {"accepted": False, "reason": blocking_residual_flags[0], "risk_flags": risk_flags, "trajectory_risk_score": trajectory_risk_score, "intervention_mode": intervention_mode}
        return {"accepted": True, "reason": "guard_passed_with_diagnostic_risk" if risk_flags else "guard_passed", "risk_flags": risk_flags, "trajectory_risk_score": trajectory_risk_score, "intervention_mode": intervention_mode}

    def _guarded_action_candidate_selection(
        self,
        candidates: List[Dict[str, Any]],
        *,
        request_json: Dict[str, Any],
        request_tool_name_set: set[str],
        recommended: List[str],
        confidence: float,
    ) -> tuple[tuple[tuple[int, int, int, int, float, int, int], Dict[str, Any], Dict[str, Any], Dict[str, Any]] | None, list[dict[str, Any]]]:
        rows: list[tuple[tuple[int, int, int, int, float, int, int], Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = []
        rejected: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidates):
            candidate = self._apply_scorer_feedback_to_candidate(candidate)
            components = self._action_candidate_score_components(
                candidate,
                request_json=request_json,
                request_tool_name_set=request_tool_name_set,
                recommended=recommended,
                confidence=confidence,
                index=index,
            )
            rank = self._rank_tuple_from_components(components)
            guard = self._action_candidate_guard_status(candidate, components, request_json=request_json)
            rows.append((rank, candidate, components, guard))
        rows.sort(key=lambda item: item[0], reverse=True)
        for rank, candidate, components, guard in rows:
            if guard.get("accepted"):
                return (rank, candidate, components, guard), rejected
            rejected.append(
                {
                    "tool": candidate.get("tool"),
                    "args": candidate.get("args") or {},
                    "rank_tuple": list(rank),
                    "guard": guard,
                    "candidate_rank_scores": components,
                    "scorer_feedback_pattern_matched": bool(candidate.get("scorer_feedback_pattern_matched")),
                    "matched_regression_guard_key": candidate.get("matched_regression_guard_key"),
                    "scorer_feedback_pattern_action": candidate.get("scorer_feedback_pattern_action"),
                    "scorer_feedback_action": candidate.get("scorer_feedback_action"),
                    "scorer_feedback_reason": candidate.get("scorer_feedback_reason"),
                    "scorer_feedback_fallback_guard_matched": bool(candidate.get("scorer_feedback_fallback_guard_matched")),
                    "matched_fallback_guard_key": candidate.get("matched_fallback_guard_key"),
                    "scorer_feedback_fallback_action": candidate.get("scorer_feedback_fallback_action"),
                    "fallback_selection_class": candidate.get("fallback_selection_class"),
                    "fallback_selection_action": candidate.get("fallback_selection_action"),
                    "fallback_selection_reason": candidate.get("fallback_selection_reason"),
                    "fallback_selection_risk_score": candidate.get("fallback_selection_risk_score"),
                }
            )
        return None, rejected

    def _next_tool_activation_predicates(self, rule: Rule, policy: DecisionPolicySpec) -> List[str]:
        next_tool_policy = getattr(policy, "next_tool_policy", None)
        configured = list(getattr(next_tool_policy, "activation_predicates", []) or [])
        if configured:
            return configured
        predicates = list(self._rule_request_predicates(rule))
        error_types = set(rule.trigger.error_types or [])
        if "actionable_no_tool_decision" in error_types and "prior_explicit_literals_present" not in predicates:
            predicates.append("prior_explicit_literals_present")
        if "post_tool_prose_summary" in error_types and "prior_tool_outputs_present" not in predicates:
            predicates.append("prior_tool_outputs_present")
        return predicates

    def _next_tool_policy_plan(self, request_json: Dict[str, Any]) -> Dict[str, Any]:
        request_tool_names = sorted(self._tool_schema_map(request_json).keys())
        request_tool_name_set = set(request_tool_names)
        observed_predicates = self._observable_request_predicates(request_json)
        plan: Dict[str, Any] = {
            "attempted": True,
            "exact_next_tool_choice_mode": self.exact_next_tool_choice_mode,
            "activated": False,
            "blocked_reason": None,
            "available_tools": request_tool_names,
            "candidate_recommended_tools": [],
            "matched_recommended_tools": [],
            "recommended_tools": [],
            "selected_tool": None,
            "tool_choice_mode": "soft",
            "policy_hits": [],
            "activation_predicates": [],
            "activation_predicate_status": {},
            "action_candidates": [],
            "selected_action_candidate": None,
            "action_candidate_guard": None,
            "rejected_action_candidates": [],
            "confidence": 0.0,
        }
        blocked_priority = {
            "no_policy_candidate": 1,
            "request_predicates_unmet": 2,
            "activation_predicates_unmet": 3,
            "recommended_tools_empty": 4,
            "recommended_tools_not_in_schema": 5,
            "action_candidate_guard_rejected": 6,
            "activated": 99,
        }
        blocked_reason = "no_policy_candidate"
        blocked_rank = blocked_priority[blocked_reason]
        best_selection: tuple[tuple[int, int, int, int, float, int, int], Dict[str, Any], Dict[str, Any], Dict[str, Any]] | None = None
        fallback_selected_tool: str | None = None

        def mark_blocked(reason: str) -> None:
            nonlocal blocked_reason, blocked_rank
            rank = blocked_priority.get(reason, 0)
            if rank >= blocked_rank:
                blocked_reason = reason
                blocked_rank = rank

        def record_predicates(predicates: List[str]) -> None:
            for predicate in predicates:
                plan["activation_predicate_status"][predicate] = predicate in observed_predicates

        def add_unique(field: str, values: List[str]) -> None:
            for value in values:
                if value and value not in plan[field]:
                    plan[field].append(value)

        if not request_tool_names:
            plan["blocked_reason"] = "no_tools_available"
            return plan
        for rule in self.rules:
            patch_sites = set(rule.scope.patch_sites)
            if patch_sites and "policy_executor" not in patch_sites and "prompt_injector" not in patch_sites:
                continue
            policy = self._rule_decision_policy(rule)
            if policy is None:
                continue
            raw_recommended = self._policy_recommended_tools(policy)
            add_unique("candidate_recommended_tools", raw_recommended)
            rule_predicates = self._rule_request_predicates(rule)
            record_predicates(rule_predicates)
            if not set(rule_predicates).issubset(observed_predicates):
                mark_blocked("request_predicates_unmet")
                continue
            activation_predicates = self._next_tool_activation_predicates(rule, policy)
            record_predicates(activation_predicates)
            if not set(activation_predicates).issubset(observed_predicates):
                mark_blocked("activation_predicates_unmet")
                continue
            if not raw_recommended:
                mark_blocked("recommended_tools_empty")
                continue
            recommended = [tool_name for tool_name in raw_recommended if tool_name in request_tool_name_set]
            if not recommended:
                mark_blocked("recommended_tools_not_in_schema")
                continue
            next_tool_policy = getattr(policy, "next_tool_policy", None)
            mode = str(getattr(next_tool_policy, "tool_choice_mode", None) or "soft")
            confidence = float(getattr(next_tool_policy, "confidence", 0.0) or 0.0)
            action_candidates = self._policy_action_candidates(policy)
            ranked_candidates = self._rank_action_candidates(
                action_candidates,
                request_json=request_json,
                request_tool_name_set=request_tool_name_set,
                recommended=recommended,
                confidence=confidence,
            )
            for _, candidate in ranked_candidates:
                if candidate not in plan["action_candidates"]:
                    plan["action_candidates"].append(candidate)
            guarded_selection = None
            rejected: list[dict[str, Any]] = []
            if action_candidates:
                guarded_selection, rejected = self._guarded_action_candidate_selection(
                    action_candidates,
                    request_json=request_json,
                    request_tool_name_set=request_tool_name_set,
                    recommended=recommended,
                    confidence=confidence,
                )
                plan["rejected_action_candidates"].extend(rejected)
                if guarded_selection is None:
                    mark_blocked("action_candidate_guard_rejected")
                    continue
            plan["activated"] = True
            plan["blocked_reason"] = "activated"
            fallback_selected_tool = fallback_selected_tool or recommended[0]
            plan["tool_choice_mode"] = "required" if mode == "required" else "soft"
            plan["confidence"] = max(float(plan["confidence"]), confidence)
            plan["activation_predicates"] = list(dict.fromkeys(plan["activation_predicates"] + activation_predicates))
            plan["policy_hits"].append(rule.rule_id)
            add_unique("matched_recommended_tools", recommended)
            add_unique("recommended_tools", recommended)
            if guarded_selection is not None and (best_selection is None or guarded_selection[0] > best_selection[0]):
                best_selection = guarded_selection
        if best_selection is not None:
            plan["selected_action_candidate"] = best_selection[1]
            plan["action_candidate_guard"] = best_selection[3]
            plan["selected_tool"] = str(best_selection[1].get("tool") or "") or fallback_selected_tool
        elif fallback_selected_tool:
            plan["selected_tool"] = fallback_selected_tool
        plan["recommended_tools"] = plan["recommended_tools"][:3]
        plan["matched_recommended_tools"] = plan["matched_recommended_tools"][:3]
        plan["candidate_recommended_tools"] = plan["candidate_recommended_tools"][:5]
        plan["action_candidates"] = plan["action_candidates"][:5]
        if not plan["activated"]:
            plan["blocked_reason"] = blocked_reason
        return plan

    def _recommended_policy_tools(self, request_json: Dict[str, Any]) -> List[str]:
        return list(self._next_tool_policy_plan(request_json).get("recommended_tools") or [])

    @staticmethod
    def _action_candidate_guidance_sources(candidate: Dict[str, Any]) -> List[str]:
        sources: set[str] = set()
        source = candidate.get("binding_source")
        if isinstance(source, str) and source.strip():
            sources.add(source.strip())
        bindings = candidate.get("arg_bindings") if isinstance(candidate.get("arg_bindings"), dict) else {}
        for binding in bindings.values():
            if isinstance(binding, dict) and isinstance(binding.get("source"), str) and binding.get("source", "").strip():
                sources.add(str(binding["source"]).strip())
        return sorted(sources)

    @staticmethod
    def _candidate_arg_guidance_json(candidate: Dict[str, Any]) -> str:
        args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
        return json.dumps(args, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _candidate_arg_guidance_schema_text(candidate: Dict[str, Any]) -> str:
        cmap = candidate.get("canonical_arg_map") if isinstance(candidate.get("canonical_arg_map"), dict) else {}
        if not cmap:
            return "canonical args: use the JSON keys exactly as shown"
        parts: list[str] = []
        for key, meta in cmap.items():
            if not isinstance(meta, dict):
                continue
            group = meta.get("alias_group") or "unknown"
            norm = meta.get("normalization_type") or "string_exact"
            parts.append(f"{key}->{group}/{norm}")
        return "canonical args: " + "; ".join(parts) if parts else "canonical args: use the JSON keys exactly as shown"

    def _recommended_policy_tool_fragments(
        self,
        request_json: Dict[str, Any],
        next_tool_plan: Dict[str, Any] | None = None,
    ) -> List[str]:
        plan = next_tool_plan if isinstance(next_tool_plan, dict) else self._next_tool_policy_plan(request_json)
        recommended = list(plan.get("recommended_tools") or [])
        fragments: List[str] = []
        selected_tool = str(plan.get("selected_tool") or "").strip()
        candidate = plan.get("selected_action_candidate") if isinstance(plan.get("selected_action_candidate"), dict) else None
        if (
            self._action_specific_guidance_enabled()
            and plan.get("activated")
            and selected_tool
            and candidate
            and str(candidate.get("tool") or "").strip() == selected_tool
        ):
            args_text = self._candidate_arg_guidance_json(candidate)
            sources = self._action_candidate_guidance_sources(candidate)
            source_text = ", ".join(sources) if sources else "action_candidate.args"
            fragments.append(
                f"Policy selected next tool: call `{selected_tool}` next. Use this exact argument JSON if you choose the policy tool: {args_text}. "
                f"{self._candidate_arg_guidance_schema_text(candidate)}. "
                f"Do not rename JSON keys or values. binding sources: {source_text}. "
                "Preserve these exact path/file literal values unless the current user explicitly changes them."
            )
        if not recommended:
            return fragments
        if len(recommended) == 1:
            fragments.append(
                f"Policy next-tool recommendation: prefer `{recommended[0]}` as the next tool action when its required arguments are locally grounded; do not end this turn with prose-only narration while the policy predicates still hold."
            )
            return fragments
        fragments.append(
            "Policy next-tool recommendations: prefer one of "
            + ", ".join(f"`{tool}`" for tool in recommended)
            + " as the next tool action when required arguments are locally grounded; do not end this turn with prose-only narration while the policy predicates still hold."
        )
        return fragments

    def _collect_prompt_fragments(self, request_json: Dict[str, Any], next_tool_plan: Dict[str, Any] | None = None) -> List[str]:
        fragments: List[str] = self._structured_tool_guidance_fragments(request_json)
        fragments.extend(self._recommended_policy_tool_fragments(request_json, next_tool_plan=next_tool_plan))
        request_tool_names = set(self._tool_schema_map(request_json).keys())
        allow_global_prompt_injection = bool(self.runtime_policy.get("allow_global_prompt_injection", False))
        for rule in self.rules:
            patch_sites = set(rule.scope.patch_sites)
            if patch_sites and "prompt_injector" not in patch_sites:
                continue
            names = set(rule.trigger.tool_names)
            rule_predicates = self._rule_request_predicates(rule)
            if names and not (names & request_tool_names):
                continue
            # Global rules that are mined from response-side failure classes do not have
            # request-local preconditions today. Injecting them into every request turns
            # post-hoc failure summaries into blanket prompt pollution, which regresses
            # otherwise healthy traces. Keep them opt-in until request-side predicates
            # exist in the IR.
            if not names and not rule_predicates and not allow_global_prompt_injection:
                continue
            if not self._request_predicates_met(rule_predicates, request_json):
                continue
            fragments.extend(self._rule_prompt_fragments(rule))
        # Preserve order while dropping duplicates.
        return list(dict.fromkeys(fragment for fragment in fragments if fragment))

    @staticmethod
    def _is_actionable_continuation_rule(rule: Rule) -> bool:
        if "actionable_no_tool_decision" not in rule.trigger.error_types:
            return False
        contract = rule.validation_contract or rule.action.verification
        return "prose_only_no_tool_termination" in contract.forbidden_terminations

    def _literal_intent(self, field_name: str, field_spec: Dict[str, Any]) -> str:
        lowered = f"{field_name} {field_spec.get('description', '')}".lower()
        if any(token in lowered for token in ["directory", "folder", "dir"]):
            return "directory"
        if any(token in lowered for token in ["file", "path", "filename", "file_name", "source", "destination"]):
            return "file"
        return "generic"

    @staticmethod
    def _looks_like_file_literal(value: str) -> bool:
        return bool(re.search(r"\.[A-Za-z0-9]{1,8}$", value.strip()))

    @staticmethod
    def _literal_present_in_text(literal: str, text: str) -> bool:
        if not literal:
            return False
        pattern = r"(?<![a-z0-9_.-])" + re.escape(literal.lower()) + r"(?![a-z0-9_.-])"
        return re.search(pattern, text.lower()) is not None

    @staticmethod
    def _normalize_literal_tokens(value: str) -> List[str]:
        return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]

    def _pick_context_literal(
        self,
        value: str,
        field_name: str,
        field_spec: Dict[str, Any],
        literals: List[str],
    ) -> str | None:
        if not literals:
            return None

        intent = self._literal_intent(field_name, field_spec)
        if intent == "directory":
            candidates = [item for item in literals if not self._looks_like_file_literal(item)]
        elif intent == "file":
            candidates = [item for item in literals if self._looks_like_file_literal(item)]
        else:
            candidates = list(literals)
        if not candidates:
            candidates = list(literals)

        if self._REFERENCE_VALUE_RE.search(value):
            return candidates[-1]

        value_tokens = set(self._normalize_literal_tokens(value))
        if not value_tokens:
            return None

        best_candidate = None
        best_score = 0.0
        second_best = 0.0
        for candidate in candidates:
            candidate_tokens = set(self._normalize_literal_tokens(candidate))
            if not candidate_tokens:
                continue
            overlap = len(value_tokens & candidate_tokens)
            if overlap == 0:
                continue
            score = overlap / max(len(value_tokens), len(candidate_tokens))
            if score > best_score:
                second_best = best_score
                best_score = score
                best_candidate = candidate
            elif score > second_best:
                second_best = score

        if best_candidate and best_score >= 0.5 and best_score >= second_best + 0.2:
            return best_candidate
        return None

    def _resolve_contextual_string_arguments(
        self,
        args: Dict[str, Any],
        schema: Dict[str, Any],
        request_json: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not self.resolve_contextual_string_args:
            return []

        literals = self._collect_context_literals(request_json)
        if not literals:
            return []

        repairs: List[Dict[str, Any]] = []
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        for field, value in list(args.items()):
            if not isinstance(value, str):
                continue
            resolved = self._pick_context_literal(value, field, properties.get(field, {}), literals)
            if resolved and resolved != value:
                args[field] = resolved
                repairs.append(
                    {
                        "kind": "resolve_contextual_string_arg",
                        "field": field,
                        "from": value,
                        "to": resolved,
                    }
                )
        return repairs

    def apply_request(self, request_json: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        patched = copy.deepcopy(request_json)
        next_tool_plan = self._next_tool_policy_plan(patched)
        fragments = self._collect_prompt_fragments(patched, next_tool_plan=next_tool_plan)
        request_patches = RequestPatchList(next_tool_plan=next_tool_plan)
        policy_request_patches: List[str] = []

        if next_tool_plan.get("activated"):
            selected_tool = next_tool_plan.get("selected_tool")
            recommended_tools = list(next_tool_plan.get("recommended_tools") or [])
            policy_request_patches.append("policy_next_tool:activated")
            if selected_tool:
                policy_request_patches.append(f"policy_next_tool:selected={selected_tool}")
            if recommended_tools:
                policy_request_patches.append("policy_next_tool:recommended=" + ",".join(recommended_tools))
            policy_request_patches.extend(f"policy_hit:{rule_id}" for rule_id in next_tool_plan.get("policy_hits") or [])
            selected_action_candidate = next_tool_plan.get("selected_action_candidate")
            if (
                self._exact_next_tool_choice_allowed(
                    selected_tool=str(selected_tool) if selected_tool else None,
                    selected_action_candidate=selected_action_candidate if isinstance(selected_action_candidate, dict) else None,
                    next_tool_plan=next_tool_plan,
                )
                and "tool_choice" not in patched
            ):
                patched["tool_choice"] = {"type": "function", "function": {"name": str(selected_tool)}}
                policy_request_patches.append(f"tool_choice:function(policy_next_tool)={selected_tool}")
            elif (
                self.exact_next_tool_choice_mode == "exact_tool_when_single_step_confident"
                and selected_tool
                and isinstance(selected_action_candidate, dict)
                and "tool_choice" not in patched
            ):
                policy_request_patches.append(f"tool_choice:function(policy_next_tool):skipped={selected_tool}")
            elif (
                self.enable_required_next_tool_choice
                and next_tool_plan.get("tool_choice_mode") == "required"
                and "tool_choice" not in patched
            ):
                patched["tool_choice"] = "required"
                policy_request_patches.append("tool_choice:required(policy_next_tool)")

        if fragments:
            system_text = "[Golden Rule Compiler]\n" + "\n".join(f"- {fragment}" for fragment in fragments)
            messages = list(patched.get("messages", []))
            if messages and messages[0].get("role") == "system":
                existing = messages[0].get("content", "")
                merged = f"{existing}\n\n{system_text}".strip() if existing else system_text
                messages[0]["content"] = merged
            else:
                messages.insert(0, {"role": "system", "content": system_text})
            patched["messages"] = messages
            request_patches.extend(f"prompt_injector:{fragment}" for fragment in fragments)

        request_patches.extend(policy_request_patches)
        return patched, request_patches

    def _apply_fallback(self, message: Dict[str, Any], tool_calls: List[Dict[str, Any]], index: int, issues: List[ValidationIssue], rule_hits: List[Rule]) -> bool:
        if not issues:
            return False

        issue_kinds = {alias for issue in issues for alias in self._issue_kind_aliases(issue.kind)}
        for rule in rule_hits:
            trigger_error_types = set(rule.trigger.error_types)
            if trigger_error_types and not (trigger_error_types & issue_kinds):
                continue
            strategy = rule.action.fallback_router.strategy
            scoped_issue_kinds = set(rule.action.fallback_router.on_issue_kinds)
            if scoped_issue_kinds and not any(
                self._issue_kind_aliases(issue.kind) & scoped_issue_kinds for issue in issues
            ):
                continue
            if strategy == "drop_tool_call":
                if 0 <= index < len(tool_calls):
                    tool_calls.pop(index)
                    return True
                continue
            if strategy == "assistant_message":
                fallback_message = rule.action.fallback_router.assistant_message or "Tool call removed after validation failure."
                if 0 <= index < len(tool_calls):
                    tool_calls.pop(index)
                    existing = message.get("content") or ""
                    message["content"] = f"{existing}\n{fallback_message}".strip()
                else:
                    message["content"] = fallback_message
                return True
        return False

    @staticmethod
    def _issue_kind_aliases(issue_kind: str) -> set[str]:
        aliases = {issue_kind}
        if issue_kind == "empty_completion":
            aliases.add("empty_tool_call")
        return aliases

    def _has_explicit_no_tool_recovery(self, issue_kind: str, rule_hits: List[Rule]) -> bool:
        issue_aliases = self._issue_kind_aliases(issue_kind)
        for rule in rule_hits:
            if rule.trigger.error_types and not (issue_aliases & set(rule.trigger.error_types)):
                continue
            strategy = rule.action.fallback_router.strategy
            if strategy == "record_only":
                continue
            scoped_issue_kinds = set(rule.action.fallback_router.on_issue_kinds)
            if scoped_issue_kinds and not (issue_aliases & scoped_issue_kinds):
                continue
            return True
        return False

    def _should_attempt_no_tool_recovery(self, issue_kind: str, rule_hits: List[Rule]) -> bool:
        if issue_kind not in self.record_only_no_tool_kinds:
            return True
        return self._has_explicit_no_tool_recovery(issue_kind, rule_hits)

    def _should_coerce_no_tool_text_to_empty(self, issue_kind: str, rule_hits: List[Rule]) -> bool:
        if issue_kind not in self.coerce_no_tool_response_to_empty_kinds:
            return False
        return not self._has_explicit_no_tool_recovery(issue_kind, rule_hits)

    _ARG_ALIAS_GROUPS = (
        {"file_name", "filename", "file", "filepath", "path"},
        {"dir_name", "dirname", "directory", "folder", "dir", "path"},
        {"source", "src", "from", "source_path", "file_name"},
        {"destination", "dest", "target", "to", "target_path", "path"},
        {"pattern", "query", "name", "needle"},
        {"content", "text", "message", "body", "value"},
    )
    _REQUIRED_PAIR_TOOL_FIELDS = {
        "cp": (("source", "src", "from", "file_name"), ("destination", "dest", "target", "to", "path")),
        "mv": (("source", "src", "from", "file_name"), ("destination", "dest", "target", "to", "path")),
        "move_file_pair": (("source", "src", "from", "file_name"), ("destination", "dest", "target", "to", "path")),
        "copy_file_pair": (("source", "src", "from", "file_name"), ("destination", "dest", "target", "to", "path")),
        "diff": (("source", "src", "from", "file_name", "path"), ("destination", "dest", "target", "to", "path")),
    }

    @classmethod
    def _candidate_required_pair_complete(cls, candidate: Dict[str, Any]) -> bool:
        tool = str(candidate.get("tool") or "")
        required = cls._REQUIRED_PAIR_TOOL_FIELDS.get(tool)
        if not required:
            return True
        args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
        arg_keys = {str(key).lower() for key in args}
        for aliases in required:
            if not any(alias in arg_keys for alias in aliases):
                return False
        return True

    @classmethod
    def _canonical_arg_aliases(cls, field: str) -> List[str]:
        field_name = str(field)
        lowered = field_name.lower()
        aliases = [field_name]
        for group in cls._ARG_ALIAS_GROUPS:
            if lowered in group:
                aliases.extend(sorted(group))
        return list(dict.fromkeys(aliases))

    @classmethod
    def _observed_arg_with_alias(cls, observed_args: Dict[str, Any], field: str) -> tuple[str | None, Any]:
        for alias in cls._canonical_arg_aliases(field):
            if alias in observed_args:
                return alias, observed_args.get(alias)
        return None, None

    @classmethod
    def _validate_action_candidate_args(cls, candidate: Dict[str, Any], observed_args: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        bindings = candidate.get("arg_bindings") if isinstance(candidate.get("arg_bindings"), dict) else {}
        expected_args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
        fields = list(dict.fromkeys(list(expected_args.keys()) + list(bindings.keys())))
        validation: Dict[str, Dict[str, Any]] = {}
        for field in fields:
            binding = bindings.get(field) if isinstance(bindings.get(field), dict) else {}
            expected = binding.get("value", expected_args.get(field))
            observed_field, observed = cls._observed_arg_with_alias(observed_args, str(field))
            key_match = observed_field == str(field)
            alias_match = observed_field is not None and observed_field != str(field)
            value_match = observed == expected
            row = {
                "expected": expected,
                "observed": observed,
                "observed_field": observed_field,
                "source": binding.get("source") or candidate.get("binding_source") or "action_candidate.args",
                "match": observed_field is not None and value_match,
                "key_match": key_match,
                "key_mismatch": observed_field is None or observed_field != str(field),
                "alias_match": alias_match and value_match,
                "value_match": value_match,
                "value_mismatch": observed_field is not None and not value_match,
                "required_pair_complete": cls._candidate_required_pair_complete(candidate),
            }
            validation[str(field)] = row
        return validation

    @staticmethod
    def _pathish_basename(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        if not stripped:
            return ""
        return stripped.replace("\\", "/").rstrip("/").split("/")[-1]

    @classmethod
    def _normalized_arg_binding_match(cls, field: str, expected: Any, observed: Any) -> tuple[bool, str]:
        if observed == expected:
            return True, "exact"
        if not isinstance(expected, str) or not isinstance(observed, str):
            return False, "unsupported_non_string"
        field_name = str(field).lower()
        if not any(token in field_name for token in ("file", "path", "dir", "name")):
            return False, "unsupported_field"
        expected_base = cls._pathish_basename(expected)
        observed_base = cls._pathish_basename(observed)
        if expected_base is not None and observed_base is not None and expected_base == observed_base:
            return True, "path_basename"
        return False, "path_basename_mismatch"

    @classmethod
    def _validate_action_candidate_args_normalized(
        cls,
        candidate: Dict[str, Any],
        observed_args: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        strict = cls._validate_action_candidate_args(candidate, observed_args)
        normalized: Dict[str, Dict[str, Any]] = {}
        for field, row in strict.items():
            match, reason = cls._normalized_arg_binding_match(field, row.get("expected"), row.get("observed"))
            normalized[field] = {
                **row,
                "match": match,
                "strict_match": bool(row.get("match")),
                "normalization": reason,
                "path_normalized_match": bool(match and reason == "path_basename"),
            }
        return normalized

    @staticmethod
    def _selected_tool_call_args(tool_calls: List[Dict[str, Any]], selected_tool: str) -> Dict[str, Any] | None:
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            function = call.get("function", {})
            if not isinstance(function, dict) or function.get("name") != selected_tool:
                continue
            raw_args = function.get("arguments", "{}")
            try:
                parsed = parse_loose_json(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                return None
            return parsed if isinstance(parsed, dict) else None
        return None

    def _coerce_no_tool_text_to_empty(self, message: Dict[str, Any], issue_kind: str) -> List[Dict[str, Any]]:
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            return []

        message["content"] = ""
        return [
            {
                "kind": "coerce_no_tool_text_to_empty",
                "issue_kind": issue_kind,
                "reason": "assistant emitted text-only content on a tool-enabled turn; coerced to empty response for structured tool clients",
            }
        ]

    def _tool_guard_action(self, rule_hits: List[Rule], issue_kind: str) -> str:
        if issue_kind in {
            "clarification_request",
            "unsupported_request",
            "hallucinated_completion",
            "malformed_output",
            "post_tool_prose_summary",
        }:
            return "record"
        issue_aliases = self._issue_kind_aliases(issue_kind)
        for rule in rule_hits:
            if rule.trigger.error_types and not (issue_aliases & set(rule.trigger.error_types)):
                continue
            guard = rule.action.tool_guard
            if not guard.enabled:
                continue
            if issue_aliases & {"empty_tool_call"}:
                return guard.on_empty_tool_call
            if issue_kind in {"tool_guard_violation", "wrong_tool_name"}:
                return guard.on_unknown_tool
            return guard.on_violation
        return "record"

    def _apply_tool_guard(self, message: Dict[str, Any], tool_calls: List[Dict[str, Any]], index: int, issues: List[ValidationIssue], rule_hits: List[Rule]) -> bool:
        if not issues:
            return False

        action = self._tool_guard_action(rule_hits, issues[0].kind)
        if action == "drop":
            tool_calls.pop(index)
            return True
        if action == "assistant_message":
            tool_calls.pop(index)
            fallback_message = None
            for rule in rule_hits:
                if rule.action.tool_guard.assistant_message:
                    fallback_message = rule.action.tool_guard.assistant_message
                    break
            existing = message.get("content") or ""
            message["content"] = f"{existing}\n{fallback_message or 'Invalid tool call removed by tool guard.'}".strip()
            return True
        return False

    def _apply_empty_tool_guard(self, message: Dict[str, Any], issues: List[ValidationIssue], rule_hits: List[Rule]) -> bool:
        action = self._tool_guard_action(rule_hits, issues[0].kind) if issues else "record"
        if action == "assistant_message":
            fallback_message = None
            for rule in rule_hits:
                if rule.action.tool_guard.assistant_message:
                    fallback_message = rule.action.tool_guard.assistant_message
                    break
            existing = message.get("content") or ""
            message["content"] = f"{existing}\n{fallback_message or 'No valid tool call was emitted.'}".strip()
            return True
        return False

    def _verification_contract(self, rule_hits: List[Rule]) -> VerificationContract:
        if rule_hits:
            return self._rule_contract(rule_hits[0])
        if self.rules:
            return self._rule_contract(self.rules[0])
        return VerificationContract()

    def _evaluate_no_tool_policy(
        self,
        content: str,
        request_json: Dict[str, Any],
        tool_schema_map: Dict[str, Dict[str, Any]],
        *,
        base_issue_kind: str | None = None,
    ) -> tuple[str, List[str], List[ValidationIssue], List[Rule], List[Rule]]:
        observed_predicates = sorted(self._observable_request_predicates(request_json))
        issue_kind = classify_no_tool_policy_issue(
            content,
            tool_schema_map,
            observed_predicates,
            self._last_observed_role(request_json),
            base_kind=base_issue_kind,
        )
        policy_rule_hits = self._matched_policy_rules(issue_kind, request_json=request_json)
        if issue_kind == "empty_completion" and not policy_rule_hits:
            policy_rule_hits = self._matched_policy_rules(
                "empty_tool_call",
                request_json=request_json,
            )
        if issue_kind == "post_tool_prose_summary" and not policy_rule_hits:
            policy_rule_hits = self._matched_policy_rules(
                "actionable_no_tool_decision",
                request_json=request_json,
            )
        compatibility_rule_hits = self._matched_compatibility_rules(issue_kind, request_json=request_json)
        if issue_kind == "empty_completion" and not compatibility_rule_hits:
            compatibility_rule_hits = self._matched_compatibility_rules(
                "empty_tool_call",
                request_json=request_json,
            )
        if issue_kind == "post_tool_prose_summary" and not compatibility_rule_hits:
            compatibility_rule_hits = self._matched_compatibility_rules(
                "actionable_no_tool_decision",
                request_json=request_json,
            )
        issues = evaluate_no_tool_policy(
            issue_kind,
            observed_predicates,
            policy_rule_hits,
            self._rule_contract,
        )
        return issue_kind, observed_predicates, issues, policy_rule_hits, compatibility_rule_hits

    def _strip_assistant_narration_with_tool_calls(
        self,
        message: Dict[str, Any],
        tool_calls: List[Dict[str, Any]],
        *,
        had_native_tool_calls: bool,
    ) -> List[Dict[str, Any]]:
        if not tool_calls or not had_native_tool_calls:
            return []

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            return []

        message["content"] = ""
        return [
            {
                "kind": "strip_assistant_content_with_tool_calls",
                "reason": "assistant narration removed because the same message already emits tool calls",
            }
        ]

    def apply_response(
        self,
        request_json: Dict[str, Any],
        response_json: Dict[str, Any],
        request_patches: List[str] | None = None,
        next_tool_plan: Dict[str, Any] | None = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], ValidationRecord]:
        final_response = copy.deepcopy(response_json)
        tool_schema_map = self._tool_schema_map(request_json)
        all_repairs: List[Dict[str, Any]] = []
        validation = ValidationRecord()
        plan = next_tool_plan
        if plan is None and request_patches is not None:
            plan = getattr(request_patches, "next_tool_plan", None)
        if isinstance(plan, dict) and plan:
            validation.next_tool_plan_attempted = bool(plan.get("attempted", True))
            validation.next_tool_plan_activated = bool(plan.get("activated", False))
            validation.next_tool_plan_blocked_reason = str(plan.get("blocked_reason") or "").strip() or None
            validation.available_tools = [str(item) for item in plan.get("available_tools") or [] if str(item).strip()]
            validation.candidate_recommended_tools = [
                str(item) for item in plan.get("candidate_recommended_tools") or [] if str(item).strip()
            ]
            validation.matched_recommended_tools = [
                str(item) for item in plan.get("matched_recommended_tools") or [] if str(item).strip()
            ]
            predicate_status = plan.get("activation_predicate_status") or {}
            if isinstance(predicate_status, dict):
                validation.activation_predicate_status = {
                    str(key): bool(value) for key, value in predicate_status.items() if str(key).strip()
                }
            validation.policy_hits.extend(str(item) for item in plan.get("policy_hits") or [] if str(item).strip())
            validation.recommended_tools.extend(
                str(item) for item in plan.get("recommended_tools") or [] if str(item).strip()
            )
            selected_tool = plan.get("selected_tool")
            if selected_tool:
                validation.selected_next_tool = str(selected_tool)
            selected_action_candidate = plan.get("selected_action_candidate")
            if isinstance(selected_action_candidate, dict):
                validation.selected_action_candidate = dict(selected_action_candidate)
            mode = str(plan.get("tool_choice_mode") or "").strip()
            if validation.selected_next_tool and mode:
                validation.tool_choice_mode = mode
        validation.request_patches = list(request_patches or [])
        for patch in validation.request_patches:
            if patch.startswith("policy_hit:"):
                validation.policy_hits.append(patch.split(":", 1)[1])
            elif patch.startswith("policy_next_tool:selected="):
                validation.selected_next_tool = patch.split("=", 1)[1]
            elif patch.startswith("policy_next_tool:recommended="):
                validation.recommended_tools = [
                    item for item in patch.split("=", 1)[1].split(",") if item
                ]
            elif patch == "tool_choice:required(policy_next_tool)":
                validation.tool_choice_mode = "required"
            elif patch.startswith("tool_choice:function(policy_next_tool)="):
                validation.tool_choice_mode = "required"
        if validation.selected_next_tool and validation.tool_choice_mode is None:
            validation.tool_choice_mode = "soft"

        for choice in final_response.get("choices", []):
            msg = choice.get("message", {})
            tool_calls = list(msg.get("tool_calls", []))
            had_native_tool_calls = bool(tool_calls)
            if request_json.get("tools") and not tool_calls:
                text_calls = parse_text_tool_calls(msg.get("content", ""))
                if text_calls:
                    for call in text_calls:
                        fn = call.get("function", {})
                        if isinstance(fn.get("arguments"), dict):
                            fn["arguments"] = json.dumps(fn["arguments"], ensure_ascii=False)
                    tool_calls = text_calls
                    msg["tool_calls"] = tool_calls
            raw_tool_calls = copy.deepcopy(tool_calls)
            narration_repairs = self._strip_assistant_narration_with_tool_calls(
                msg,
                tool_calls,
                had_native_tool_calls=had_native_tool_calls,
            )
            all_repairs.extend(narration_repairs)
            if request_json.get("tools") and not tool_calls:
                content = msg.get("content", "")
                no_tool_response_shape = self._detect_no_tool_response_shape(msg, choice, final_response)
                if no_tool_response_shape:
                    validation.response_shapes.append(no_tool_response_shape)
                validation.request_predicates = sorted(self._observable_request_predicates(request_json))
                validation.last_observed_role = self._last_observed_role(request_json)
                if is_post_tool_structured_final_answer(
                    str(content),
                    validation.request_predicates,
                    validation.last_observed_role,
                    final_answer_format_observable=self._structured_final_answer_format_observable(request_json),
                ):
                    continue
                issue_kind, observed_predicates, issues, policy_rule_hits, compatibility_rule_hits = self._evaluate_no_tool_policy(
                    content,
                    request_json,
                    tool_schema_map,
                    base_issue_kind="empty_completion" if no_tool_response_shape == "empty_completion" else None,
                )
                validation.request_predicates = observed_predicates
                effective_rule_hits = policy_rule_hits or compatibility_rule_hits
                validation.issues.extend(issues)
                validation.rule_hits.extend(rule.rule_id for rule in effective_rule_hits)
                if self._should_coerce_no_tool_text_to_empty(issues[0].kind, effective_rule_hits):
                    coercion_repairs = self._coerce_no_tool_text_to_empty(msg, issues[0].kind)
                    all_repairs.extend(coercion_repairs)
                    continue
                if self._should_attempt_no_tool_recovery(issues[0].kind, effective_rule_hits):
                    guarded = self._apply_empty_tool_guard(msg, issues, effective_rule_hits)
                    validation.fallback_applied = validation.fallback_applied or guarded
                    if not guarded:
                        applied = self._apply_fallback(msg, tool_calls, 0, issues, effective_rule_hits)
                        validation.fallback_applied = validation.fallback_applied or applied
            for index in range(len(tool_calls) - 1, -1, -1):
                tool_call = tool_calls[index]
                name = tool_call.get("function", {}).get("name")
                if not name:
                    effective_rule_hits = self._matched_global_rules("wrong_tool_name", request_json=request_json)
                    issues = [ValidationIssue(kind="wrong_tool_name", message="tool call missing function name")]
                    validation.issues.extend(issues)
                    validation.rule_hits.extend(rule.rule_id for rule in effective_rule_hits)
                    guarded = self._apply_tool_guard(msg, tool_calls, index, issues, effective_rule_hits)
                    validation.fallback_applied = validation.fallback_applied or guarded
                    if not guarded:
                        applied = self._apply_fallback(msg, tool_calls, index, issues, effective_rule_hits)
                        validation.fallback_applied = validation.fallback_applied or applied
                    continue

                rule_hits = self._matched_rules(name, request_json=request_json)
                validation.rule_hits.extend(rule.rule_id for rule in rule_hits)
                schema = tool_schema_map.get(name, {})
                if not schema:
                    issues = [
                        ValidationIssue(
                            kind="tool_guard_violation",
                            tool_name=name,
                            message=f"tool `{name}` not found in request schema",
                        )
                    ]
                    validation.issues.extend(issues)
                    effective_rule_hits = rule_hits or self._matched_global_rules("tool_guard_violation", request_json=request_json)
                    validation.rule_hits.extend(rule.rule_id for rule in effective_rule_hits)
                    guarded = self._apply_tool_guard(msg, tool_calls, index, issues, effective_rule_hits)
                    validation.fallback_applied = validation.fallback_applied or guarded
                    if guarded:
                        continue
                    applied = self._apply_fallback(msg, tool_calls, index, issues, effective_rule_hits)
                    validation.fallback_applied = validation.fallback_applied or applied
                    continue

                rule_spec = self._matched_sanitizer(name)
                repaired = tool_call
                repairs: List[Dict[str, Any]] = []
                if rule_spec is not None:
                    repaired, repairs = sanitize_tool_call(tool_call, schema, rule_spec)
                    tool_calls[index] = repaired
                    for repair in repairs:
                        repair["tool_name"] = name
                    all_repairs.extend(repairs)

                args_text = repaired.get("function", {}).get("arguments", "{}")
                try:
                    args = parse_loose_json(args_text) if isinstance(args_text, str) else args_text
                except Exception:
                    issues = [
                        ValidationIssue(
                            kind="invalid_json_args",
                            tool_name=name,
                            message="tool arguments could not be parsed as JSON",
                        )
                    ]
                    validation.issues.extend(issues)
                    effective_rule_hits = self._matched_rules(name, "invalid_json_args") or rule_hits
                    validation.rule_hits.extend(rule.rule_id for rule in effective_rule_hits)
                    applied = self._apply_fallback(msg, tool_calls, index, issues, effective_rule_hits)
                    validation.fallback_applied = validation.fallback_applied or applied
                    continue

                if not isinstance(args, dict):
                    issues = [
                        ValidationIssue(
                            kind="non_object_args",
                            tool_name=name,
                            message="tool arguments must be a JSON object",
                        )
                    ]
                    validation.issues.extend(issues)
                    effective_rule_hits = self._matched_rules(name, "non_object_args") or rule_hits
                    validation.rule_hits.extend(rule.rule_id for rule in effective_rule_hits)
                    applied = self._apply_fallback(msg, tool_calls, index, issues, effective_rule_hits)
                    validation.fallback_applied = validation.fallback_applied or applied
                    continue

                contextual_repairs = self._resolve_contextual_string_arguments(args, schema, request_json)
                if contextual_repairs:
                    repaired["function"]["arguments"] = json.dumps(args, ensure_ascii=False)
                    tool_calls[index] = repaired
                    for repair in contextual_repairs:
                        repair["tool_name"] = name
                    all_repairs.extend(contextual_repairs)

                contract = self._verification_contract(rule_hits)
                issues = validate_tool_arguments(
                    name,
                    args,
                    schema,
                    contract,
                    repair_count=len(repairs),
                )
                for issue in issues:
                    issue.repaired = any(repair.get("field") == issue.field for repair in repairs if issue.field)
                validation.issues.extend(issues)
                issue_kinds = {issue.kind for issue in issues}
                effective_rule_hits = [
                    rule
                    for rule in rule_hits
                    if not rule.trigger.error_types or set(rule.trigger.error_types) & issue_kinds
                ] or rule_hits
                validation.rule_hits.extend(rule.rule_id for rule in effective_rule_hits)
                applied = self._apply_fallback(msg, tool_calls, index, issues, effective_rule_hits)
                validation.fallback_applied = validation.fallback_applied or applied
            if validation.selected_next_tool is not None:
                emitted_names = [
                    call.get("function", {}).get("name")
                    for call in tool_calls
                    if isinstance(call, dict)
                ]
                if validation.next_tool_emitted is not True:
                    validation.next_tool_emitted = any(bool(name) for name in emitted_names)
                if validation.next_tool_matches_recommendation is not True:
                    validation.next_tool_matches_recommendation = validation.selected_next_tool in emitted_names
                if validation.selected_action_candidate:
                    raw_selected_args = self._selected_tool_call_args(raw_tool_calls, validation.selected_next_tool)
                    final_selected_args = self._selected_tool_call_args(tool_calls, validation.selected_next_tool)
                    validation.next_tool_args_emitted = raw_selected_args is not None
                    validation.candidate_arg_json = dict(validation.selected_action_candidate.get("args") or {})
                    if raw_selected_args is None:
                        validation.next_tool_args_match_binding = False
                    if raw_selected_args is not None:
                        validation.emitted_arg_json = dict(raw_selected_args)
                        validation.arg_binding_validation = self._validate_action_candidate_args(
                            validation.selected_action_candidate,
                            raw_selected_args,
                        )
                        if validation.arg_binding_validation:
                            validation.next_tool_args_match_binding = all(
                                bool(row.get("match")) for row in validation.arg_binding_validation.values()
                            )
                        validation.normalized_arg_binding_validation = self._validate_action_candidate_args_normalized(
                            validation.selected_action_candidate,
                            raw_selected_args,
                        )
                        if validation.normalized_arg_binding_validation:
                            validation.next_tool_args_match_binding_normalized = all(
                                bool(row.get("match")) for row in validation.normalized_arg_binding_validation.values()
                            )
                    if final_selected_args is None:
                        validation.next_tool_final_args_match_binding = False
                        validation.next_tool_final_args_match_binding_normalized = False
                    if final_selected_args is not None:
                        validation.final_emitted_arg_json = dict(final_selected_args)
                        validation.final_arg_binding_validation = self._validate_action_candidate_args(
                            validation.selected_action_candidate,
                            final_selected_args,
                        )
                        if validation.final_arg_binding_validation:
                            validation.next_tool_final_args_match_binding = all(
                                bool(row.get("match")) for row in validation.final_arg_binding_validation.values()
                            )
                        validation.final_normalized_arg_binding_validation = self._validate_action_candidate_args_normalized(
                            validation.selected_action_candidate,
                            final_selected_args,
                        )
                        if validation.final_normalized_arg_binding_validation:
                            validation.next_tool_final_args_match_binding_normalized = all(
                                bool(row.get("match"))
                                for row in validation.final_normalized_arg_binding_validation.values()
                            )
            msg["tool_calls"] = tool_calls
            choice["message"] = msg

        validation.rule_hits = list(dict.fromkeys(validation.rule_hits))
        validation.policy_hits = list(dict.fromkeys(validation.policy_hits))
        validation.recommended_tools = list(dict.fromkeys(validation.recommended_tools))
        validation.response_shapes = list(dict.fromkeys(validation.response_shapes))
        validation.repairs = all_repairs
        validation.repair_kinds = list(
            dict.fromkeys(
                str(repair.get("kind"))
                for repair in all_repairs
                if isinstance(repair, dict) and str(repair.get("kind") or "").strip()
            )
        )
        validation.failure_labels = list(
            dict.fromkeys(
                classify_error_type(
                    issue.kind,
                    request_predicates=validation.request_predicates,
                    has_prior_tool_output="prior_tool_outputs_present" in set(validation.request_predicates),
                ).label
                for issue in validation.issues
            )
        )
        return final_response, all_repairs, validation
