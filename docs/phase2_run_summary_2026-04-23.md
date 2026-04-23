# Phase-2 Run Summary

Date: 2026-04-23

This table summarizes the currently available `multi_turn_miss_param` Phase-2 runs on the server path `/cephfs/qiuyn/training-free/outputs/phase2_runs`. Scores are taken from BFCL score CSVs when present. Historical rows are included only when they were observed in the console logs but are not currently present on the new server filesystem.

| Run / Version | Slice | Accuracy | Correct Count | Dominant Failure | Claim Status |
|---|---:|---:|---:|---|---|
| `primary_v2` | `multi_turn_miss_param` | 0.0% | 0 / 200 | Run failed behaviorally; no useful tool-use recovery | Rejected |
| `primary_v3` | `multi_turn_miss_param` | 35.0% | 70 / 200 | No-tool / premature-stop failures remained dominant | Evidence Only |
| `primary_v4` | `multi_turn_miss_param` | 40.0% | 80 / 200 | No-tool / wrong-stop failures reduced but still dominant | Evidence Only |
| `rerun_v4` | `multi_turn_miss_param` | 43.5% | 87 / 200 | Historical console result; run artifacts not present on current server | Claimable |
| `primary_v5` / `iter_003_execute` | `multi_turn_miss_param` + `simple_python` holdout | Pending | Pending | Active evolution execute run; final metrics not yet emitted | Pending |

## Artifact Locations

- Server run roots: `/cephfs/qiuyn/training-free/outputs/phase2_runs`
- Current execute root: `/cephfs/qiuyn/training-free/outputs/phase2_evolution/iter_003_execute`
- Analysis reports: `/cephfs/qiuyn/training-free/outputs/phase2_analysis`
- Current proxy log: `/tmp/grc_patch_proxy.log`

## Notes

- `primary_v2`, `primary_v3`, and `primary_v4` have BFCL score files on the current server.
- `rerun_v4=43.5%` is supported by prior console output in this thread but its artifacts were not found under the current new-server output tree.
- `iter_003_execute` is still active or incomplete: no final `candidate_run/artifacts/metrics.json`, `holdout_run/artifacts/metrics.json`, `proposals/fresh_00/accept.json`, or `evolution_iteration_summary.json` was found at the time of this summary.
