from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from grc.runtime.sanitizer import sanitize_tool_call
from grc.runtime.validator import validate_tool_arguments
from grc.types import PatchBundle, Rule, ToolSanitizerSpec, ValidationIssue, ValidationRecord, VerificationContract
from grc.utils.jsonfix import parse_loose_json


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
            elif tool_name is not None and (not names or tool_name in names):
                matched.append(rule)
        return matched

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
            for index in range(len(tool_calls) - 1, -1, -1):
                tool_call = tool_calls[index]
                name = tool_call.get("function", {}).get("name")
                if not name:
                    validation.issues.append(
                        ValidationIssue(kind="wrong_tool_name", message="tool call missing function name")
                    )
                    continue

                rule_hits = self._matched_rules(name)
                validation.rule_hits.extend(rule.rule_id for rule in rule_hits)
                schema = tool_schema_map.get(name, {})
                if not schema:
                    validation.issues.append(
                        ValidationIssue(
                            kind="tool_guard_violation",
                            tool_name=name,
                            message=f"tool `{name}` not found in request schema",
                        )
                    )
                    applied = self._apply_fallback(msg, tool_calls, index, validation.issues[-1:], rule_hits)
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
