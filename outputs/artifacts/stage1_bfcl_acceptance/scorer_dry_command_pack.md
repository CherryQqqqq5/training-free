# Stage1 BFCL Scorer Dry Command Pack

This artifact is a dry command pack only. It does not call the provider, BFCL,
a model, or a scorer, and it is not performance evidence.

The command templates become executable only after both gates are true:

- `GRC_CANDIDATE_POOL_PROMOTED=1`
- `GRC_SCORER_AUTHORIZED=1`

Required runtime variables:

- `GRC_BFCL_MODEL`
- `GRC_BFCL_DEV_CATEGORY`
- `GRC_BFCL_HOLDOUT_CATEGORY`
- `GRC_EXPLICIT_LITERAL_RULES_DIR`
- `GRC_NOOP_CONTROL_RULES_DIR`

Raw BFCL run roots stay under `/tmp/stage1_bfcl_scorer`. Compact run artifacts
land under `outputs/artifacts/stage1_bfcl_acceptance/scorer`.

## Dev Commands

```bash
test "${GRC_CANDIDATE_POOL_PROMOTED:-0}" = "1" || { echo 'candidate pool promotion required'; exit 2; }; test "${GRC_SCORER_AUTHORIZED:-0}" = "1" || { echo 'scorer authorization required'; exit 2; }; bash scripts/run_bfcl_v4_baseline.sh "${GRC_BFCL_MODEL}" /tmp/stage1_bfcl_scorer/dev/baseline 8111 "${GRC_BFCL_DEV_CATEGORY}" configs/runtime_bfcl_structured.yaml rules/baseline_empty /tmp/stage1_bfcl_scorer/dev/baseline/traces outputs/artifacts/stage1_bfcl_acceptance/scorer/dev/baseline/artifacts

test "${GRC_CANDIDATE_POOL_PROMOTED:-0}" = "1" || { echo 'candidate pool promotion required'; exit 2; }; test "${GRC_SCORER_AUTHORIZED:-0}" = "1" || { echo 'scorer authorization required'; exit 2; }; bash scripts/run_bfcl_v4_patch.sh "${GRC_BFCL_MODEL}" /tmp/stage1_bfcl_scorer/dev/explicit_literal_only 8112 "${GRC_BFCL_DEV_CATEGORY}" configs/runtime_bfcl_structured.yaml "${GRC_EXPLICIT_LITERAL_RULES_DIR}" /tmp/stage1_bfcl_scorer/dev/explicit_literal_only/traces outputs/artifacts/stage1_bfcl_acceptance/scorer/dev/explicit_literal_only/artifacts outputs/artifacts/stage1_bfcl_acceptance/scorer/dev/baseline/artifacts/metrics.json

test "${GRC_CANDIDATE_POOL_PROMOTED:-0}" = "1" || { echo 'candidate pool promotion required'; exit 2; }; test "${GRC_SCORER_AUTHORIZED:-0}" = "1" || { echo 'scorer authorization required'; exit 2; }; bash scripts/run_bfcl_v4_patch.sh "${GRC_BFCL_MODEL}" /tmp/stage1_bfcl_scorer/dev/noop_control 8113 "${GRC_BFCL_DEV_CATEGORY}" configs/runtime_bfcl_structured.yaml "${GRC_NOOP_CONTROL_RULES_DIR}" /tmp/stage1_bfcl_scorer/dev/noop_control/traces outputs/artifacts/stage1_bfcl_acceptance/scorer/dev/noop_control/artifacts outputs/artifacts/stage1_bfcl_acceptance/scorer/dev/baseline/artifacts/metrics.json
```

## Holdout Commands

```bash
test "${GRC_CANDIDATE_POOL_PROMOTED:-0}" = "1" || { echo 'candidate pool promotion required'; exit 2; }; test "${GRC_SCORER_AUTHORIZED:-0}" = "1" || { echo 'scorer authorization required'; exit 2; }; bash scripts/run_bfcl_v4_baseline.sh "${GRC_BFCL_MODEL}" /tmp/stage1_bfcl_scorer/holdout/baseline 8121 "${GRC_BFCL_HOLDOUT_CATEGORY}" configs/runtime_bfcl_structured.yaml rules/baseline_empty /tmp/stage1_bfcl_scorer/holdout/baseline/traces outputs/artifacts/stage1_bfcl_acceptance/scorer/holdout/baseline/artifacts

test "${GRC_CANDIDATE_POOL_PROMOTED:-0}" = "1" || { echo 'candidate pool promotion required'; exit 2; }; test "${GRC_SCORER_AUTHORIZED:-0}" = "1" || { echo 'scorer authorization required'; exit 2; }; bash scripts/run_bfcl_v4_patch.sh "${GRC_BFCL_MODEL}" /tmp/stage1_bfcl_scorer/holdout/explicit_literal_only 8122 "${GRC_BFCL_HOLDOUT_CATEGORY}" configs/runtime_bfcl_structured.yaml "${GRC_EXPLICIT_LITERAL_RULES_DIR}" /tmp/stage1_bfcl_scorer/holdout/explicit_literal_only/traces outputs/artifacts/stage1_bfcl_acceptance/scorer/holdout/explicit_literal_only/artifacts outputs/artifacts/stage1_bfcl_acceptance/scorer/holdout/baseline/artifacts/metrics.json

test "${GRC_CANDIDATE_POOL_PROMOTED:-0}" = "1" || { echo 'candidate pool promotion required'; exit 2; }; test "${GRC_SCORER_AUTHORIZED:-0}" = "1" || { echo 'scorer authorization required'; exit 2; }; bash scripts/run_bfcl_v4_patch.sh "${GRC_BFCL_MODEL}" /tmp/stage1_bfcl_scorer/holdout/noop_control 8123 "${GRC_BFCL_HOLDOUT_CATEGORY}" configs/runtime_bfcl_structured.yaml "${GRC_NOOP_CONTROL_RULES_DIR}" /tmp/stage1_bfcl_scorer/holdout/noop_control/traces outputs/artifacts/stage1_bfcl_acceptance/scorer/holdout/noop_control/artifacts outputs/artifacts/stage1_bfcl_acceptance/scorer/holdout/baseline/artifacts/metrics.json
```

## Run Schema Gates

Run after each compact run artifact is present:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_run_artifact_schema.py outputs/artifacts/stage1_bfcl_acceptance/scorer/dev/baseline --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_run_artifact_schema.py outputs/artifacts/stage1_bfcl_acceptance/scorer/dev/explicit_literal_only --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_run_artifact_schema.py outputs/artifacts/stage1_bfcl_acceptance/scorer/dev/noop_control --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_run_artifact_schema.py outputs/artifacts/stage1_bfcl_acceptance/scorer/holdout/baseline --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_run_artifact_schema.py outputs/artifacts/stage1_bfcl_acceptance/scorer/holdout/explicit_literal_only --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_run_artifact_schema.py outputs/artifacts/stage1_bfcl_acceptance/scorer/holdout/noop_control --compact --strict
```

## Paired Artifacts

Each paired comparison directory must contain:

- `paired_comparison.json`
- `acceptance_decision.json`
- `regression_report.json`
- `cost_latency_report.json`

The required paired roots are:

- `outputs/artifacts/stage1_bfcl_acceptance/paired/dev_explicit_literal`
- `outputs/artifacts/stage1_bfcl_acceptance/paired/dev_noop_control`
- `outputs/artifacts/stage1_bfcl_acceptance/paired/holdout_explicit_literal`
- `outputs/artifacts/stage1_bfcl_acceptance/paired/holdout_noop_control`

Run the paired checks after the paired artifacts are generated:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_paired_comparison.py --acceptance-root outputs/artifacts/stage1_bfcl_acceptance/paired/dev_explicit_literal --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_paired_comparison.py --acceptance-root outputs/artifacts/stage1_bfcl_acceptance/paired/dev_noop_control --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_paired_comparison.py --acceptance-root outputs/artifacts/stage1_bfcl_acceptance/paired/holdout_explicit_literal --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_paired_comparison.py --acceptance-root outputs/artifacts/stage1_bfcl_acceptance/paired/holdout_noop_control --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json --compact --strict
```

## Global Gates

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
PYTHONPATH=.:src .venv/bin/python scripts/check_stage1_bfcl_performance_ready.py --compact --strict
```

Expected current status: blocked until candidate pool promotion and scorer
authorization.
