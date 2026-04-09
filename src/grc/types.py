from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FieldConstraint(BaseModel):
    type: Optional[str] = None
    required: bool = False
    enum: Optional[List[Any]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    pattern: Optional[str] = None
    default: Any = None


class ToolSanitizerSpec(BaseModel):
    repair_json: bool = True
    coerce_types: bool = True
    strip_unknown_keys: bool = True
    fill_defaults: bool = True
    fields: Dict[str, FieldConstraint] = Field(default_factory=dict)


class MatchSpec(BaseModel):
    tool_names: List[str] = Field(default_factory=list)
    error_types: List[str] = Field(default_factory=list)
    category_patterns: List[str] = Field(default_factory=list)


class RuleAction(BaseModel):
    prompt_fragments: List[str] = Field(default_factory=list)
    arg_sanitizer: Dict[str, ToolSanitizerSpec] = Field(default_factory=dict)


class Rule(BaseModel):
    rule_id: str
    priority: int = 0
    enabled: bool = True
    match: MatchSpec = Field(default_factory=MatchSpec)
    action: RuleAction = Field(default_factory=RuleAction)


class FailureCase(BaseModel):
    trace_id: str
    turn_index: int
    tool_name: str
    error_type: str
    field_name: Optional[str] = None
    expected_type: Optional[str] = None
    observed_value: Any = None
    category: Optional[str] = None


class PatchBundle(BaseModel):
    patch_id: str
    rules: List[Rule] = Field(default_factory=list)

