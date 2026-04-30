# Explicit Literal Pool Existing Source Dry Audit

This is an offline dry audit. It did not call the provider, BFCL, a model, or a scorer, and it did not overwrite default candidate artifacts.

- Source manifest: `outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_manifest.json`
- Source manifest present: `true`
- Source manifest categories: `14`
- Categories with available source artifacts: `0`
- BFCL result files under source pool: `0`
- Dataset fixture present: `false`
- Candidate records from temp builder run: `0`
- Eligible records from temp builder run: `0`
- Rejected records from temp builder run: `0`
- Reject reason counts: `{}`
- Dev selected count: `0`
- Holdout selected count: `0`
- Candidate pool build passed: `false`

Temp builder outputs were written under:

```text
/tmp/explicit_literal_pool_audit.qJymXn/
```

Blockers:

- `source_pool_has_no_bfcl_result_files`
- `source_manifest_has_no_available_source_artifacts`
- `dataset_json_missing`
- `dataset_records_missing`
- `eligible_explicit_literal_candidates_below_minimum`
- `dev_count_not_met`
- `holdout_count_not_met`

Next required action:

```text
get_provider_green_then_run_priority_source_collection_before_rebuilding_explicit_literal_pool
```
