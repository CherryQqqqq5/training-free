# ABHE-v0 Runtime Slot Controller Residual Analysis

## Scope

This is bounded residual dev-smoke evidence only. It is not full BFCL, not holdout, not performance evidence, and not a +3pp/SOTA/Huawei acceptance claim. The run uses compact identifiers and sanitized trace telemetry only.

## Fresh Residual Slice

- Slice artifact: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_residual_stress_slice_manifest.json`
- Slice hash: `sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c`
- Selected compact identifiers: 48
- Archive / prior-slice overlap: 0
- Target category: `multi_turn_miss_param` with 24 compact identifiers
- Regression controls: `multi_turn_miss_func`, `multi_turn_base`, `multi_turn_long_context`, `irrelevance`, `live_irrelevance`

## Result Summary

| Arm | Passed / 48 | Accuracy | Notes |
| --- | ---: | ---: | --- |
| baseline | 10 | 0.208333 | bounded dev smoke only |
| conditional_frozen_v2 | 10 | 0.208333 | no net gain over baseline on this slice |
| runtime_slot_controller_v2 | 34 | 0.708333 | score-positive on target bucket |

Category-level scorer-unit summary:

| Category | baseline | conditional_frozen_v2 | runtime_slot_controller_v2 |
| --- | ---: | ---: | ---: |
| multi_turn_miss_param | 0/24 | 0/24 | 24/24 |
| multi_turn_base | 6/6 | 6/6 | 6/6 |
| multi_turn_long_context | 4/4 | 0/4 | 0/4 |
| multi_turn_miss_func | 0/6 | 0/6 | 0/6 |
| irrelevance | 0/4 | 4/4 | 4/4 |
| live_irrelevance | 0/4 | 0/4 | 0/4 |

## Trace Audit Finding

The sanitized trace audit confirms the runtime slot controller patch was enabled for the runtime arm, but observed slot bind repairs were zero:

- `slot_controller_enabled_patch_count = 41`
- `slot_bind_repair_count = 0`
- No raw prompts, argument values, provider payloads, or scorer diffs are committed.

This means the score-positive result cannot yet be attributed to actual runtime slot binding. The honest interpretation is:

`runtime_slot_controller_v2` has a strong bounded score-positive diagnostic signal, but mechanism attribution is unconfirmed because the repair layer did not fire in committed telemetry.

## Current Mechanism Status

- `runtime_slot_controller_v2`: diagnostic score-positive, mechanism unconfirmed; do not promote until an actual bind-repair run or stricter per-case evidence confirms causality.
- `post_tool_continuation_guard_v0`: remains conditional, not a broad invariant; stress evidence still shows sensitivity in `multi_turn_long_context`.
- `no_tool_boundary_v0`: remains regression suite material for irrelevance controls.
- `missing_param_slot_recovery_controller_v1`: superseded by the runtime controller attempt, but the previous no-signal result remains valid negative evidence.
- `long_context_state_retrieval_v0`: remains narrow-router / regression-risk only.

## Next Required Action

Do not expand to full BFCL. The next loop should make mechanism attribution stricter:

1. Add telemetry that distinguishes provider-generated valid calls from controller-repaired calls without persisting raw values.
2. Add a no-provider proxy fixture where the controller must repair a missing required slot from a structured prior tool observation.
3. If BFCL is rerun, require `slot_bind_repair_count > 0` for promotion; otherwise mark score gains as nondeterministic or prompt/proxy side effects.
