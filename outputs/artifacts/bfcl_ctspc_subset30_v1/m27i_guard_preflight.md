# M2.7i Guard Preflight

- Passed: `True`
- Selected cases: `30`
- Before guard activations: `30`
- After guard activations: `13`
- Guard rejected cases: `17`
- Guard reasons: `{'weak_arg_binding_evidence': 305, 'write_intent_unconfirmed': 4, 'cat_competing_intent': 3}`
- After guard tool distribution: `{'cat': 8, 'touch': 5}`
- Dominant after guard rate: `0.6153846153846154`
- Regressed status: `{'multi_turn_miss_param_9': 'guard_rejected', 'multi_turn_miss_param_21': 'guard_rejected', 'multi_turn_miss_param_36': 'guard_rejected'}`
- Fixed status: `{'multi_turn_miss_param_31': 'guard_kept', 'multi_turn_miss_param_39': 'guard_kept'}`
- First failed criterion: `None`

## Changed Cases

| Case | Status | Before Tool | After Tool | Guard Reasons |
| --- | --- | --- | --- | --- |
| multi_turn_miss_param_31 | guard_kept | cat | cat | weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence |
| multi_turn_miss_param_9 | guard_rejected | touch | None | weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence |
| multi_turn_miss_param_21 | guard_rejected | cat | None | weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, cat_competing_intent, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence |
| multi_turn_miss_param_36 | guard_rejected | cat | None | weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, cat_competing_intent, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence |
| multi_turn_miss_param_39 | guard_kept | touch | touch | weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence, weak_arg_binding_evidence |

## Interpretation

This checker is an offline source-trace replay. It gates whether the conservative action guard is precise enough to justify a later M2.7f-lite rerun; it is not BFCL performance evidence.
