# Phase-2 Run Summary

Date: 2026-04-23

This table summarizes the currently available `multi_turn_miss_param` Phase-2 runs on the server path `/cephfs/qiuyn/training-free/outputs`. Scores are taken from BFCL score CSVs or normalized `metrics.json` artifacts when present. Historical rows are retained only when the original artifact is not available on the current server.

| Run / Version | Slice | Accuracy | Correct Count | Dominant Failure | Claim Status |
|---|---:|---:|---:|---|---|
| `primary_v2` | `multi_turn_miss_param` | 0.0% | 0 / 200 | Run failed behaviorally; no useful tool-use recovery | Rejected |
| `primary_v3` | `multi_turn_miss_param` | 35.0% | 70 / 200 | No-tool / premature-stop failures remained dominant | Evidence Only |
| `baseline` | `multi_turn_miss_param` | 36.5% | 73 / 200 | `(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)` dominated taxonomy report | Baseline |
| `primary_v4` | `multi_turn_miss_param` | 40.0% | 80 / 200 | `ACTIONABLE_NO_TOOL_DECISION` decreased, but `EMPTY_TOOL_CALL`, `POST_TOOL_PROSE_SUMMARY`, and `TERMINATION_INADMISSIBLE` increased as residual buckets | Evidence Only |
| `rerun_v4` | `multi_turn_miss_param` | 43.5% | 87 / 200 | Historical console result; run artifacts not present on current server | Claimable historical evidence |
| `iter_003_execute` | `multi_turn_miss_param` + `simple_python` holdout | Incomplete | N/A | Driver/process ended without final outputs; archived as incomplete | Rejected for formal claim |
| `iter_004_execute` / `fresh_02` target | `multi_turn_miss_param` | 42.0% | 84 / 200 | Fresh policy proposal for `(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)` with explicit-context literals | Evidence Only until rerun + selector finalization |
| `iter_004_execute` / `fresh_02` holdout | `simple_python` | 95.0% | 380 / 400 | No validation issues; only 5 contextual string repairs | Safety holdout passes so far |
| `iter_004_execute` / `fresh_02` paired rerun | `multi_turn_miss_param` | Pending | Pending | Rerun active; final metrics, paired-rerun report, accept decision not emitted yet | Pending |

## Current `iter_004_execute` Status

- Selected proposal: `fresh_02`.
- Proposal mode: `fresh`.
- Failure signature: `(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)`, `literals_pattern=explicit_context_literals`, predicates `prior_explicit_literals_present`, `prior_tool_outputs_present`, `tools_available`.
- Target result: `42.0%` (`84 / 200`), which is `+5.5 pp` over the `36.5%` baseline and `+2.0 pp` over `primary_v4=40.0%`, but still `-1.5 pp` below the historical `rerun_v4=43.5%`.
- Holdout result: `simple_python=95.0%` (`380 / 400`), matching the baseline holdout and showing no measured holdout regression so far.
- Paired rerun is still active. Do not treat `iter_004_execute` as a final claim until `paired_rerun.json`, `accept.json`, and `evolution_iteration_summary.json` exist.

## Artifact Locations

- Current execute root: `/cephfs/qiuyn/training-free/outputs/phase2_evolution/iter_004_execute`
- Current proposal metrics: `/cephfs/qiuyn/training-free/outputs/phase2_evolution/iter_004_execute/proposals/fresh_02/metrics.json`
- Current holdout metrics: `/cephfs/qiuyn/training-free/outputs/phase2_evolution/iter_004_execute/holdout_run/artifacts/metrics.json`
- Git-tracked compact summary: `outputs/artifacts/phase2/iter_004_execute_current/status_summary.json`
- Git-tracked taxonomy snapshot: `outputs/artifacts/phase2/iter_004_execute_current/taxonomy_report.md`
- Full traces and logs remain on the server and are intentionally not committed.

## Notes

- `primary_v2`, `primary_v3`, and `primary_v4` are useful for trend discussion, but only `primary_v4` and `iter_004_execute` currently have directly inspected server-side artifacts in this pass.
- `rerun_v4=43.5%` remains the strongest historical top-line evidence, but its artifacts were not found under the current new-server output tree.
- `iter_004_execute` is the first current-server evolution execute run with completed target and clean holdout metrics, but it is still pending paired rerun and selector acceptance.
