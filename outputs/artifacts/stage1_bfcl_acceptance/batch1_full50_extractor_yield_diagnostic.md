# Batch 1 Full50 Extractor Yield Diagnostic

- Source collection completed diagnostic: `True`
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
  "calls_with_function_schema": 244,
  "calls_with_missing_required_arg": 0,
  "calls_with_multiple_missing_required_args": 0,
  "current_observation_literal_rows": 0,
  "current_request_literal_rows": 6,
  "emitted_arg_key_conflicts": 0,
  "matched_calls_with_empty_properties": 0,
  "matched_calls_with_empty_required": 48,
  "missing_required_samples": [],
  "parsed_emitted_calls": 557,
  "result_jsonl_rows": 50,
  "rows_with_any_missing_required_arg": 0,
  "rows_with_exactly_one_missing_required_arg": 0,
  "rows_with_function_schema": 49,
  "rows_with_multiple_missing_required_args": 0,
  "rows_with_non_unique_calls": 50,
  "rows_with_single_call": 0,
  "schema_function_alias_not_unique": 0,
  "schema_functions_with_empty_properties": 0,
  "schema_functions_with_empty_required": 29,
  "schema_match_samples": [
    {
      "arg_key_conflicts": [],
      "call_index": 0,
      "candidate_schema_names": [
        "GorillaFileSystem.find",
        "GorillaFileSystem.mv",
        "GorillaFileSystem.grep",
        "GorillaFileSystem.sort",
        "GorillaFileSystem.diff",
        "TwitterAPI.post_tweet"
      ],
      "candidate_schema_names_normalized": [
        "find",
        "mv",
        "grep",
        "sort",
        "diff",
        "posttweet"
      ],
      "case_id": "multi_turn_miss_func_0",
      "category": "multi_turn_miss_func",
      "emitted_arg_keys": [
        "a"
      ],
      "emitted_normalized_name": "ls",
      "emitted_raw_name": "ls",
      "match_reason": "no exact/suffix/normalized schema alias matched emitted tool",
      "match_status": "unmatched",
      "matched_function": null,
      "missing_args": [],
      "normalized_emitted_arg_keys": [
        "a"
      ],
      "present_schema_args": [],
      "properties_keys": [],
      "required_args": [],
      "schema_path": null,
      "schema_source": null,
      "step_index": 0,
      "turn_index": 0
    },
    {
      "arg_key_conflicts": [],
      "call_index": 1,
      "candidate_schema_names": [
        "GorillaFileSystem.find",
        "GorillaFileSystem.mv",
        "GorillaFileSystem.grep",
        "GorillaFileSystem.sort",
        "GorillaFileSystem.diff",
        "TwitterAPI.post_tweet"
      ],
      "candidate_schema_names_normalized": [
        "find",
        "mv",
        "grep",
        "sort",
        "diff",
        "posttweet"
      ],
      "case_id": "multi_turn_miss_func_0",
      "category": "multi_turn_miss_func",
      "emitted_arg_keys": [],
      "emitted_normalized_name": "pwd",
      "emitted_raw_name": "pwd",
      "match_reason": "no exact/suffix/normalized schema alias matched emitted tool",
      "match_status": "unmatched",
      "matched_function": null,
      "missing_args": [],
      "normalized_emitted_arg_keys": [],
      "present_schema_args": [],
      "properties_keys": [],
      "required_args": [],
      "schema_path": null,
      "schema_source": null,
      "step_index": 0,
      "turn_index": 0
    },
    {
      "arg_key_conflicts": [],
      "call_index": 0,
      "candidate_schema_names": [
        "GorillaFileSystem.find",
        "GorillaFileSystem.mv",
        "GorillaFileSystem.grep",
        "GorillaFileSystem.sort",
        "GorillaFileSystem.diff",
        "TwitterAPI.post_tweet"
      ],
      "candidate_schema_names_normalized": [
        "find",
        "mv",
        "grep",
        "sort",
        "diff",
        "posttweet"
      ],
      "case_id": "multi_turn_miss_func_0",
      "category": "multi_turn_miss_func",
      "emitted_arg_keys": [
        "folder"
      ],
      "emitted_normalized_name": "cd",
      "emitted_raw_name": "cd",
      "match_reason": "no exact/suffix/normalized schema alias matched emitted tool",
      "match_status": "unmatched",
      "matched_function": null,
      "missing_args": [],
      "normalized_emitted_arg_keys": [
        "folder"
      ],
      "present_schema_args": [],
      "properties_keys": [],
      "required_args": [],
      "schema_path": null,
      "schema_source": null,
      "step_index": 1,
      "turn_index": 0
    },
    {
      "arg_key_conflicts": [],
      "call_index": 1,
      "candidate_schema_names": [
        "GorillaFileSystem.find",
        "GorillaFileSystem.mv",
        "GorillaFileSystem.grep",
        "GorillaFileSystem.sort",
        "GorillaFileSystem.diff",
        "TwitterAPI.post_tweet"
      ],
      "candidate_schema_names_normalized": [
        "find",
        "mv",
        "grep",
        "sort",
        "diff",
        "posttweet"
      ],
      "case_id": "multi_turn_miss_func_0",
      "category": "multi_turn_miss_func",
      "emitted_arg_keys": [
        "a"
      ],
      "emitted_normalized_name": "ls",
      "emitted_raw_name": "ls",
      "match_reason": "no exact/suffix/normalized schema alias matched emitted tool",
      "match_status": "unmatched",
      "matched_function": null,
      "missing_args": [],
      "normalized_emitted_arg_keys": [
        "a"
      ],
      "present_schema_args": [],
      "properties_keys": [],
      "required_args": [],
      "schema_path": null,
      "schema_source": null,
      "step_index": 1,
      "turn_index": 0
    },
    {
      "arg_key_conflicts": [],
      "call_index": 0,
      "candidate_schema_names": [
        "GorillaFileSystem.find",
        "GorillaFileSystem.mv",
        "GorillaFileSystem.grep",
        "GorillaFileSystem.sort",
        "GorillaFileSystem.diff",
        "TwitterAPI.post_tweet"
      ],
      "candidate_schema_names_normalized": [
        "find",
        "mv",
        "grep",
        "sort",
        "diff",
        "posttweet"
      ],
      "case_id": "multi_turn_miss_func_0",
      "category": "multi_turn_miss_func",
      "emitted_arg_keys": [
        "a"
      ],
      "emitted_normalized_name": "ls",
      "emitted_raw_name": "ls",
      "match_reason": "no exact/suffix/normalized schema alias matched emitted tool",
      "match_status": "unmatched",
      "matched_function": null,
      "missing_args": [],
      "normalized_emitted_arg_keys": [
        "a"
      ],
      "present_schema_args": [],
      "properties_keys": [],
      "required_args": [],
      "schema_path": null,
      "schema_source": null,
      "step_index": 2,
      "turn_index": 0
    }
  ],
  "schema_match_status_counts": {
    "matched": 244,
    "unmatched": 313
  }
}
```

Full schema match samples are in the JSON artifact.
Candidate JSONL/audit/dev/holdout outputs remain under `/tmp/explicit_literal_pool` and are not promoted.
Raw traces/results/score/env/file locks remain under `/tmp` and are not deliverable artifacts.
