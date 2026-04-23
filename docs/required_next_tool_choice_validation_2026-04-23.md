# Required Next-Tool Validation Snapshot

Date: 2026-04-23

This note records the launch state of the restrained Phase-2 validation round for `enable_required_next_tool_choice`. It is intentionally a status snapshot, not a final result claim.

## Validation Question

With the same policy rule set and the same upstream route, does enabling `runtime_policy.enable_required_next_tool_choice` create real net gain over the default soft recommendation path?

## Fixed Inputs

- Repo commit: `e82ea36413351949acb853b1d089cea81ca06435`
- Repo root: `/cephfs/qiuyn/training-free`
- Policy ruleset: `/cephfs/qiuyn/training-free-archive/rules/rejected/fresh_02_20260423_232951`
- Baseline ruleset: `/cephfs/qiuyn/training-free/rules/baseline_empty`
- Validation root: `/cephfs/qiuyn/training-free/outputs/phase2_validation/required_next_tool_choice_v1`
- Compact artifact root: `/cephfs/qiuyn/training-free/outputs/artifacts/phase2/required_next_tool_choice_v1`

## Runtime Config Snapshots

Two config snapshots were generated under the validation root:

- `configs/runtime_soft.yaml`
  - identical to current `configs/runtime_bfcl_structured.yaml` except `runtime_policy.enable_required_next_tool_choice: false`
  - SHA1: `89c5de7f73d659c5486cf38dcbf5eb7bdf4db6e6`
- `configs/runtime_required.yaml`
  - identical to current `configs/runtime_bfcl_structured.yaml` except `runtime_policy.enable_required_next_tool_choice: true`
  - SHA1: `f00142487dd48a1bb2ad315d2d53f47389065058`

## Run Matrix

The validation driver is running the following six jobs:

| Run | Slice | Ruleset | Mode | Port |
| --- | --- | --- | --- | ---: |
| `baseline_target` | `multi_turn_miss_param` | `baseline_empty` | `soft` | 8030 |
| `baseline_holdout` | `simple_python` | `baseline_empty` | `soft` | 8031 |
| `soft_target` | `multi_turn_miss_param` | `fresh_02` | `soft` | 8040 |
| `soft_holdout` | `simple_python` | `fresh_02` | `soft` | 8041 |
| `required_target` | `multi_turn_miss_param` | `fresh_02` | `required` | 8050 |
| `required_holdout` | `simple_python` | `fresh_02` | `required` | 8051 |

## Current Status

- Driver PID: `4585`
- Current step: `baseline_target`
- Driver path: `/cephfs/qiuyn/training-free/outputs/phase2_validation/required_next_tool_choice_v1/run_validation.py`
- Status files: `/cephfs/qiuyn/training-free/outputs/phase2_validation/required_next_tool_choice_v1/step_status/`
- Logs: `/cephfs/qiuyn/training-free/outputs/phase2_validation/required_next_tool_choice_v1/logs/`
- Monitoring heartbeat: `watch-required-next-tool-v1`

At launch-time inspection:

- `baseline_target` proxy preflight passed
- upstream route observed in preflight: `x-ai/grok-3`
- environment check passed for `OPENROUTER_API_KEY`
- BFCL generation for `multi_turn_miss_param` had started successfully
- no `failure_state.json` had been emitted yet

## Expected Final Deliverables

When the run completes, the compact output package should contain:

- `run_matrix.json` / `run_matrix.md`
- `target_taxonomy_report.json` / `target_taxonomy_report.md`
- `soft_target_repair_report.json` / `.md`
- `required_target_repair_report.json` / `.md`
- `soft_holdout_repair_report.json` / `.md`
- `required_holdout_repair_report.json` / `.md`
- `validation_summary.json` / `validation_summary.md`

## Discipline

- Raw traces, BFCL result trees, logs, and live run directories remain on the server only.
- This repository update records only the experiment definition and current status snapshot.
- Do not treat this validation as complete until `validation_summary.json` exists and the route-consistency guard passes for all six runs.
