# M2.8-pre Source/Result Availability Audit

- Audit ready: `True`
- Source/result availability ready: `True`
- Hard issue counts: `{}`
- Issue counts: `{'baseline_no_tool_call': 30, 'emitted_args_complete': 269, 'missing_required_arg_candidate': 1, 'no_matching_emitted_tool': 36, 'parallel_call_mapping_not_unique': 254, 'source_result_case_not_collected': 2065}`

| Category | Dataset cases | Result records | Top issues |
| --- | ---: | ---: | --- |
| `irrelevance` | `240` | `30` | `{'emitted_args_complete': 30, 'source_result_case_not_collected': 210}` |
| `memory_kv` | `155` | `30` | `{'emitted_args_complete': 21, 'no_matching_emitted_tool': 8, 'parallel_call_mapping_not_unique': 1, 'source_result_case_not_collected': 125}` |
| `memory_rec_sum` | `155` | `30` | `{'emitted_args_complete': 2, 'no_matching_emitted_tool': 28, 'source_result_case_not_collected': 125}` |
| `memory_vector` | `155` | `30` | `{'baseline_no_tool_call': 30, 'source_result_case_not_collected': 125}` |
| `multi_turn_base` | `200` | `30` | `{'emitted_args_complete': 14, 'parallel_call_mapping_not_unique': 16, 'source_result_case_not_collected': 170}` |
| `multi_turn_long_context` | `200` | `30` | `{'emitted_args_complete': 14, 'parallel_call_mapping_not_unique': 16, 'source_result_case_not_collected': 170}` |
| `multi_turn_miss_func` | `200` | `30` | `{'emitted_args_complete': 11, 'parallel_call_mapping_not_unique': 19, 'source_result_case_not_collected': 170}` |
| `multi_turn_miss_param` | `200` | `200` | `{'emitted_args_complete': 32, 'parallel_call_mapping_not_unique': 168}` |
| `multiple` | `200` | `30` | `{'emitted_args_complete': 29, 'missing_required_arg_candidate': 1, 'source_result_case_not_collected': 170}` |
| `parallel` | `200` | `30` | `{'emitted_args_complete': 1, 'parallel_call_mapping_not_unique': 29, 'source_result_case_not_collected': 170}` |
| `parallel_multiple` | `200` | `30` | `{'emitted_args_complete': 25, 'parallel_call_mapping_not_unique': 5, 'source_result_case_not_collected': 170}` |
| `simple_java` | `100` | `30` | `{'emitted_args_complete': 30, 'source_result_case_not_collected': 70}` |
| `simple_javascript` | `50` | `30` | `{'emitted_args_complete': 30, 'source_result_case_not_collected': 20}` |
| `simple_python` | `400` | `30` | `{'emitted_args_complete': 30, 'source_result_case_not_collected': 370}` |
