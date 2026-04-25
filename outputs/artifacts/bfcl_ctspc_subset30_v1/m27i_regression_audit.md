# M2.7i Regression Audit

- Passed: `True`
- Selected cases: `30`
- Case kinds: `{'stable_failure': 24, 'fixed': 2, 'stable_success': 1, 'regressed': 3}`
- Failure layers: `{'wrong_next_tool': 19, 'repair_interaction': 26, 'wrong_args': 8, 'over_actuation': 3}`
- Binding risks: `{'prior_output_binding_not_realized': 16, 'explicit_literal_binding_not_realized': 13}`
- Regressed cases: `['multi_turn_miss_param_9', 'multi_turn_miss_param_21', 'multi_turn_miss_param_36']`
- Fixed cases: `['multi_turn_miss_param_31', 'multi_turn_miss_param_39']`

## Changed Cases

| Case | Kind | Selected Tool | Arg Match | Repairs | Layers / Conditions |
| --- | --- | --- | --- | --- | --- |
| multi_turn_miss_param_31 | fixed | touch | True | coerce_no_tool_text_to_empty, resolve_contextual_string_arg | recommended_tool_match, raw_arg_binding_match, final_arg_binding_match, explicit_literal_binding, tool_emitted |
| multi_turn_miss_param_9 | regressed | touch | False | coerce_no_tool_text_to_empty, resolve_contextual_string_arg | over_actuation, wrong_args, repair_interaction |
| multi_turn_miss_param_21 | regressed | cat | False | - | over_actuation, wrong_next_tool |
| multi_turn_miss_param_36 | regressed | touch | False | coerce_no_tool_text_to_empty, resolve_contextual_string_arg, strip_assistant_content_with_tool_calls | over_actuation, wrong_next_tool, repair_interaction |
| multi_turn_miss_param_39 | fixed | mkdir | False | coerce_no_tool_text_to_empty | recommended_tool_match, explicit_literal_binding, tool_emitted |

## Interpretation

M2.7i treats the M2.7f rerun as durable evidence and focuses on over-actuation, wrong tool selection, and weak argument binding rather than activation coverage.
