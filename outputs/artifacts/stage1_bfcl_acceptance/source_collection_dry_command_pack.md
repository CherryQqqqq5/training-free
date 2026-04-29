# Provider-Green Source Collection Dry Command Pack

This artifact is a dry command pack only. It does not call the provider, BFCL,
a model, or a scorer, and it is not performance evidence.

The command templates are approval-gated. They must fail locally unless
`GRC_SOURCE_COLLECTION_APPROVED=1` is set after `provider_green` and source
collection scope signoff.

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
| 1 | `multi_turn_miss_func` | 8076 | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_func/baseline/artifacts` |
| 2 | `multi_turn_long_context` | 8075 | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_long_context/baseline/artifacts` |
| 3 | `multi_turn_base` | 8074 | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_base/baseline/artifacts` |
| 4 | `parallel_multiple` | 8080 | `outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline/artifacts` |
| 5 | `multiple` | 8078 | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline/artifacts` |

Raw BFCL run roots are temporary and must stay under
`/tmp/bfcl_source_collection/<category>/baseline`. BFCL result, score, traces,
and `diagnostics/repairs.jsonl` stay in that raw run root. Only compact
artifacts may land under `outputs/artifacts`.

## Command Templates

```bash
test "${GRC_SOURCE_COLLECTION_APPROVED:-0}" = "1" || { echo 'source collection approval required'; exit 2; }; bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC /tmp/bfcl_source_collection/multi_turn_miss_func/baseline 8076 multi_turn_miss_func configs/runtime_bfcl_structured.yaml rules/baseline_empty /tmp/bfcl_source_collection/multi_turn_miss_func/baseline/traces outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_func/baseline/artifacts
test "${GRC_SOURCE_COLLECTION_APPROVED:-0}" = "1" || { echo 'source collection approval required'; exit 2; }; bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC /tmp/bfcl_source_collection/multi_turn_long_context/baseline 8075 multi_turn_long_context configs/runtime_bfcl_structured.yaml rules/baseline_empty /tmp/bfcl_source_collection/multi_turn_long_context/baseline/traces outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_long_context/baseline/artifacts
test "${GRC_SOURCE_COLLECTION_APPROVED:-0}" = "1" || { echo 'source collection approval required'; exit 2; }; bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC /tmp/bfcl_source_collection/multi_turn_base/baseline 8074 multi_turn_base configs/runtime_bfcl_structured.yaml rules/baseline_empty /tmp/bfcl_source_collection/multi_turn_base/baseline/traces outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_base/baseline/artifacts
test "${GRC_SOURCE_COLLECTION_APPROVED:-0}" = "1" || { echo 'source collection approval required'; exit 2; }; bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC /tmp/bfcl_source_collection/parallel_multiple/baseline 8080 parallel_multiple configs/runtime_bfcl_structured.yaml rules/baseline_empty /tmp/bfcl_source_collection/parallel_multiple/baseline/traces outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline/artifacts
test "${GRC_SOURCE_COLLECTION_APPROVED:-0}" = "1" || { echo 'source collection approval required'; exit 2; }; bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC /tmp/bfcl_source_collection/multiple/baseline 8078 multiple configs/runtime_bfcl_structured.yaml rules/baseline_empty /tmp/bfcl_source_collection/multiple/baseline/traces outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline/artifacts
```

## Expected Compact Artifacts

Each category should produce compact artifacts under its output directory:

- `artifacts/preflight_report.json`
- `artifacts/metrics.json`
- `artifacts/failure_summary.json`
- `artifacts/run_manifest.json`

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
Stop if any BFCL result, score, trace, file lock, or log path appears under
`outputs/artifacts`.

## Builder Feed

After source collection completes, rebuild the source manifest and feed the
explicit-literal pool builder through temporary outputs first. Because raw BFCL
result files stay under `/tmp`, create a temporary source manifest overlay that
points `existing_source_roots` at those approved raw run roots.

```bash
PYTHONPATH=.:src .venv/bin/python scripts/build_m27t_source_pool_manifest.py \
  --out-root outputs/artifacts/bfcl_ctspc_source_pool_v1

mkdir -p /tmp/explicit_literal_pool
PYTHONPATH=.:src .venv/bin/python - <<'PY'
import json
from pathlib import Path

cats = [
    "multi_turn_miss_func",
    "multi_turn_long_context",
    "multi_turn_base",
    "parallel_multiple",
    "multiple",
]
root = Path("/tmp/bfcl_source_collection")
out = Path("/tmp/explicit_literal_pool/source_collection_manifest_with_tmp_roots.json")
out.write_text(
    json.dumps(
        {
            "report_scope": "tmp_source_collection_manifest_with_raw_roots",
            "source_collection_only": True,
            "category_status": [
                {
                    "category": category,
                    "source_artifacts_available": True,
                    "existing_source_roots": [str(root / category / "baseline")],
                }
                for category in cats
            ],
        },
        indent=2,
        sort_keys=True,
    )
    + "\n"
)
PY

PYTHONPATH=.:src .venv/bin/python scripts/check_explicit_literal_dataset.py \
  --dataset-json <approved_bfcl_dataset_fixture_or_export.json> \
  --categories multi_turn_miss_func,multi_turn_long_context,multi_turn_base,parallel_multiple,multiple \
  --output /tmp/explicit_literal_pool/dataset_schema_gate.json \
  --markdown-output /tmp/explicit_literal_pool/dataset_schema_gate.md \
  --compact --strict

PYTHONPATH=.:src .venv/bin/python scripts/build_explicit_literal_candidate_pool.py \
  --source-manifest /tmp/explicit_literal_pool/source_collection_manifest_with_tmp_roots.json \
  --dataset-json <approved_bfcl_dataset_fixture_or_export.json> \
  --candidate-jsonl /tmp/explicit_literal_pool/candidate_rules.jsonl \
  --audit-json /tmp/explicit_literal_pool/audit.json \
  --dev-manifest /tmp/explicit_literal_pool/dev20_manifest.json \
  --holdout-manifest /tmp/explicit_literal_pool/holdout20_manifest.json \
  --summary-output /tmp/explicit_literal_pool/summary.json \
  --markdown-output /tmp/explicit_literal_pool/summary.md \
  --compact --strict

PYTHONPATH=.:src .venv/bin/python scripts/check_explicit_literal_candidate_pool.py \
  --candidate-jsonl /tmp/explicit_literal_pool/candidate_rules.jsonl \
  --dev-manifest /tmp/explicit_literal_pool/dev20_manifest.json \
  --holdout-manifest /tmp/explicit_literal_pool/holdout20_manifest.json \
  --compact --strict
```

Do not overwrite tracked/default `candidate_rules.jsonl`, dev manifest, or
holdout manifest until the temporary builder outputs pass no-leakage,
duplicate-case, and dev/holdout integrity gates.

The dataset schema gate fails closed unless the approved dataset JSON contains
records with `id`, `question` or `messages`, function schemas with
`parameters.properties`, and non-empty required arguments whose schemas are
present. It also requires coverage for every priority category and rejects
gold/score/candidate-style top-level fields. It does not require or consume
gold answers, score outputs, or candidate outputs.

## Post-Collection Rebuild

After all priority categories finish and artifact boundary remains clean:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/build_m27t_source_pool_manifest.py
mkdir -p /tmp/explicit_literal_pool && PYTHONPATH=.:src .venv/bin/python -c 'import json, pathlib; cats=["multi_turn_miss_func","multi_turn_long_context","multi_turn_base","parallel_multiple","multiple"]; root=pathlib.Path("/tmp/bfcl_source_collection"); out=pathlib.Path("/tmp/explicit_literal_pool/source_collection_manifest_with_tmp_roots.json"); out.write_text(json.dumps({"report_scope":"tmp_source_collection_manifest_with_raw_roots","source_collection_only":True,"category_status":[{"category":c,"source_artifacts_available":True,"existing_source_roots":[str(root/c/"baseline")]} for c in cats]}, indent=2, sort_keys=True)+"\n")'
PYTHONPATH=.:src .venv/bin/python scripts/check_explicit_literal_dataset.py --dataset-json <approved_bfcl_dataset_fixture_or_export.json> --categories multi_turn_miss_func,multi_turn_long_context,multi_turn_base,parallel_multiple,multiple --output /tmp/explicit_literal_pool/dataset_schema_gate.json --markdown-output /tmp/explicit_literal_pool/dataset_schema_gate.md --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/build_explicit_literal_candidate_pool.py --source-manifest /tmp/explicit_literal_pool/source_collection_manifest_with_tmp_roots.json --dataset-json <approved_bfcl_dataset_fixture_or_export.json> --candidate-jsonl /tmp/explicit_literal_pool/candidate_rules.jsonl --audit-json /tmp/explicit_literal_pool/audit.json --dev-manifest /tmp/explicit_literal_pool/dev20_manifest.json --holdout-manifest /tmp/explicit_literal_pool/holdout20_manifest.json --summary-output /tmp/explicit_literal_pool/summary.json --markdown-output /tmp/explicit_literal_pool/summary.md --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_explicit_literal_candidate_pool.py --candidate-jsonl /tmp/explicit_literal_pool/candidate_rules.jsonl --dev-manifest /tmp/explicit_literal_pool/dev20_manifest.json --holdout-manifest /tmp/explicit_literal_pool/holdout20_manifest.json --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_m28pre_offline.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
```

Fail closed if the explicit-literal candidate pool remains below 35 eligible
candidates, if dev20 or holdout20 is incomplete, if dev/holdout overlap exists,
if any candidate is leakage-tainted, or if source-result-only candidates are the
only available evidence.
