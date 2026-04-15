from __future__ import annotations

from typing import Any, Dict, List

from grc.types import ValidationIssue, VerificationContract


def _python_matches_json_type(value: Any, expected: str) -> bool:
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def validate_tool_arguments(
    tool_name: str,
    args: Dict[str, Any],
    schema: Dict[str, Any],
    contract: VerificationContract,
    repair_count: int = 0,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required = set(schema.get("required", []) if isinstance(schema, dict) else [])

    if contract.require_required_fields:
        for field in sorted(required):
            if field not in args:
                issues.append(
                    ValidationIssue(
                        kind="missing_required",
                        tool_name=tool_name,
                        field=field,
                        message=f"missing required field `{field}`",
                    )
                )

    for field, value in args.items():
        if contract.require_known_fields and field not in properties:
            issues.append(
                ValidationIssue(
                    kind="unknown_field",
                    tool_name=tool_name,
                    field=field,
                    message=f"field `{field}` is not in schema",
                )
            )
            continue

        expected = properties.get(field, {}).get("type")
        if contract.require_type_match and expected and not _python_matches_json_type(value, expected):
            issues.append(
                ValidationIssue(
                    kind="type_mismatch",
                    tool_name=tool_name,
                    field=field,
                    message=f"field `{field}` should be `{expected}`",
                )
            )
        description = str(properties.get(field, {}).get("description", "")).lower()
        if isinstance(value, str) and "cannot be path" in description and ("/" in value or "\\" in value):
            issues.append(
                ValidationIssue(
                    kind="semantic_constraint_violation",
                    tool_name=tool_name,
                    field=field,
                    message=f"field `{field}` violates description constraint: cannot be path",
                )
            )

    if contract.max_repairs is not None and repair_count > contract.max_repairs:
        issues.append(
            ValidationIssue(
                kind="repair_budget_exceeded",
                tool_name=tool_name,
                message=f"repair count {repair_count} exceeded max {contract.max_repairs}",
            )
        )

    return issues
