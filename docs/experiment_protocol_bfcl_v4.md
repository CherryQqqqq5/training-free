# BFCL V4 Phase-1 Protocol

Failure attribution vocabulary (`error_type` / issue `kind`) is fixed for Phase-1 reporting in [failure_taxonomy.md](failure_taxonomy.md).

## Fixed Evaluator

- evaluator package: `bfcl-eval==2025.12.17`
- official reproduction anchor: checkout `f7cf735`
- policy: do not modify BFCL evaluator internals

These values are pinned in [`configs/bfcl_v4_phase1.env`](/Users/cherry/Documents/trainingfree/configs/bfcl_v4_phase1.env).

## Fixed Upstream Configuration

- upstream protocol: OpenAI-compatible `v1/chat/completions`
- default upstream relay profile: `openrouter` (override with `GRC_UPSTREAM_PROFILE=novacode` if needed)
- default BFCL evaluator alias: `gpt-4o-mini-2024-07-18-FC`
- default OpenRouter upstream route: `x-ai/grok-3-beta`
- default BFCL runtime config: [`configs/runtime_bfcl_structured.yaml`](/Users/cherry/.codex/worktrees/3253/training-free/configs/runtime_bfcl_structured.yaml)
- generic runtime config: [`configs/runtime.yaml`](/Users/cherry/.codex/worktrees/3253/training-free/configs/runtime.yaml)
- recommended override path: `GRC_UPSTREAM_BASE_URL`

`base_url` and API key env var are operator supplied, but Phase-1 runs must keep evaluator version, BFCL alias, upstream route, and endpoint protocol fixed across baseline and candidate runs. The proxy now accepts relay profiles:

- `novacode`: default `gpt-5.4`
- `openrouter`: default `x-ai/grok-3-beta`

`GRC_BFCL_MODEL` is passed to `bfcl --model`. `GRC_UPSTREAM_MODEL` is the real provider model sent by `grc serve`; do not set it to a BFCL `*-FC` alias.

The proxy accepts `GRC_UPSTREAM_PROFILE`, `GRC_UPSTREAM_BASE_URL`, `GRC_UPSTREAM_MODEL`, and provider-specific env vars so runs do not require editing the tracked config file.

Benchmark-specific compatibility rules belong in the BFCL runner/config layer, not in generic runtime defaults. The BFCL runners therefore default to `configs/runtime_bfcl_structured.yaml`, while the core runtime remains conservative under `configs/runtime.yaml`.

## Suite Selection

Phase-1 is BFCL-first and should prefer the evaluator default full suite. The new runners intentionally omit `--test-category` unless `GRC_BFCL_TEST_CATEGORY` is explicitly set.

- default: evaluator default full-suite execution
- allowed override: set `GRC_BFCL_TEST_CATEGORY` only for subset ablations
- `--run-ids` is disabled by default; enable it only by setting `GRC_BFCL_USE_RUN_IDS=1`
- reporting rule: every run must record the exact category string used in `metrics.json`

This keeps baseline and patched runs aligned without hard-coding a partial subset into the repo or accidentally switching into `test_case_ids_to_generate.json` mode.

## Official Runners

- baseline: [`scripts/run_bfcl_v4_baseline.sh`](/Users/cherry/Documents/trainingfree/scripts/run_bfcl_v4_baseline.sh)
- candidate: [`scripts/run_bfcl_v4_patch.sh`](/Users/cherry/Documents/trainingfree/scripts/run_bfcl_v4_patch.sh)
- smoke: [`scripts/run_phase1_smoke.sh`](/Users/cherry/Documents/trainingfree/scripts/run_phase1_smoke.sh)
- aggregate: [`scripts/aggregate_bfcl_metrics.py`](/Users/cherry/Documents/trainingfree/scripts/aggregate_bfcl_metrics.py)
- ablation loop: [`scripts/run_phase1_ablation.sh`](/Users/cherry/Documents/trainingfree/scripts/run_phase1_ablation.sh)

Baseline cleanliness rule:

- default baseline rules dir is `rules/baseline_empty/`
- baseline runner fails if that directory contains any YAML patch unless `GRC_ALLOW_DIRTY_BASELINE_RULES=1`

Each run must emit:

- `metrics.json`
- `repairs.jsonl`
- `failure_summary.json`
- `run_manifest.json`

Each candidate directory must additionally contain:

- `rule.yaml`
- `compile_status.json`
- `accept.json`

Archive rule:

- accepted candidates are copied to `rules/accepted/<patch_id>/`
- rejected candidates are copied to `rules/rejected/<patch_id>/`
- active accepted runtime rules are materialized as `rules/active/<patch_id>.yaml`

Rerun cleanliness rule:

- BFCL runners clean the current run's `bfcl/result`, `bfcl/score`, and `traces` by default before generation.
- Set `GRC_BFCL_CLEAN_RUN=0` only when intentionally resuming/debugging a run.
- Generation/evaluation pass explicit `--result-dir` and `--score-dir` under the run root and use `--allow-overwrite` so stale BFCL rows do not pollute subset evaluation.

## Aggregation

Phase-1 aggregation records:

- overall `acc`
- overall `cost`
- overall `latency`
- subset scores when BFCL outputs expose them
- `repair_count`
- `validation_issue_count`
- `fallback_count`
- derived `regression` versus baseline subset scores

Aggregation additionally records experiment validity metadata:

- `evaluation_status`
- `artifact_validity_issues`
- `resolved_result_sources`
- `resolved_score_sources`

`evaluation_status=complete` means the run can recover:

- overall `acc`
- at least one subset metric for the current `test_category`
- at least one result source
- at least one score source
- non-empty `metric_sources`
- a valid trace summary (`trace_count > 0`)

If any of the above is missing, the run is `incomplete` and must not enter Pareto selection. Incomplete runs are not represented as synthetic `acc=0.0` candidates.

The selector compares baseline and candidate on a Pareto-style rule over `acc`, `cost`, `latency`, and `regression`.

## Accept / Reject Rule

Accept a candidate only if it dominates baseline:

- `acc` greater than or equal to baseline
- `cost` less than or equal to baseline
- `latency` less than or equal to baseline
- `regression` less than or equal to baseline
- at least one of the above is strictly better

Otherwise reject the candidate and archive its evidence under `rules/rejected/`.

Before Pareto comparison, the selector must also verify:

- baseline and candidate both have `evaluation_status=complete`
- candidate `compile_status` is `actionable_patch`
- baseline and candidate `run_manifest.json` agree on:
  - `protocol_id`
  - `test_category`
  - `bfcl_model_alias`
  - `upstream_profile`
  - `upstream_model_route`

`git_dirty` does not block a run, but it must be recorded in the manifest and treated as a reproducibility warning.
