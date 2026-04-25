# M2.7l Trace Completeness Preflight

- Passed: `False`
- Case-level gate allowed: `False`
- Selected cases: `30`
- Missing trace ids: `{'baseline': [], 'candidate': ['multi_turn_miss_param_43']}`
- Missing result ids: `{'baseline': [], 'candidate': []}`
- Missing effective score ids: `{'baseline': [], 'candidate': []}`
- First failed criterion: `missing_prompt_prefix_trace_ids`

This preflight is a hard durability gate for case-level attribution. If it fails, downstream M2.7f case-level performance gates are diagnostic only.
