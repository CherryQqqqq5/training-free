# Provider-Green Source Collection Dry Command Pack

This artifact is a dry command pack only. It does not call the provider, BFCL,
a model, or a scorer, and it is not performance evidence.

## Acceptance State Boundary

While the acceptance state is `provider_blocked`, this dry command pack is the
only source-collection-related material that may be reviewed or maintained.
Actual source collection, baseline scorer, candidate scorer, paired comparison,
and full-suite BFCL commands are prohibited.

The command templates below become executable only after the state advances to
`provider_green`, provider unblock is signed, and source collection scope is
approved. `provider_green` still does not authorize scorer execution.

## Preconditions

Run only after the provider route is green:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_provider_green_preflight.py \
  --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json \
  --compact --strict
```

Stop if provider credential is missing, HTTP 401/403/429 is present, the model
route is unavailable, tool-call preflight fails, or trace emission fails.

## Priority Order

Memory categories are excluded from the first-stage explicit-literal mainline.
Do not count `memory_kv`, `memory_rec_sum`, or `memory_vector` toward source
collection authorization.

| Priority | Category | Port | Output directory |
| ---: | --- | ---: | --- |
| 1 | `multi_turn_miss_func` | 8076 | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_func/baseline` |
| 2 | `multi_turn_long_context` | 8075 | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_long_context/baseline` |
| 3 | `multi_turn_base` | 8074 | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_base/baseline` |
| 4 | `parallel_multiple` | 8080 | `outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline` |
| 5 | `multiple` | 8078 | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline` |

## Command Templates

```bash
bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_func/baseline 8076 multi_turn_miss_func configs/runtime_bfcl_structured.yaml
bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_long_context/baseline 8075 multi_turn_long_context configs/runtime_bfcl_structured.yaml
bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_base/baseline 8074 multi_turn_base configs/runtime_bfcl_structured.yaml
bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline 8080 parallel_multiple configs/runtime_bfcl_structured.yaml
bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline 8078 multiple configs/runtime_bfcl_structured.yaml
```

## Expected Compact Artifacts

Each category should produce compact artifacts under its output directory:

- `artifacts/preflight_report.json`
- `artifacts/metrics.json`
- `artifacts/failure_summary.json`
- `artifacts/run_manifest.json`
- `bfcl/test_case_ids_to_generate.json`

These raw artifacts must not be committed or delivered:

- `traces/`
- `bfcl/result/`
- `bfcl/score/`
- `bfcl/.file_locks/`
- `logs/`
- `.env`
- `repairs.jsonl`
- `*_repair_records.jsonl`
- `*.log`

## Per-Step Gates

After each command, stop on any failure and run:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
```

Also stop if any expected compact artifact is missing or if
`artifacts/preflight_report.json` records a failed provider/tool-call preflight.

## Post-Collection Rebuild

After all priority categories finish and artifact boundary remains clean:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/build_m27t_source_pool_manifest.py
PYTHONPATH=.:src .venv/bin/python scripts/build_m28pre_explicit_required_arg_literal.py
PYTHONPATH=.:src .venv/bin/python scripts/check_explicit_literal_candidate_pool.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_m28pre_offline.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
```

Fail closed if the explicit-literal candidate pool remains below 35 eligible
candidates, if dev20 or holdout20 is incomplete, if dev/holdout overlap exists,
if any candidate is leakage-tainted, or if source-result-only candidates are the
only available evidence.
