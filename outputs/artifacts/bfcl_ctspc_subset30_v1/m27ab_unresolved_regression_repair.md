# M2.7ab Unresolved Regression Repair

- Passed: `False`
- Pattern effective coverage: `0.6666666666666666`
- Unresolved after repair: `1`

## Cases
- `multi_turn_miss_param_35`: effective=`True`, outcome=`post_feedback_fallback_record_only_rejection`, tool=`None`
- `multi_turn_miss_param_39`: effective=`False`, outcome=`post_feedback_fallback_candidate`, tool=`cat`
  - unresolved: The original regression pattern was blocked or bypassed, but another scorer-feedback pattern candidate became hard guidance.
- `multi_turn_miss_param_9`: effective=`True`, outcome=`post_feedback_fallback_record_only_rejection`, tool=`None`

This is an offline replay diagnostic only. It does not call BFCL or prove performance.
