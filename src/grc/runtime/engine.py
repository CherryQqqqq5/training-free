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
        if self._tool_schema_map(request_json):
            predicates.add("tools_available")
        if self._collect_context_literals(request_json):
            predicates.add("prior_explicit_literals_present")
        if self._has_prior_tool_outputs(request_json):
            predicates.add("prior_tool_outputs_present")
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
            "confidence": 0.0,
        }
        blocked_priority = {
            "no_policy_candidate": 1,
            "request_predicates_unmet": 2,
            "activation_predicates_unmet": 3,
            "recommended_tools_empty": 4,
            "recommended_tools_not_in_schema": 5,
            "activated": 99,
        }
        blocked_reason = "no_policy_candidate"
        blocked_rank = blocked_priority[blocked_reason]

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
            plan["activated"] = True
            plan["blocked_reason"] = "activated"
            plan["selected_tool"] = plan["selected_tool"] or recommended[0]
            plan["tool_choice_mode"] = "required" if mode == "required" else "soft"
            plan["confidence"] = max(float(plan["confidence"]), confidence)
            plan["activation_predicates"] = list(dict.fromkeys(plan["activation_predicates"] + activation_predicates))
            plan["policy_hits"].append(rule.rule_id)
            add_unique("matched_recommended_tools", recommended)
            add_unique("recommended_tools", recommended)
            for candidate in self._policy_action_candidates(policy):
                if candidate not in plan["action_candidates"]:
                    plan["action_candidates"].append(candidate)
            if plan["selected_action_candidate"] is None:
                selected_candidates = self._policy_action_candidates(policy, recommended[0])
                if selected_candidates:
                    plan["selected_action_candidate"] = selected_candidates[0]
        plan["recommended_tools"] = plan["recommended_tools"][:3]
        plan["matched_recommended_tools"] = plan["matched_recommended_tools"][:3]
        plan["candidate_recommended_tools"] = plan["candidate_recommended_tools"][:5]
        plan["action_candidates"] = plan["action_candidates"][:5]
        if not plan["activated"]:
            plan["blocked_reason"] = blocked_reason
        return plan

    def _recommended_policy_tools(self, request_json: Dict[str, Any]) -> List[str]:
        return list(self._next_tool_policy_plan(request_json).get("recommended_tools") or [])

    def _recommended_policy_tool_fragments(self, request_json: Dict[str, Any]) -> List[str]:
        recommended = self._recommended_policy_tools(request_json)
        if not recommended:
            return []
        if len(recommended) == 1:
            return [
                f"Policy next-tool recommendation: prefer `{recommended[0]}` as the next tool action when its required arguments are locally grounded; do not end this turn with prose-only narration while the policy predicates still hold."
            ]
        return [
            "Policy next-tool recommendations: prefer one of "
            + ", ".join(f"`{tool}`" for tool in recommended)
            + " as the next tool action when required arguments are locally grounded; do not end this turn with prose-only narration while the policy predicates still hold."
        ]

    def _collect_prompt_fragments(self, request_json: Dict[str, Any]) -> List[str]:
        fragments: List[str] = self._structured_tool_guidance_fragments(request_json)
        fragments.extend(self._recommended_policy_tool_fragments(request_json))
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
        fragments = self._collect_prompt_fragments(patched)
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
            if (
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

    @staticmethod
    def _validate_action_candidate_args(candidate: Dict[str, Any], observed_args: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        bindings = candidate.get("arg_bindings") if isinstance(candidate.get("arg_bindings"), dict) else {}
        expected_args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
        fields = list(dict.fromkeys(list(expected_args.keys()) + list(bindings.keys())))
        validation: Dict[str, Dict[str, Any]] = {}
        for field in fields:
            binding = bindings.get(field) if isinstance(bindings.get(field), dict) else {}
            expected = binding.get("value", expected_args.get(field))
            observed = observed_args.get(field)
            validation[str(field)] = {
                "expected": expected,
                "observed": observed,
                "source": binding.get("source") or candidate.get("binding_source") or "action_candidate.args",
                "match": observed == expected,
            }
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
                    if raw_selected_args is None:
                        validation.next_tool_args_match_binding = False
                    if raw_selected_args is not None:
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
