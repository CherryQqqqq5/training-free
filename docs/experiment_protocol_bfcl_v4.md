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
- default upstream model: `gpt-5.4`
- runtime config: [`configs/runtime.yaml`](/Users/cherry/Documents/trainingfree/configs/runtime.yaml)
- recommended override path: `GRC_UPSTREAM_BASE_URL`

`base_url` and API key env var are operator supplied, but Phase-1 runs must keep evaluator version, model id, and endpoint protocol fixed across baseline and candidate runs. The proxy now accepts relay profiles:

- `novacode`: default `gpt-5.4`
- `openrouter`: default `grok-3`

The proxy accepts `GRC_UPSTREAM_PROFILE`, `GRC_UPSTREAM_BASE_URL`, and provider-specific env vars so runs do not require editing the tracked config file.

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

Each candidate directory must additionally contain:

- `rule.yaml`
- `accept.json`

Archive rule:

- accepted candidates are copied to `rules/accepted/<patch_id>/`
- rejected candidates are copied to `rules/rejected/<patch_id>/`
- active accepted runtime rules are materialized as `rules/active/<patch_id>.yaml`

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

The selector compares baseline and candidate on a Pareto-style rule over `acc`, `cost`, `latency`, and `regression`.

## Accept / Reject Rule

Accept a candidate only if it dominates baseline:

- `acc` greater than or equal to baseline
- `cost` less than or equal to baseline
- `latency` less than or equal to baseline
- `regression` less than or equal to baseline
- at least one of the above is strictly better

Otherwise reject the candidate and archive its evidence under `rules/rejected/`.
