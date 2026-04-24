from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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
    request_predicates: List[str] = Field(default_factory=list)


class PatchScope(BaseModel):
    tool_names: List[str] = Field(default_factory=list)
    patch_sites: List[str] = Field(default_factory=list)


class PromptInjectionSpec(BaseModel):
    fragments: List[str] = Field(default_factory=list)
    position: str = "prepend_system"


class NextToolPolicySpec(BaseModel):
    activation_predicates: List[str] = Field(default_factory=list)
    recommended_tools: List[str] = Field(default_factory=list)
    tool_choice_mode: str = "soft"
    confidence: float = 0.0


class DecisionPolicySpec(BaseModel):
    request_predicates: List[str] = Field(default_factory=list)
    recommended_tools: List[str] = Field(default_factory=list)
    action_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    continue_condition: Optional[str] = None
    stop_condition: Optional[str] = None
    forbidden_terminations: List[str] = Field(default_factory=list)
    evidence_requirements: List[str] = Field(default_factory=list)
    next_tool_policy: NextToolPolicySpec = Field(default_factory=NextToolPolicySpec)


class ToolGuardSpec(BaseModel):
    enabled: bool = True
    on_violation: str = "record"
    on_unknown_tool: str = "record"
    on_empty_tool_call: str = "record"
    assistant_message: Optional[str] = None


class VerificationContract(BaseModel):
    require_known_tool: bool = True
    require_object_args: bool = True
    require_required_fields: bool = True
    require_known_fields: bool = True
    require_type_match: bool = True
    max_repairs: Optional[int] = None
    forbidden_terminations: List[str] = Field(default_factory=list)
    evidence_requirements: List[str] = Field(default_factory=list)


class FallbackRoutingSpec(BaseModel):
    strategy: str = "record_only"
    assistant_message: Optional[str] = None
    on_issue_kinds: List[str] = Field(default_factory=list)


class RetentionPolicy(BaseModel):
    promote_to: str = "rules/accepted"
    reject_to: str = "rules/rejected"
    keep_in_candidates: bool = True


class RuleAction(BaseModel):
    prompt_fragments: List[str] = Field(default_factory=list)
    prompt_injection: PromptInjectionSpec = Field(default_factory=PromptInjectionSpec)
    decision_policy: DecisionPolicySpec = Field(default_factory=DecisionPolicySpec)
    arg_sanitizer: Dict[str, ToolSanitizerSpec] = Field(default_factory=dict)
    tool_guard: ToolGuardSpec = Field(default_factory=ToolGuardSpec)
    verification: VerificationContract = Field(default_factory=VerificationContract)
    fallback_router: FallbackRoutingSpec = Field(default_factory=FallbackRoutingSpec)


class Rule(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    rule_id: str
    priority: int = 0
    enabled: bool = True
    trigger: MatchSpec = Field(
        default_factory=MatchSpec,
        validation_alias=AliasChoices("trigger", "match"),
    )
    scope: PatchScope = Field(default_factory=PatchScope)
    action: RuleAction = Field(default_factory=RuleAction)
    validation_contract: VerificationContract = Field(default_factory=VerificationContract)
    retention: RetentionPolicy = Field(default_factory=RetentionPolicy)


class FailureCase(BaseModel):
    trace_id: str
    turn_index: int
    tool_name: str
    error_type: str
    stage: Optional[str] = None
    failure_type: Optional[str] = None
    failure_label: Optional[str] = None
    field_name: Optional[str] = None
    expected_type: Optional[str] = None
    observed_value: Any = None
    category: Optional[str] = None
    request_predicates: List[str] = Field(default_factory=list)
    request_literals: List[str] = Field(default_factory=list)
    predicate_evidence: Dict[str, bool] = Field(default_factory=dict)
    recommended_tools: List[str] = Field(default_factory=list)
    action_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    tool_schema_hash: str = "*"


class FailureIR(BaseModel):
    failure_id: str
    tool_name: str
    error_types: List[str] = Field(default_factory=list)
    stages: List[str] = Field(default_factory=list)
    failure_types: List[str] = Field(default_factory=list)
    failure_labels: List[str] = Field(default_factory=list)
    field_names: List[str] = Field(default_factory=list)
    expected_types: Dict[str, str] = Field(default_factory=dict)
    categories: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    trace_ids: List[str] = Field(default_factory=list)
    request_predicates: List[str] = Field(default_factory=list)
    request_literals: List[str] = Field(default_factory=list)
    predicate_evidence: Dict[str, int] = Field(default_factory=dict)
    recommended_tools: List[str] = Field(default_factory=list)
    action_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    tool_schema_hash: str = "*"


class ValidationIssue(BaseModel):
    kind: str
    tool_name: Optional[str] = None
    field: Optional[str] = None
    message: Optional[str] = None
    severity: str = "error"
    repaired: bool = False


class ValidationRecord(BaseModel):
    trace_id: Optional[str] = None
    rule_hits: List[str] = Field(default_factory=list)
    issues: List[ValidationIssue] = Field(default_factory=list)
    repairs: List[Dict[str, Any]] = Field(default_factory=list)
    repair_kinds: List[str] = Field(default_factory=list)
    failure_labels: List[str] = Field(default_factory=list)
    request_predicates: List[str] = Field(default_factory=list)
    response_shapes: List[str] = Field(default_factory=list)
    last_observed_role: Optional[str] = None
    fallback_applied: bool = False
    request_patches: List[str] = Field(default_factory=list)
    policy_hits: List[str] = Field(default_factory=list)
    recommended_tools: List[str] = Field(default_factory=list)
    next_tool_plan_attempted: bool = False
    next_tool_plan_activated: bool = False
    next_tool_plan_blocked_reason: Optional[str] = None
    available_tools: List[str] = Field(default_factory=list)
    candidate_recommended_tools: List[str] = Field(default_factory=list)
    matched_recommended_tools: List[str] = Field(default_factory=list)
    activation_predicate_status: Dict[str, bool] = Field(default_factory=dict)
    selected_next_tool: Optional[str] = None
    selected_action_candidate: Optional[Dict[str, Any]] = None
    tool_choice_mode: Optional[str] = None
    next_tool_emitted: Optional[bool] = None
    next_tool_matches_recommendation: Optional[bool] = None
    next_tool_args_emitted: Optional[bool] = None
    next_tool_args_match_binding: Optional[bool] = None
    arg_binding_validation: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class PatchBundle(BaseModel):
    patch_id: str
    rules: List[Rule] = Field(default_factory=list)
    failure_ir: List[FailureIR] = Field(default_factory=list)
    source_failure_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
