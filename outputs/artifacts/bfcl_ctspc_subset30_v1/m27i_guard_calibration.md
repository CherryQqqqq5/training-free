# M2.7j Guard Calibration

- Source preflight passed: `True`
- After guard activations: `13`
- Fixed false negatives: `[]`
- Regressed false positives: `[]`
- Case-level reasons: `{'clean_cwd_listing_binding': 4, 'weak_arg_binding_evidence': 14, 'strong_prior_output_binding': 4, 'strong_prior_output_match_binding': 4, 'write_intent_unconfirmed': 3, 'strong_explicit_literal_binding': 1}`
- Top rejected reasons: `{'weak_arg_binding_evidence': 27, 'write_intent_unconfirmed': 3}`
- Recommendations: `['guard_preflight_ready']`

## Changed Cases

| Case | Kind | Status | Before | After | Case Reason | Top Rejected Reason |
| --- | --- | --- | --- | --- | --- | --- |
| multi_turn_miss_param_31 | fixed | guard_kept | cat | cat | strong_prior_output_binding | weak_arg_binding_evidence |
| multi_turn_miss_param_9 | regressed | guard_rejected | touch | None | weak_arg_binding_evidence | weak_arg_binding_evidence |
| multi_turn_miss_param_21 | regressed | guard_rejected | cat | None | weak_arg_binding_evidence | weak_arg_binding_evidence |
| multi_turn_miss_param_36 | regressed | guard_rejected | cat | None | weak_arg_binding_evidence | weak_arg_binding_evidence |
| multi_turn_miss_param_39 | fixed | guard_kept | touch | touch | clean_cwd_listing_binding | weak_arg_binding_evidence |
