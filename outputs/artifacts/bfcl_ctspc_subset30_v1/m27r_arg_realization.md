# M2.7r Arg Realization Audit

- Ready: `True`
- Activated arg mismatch cases: `10`
- Failure reason distribution: `{'candidate_arg_wrong': 1, 'emitted_arg_wrong_or_guidance_not_followed': 3, 'tool_mismatch_before_arg_realization': 6}`

| Case | Tool | Failure Reason | Candidate Arg Validity | Binding Source | Raw Match | Final Match |
| --- | --- | --- | --- | --- | ---: | ---: |
| `multi_turn_miss_param_3` | `cp` | `candidate_arg_wrong` | `missing_candidate` | `[]` | `False` | `False` |
| `multi_turn_miss_param_5` | `cat` | `emitted_arg_wrong_or_guidance_not_followed` | `plausible_candidate_args` | `['prior_tool_output.matches[0]|basename']` | `False` | `False` |
| `multi_turn_miss_param_7` | `cat` | `tool_mismatch_before_arg_realization` | `candidate_tool_mismatch_proxy` | `['prior_tool_output.matches[0]|basename']` | `False` | `False` |
| `multi_turn_miss_param_16` | `touch` | `tool_mismatch_before_arg_realization` | `missing_candidate` | `[]` | `False` | `False` |
| `multi_turn_miss_param_22` | `cat` | `tool_mismatch_before_arg_realization` | `candidate_tool_mismatch_proxy` | `['prior_tool_output.cwd_or_listing']` | `False` | `False` |
| `multi_turn_miss_param_2` | `cat` | `emitted_arg_wrong_or_guidance_not_followed` | `plausible_candidate_args` | `['prior_tool_output.matches[0]|basename']` | `False` | `False` |
| `multi_turn_miss_param_35` | `cat` | `emitted_arg_wrong_or_guidance_not_followed` | `plausible_candidate_args` | `['prior_tool_output.matches[0]|basename']` | `False` | `False` |
| `multi_turn_miss_param_40` | `cat` | `tool_mismatch_before_arg_realization` | `candidate_tool_mismatch_proxy` | `['prior_tool_output.cwd_or_listing']` | `False` | `False` |
| `multi_turn_miss_param_4` | `cat` | `tool_mismatch_before_arg_realization` | `missing_candidate` | `[]` | `False` | `False` |
| `multi_turn_miss_param_37` | `cat` | `tool_mismatch_before_arg_realization` | `missing_candidate` | `[]` | `False` | `False` |
