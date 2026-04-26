# M2.7r Offline Summary

- Passed: `False`

| Check | Passed |
| --- | ---: |
| `m27r_dev_subset_protocol_ready` | `True` |
| `m27r_rule_retention_ready` | `True` |
| `m27r_not_activated_audit_ready` | `True` |
| `m27r_arg_realization_audit_ready` | `True` |
| `m27r_holdout_manifest_ready` | `False` |

## Diagnostics

- Rule decisions: `{'demote': 0, 'reject': 3, 'retain': 0}`
- Not-activated classifications: `{'not_activated_false_negative': 12, 'not_activated_unknown': 2}`
- Arg realization reasons: `{'candidate_arg_wrong': 1, 'emitted_arg_wrong_or_guidance_not_followed': 3, 'tool_mismatch_before_arg_realization': 6}`
- Holdout selected cases: `4`
