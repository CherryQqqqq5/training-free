# M2.7k Tool/Arg Alignment Diagnostic

- Passed: `True`
- Activated cases: `13`
- Classification counts: `{'not_activated_context': 17, 'trajectory_continuation_or_final_answer': 11, 'argument_realization': 2}`
- Action-specific guidance coverage: `1.0`
- Exact tool-choice coverage: `0.0`
- Exact tool-choice mode: `guidance_only`
- First failed criterion: `None`

| Case | Kind | Classification | Selected Tool | Tool Match | Raw Arg Match |
| --- | --- | --- | --- | --- | --- |
| multi_turn_miss_param_17 | stable_failure | trajectory_continuation_or_final_answer | touch | True | True |
| multi_turn_miss_param_31 | stable_failure | trajectory_continuation_or_final_answer | cat | True | True |
| multi_turn_miss_param_5 | stable_failure | trajectory_continuation_or_final_answer | cat | True | True |
| multi_turn_miss_param_7 | stable_failure | trajectory_continuation_or_final_answer | cat | True | True |
| multi_turn_miss_param_22 | regressed | trajectory_continuation_or_final_answer | touch | True | True |
| multi_turn_miss_param_2 | stable_failure | argument_realization | cat | True | False |
| multi_turn_miss_param_28 | stable_failure | trajectory_continuation_or_final_answer | cat | True | True |
| multi_turn_miss_param_35 | regressed | trajectory_continuation_or_final_answer | cat | True | True |
| multi_turn_miss_param_40 | stable_failure | trajectory_continuation_or_final_answer | touch | True | True |
| multi_turn_miss_param_43 | stable_failure | trajectory_continuation_or_final_answer | touch | True | True |
| multi_turn_miss_param_27 | stable_failure | trajectory_continuation_or_final_answer | cat | True | True |
| multi_turn_miss_param_37 | stable_failure | argument_realization | cat | True | False |
| multi_turn_miss_param_39 | regressed | trajectory_continuation_or_final_answer | touch | True | True |

This is an offline diagnostic and preflight. It is not BFCL performance evidence.
