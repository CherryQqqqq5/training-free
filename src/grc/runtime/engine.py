from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from grc.runtime.sanitizer import sanitize_tool_call
from grc.runtime.validator import validate_tool_arguments
from grc.types import (
    PatchBundle,
    Rule,
    ToolSanitizerSpec,
    ValidationIssue,
    ValidationRecord,
    VerificationContract,
)
from grc.utils.jsonfix import parse_loose_json
from grc.utils.text_tool_calls import (
    classify_no_tool_call_content,
    parse_text_tool_calls,
)
from grc.utils.tool_schema import tool_map_from_tools_payload


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

    def _matched_rules(self, tool_name: str | None = None, issue_kind: str | None = None) -> List[Rule]:
        matched: List[Rule] = []
        for rule in self.rules:
            names = rule.trigger.tool_names
            if tool_name is None and not names:
                if issue_kind and rule.trigger.error_types and issue_kind not in rule.trigger.error_types:
                    continue
                matched.append(rule)
            elif tool_name is not None and names and tool_name in names:
                if issue_kind and rule.trigger.error_types and issue_kind not in rule.trigger.error_types:
                    continue
                matched.append(rule)
        return matched

    def _matched_global_rules(self, issue_kind: str | None = None) -> List[Rule]:
        matched: List[Rule] = []
        for rule in self.rules:
            if rule.trigger.tool_names:
                continue
            if issue_kind and rule.trigger.error_types and issue_kind not in rule.trigger.error_types:
                continue
            matched.append(rule)
        return matched

    def _rule_prompt_fragments(self, rule: Rule) -> List[str]:
        injected = list(rule.action.prompt_injection.fragments)
        if injected:
            return injected
        return list(rule.action.prompt_fragments)

    def _collect_context_literals(self, request_json: Dict[str, Any]) -> List[str]:
        values: List[str] = []

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
                for match in self._QUOTED_LITERAL_RE.finditer(content):
                    add_value(match.group(1) or match.group(2) or "")
                for token in self._PATH_TOKEN_RE.findall(content):
                    add_value(token)
                for token in self._FILE_TOKEN_RE.findall(content):
                    add_value(token)
                try:
                    parsed = json.loads(content)
                except Exception:
                    parsed = None
                if parsed is not None:
                    visit_jsonlike(parsed)
        return values[:12]

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

    def _collect_prompt_fragments(self, request_json: Dict[str, Any]) -> List[str]:
        fragments: List[str] = self._structured_tool_guidance_fragments(request_json)
        request_tool_names = set(self._tool_schema_map(request_json).keys())
        allow_global_prompt_injection = bool(self.runtime_policy.get("allow_global_prompt_injection", False))
        for rule in self.rules:
            patch_sites = set(rule.scope.patch_sites)
            if patch_sites and "prompt_injector" not in patch_sites:
                continue
            names = set(rule.trigger.tool_names)
            if names and not (names & request_tool_names):
                continue
            # Global rules that are mined from response-side failure classes do not have
            # request-local preconditions today. Injecting them into every request turns
            # post-hoc failure summaries into blanket prompt pollution, which regresses
            # otherwise healthy traces. Keep them opt-in until request-side predicates
            # exist in the IR.
            if not names and not allow_global_prompt_injection:
                continue
            fragments.extend(self._rule_prompt_fragments(rule))
        # Preserve order while dropping duplicates.
        return list(dict.fromkeys(fragment for fragment in fragments if fragment))

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
        fragments = self._collect_prompt_fragments(patched)
        if not fragments:
            return patched, []

        system_text = "[Golden Rule Compiler]\n" + "\n".join(f"- {fragment}" for fragment in fragments)
        messages = list(patched.get("messages", []))
        if messages and messages[0].get("role") == "system":
            existing = messages[0].get("content", "")
            merged = f"{existing}\n\n{system_text}".strip() if existing else system_text
            messages[0]["content"] = merged
        else:
            messages.insert(0, {"role": "system", "content": system_text})
        patched["messages"] = messages
        request_patches = [f"prompt_injector:{fragment}" for fragment in fragments]
        return patched, request_patches

    def _apply_fallback(self, message: Dict[str, Any], tool_calls: List[Dict[str, Any]], index: int, issues: List[ValidationIssue], rule_hits: List[Rule]) -> bool:
        if not issues:
            return False

        issue_kinds = {issue.kind for issue in issues}
        for rule in rule_hits:
            trigger_error_types = set(rule.trigger.error_types)
            if trigger_error_types and not (trigger_error_types & issue_kinds):
                continue
            strategy = rule.action.fallback_router.strategy
            scoped_issue_kinds = set(rule.action.fallback_router.on_issue_kinds)
            if scoped_issue_kinds and not any(issue.kind in scoped_issue_kinds for issue in issues):
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

    def _has_explicit_no_tool_recovery(self, issue_kind: str, rule_hits: List[Rule]) -> bool:
        for rule in rule_hits:
            if rule.trigger.error_types and issue_kind not in rule.trigger.error_types:
                continue
            strategy = rule.action.fallback_router.strategy
            if strategy == "record_only":
                continue
            scoped_issue_kinds = set(rule.action.fallback_router.on_issue_kinds)
            if scoped_issue_kinds and issue_kind not in scoped_issue_kinds:
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
        }:
            return "record"
        for rule in rule_hits:
            if rule.trigger.error_types and issue_kind not in rule.trigger.error_types:
                continue
            guard = rule.action.tool_guard
            if not guard.enabled:
                continue
            if issue_kind == "empty_tool_call":
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
            return rule_hits[0].validation_contract or rule_hits[0].action.verification
        if self.rules:
            return self.rules[0].validation_contract
        return VerificationContract()

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
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], ValidationRecord]:
        final_response = copy.deepcopy(response_json)
        tool_schema_map = self._tool_schema_map(request_json)
        all_repairs: List[Dict[str, Any]] = []
        validation = ValidationRecord()
        validation.request_patches = list(request_patches or [])

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
            narration_repairs = self._strip_assistant_narration_with_tool_calls(
                msg,
                tool_calls,
                had_native_tool_calls=had_native_tool_calls,
            )
            all_repairs.extend(narration_repairs)
            if request_json.get("tools") and not tool_calls:
                content = msg.get("content", "")
                issue_kind = classify_no_tool_call_content(content, tool_schema_map)
                global_rule_hits = self._matched_global_rules(issue_kind)
                issue_messages = {
                    "natural_language_termination": "assistant ended turn with natural language without tool call",
                    "clarification_request": "assistant requested missing user parameters before tool invocation",
                    "unsupported_request": "assistant refused because request appears unsupported by available tools",
                    "hallucinated_completion": "assistant claimed progress or completion without emitting a tool call",
                    "malformed_output": "assistant emitted malformed content instead of a tool call",
                    "empty_tool_call": "no tool call emitted for tool-enabled request",
                }
                issues = [ValidationIssue(kind=issue_kind, message=issue_messages[issue_kind])]
                validation.issues.extend(issues)
                validation.rule_hits.extend(rule.rule_id for rule in global_rule_hits)
                if self._should_coerce_no_tool_text_to_empty(issues[0].kind, global_rule_hits):
                    coercion_repairs = self._coerce_no_tool_text_to_empty(msg, issues[0].kind)
                    all_repairs.extend(coercion_repairs)
                    continue
                if self._should_attempt_no_tool_recovery(issues[0].kind, global_rule_hits):
                    guarded = self._apply_empty_tool_guard(msg, issues, global_rule_hits)
                    validation.fallback_applied = validation.fallback_applied or guarded
                    if not guarded:
                        applied = self._apply_fallback(msg, tool_calls, 0, issues, global_rule_hits)
                        validation.fallback_applied = validation.fallback_applied or applied
            for index in range(len(tool_calls) - 1, -1, -1):
                tool_call = tool_calls[index]
                name = tool_call.get("function", {}).get("name")
                if not name:
                    effective_rule_hits = self._matched_global_rules("wrong_tool_name")
                    issues = [ValidationIssue(kind="wrong_tool_name", message="tool call missing function name")]
                    validation.issues.extend(issues)
                    validation.rule_hits.extend(rule.rule_id for rule in effective_rule_hits)
                    guarded = self._apply_tool_guard(msg, tool_calls, index, issues, effective_rule_hits)
                    validation.fallback_applied = validation.fallback_applied or guarded
                    if not guarded:
                        applied = self._apply_fallback(msg, tool_calls, index, issues, effective_rule_hits)
                        validation.fallback_applied = validation.fallback_applied or applied
                    continue

                rule_hits = self._matched_rules(name)
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
                    effective_rule_hits = rule_hits or self._matched_global_rules("tool_guard_violation")
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
            msg["tool_calls"] = tool_calls
            choice["message"] = msg

        validation.rule_hits = list(dict.fromkeys(validation.rule_hits))
        validation.repairs = all_repairs
        return final_response, all_repairs, validation
