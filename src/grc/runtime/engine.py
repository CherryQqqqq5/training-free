from __future__ import annotations

import copy
import json
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
from grc.utils.text_tool_calls import looks_like_terminal_natural_language, parse_text_tool_calls


class RuleEngine:
    def __init__(self, rules_dir: str):
        self.rules_dir = Path(rules_dir)
        self.rules: List[Rule] = self._load_rules()

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
        tool_map: Dict[str, Dict[str, Any]] = {}
        for tool in request_json.get("tools", []):
            fn = tool.get("function", {})
            name = fn.get("name")
            params = fn.get("parameters", {})
            if name:
                tool_map[name] = params
        return tool_map

    def _matched_sanitizer(self, tool_name: str) -> ToolSanitizerSpec | None:
        for rule in self.rules:
            names = rule.trigger.tool_names
            if not names or tool_name in names:
                spec = rule.action.arg_sanitizer.get(tool_name)
                if spec:
                    return spec
        return None

    def _matched_rules(self, tool_name: str | None = None) -> List[Rule]:
        matched: List[Rule] = []
        for rule in self.rules:
            names = rule.trigger.tool_names
            if tool_name is None and not names:
                matched.append(rule)
            elif tool_name is not None and names and tool_name in names:
                matched.append(rule)
        return matched

    def _matched_global_rules(self) -> List[Rule]:
        return [rule for rule in self.rules if not rule.trigger.tool_names]

    def _collect_prompt_fragments(self, request_json: Dict[str, Any]) -> List[str]:
        fragments: List[str] = []
        request_tool_names = set(self._tool_schema_map(request_json).keys())
        for rule in self.rules:
            names = set(rule.trigger.tool_names)
            if names and not (names & request_tool_names):
                continue
            fragments.extend(rule.action.prompt_fragments)
            fragments.extend(rule.action.prompt_injection.fragments)
        # Preserve order while dropping duplicates.
        return list(dict.fromkeys(fragment for fragment in fragments if fragment))

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

        for rule in rule_hits:
            strategy = rule.action.fallback_router.strategy
            scoped_issue_kinds = set(rule.action.fallback_router.on_issue_kinds)
            if scoped_issue_kinds and not any(issue.kind in scoped_issue_kinds for issue in issues):
                continue
            if strategy == "drop_tool_call":
                tool_calls.pop(index)
                return True
            if strategy == "assistant_message":
                tool_calls.pop(index)
                fallback_message = rule.action.fallback_router.assistant_message or "Tool call removed after validation failure."
                existing = message.get("content") or ""
                message["content"] = f"{existing}\n{fallback_message}".strip()
                return True
        return False

    def _tool_guard_action(self, rule_hits: List[Rule], issue_kind: str) -> str:
        for rule in rule_hits:
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
            if request_json.get("tools") and not tool_calls:
                text_calls = parse_text_tool_calls(msg.get("content", ""))
                if text_calls:
                    # Bring BFCL prompting-style textual calls into the same tool_call pipeline.
                    for call in text_calls:
                        fn = call.get("function", {})
                        if isinstance(fn.get("arguments"), dict):
                            fn["arguments"] = json.dumps(fn["arguments"], ensure_ascii=False)
                    tool_calls = text_calls
                    msg["tool_calls"] = tool_calls
            global_rule_hits = self._matched_global_rules()
            if request_json.get("tools") and not tool_calls:
                if looks_like_terminal_natural_language(msg.get("content", "")):
                    issues = [
                        ValidationIssue(
                            kind="natural_language_termination",
                            message="assistant ended turn with natural language without tool call",
                        )
                    ]
                else:
                    issues = [ValidationIssue(kind="empty_tool_call", message="no tool call emitted for tool-enabled request")]
                validation.issues.extend(issues)
                validation.rule_hits.extend(rule.rule_id for rule in global_rule_hits)
                guarded = self._apply_empty_tool_guard(msg, issues, global_rule_hits)
                validation.fallback_applied = validation.fallback_applied or guarded
                if not guarded:
                    applied = self._apply_fallback(msg, tool_calls, 0, issues, global_rule_hits)
                    validation.fallback_applied = validation.fallback_applied or applied
            for index in range(len(tool_calls) - 1, -1, -1):
                tool_call = tool_calls[index]
                name = tool_call.get("function", {}).get("name")
                if not name:
                    issues = [ValidationIssue(kind="wrong_tool_name", message="tool call missing function name")]
                    validation.issues.extend(issues)
                    validation.rule_hits.extend(rule.rule_id for rule in global_rule_hits)
                    guarded = self._apply_tool_guard(msg, tool_calls, index, issues, global_rule_hits)
                    validation.fallback_applied = validation.fallback_applied or guarded
                    if not guarded:
                        applied = self._apply_fallback(msg, tool_calls, index, issues, global_rule_hits)
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
                    effective_rule_hits = rule_hits or global_rule_hits
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
                    applied = self._apply_fallback(msg, tool_calls, index, issues, rule_hits)
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
                    applied = self._apply_fallback(msg, tool_calls, index, issues, rule_hits)
                    validation.fallback_applied = validation.fallback_applied or applied
                    continue

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
                applied = self._apply_fallback(msg, tool_calls, index, issues, rule_hits)
                validation.fallback_applied = validation.fallback_applied or applied
            msg["tool_calls"] = tool_calls
            choice["message"] = msg

        validation.rule_hits = list(dict.fromkeys(validation.rule_hits))
        validation.repairs = all_repairs
        return final_response, all_repairs, validation
