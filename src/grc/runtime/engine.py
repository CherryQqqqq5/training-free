from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from grc.runtime.sanitizer import sanitize_tool_call
from grc.types import PatchBundle, Rule, ToolSanitizerSpec


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
            names = rule.match.tool_names
            if not names or tool_name in names:
                spec = rule.action.arg_sanitizer.get(tool_name)
                if spec:
                    return spec
        return None

    def apply_request(self, request_json: Dict[str, Any]) -> Dict[str, Any]:
        return request_json

    def apply_response(
        self,
        request_json: Dict[str, Any],
        response_json: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        tool_schema_map = self._tool_schema_map(request_json)
        all_repairs: List[Dict[str, Any]] = []

        for choice in response_json.get("choices", []):
            msg = choice.get("message", {})
            tool_calls = msg.get("tool_calls", [])
            for index, tool_call in enumerate(tool_calls):
                name = tool_call.get("function", {}).get("name")
                if not name:
                    continue
                schema = tool_schema_map.get(name, {})
                rule_spec = self._matched_sanitizer(name)
                if rule_spec is None:
                    continue
                repaired, repairs = sanitize_tool_call(tool_call, schema, rule_spec)
                tool_calls[index] = repaired
                for repair in repairs:
                    repair["tool_name"] = name
                all_repairs.extend(repairs)
            msg["tool_calls"] = tool_calls
            choice["message"] = msg

        return response_json, all_repairs

