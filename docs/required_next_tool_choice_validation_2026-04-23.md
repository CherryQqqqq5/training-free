# Required Next-Tool Validation Result

Date: 2026-04-23

This note records the final result of the restrained Phase-2 validation round for `runtime_policy.enable_required_next_tool_choice`.

## Question

With the same policy ruleset and the same upstream route, does enabling `runtime_policy.enable_required_next_tool_choice` create real net gain over the default soft recommendation path?

## Fixed Inputs

- Repo root: `/cephfs/qiuyn/training-free`
- Policy ruleset: `/cephfs/qiuyn/training-free-archive/rules/rejected/fresh_02_20260423_232951`
- Baseline ruleset: `/cephfs/qiuyn/training-free/rules/baseline_empty`
- Validation root: `/cephfs/qiuyn/training-free/outputs/phase2_validation/required_next_tool_choice_v1`
- Compact artifact root: `outputs/artifacts/phase2/required_next_tool_choice_v1`

The validation used two runtime snapshots:

- `configs/runtime_soft.yaml`: `runtime_policy.enable_required_next_tool_choice: false`
- `configs/runtime_required.yaml`: `runtime_policy.enable_required_next_tool_choice: true`

## Run Matrix

| Run | Slice | Ruleset | Mode | Route | Accuracy | Correct Count |
| --- | --- | --- | --- | --- | ---: | ---: |
| `baseline_target` | `multi_turn_miss_param` | `baseline_empty` | `soft` | `x-ai/grok-3-beta` | 37.0% | 74 / 200 |
| `soft_target` | `multi_turn_miss_param` | `fresh_02` | `soft` | `x-ai/grok-3-beta` | 39.5% | 79 / 200 |
| `required_target` | `multi_turn_miss_param` | `fresh_02` | `required` | `x-ai/grok-3-beta` | 38.0% | 76 / 200 |
| `baseline_holdout` | `simple_python` | `baseline_empty` | `soft` | `x-ai/grok-3-beta` | 95.25% | 381 / 400 |
| `soft_holdout` | `simple_python` | `fresh_02` | `soft` | `x-ai/grok-3-beta` | 94.25% | 377 / 400 |
| `required_holdout` | `simple_python` | `fresh_02` | `required` | `x-ai/grok-3-beta` | 94.50% | 378 / 400 |

All runs completed without route mismatch. Proxy traffic was healthy, with no observed 5xx, auth, timeout, traceback, or trace-write failure.

## Verdict

Final verdict: `neutral`.

Required mode did not improve the target slice:

- Soft target: `39.5%`
- Required target: `38.0%`
- Difference: `-1.5 pp`, or `-3 / 200` cases

Required mode did not create meaningful holdout regression:

- Soft holdout: `94.25%`
- Required holdout: `94.50%`
- Difference: `+0.25 pp`, or `+1 / 400` case

This is not a positive milestone because the required target score is lower than the soft target score and there is no measured family-level policy conversion.

## Taxonomy Readout

Target taxonomy summary:

| Run | Failure Count | Top Families |
| --- | ---: | --- |
| `baseline_target` | 1217 | `(POST_TOOL,EMPTY_TOOL_CALL)`, `(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)`, `(POST_TOOL,POST_TOOL_PROSE_SUMMARY)` |
| `soft_target` | 1566 | `(POST_TOOL,EMPTY_TOOL_CALL)`, `(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)`, `(POST_TOOL,TERMINATION_INADMISSIBLE)` |
| `required_target` | 1534 | `(POST_TOOL,EMPTY_TOOL_CALL)`, `(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)`, `(POST_TOOL,TERMINATION_INADMISSIBLE)` |

Soft vs required target deltas:

- `(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)`: `353 -> 344` in taxonomy table, while raw validation issue count was `66 -> 72`
- `(POST_TOOL,POST_TOOL_PROSE_SUMMARY)`: `287 -> 272`
- `(POST_TOOL,TERMINATION_INADMISSIBLE)`: `353 -> 344`
- `(POST_TOOL,EMPTY_TOOL_CALL)`: `483 -> 484`

Required mode reduced some prose/termination symptoms, but the reduction did not translate into more correct BFCL cases.

## Repair And Policy Conversion

The repair reports show the target runs are still dominated by `coerce_no_tool_text_to_empty`.

Soft target:

- `coerce_no_tool_text_to_empty`: `442`
- `resolve_contextual_string_arg`: `75`
- `strip_assistant_content_with_tool_calls`: `34`

Required target:

- `coerce_no_tool_text_to_empty`: `434`
- `resolve_contextual_string_arg`: `74`
- `strip_assistant_content_with_tool_calls`: `32`

Policy conversion was not measurable:

- `policy_validation` records: `0`
- `tool_choice_mode="required"` records: `0`
- `selected_next_tool` records: `0`
- `next_tool_emitted` records: `0`
- `next_tool_matches_recommendation` records: `0`

The fixed `fresh_02` ruleset contains `decision_policy.recommended_tools: []`, so the required-mode switch had no concrete next-tool recommendation to harden.

## Interpretation

This run tested the configured switch, but it did not test a real action policy. The active policy artifact is still mostly a constraint system:

- it says not to stop with prose-only narration
- it records or coerces no-tool prose responses
- it does not yet recommend a concrete next tool
- it does not emit observable case-level conversion telemetry

The required-mode path should not be rerun at full scale until two prerequisites are satisfied:

- compiler output includes non-empty `recommended_tools` for `ACTIONABLE_NO_TOOL_DECISION` and `POST_TOOL_PROSE_SUMMARY`
- runtime traces record `policy_validation`, including `policy_hits`, `selected_next_tool`, `tool_choice_mode`, `next_tool_emitted`, and `next_tool_matches_recommendation`

## Compact Artifacts

Committed compact artifacts:

- `outputs/artifacts/phase2/required_next_tool_choice_v1/run_matrix.json`
- `outputs/artifacts/phase2/required_next_tool_choice_v1/run_matrix.md`
- `outputs/artifacts/phase2/required_next_tool_choice_v1/validation_summary.json`
- `outputs/artifacts/phase2/required_next_tool_choice_v1/validation_summary.md`
- `outputs/artifacts/phase2/required_next_tool_choice_v1/target_taxonomy_report.json`
- `outputs/artifacts/phase2/required_next_tool_choice_v1/target_taxonomy_report.md`
- `outputs/artifacts/phase2/required_next_tool_choice_v1/*_repair_report.json`
- `outputs/artifacts/phase2/required_next_tool_choice_v1/*_repair_report.md`

Raw traces, logs, BFCL result trees, and full run directories remain on the server only.
