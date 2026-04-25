# M2.7k Tool/Arg Alignment Diagnostic

- Passed: `True`
- Activated cases: `14`
- Classification counts: `{'not_activated_context': 16, 'actuation_or_prompt_guidance': 8, 'argument_realization': 4, 'aligned_or_fixed': 1, 'trajectory_continuation_or_final_answer': 1}`
- Action-specific guidance coverage: `1.0`
- Exact tool-choice coverage: `1.0`
- First failed criterion: `None`

| Case | Kind | Classification | Selected Tool | Tool Match | Raw Arg Match |
| --- | --- | --- | --- | --- | --- |
| multi_turn_miss_param_17 | stable_failure | argument_realization | touch | True | False |
| multi_turn_miss_param_31 | fixed | aligned_or_fixed | cat | True | True |
| multi_turn_miss_param_5 | stable_failure | argument_realization | cat | True | False |
| multi_turn_miss_param_7 | stable_failure | actuation_or_prompt_guidance | cat | False | False |
| multi_turn_miss_param_22 | fixed | actuation_or_prompt_guidance | touch | False | False |
| multi_turn_miss_param_2 | stable_failure | argument_realization | cat | True | False |
| multi_turn_miss_param_10 | stable_failure | actuation_or_prompt_guidance | touch | False | False |
| multi_turn_miss_param_28 | stable_failure | actuation_or_prompt_guidance | cat | False | False |
| multi_turn_miss_param_35 | regressed | argument_realization | cat | True | False |
| multi_turn_miss_param_40 | stable_failure | actuation_or_prompt_guidance | touch | False | False |
| multi_turn_miss_param_27 | stable_failure | actuation_or_prompt_guidance | cat | False | False |
| multi_turn_miss_param_30 | stable_failure | trajectory_continuation_or_final_answer | cat | True | True |
| multi_turn_miss_param_37 | stable_failure | actuation_or_prompt_guidance | cat | False | False |
| multi_turn_miss_param_39 | fixed | actuation_or_prompt_guidance | touch | False | False |

This is an offline diagnostic and preflight. It is not BFCL performance evidence.
