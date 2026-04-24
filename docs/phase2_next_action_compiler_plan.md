# Phase-2 Next-Action Compiler Plan

Date: 2026-04-24

This document is the current non-drifting Phase-2 plan after the required next-tool validation round. It records what the repository actually implements, what the latest experiment proved, what remains incomplete, and what should be built next.

## Verification Verdict

The current codebase largely matches the latest analysis: Phase-2 has a functional failure taxonomy, compiler, runtime patching path, validation records, selector, and history skeleton, but the measured behavior remains repair-heavy and constraint-heavy rather than action-policy-heavy.

The important nuance is that next-tool policy infrastructure exists in code. `NextToolPolicySpec`, `recommended_tools`, `tool_choice_mode`, `selected_next_tool`, `next_tool_emitted`, and `next_tool_matches_recommendation` are already represented in the IR/runtime/reporting path. However, the latest validation showed that these fields were not exercised by the active policy artifact.

The resulting diagnosis is:

- The system is good at identifying where the model should not stop.
- The system is not yet reliable at deciding the next concrete tool action and arguments.
- `runtime_policy.enable_required_next_tool_choice` is not useful until compiler output contains non-empty, request-valid `recommended_tools`.
- The next Phase-2 target should be a minimal next-action compiler, not another compatibility repair layer.

## Current Algorithm Shape

The implemented chain is:

```text
trace -> mine failures -> classify taxonomy -> compile rule/policy -> runtime patch -> repair/validate -> score/select/history
```

The main objects are already present:

- `FailureCase` and `FailureIR` represent mined failures.
- `Rule`, `DecisionPolicySpec`, and `NextToolPolicySpec` represent compiled policy artifacts.
- `ValidationRecord` records repairs, policy hits, selected next tools, tool-choice mode, emitted tool calls, and recommendation matches.
- The runtime `RuleEngine` observes request predicates, computes a next-tool plan, applies request patches, optionally sets `tool_choice="required"`, and validates the response.
- The selector evaluates aggregate target accuracy, latency/cost, holdout regression, manifest validity, route consistency, and paired rerun consistency.
- History can retain policy units and recommended tools for later reuse.

This is a credible scaffold, but the current policy is still mostly a constraint system:

- It forbids or repairs prose-only termination.
- It records no-tool or wrong-stop symptoms.
- It can bias the prompt toward a recommended tool, but only if a recommendation exists.
- It does not yet synthesize reliable state -> action -> argument bindings.

## Latest Experimental Evidence

The required next-tool validation used the fixed archived `fresh_02` ruleset and compared soft recommendation against required next-tool mode on the same upstream route.

Run summary:

| Run | Slice | Mode | Route | Accuracy |
| --- | --- | --- | --- | ---: |
| `baseline_target` | `multi_turn_miss_param` | `soft` | `x-ai/grok-3-beta` | 37.0% |
| `soft_target` | `multi_turn_miss_param` | `soft` | `x-ai/grok-3-beta` | 39.5% |
| `required_target` | `multi_turn_miss_param` | `required` | `x-ai/grok-3-beta` | 38.0% |
| `baseline_holdout` | `simple_python` | `soft` | `x-ai/grok-3-beta` | 95.25% |
| `soft_holdout` | `simple_python` | `soft` | `x-ai/grok-3-beta` | 94.25% |
| `required_holdout` | `simple_python` | `required` | `x-ai/grok-3-beta` | 94.50% |

Verdict: `neutral`.

The required path did not produce a positive target gain. Holdout safety was acceptable, but the target score fell from `39.5%` to `38.0%`.

The key causal observation is stronger than the aggregate score:

- `policy_validation` records: `0`
- `tool_choice_mode="required"` records: `0`
- `selected_next_tool` records: `0`
- `next_tool_emitted` records: `0`
- `next_tool_matches_recommendation` records: `0`

The fixed `fresh_02` policy artifact had `decision_policy.recommended_tools: []`. Therefore the experiment mostly tested a configuration switch with no concrete action object behind it. It did not test a real required next-tool policy.

Repair reports remained dominated by `coerce_no_tool_text_to_empty`, with `resolve_contextual_string_arg` and `strip_assistant_content_with_tool_calls` as secondary repairs. This confirms that the current score movement still comes mostly from protocol hygiene and wrong-stop coercion rather than from next-action conversion.

## Confirmed Gaps

### 1. State Representation Is Too Coarse

Current request predicates include signals such as `tools_available`, `prior_explicit_literals_present`, and `prior_tool_outputs_present`. These are useful but too weak for multi-turn tool use.

The system needs a richer tool-state representation:

```yaml
last_tool: find
last_tool_output_keys: [matches]
last_tool_output_values:
  matches: ["./goals.txt"]
user_intent: read_or_output_file
available_tools:
  - cat(file_name)
candidate_bindings:
  file_name: first_basename(last_tool_output.matches)
stop_allowed: false
```

Without this state, the compiler can often tell that prose-only termination is bad, but cannot reliably decide the correct next action.

### 2. Recommended Tool Generation Is Weak

`mine.py` currently ranks recommended tools mostly through context-token and schema-token overlap, plus simple file/path literal bonuses. This can work for trivial or single-tool cases, but it is not a reliable semantic action planner.

The compiler path copies `failure_ir.recommended_tools` into `DecisionPolicySpec` and `NextToolPolicySpec`. If mining produces an empty list, runtime actuation cannot happen.

### 3. Required Tool Choice Is Only a Mode, Not a Tool Selector

The runtime intentionally does not force a specific tool name. When enabled, `tool_choice="required"` only asks the model to call some tool. It does not guarantee the selected or recommended tool is called, and it does not guarantee arguments are correct.

This is safe as a first boundary, but it means required mode cannot substitute for a real next-action compiler.

### 4. Argument-Level Policy Is Missing

BFCL scoring requires exact tool and exact arguments. A tool-level recommendation is insufficient if parameters are not grounded from literals or prior tool outputs.

The missing layer is an argument binding policy:

```yaml
action:
  tool: cat
  args:
    file_name: first_basename(last_tool_output.matches)
grounding:
  source: prior_tool_output
  field: matches
  transform: first_basename
```

### 5. Runtime Telemetry Only Proves Activated Plans

Current validation fields are useful after a plan activates. They are not sufficient to diagnose why no plan activated.

The runtime should record plan attempts and non-activation reasons:

- no policy matched
- activation predicate unmet
- recommended tools empty
- recommended tools unavailable in current request schema
- selected tool unavailable
- required mode disabled

This must be recorded even when no request patch is applied.

### 6. Selector Is Aggregate, Not Causal

The selector correctly handles target score, holdout regression, route consistency, manifests, and paired reruns. It does not yet prove which policy fixed which case.

Phase-2 needs case-level causal attribution:

| Case | Baseline Action | Soft Action | Required Action | Expected Tool | Changed | Fixed | Regressed |
| --- | --- | --- | --- | --- | --- | --- | --- |

Aggregate accuracy remains necessary, but it should not be the only acceptance signal for policy claims.

### 7. History Exists But Does Not Yet Prove Evolution

History can store and retrieve policy units, but the main claim is not proven until history-derived policies produce executable candidates that improve or stabilize future iterations.

The required evidence is longitudinal:

- failure rate decreases
- policy reuse increases
- new patch count decreases
- holdout regression remains bounded

## Target Method: Causal Tool-State Policy Compiler

The next Phase-2 target is a minimal Causal Tool-State Policy Compiler, abbreviated here as CTSPC.

The goal is not to train model weights. The goal is to compile reusable, request-local tool-state transition policies from success and failure traces.

The intended policy object is:

```yaml
state:
  last_tool: find
  last_output_has: matches
  user_intent: read_or_output_file
action:
  tool: cat
  args:
    file_name: first_basename(last_output.matches)
stop_allowed: false
confidence: 0.86
source:
  failure_label: [POST_TOOL, ACTIONABLE_NO_TOOL_DECISION]
  evidence: success_failure_contrast
```

This reframes Phase-2 from:

```text
failure -> prompt/repair patch
```

to:

```text
tool-state -> candidate action -> argument binding -> bounded validation -> reusable policy
```

## P0 Plan

### P0.1 Record Next-Tool Plan Attempts

Add request-side telemetry that records every `_next_tool_policy_plan()` attempt, including non-activation reasons.

Required fields:

- `next_tool_plan_attempted`
- `next_tool_plan_activated`
- `next_tool_plan_blocked_reason`
- `available_tools`
- `candidate_recommended_tools`
- `matched_recommended_tools`
- `activation_predicate_status`
- `selected_next_tool`
- `tool_choice_mode`

Primary files:

- `src/grc/compiler/ir.py`
- `src/grc/runtime/engine.py`
- `src/grc/runtime/policy_executor.py`
- `scripts/analyze_repair_contribution.py`

Acceptance criterion:

- Even when no plan activates, traces explain why.

### P0.2 Make Recommended Tools Non-Empty And Explainable

Replace weak lexical-only recommendation with a bounded action candidate generator.

Candidate signals:

- current user intent
- available tool names and schemas
- prior tool name
- prior tool output keys and values
- explicit literals from user context
- successful trace next-action patterns
- failed trace state at wrong-stop point

Primary files:

- `src/grc/compiler/mine.py`
- new `src/grc/compiler/tool_state.py` if needed
- new `src/grc/compiler/action_candidates.py` if needed
- `src/grc/compiler/trace_to_patch.py`

Acceptance criterion:

- For known actionable no-tool and post-tool prose cases, compiled `policy_unit.yaml` contains non-empty `recommended_tools` with evidence.

### P0.3 Build 20 Known Actionable Smoke Cases

Create a small deterministic smoke set before another full BFCL run.

Each case should verify:

- `policy_next_tool:activated`
- `selected_next_tool != null`
- `tool_choice_mode = required` when required mode is enabled
- `next_tool_emitted = true`
- `next_tool_matches_recommendation = true`

This is not a score benchmark. It is a wiring and causality check.

Primary files:

- `tests/test_runtime_engine.py`
- `tests/test_trace_to_patch.py`
- new fixtures under `tests/fixtures/phase2_next_action/` if needed

### P0.4 Do Not Rerun Required Full Validation Yet

Do not spend another full validation round on `enable_required_next_tool_choice` until the smoke cases show real policy activation and non-empty recommendations.

## P1 Plan

### P1.1 Add Tool-State IR

Introduce a structured state representation that includes:

- last tool
- prior tool output fields
- explicit literals
- current request intent family
- available tool schema summary
- candidate argument bindings
- stop permission

This state should be derived from traces and be serializable in failure IR or sidecar records.

### P1.2 Add Argument Binding Policy

Extend policy units from tool-only recommendation to tool plus arguments.

Binding rules should remain request-local and auditable:

- literal-to-argument binding
- prior-output-field-to-argument binding
- basename/path transforms
- first-match selection
- schema validation before activation

Acceptance criterion:

- The compiler can explain both why a tool was selected and where each required argument came from.

### P1.3 Mine Success Traces

Do not learn only from failures. Mine successful traces for state -> next-action patterns and contrast them with failed wrong-stop traces.

Expected output:

```yaml
pattern:
  state_signature: ...
  next_action:
    tool: ...
    arg_bindings: ...
support:
  success_cases: [...]
  failure_cases: [...]
```

### P1.4 Case-Level Causal Selector

Add reports that compare baseline, soft, and required variants at the case level.

Required metrics:

- policy hit count
- next-action conversion
- recommended-tool match
- argument binding validity
- case fix count
- case regression count
- net case gain
- holdout regression

Aggregate accuracy remains in the report, but policy acceptance should also require positive case-level conversion.

## P2 Plan

### P2.1 History-Driven Longitudinal Evaluation

Use history as a real prior, not only as metadata.

Required evidence:

- reused policies become executable candidates
- reused policies compete against fresh policies
- accepted or retained policies influence the next iteration
- new patch count falls over iterations

### P2.2 Expand Beyond The Current Slice Only After Conversion Works

Do not expand to more benchmark slices until:

- next-tool policy activation is observable
- recommended-tool match is non-zero
- argument binding is validated
- holdout regression remains bounded

## Anti-Overfitting Rules

- Do not hard-code BFCL case IDs.
- Do not hard-code benchmark filenames or sample IDs.
- Keep policies request-local.
- Separate compatibility repairs from decision-policy gains.
- Keep raw traces, `.file_locks`, and full BFCL result trees out of `main`.
- Commit compact reports, manifests, summaries, and reproducible protocol notes only.

## Completion Criteria

Phase-2 should not be called complete when only taxonomy and repairs work.

The next milestone is reached when all of the following are true:

- A 20-case smoke suite shows non-zero and correct next-tool activation.
- `policy_unit.yaml` contains non-empty `recommended_tools` and argument binding evidence for target families.
- Runtime traces record both activation and non-activation reasons.
- `multi_turn_miss_param` reports include case-level conversion, not only top-line accuracy.
- Required mode is accepted only if it beats soft mode on target, does not regress holdout, and improves at least one target family in conversion and scorer success.
- History-derived policies become executable candidates and produce longitudinal reuse evidence.

## Near-Term Do-Not-Do List

- Do not add more compatibility repairs as the main Phase-2 contribution.
- Do not rerun a full required next-tool experiment before recommendations and telemetry are fixed.
- Do not claim self-evolution until history changes executable candidate selection and produces longitudinal signal.
- Do not rely on aggregate score alone to justify a policy.

## Next Recommended Work Order

1. Add plan-attempt telemetry and non-activation reasons.
2. Add a 20-case next-action smoke suite.
3. Strengthen `recommended_tools` generation using tool-state and success-trace contrast.
4. Add argument binding policy for at least file/path-style actions.
5. Add case-level causal reports.
6. Only then rerun the soft vs required validation.

