# Phase-2 Evolution Plan

## Objective

Phase-2 moves GRC from a compatibility harness into a training-free policy-evolution loop. The stable target is not another broad benchmark patch. The target is a computable, auditable loop:

1. classify failures into a reproducible taxonomy,
2. attribute repairs by causal contribution,
3. compile failures into reusable decision policies,
4. search and select bounded policy candidates,
5. retain successful policies for later reuse.

The main MVP failure family remains premature no-tool termination: `EMPTY_TOOL_CALL`, `ACTIONABLE_NO_TOOL_DECISION`, and `POST_TOOL_PROSE_SUMMARY`.

## Failure Taxonomy

Every mined failure must preserve the legacy `error_type` for compatibility and also expose a first-class `(stage, type)` label.

Stages:

- `PRE_TOOL`: no tool call or tool output has occurred in the local task state.
- `MID_TOOL`: at least one tool action is being formed or validated, but the task is not complete.
- `POST_TOOL`: a prior tool output is available and should inform the next action or final answer.

Types:

- `EMPTY_TOOL_CALL`: a tool-enabled request produced no tool call.
- `ACTIONABLE_NO_TOOL_DECISION`: enough local evidence exists, but the assistant ended in prose.
- `POST_TOOL_PROSE_SUMMARY`: a prior tool result exists, but the assistant summarizes instead of continuing structurally.
- `TERMINATION_INADMISSIBLE`: a matched policy forbids stopping under the observed evidence.
- `MALFORMED_CALL`: tool name, JSON, schema, field, or type shape is invalid.
- `ARG_UNDERSPECIFIED`: required arguments are missing or still refer to ambiguous context.
- `CLARIFICATION_REQUEST`: an allowed request for genuinely missing information.
- `UNSUPPORTED_REQUEST`: an allowed unsupported/refusal outcome when no local tool action is valid.

Required classifier predicates:

- `has_sufficient_literals`: context contains explicit filenames, paths, IDs, quoted values, or other concrete argument literals.
- `tool_output_sufficient`: previous tool output contains non-empty evidence that can ground a next step or final answer.
- `is_clarification`: response is a question and explicitly asks for missing information.

Required outputs for each experiment comparison:

- Table A: `(stage,type)` distribution for baseline, `primary_v4`, and `rerun_v4`.
- Top-3 failure families by count and their share of total failures.

## Repair Attribution

Repair reporting must move beyond trigger counts. Runtime traces should contain enough data to build records shaped as:

```json
{
  "case_id": "miss_param_123",
  "run_id": "multi_turn_miss_param_rerun_v4",
  "trace_id": "trace-id",
  "failure_stage": "POST_TOOL",
  "failure_type": "ACTIONABLE_NO_TOOL_DECISION",
  "repairs_applied": ["coerce_no_tool_text_to_empty"],
  "final_success": true
}
```

Metrics:

- `coverage(r) = #cases where r applied / #cases of target failure`
- `success(r) = #cases fixed by r / #cases where r applied`
- `gain(r) = Acc(full) - Acc(without r)`

Protocol:

- Run `RUN=full` for the full candidate.
- Run `DISABLE=<repair_name>` for targeted ablations.
- Keep compatibility repairs and decision-policy gains in separate reporting columns.

Compatibility-class examples:

- `resolve_contextual_string_arg`
- `repair_json`
- `coerce_types`

Decision-layer examples:

- policy rule causing `ACTIONABLE_NO_TOOL_DECISION` continuation
- policy rule forbidding `POST_TOOL_PROSE_SUMMARY`
- policy rule adding `TERMINATION_INADMISSIBLE` only when evidence requirements hold

## Policy Units

Compiler output must include reusable policy units for decision-layer failures. A policy unit is not a benchmark case patch; it is a request-local decision rule.

Minimal schema:

```yaml
policy_unit:
  name: avoid_premature_termination
  trigger:
    error_types:
      - actionable_no_tool_decision
    request_predicates:
      - tools_available
      - prior_explicit_literals_present
  recommended_tools: []
  continue_condition: tools remain available and locally grounded evidence supports another tool action
  stop_condition: do not stop with prose-only narration while matched local continuation evidence still holds
  forbidden_terminations:
    - prose_only_no_tool_termination
  evidence_requirements:
    - tools_available
    - prior_explicit_literals_present
  confidence: 0.8
  source_failure_signature:
    stage: PRE_TOOL
    type: ACTIONABLE_NO_TOOL_DECISION
    tool_schema_hash: "*"
    literals_pattern: explicit_context_literals
```

Policy units must remain request-local:

- no BFCL case IDs,
- no hard-coded benchmark filenames,
- no global always-on behavioral instruction,
- no claim that compatibility-only changes are policy evolution.

## Search, Selection, And Memory

Candidate generation:

- Fresh: compile directly from newly mined failures.
- Reuse: retrieve similar historical policy units by failure signature.
- Specialize: adapt retrieved predicates or evidence requirements to the current failure.
- Mutate: optionally relax or strengthen predicates in bounded variants.

Failure signature:

```text
(stage, type, tool_schema_hash, literals_pattern)
```

Selection score:

```text
score = acc - alpha * latency - beta * regression
```

Selection states:

- `accepted`: stable uplift, bounded cost/latency, no unacceptable regression.
- `retained`: positive signal but insufficient rerun evidence.
- `rejected`: invalid, regressive, or no positive target-slice uplift.

History must retain:

- decision code,
- target delta,
- policy fingerprints,
- error families,
- request predicates,
- failure signatures,
- reuse source if any.

## Evolution Loop

Target loop:

```text
for iteration t:
    run benchmark
    collect traces and scores
    classify failures into (stage,type)
    mine top failure signatures
    retrieve similar historical policies
    generate fresh/reused/specialized candidates
    evaluate candidates plus clean holdout
    select accepted/retained/rejected
    update policy history
```

The proof of evolution is longitudinal:

- failure rate decreases,
- policy reuse increases,
- number of new patches needed per iteration decreases,
- clean-slice regression remains bounded.

## Anti-Overfitting Guardrails

Every Phase-2 claim must satisfy:

- request-local predicates are present for live decision policies,
- policy rules do not mention benchmark IDs or task-specific sample names,
- compatibility gains are reported separately from decision-policy gains,
- clean-slice or cross-subset regression is checked,
- ablations isolate at least one high-impact repair or policy family,
- selected policies are reproducible from traces and history records.

## Implementation Checklist

- Add `src/grc/compiler/failure_taxonomy.py` with stage/type enums, predicate functions, and classifiers.
- Extend `FailureCase` and `FailureIR` with taxonomy fields while preserving `error_type`.
- Route mining through taxonomy classification and emit taxonomy distributions in failure summaries.
- Add `scripts/summarize_failure_taxonomy.py` for Table A and Top-3 failure families.
- Add `scripts/analyze_repair_contribution.py` for coverage/success and ablation gain summaries.
- Emit `policy_unit.yaml` from compiler candidate output for decision-layer failures.
- Add selector history records and retrieval helpers for failure signatures.
- Validate with taxonomy, policy-unit, repair attribution, selector history, and existing runtime/compiler tests.
