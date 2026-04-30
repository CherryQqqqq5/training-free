# Batch 1 Full50 Extractor Yield Diagnostic

- Source collection only: `True`
- Scorer authorization: `False`
- Accepted candidates: `0`
- Eligible count: `0`
- Candidate pool passed: `False`
- Blockers: `['eligible_explicit_literal_candidates_below_minimum', 'dev_count_not_met', 'holdout_count_not_met']`
- Reject reasons: `{'ambiguous_literal': 44, 'no_single_missing_required_arg': 6}`

## Extraction Diagnostics

```json
{
  "calls_with_exactly_one_missing_required_arg": 0,
  "calls_with_function_schema": 22,
  "calls_with_missing_required_arg": 0,
  "calls_with_multiple_missing_required_args": 0,
  "current_observation_literal_rows": 0,
  "current_request_literal_rows": 6,
  "missing_required_samples": [],
  "parsed_emitted_calls": 66,
  "result_jsonl_rows": 50,
  "rows_with_any_missing_required_arg": 0,
  "rows_with_exactly_one_missing_required_arg": 0,
  "rows_with_function_schema": 5,
  "rows_with_multiple_missing_required_args": 0,
  "rows_with_non_unique_calls": 6,
  "rows_with_single_call": 0,
  "schema_function_alias_not_unique": 0
}
```

Candidate JSONL/audit/dev/holdout outputs remain under `/tmp/explicit_literal_pool` and are not promoted.
Raw traces/results/score/env/file locks remain under `/tmp` and are not deliverable artifacts.
