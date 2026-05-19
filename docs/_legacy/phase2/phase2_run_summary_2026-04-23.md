# Phase-2 Run Summary

Date: 2026-04-23

This table summarizes the currently available `multi_turn_miss_param` Phase-2 runs on the server path `/cephfs/qiuyn/training-free/outputs`. Scores are taken from BFCL score CSVs or normalized `metrics.json` artifacts when present. Historical rows are retained only when the original artifact is not available on the current server.

| Run / Version | Slice | Accuracy | Correct Count | Dominant Failure | Claim Status |
|---|---:|---:|---:|---|---|
| `primary_v2` | `multi_turn_miss_param` | 0.0% | 0 / 200 | Run failed behaviorally; no useful tool-use recovery | Rejected |
| `primary_v3` | `multi_turn_miss_param` | 35.0% | 70 / 200 | No-tool / premature-stop failures remained dominant | Evidence Only |
| `baseline` | `multi_turn_miss_param` | 36.5% | 73 / 200 | `(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)` dominated taxonomy report | Baseline |
| `primary_v4` | `multi_turn_miss_param` | 40.0% | 80 / 200 | `ACTIONABLE_NO_TOOL_DECISION` decreased, but `EMPTY_TOOL_CALL`, `POST_TOOL_PROSE_SUMMARY`, and `TERMINATION_INADMISSIBLE` remained residual buckets | Evidence Only |
| `rerun_v4` | `multi_turn_miss_param` | 43.5% | 87 / 200 | Historical console result; run artifacts not present on current server | Claimable historical evidence |
| `iter_003_execute` | `multi_turn_miss_param` + `simple_python` holdout | Incomplete | N/A | Driver/process ended without final outputs; archived as incomplete | Rejected for formal claim |
| `iter_004_execute` / `fresh_02` target | `multi_turn_miss_param` | 42.0% | 84 / 200 | Fresh policy proposal for `(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)` with explicit-context literals | Evidence Only |
| `iter_004_execute` / `fresh_02` holdout | `simple_python` | 95.0% | 380 / 400 | No validation issues; only 5 contextual string repairs | Safety holdout passes |
| `iter_004_execute` / `fresh_02` paired rerun | `multi_turn_miss_param` | 40.5% | 81 / 200 | Directionally consistent with primary target run, but selector rejected because baseline/candidate routes differed | Evidence Only / Protocol Rejected |
| `required_next_tool_choice_v1` soft target | `multi_turn_miss_param` | 39.5% | 79 / 200 | Soft prompt-biased policy using fixed `fresh_02` ruleset | Evidence Only |
| `required_next_tool_choice_v1` required target | `multi_turn_miss_param` | 38.0% | 76 / 200 | Required mode did not produce measurable next-tool policy conversion | Neutral / Not Claimable |
| `required_next_tool_choice_v1` soft holdout | `simple_python` | 94.25% | 377 / 400 | No validation issues; benign holdout behavior | Holdout OK |
| `required_next_tool_choice_v1` required holdout | `simple_python` | 94.50% | 378 / 400 | No validation issues; benign holdout behavior | Holdout OK |

## Required Next-Tool Validation

The required next-tool validation completed under `/cephfs/qiuyn/training-free/outputs/phase2_validation/required_next_tool_choice_v1`.

All six jobs used the same upstream route, `x-ai/grok-3-beta`, so the comparison passed the route-consistency guard. The final verdict is `neutral`: required mode did not beat soft mode on the target slice, while holdout stayed effectively flat.

Key readout:

- Baseline target: `37.0%` (`74 / 200`)
- Soft target: `39.5%` (`79 / 200`)
- Required target: `38.0%` (`76 / 200`)
- Baseline holdout: `95.25%` (`381 / 400`)
- Soft holdout: `94.25%` (`377 / 400`)
- Required holdout: `94.50%` (`378 / 400`)

The most important diagnostic is that traces showed no measurable policy actuation:

- `policy_validation` records: `0` across soft/required target and holdout runs
- `tool_choice_mode="required"` records: `0`
- `selected_next_tool` records: `0`
- `next_tool_emitted` records: `0`

The fixed `fresh_02` ruleset has `decision_policy.recommended_tools: []`, so enabling `runtime_policy.enable_required_next_tool_choice` did not give the runtime a concrete next-tool candidate to harden. The result should therefore be read as evidence that the current policy artifact is still constraint-heavy rather than action-policy-heavy.

Compact result package:

- `outputs/artifacts/phase2/required_next_tool_choice_v1/run_matrix.json`
- `outputs/artifacts/phase2/required_next_tool_choice_v1/validation_summary.json`
- `outputs/artifacts/phase2/required_next_tool_choice_v1/target_taxonomy_report.md`
- `outputs/artifacts/phase2/required_next_tool_choice_v1/*_repair_report.md`

## Artifact Locations

- Current validation root: `/cephfs/qiuyn/training-free/outputs/phase2_validation/required_next_tool_choice_v1`
- Current compact artifacts: `outputs/artifacts/phase2/required_next_tool_choice_v1`
- Full traces and BFCL result trees remain on the server and are intentionally not committed.

## Notes

- `rerun_v4=43.5%` remains the strongest historical top-line evidence, but its full artifacts were not found under the current new-server output tree.
- `iter_004_execute` is useful evidence because target and paired rerun were directionally consistent, but it is not an accepted claim because selector validation found an upstream route mismatch.
- The required next-tool validation shows that the next engineering step is not another full run. The next step is to make compiler output non-empty `recommended_tools` and make runtime trace policy conversion fields observable before rerunning required mode.
