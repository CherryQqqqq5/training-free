# M2.7ab Unresolved Regression Repair

- Passed: `False`
- Pattern effective coverage: `0.6666666666666666`
- Unresolved after repair: `1`

## Cases
- `multi_turn_miss_param_35`: effective=`True`, outcome=`pattern_record_only_rejection`, tool=`None`
- `multi_turn_miss_param_39`: effective=`False`, outcome=`pattern_matched_but_still_selected`, tool=`cat`
  - unresolved: Regression pattern matched, but the candidate remained selected for hard guidance.
- `multi_turn_miss_param_9`: effective=`True`, outcome=`pattern_record_only_rejection`, tool=`None`

This is an offline replay diagnostic only. It does not call BFCL or prove performance.
