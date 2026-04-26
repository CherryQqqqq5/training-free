# M2.7s Activation Recall

- Passed: `True`
- Actionable false negatives: `2`
- Distribution: `{'candidate_rejected_by_guard': 2, 'offline_activation_available_runtime_missed': 2, 'weak_binding': 10}`

| Case | Class | Reason | Actionable FN |
| --- | --- | --- | ---: |
| `multi_turn_miss_param_38` | `weak_binding` | `weak_arg_binding_evidence` | `False` |
| `multi_turn_miss_param_6` | `weak_binding` | `weak_arg_binding_evidence` | `False` |
| `multi_turn_miss_param_9` | `weak_binding` | `weak_arg_binding_evidence` | `False` |
| `multi_turn_miss_param_10` | `offline_activation_available_runtime_missed` | `strong_explicit_literal_binding` | `True` |
| `multi_turn_miss_param_18` | `weak_binding` | `weak_arg_binding_evidence` | `False` |
| `multi_turn_miss_param_21` | `weak_binding` | `weak_arg_binding_evidence` | `False` |
| `multi_turn_miss_param_36` | `weak_binding` | `weak_arg_binding_evidence` | `False` |
| `multi_turn_miss_param_43` | `weak_binding` | `weak_arg_binding_evidence` | `False` |
| `multi_turn_miss_param_45` | `weak_binding` | `weak_arg_binding_evidence` | `False` |
| `multi_turn_miss_param_0` | `candidate_rejected_by_guard` | `write_intent_unconfirmed` | `False` |
| `multi_turn_miss_param_8` | `weak_binding` | `weak_arg_binding_evidence` | `False` |
| `multi_turn_miss_param_25` | `candidate_rejected_by_guard` | `write_intent_unconfirmed` | `False` |
| `multi_turn_miss_param_29` | `weak_binding` | `weak_arg_binding_evidence` | `False` |
| `multi_turn_miss_param_39` | `offline_activation_available_runtime_missed` | `clean_cwd_listing_binding` | `True` |
