# BFCL Current-System Baseline Execution Gate

Status: pending and fail-closed. This packet freezes the future baseline execution scope but does not authorize execution.

## Frozen Baseline Scope

- Measurement kind: `current_system_baseline_only`
- Target commit: `221e2b7c16247cb1886de4e3c6b38ea02c8b7bc8`
- Route: `novacode/gpt-4.1`
- Evaluator: `bfcl-eval==2025.12.17`
- BFCL: `v4`, checkout `f7cf735`, data pinned by evaluator checkout
- Case protocol: full/default cases for configured baseline-freeze categories from `configs/bfcl_eval_protocol.yaml`
- Candidates: inert, not activated

## Future Command Template

The frozen future command template is recorded in the JSON packet as env-name-only tokens and `scripts/run_bfcl_v4_baseline.sh`. Endpoint and key values remain environment-only and must not be printed or committed.

## Output Boundary

Future execution may commit only compact manifest and compact metrics. Prompts, cases, provider payloads, logs, traces, result trees, endpoint/key values, scorer diffs, and candidate outputs remain forbidden.

## Stop Gates

Future execution must stop on route drift, candidate activation, raw/secret leak, manifest mismatch, scorer feedback contamination, missing metrics/manifest, output boundary failure, fallback/OpenRouter activation, or active `gpt-5.2` route.

## Claim Policy

This gate requests only current-system baseline measurement readiness. It does not authorize candidate comparison, +3pp, SOTA, Huawei, or performance claims.
