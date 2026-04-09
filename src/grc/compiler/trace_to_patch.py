from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List

import yaml

from grc.types import FailureCase, FieldConstraint, MatchSpec, PatchBundle, Rule, RuleAction, ToolSanitizerSpec


def compile_patch(failure_jsonl: str, out_path: str, patch_id: str = "patch_auto_001") -> None:
    grouped: DefaultDict[str, List[FailureCase]] = defaultdict(list)

    with open(failure_jsonl, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = FailureCase(**json.loads(line))
            grouped[item.tool_name].append(item)

    rules: List[Rule] = []

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

        rules.append(
            Rule(
                rule_id=f"rule_{tool_name}_arg_sanitizer_v1",
                priority=10,
                enabled=True,
                match=MatchSpec(tool_names=[tool_name]),
                action=RuleAction(arg_sanitizer={tool_name: spec}),
            )
        )

    bundle = PatchBundle(patch_id=patch_id, rules=rules)
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        yaml.safe_dump(bundle.model_dump(mode="python"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
