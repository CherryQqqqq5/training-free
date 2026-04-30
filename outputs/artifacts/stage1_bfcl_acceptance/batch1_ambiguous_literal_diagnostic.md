# Batch 1 Ambiguous Literal And Missing Required Diagnostic

- Result JSONL rows: `37`
- Bad result rows: `0`
- Trace count: `568`
- Latest trace age sec: `3.9`
- Scorer authorization: `False`

## Missing Required Aggregate

```json
{
  "rows_with_any_missing_required_arg": 0,
  "rows_with_exactly_one_missing_required_arg": 0,
  "rows_with_function_schema": 0,
  "rows_with_multiple_missing_required_args": 0,
  "rows_with_no_missing_required_arg": 37,
  "rows_with_non_unique_calls": 37,
  "rows_with_single_call": 0
}
```

## Ambiguous Literal Samples

| Case | Why ambiguous | Request literals | Observation literals | Tool calls | Unique functions |
| --- | --- | ---: | ---: | ---: | ---: |
| `multi_turn_miss_func_0` | `multiple_current_request_literals, tool_call_mapping_not_unique_for_missing_arg_attribution` | `4` | `0` | `23` | `8` |
| `multi_turn_miss_func_1` | `multiple_current_request_literals, tool_call_mapping_not_unique_for_missing_arg_attribution` | `3` | `0` | `11` | `8` |
| `multi_turn_miss_func_2` | `multiple_current_request_literals, tool_call_mapping_not_unique_for_missing_arg_attribution` | `8` | `0` | `16` | `8` |
| `multi_turn_miss_func_3` | `multiple_current_request_literals, tool_call_mapping_not_unique_for_missing_arg_attribution` | `2` | `0` | `9` | `6` |
| `multi_turn_miss_func_5` | `multiple_current_request_literals, tool_call_mapping_not_unique_for_missing_arg_attribution` | `5` | `0` | `9` | `8` |

## Missing Required Samples

| Case | Tool calls | Unique functions | Missing total | Exactly one | Diagnostic sample |
| --- | ---: | ---: | ---: | --- | --- |
| `multi_turn_miss_func_0` | `23` | `8` | `0` | `False` | `ls missing=None required=None schema=False; pwd missing=None required=None schema=False; cd missing=None required=None schema=False; find missing=None required=None schema=False` |
| `multi_turn_miss_func_1` | `11` | `8` | `0` | `False` | `pwd missing=None required=None schema=False; ls missing=None required=None schema=False; cd missing=None required=None schema=False; find missing=None required=None schema=False` |
| `multi_turn_miss_func_2` | `16` | `8` | `0` | `False` | `cd missing=None required=None schema=False; echo missing=None required=None schema=False; touch missing=None required=None schema=False; ls missing=None required=None schema=False` |
| `multi_turn_miss_func_3` | `9` | `6` | `0` | `False` | `pwd missing=None required=None schema=False; echo missing=None required=None schema=False; grep missing=None required=None schema=False; find missing=None required=None schema=False` |
| `multi_turn_miss_func_4` | `10` | `8` | `0` | `False` | `pwd missing=None required=None schema=False; ls missing=None required=None schema=False; cat missing=None required=None schema=False; touch missing=None required=None schema=False` |

Raw traces/results/env/file locks remain under `/tmp` and are not deliverable artifacts.
