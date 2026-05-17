# Stage 1 ABHE-v0 Next Fresh-Slice Verification

This document summarizes the next ABHE-v0 bounded dev smoke. It is diagnostic dev evidence only. It is not full BFCL, not holdout, not a performance/+3pp/SOTA/Huawei acceptance claim, and it does not update the archive.

## Scope

The run verifies whether the frozen v2 mechanisms generalize to a new fresh balanced slice and separately probes two residual child mechanisms.

Frozen mechanisms:

- `post_tool_continuation_guard_v0`
- `no_tool_boundary_v0`

New child mechanisms:

- `missing_param_epistemic_gate_v0`
- `long_context_state_retrieval_v0`

The new balanced slice contains 54 compact identifiers with zero overlap against the 20-case smoke slice, old expanded slice, and archive/discovery compact hashes. `live_relevance` has only limited remaining BFCL rows after prior slice exclusion, so the new balanced slice uses 6 `live_relevance` compact identifiers rather than 8.

## Arms

| Arm | Mechanisms | Role |
| --- | --- | --- |
| `baseline` | none | route baseline |
| `frozen_v2` | post-tool continuation + no-tool boundary | generalization check |
| `missing_param_gate` | frozen v2 + missing-param epistemic gate | residual miss-param check |
| `long_context_retrieval` | frozen v2 + long-context state retrieval | residual long-context check |
| `both` | frozen v2 + both child mechanisms | interaction/conflict check |

## Result

| Arm | Passed / Total | Accuracy | Interpretation |
| --- | ---: | ---: | --- |
| baseline | 30 / 54 | 0.555556 | baseline already passes long-context/base/miss-func/live-relevance scorer units |
| frozen_v2 | 46 / 54 | 0.851852 | frozen v2 generalizes on this fresh balanced slice |
| missing_param_gate | 46 / 54 | 0.851852 | no independent improvement over frozen v2; `multi_turn_miss_param` remains 0/8 |
| long_context_retrieval | 38 / 54 | 0.703704 | no target upside; non-target `multi_turn_miss_func` regression observed |
| both | 46 / 54 | 0.851852 | no gain over frozen v2; no combined uplift |

## Mechanism Conclusions

`post_tool_continuation_guard_v0` should remain a child mechanism candidate. It preserved the positive signal on a new fresh slice without touching holdout or full BFCL.

`no_tool_boundary_v0` should become a regression suite / guard. It held `irrelevance`, `live_irrelevance`, and `live_relevance` at 22/22 on the fresh balanced slice.

`missing_param_epistemic_gate_v0` did not move the target substratum: `multi_turn_miss_param` stayed 0/8. The likely issue is that compact prompt guidance is too weak for BFCL miss-param scorer behavior; next work should inspect sanitized scorer-unit traces and design a stronger slot-state/tool-recovery mechanism before rerunning.

`long_context_state_retrieval_v0` was not needed on this fresh balanced slice because baseline and frozen v2 already passed `multi_turn_long_context` 8/8. The single-child arm regressed `multi_turn_miss_func`, so it should not be promoted without redesign or narrower routing.

## Evidence Boundary

The paired matrix is scorer-unit/category-level plus hash-only compact rows. Strict per-compact-case pass/fail is not available from the safe committed artifacts because BFCL selected compact identifiers can collapse into category scorer units. Disallowed benchmark/provider materials are absent from committed artifacts.

## Next Step

Do not proceed to full BFCL yet. The next useful step is a targeted redesign of `missing_param_epistemic_gate_v0`, using separately approved sanitized trace extraction for failed `multi_turn_miss_param` scorer units, followed by another fresh residual stress dev smoke. Archive changes should remain dry-run until independent verification exists.

## Sanitized Trace Audit

A sanitized audit sampled real trace files under `/tmp/abhe_v0_next_dev_smoke/balanced_verification` and persisted only field-presence counts, patch-marker counts, and hashed trace filenames in `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_next_trace_audit.json`. Disallowed benchmark/provider materials are absent from the committed audit.
