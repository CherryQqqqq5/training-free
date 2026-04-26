# M2.7z Feedback Effect

- Ready: `True`
- Previous regression cases resolved: `2/4`
- Previous regression cases still regressed: `2`
- New regression cases: `1`
- Record-only feedback case activations: `2`
- Diagnostic-only feedback case activations: `6`
- Previous fixed cases preserved: `1/2`

## Previous Regression Cases
- `multi_turn_miss_param_21`: candidate_success=`True`, regressed=`False`, activated=`False`, selected_tool=`None`
- `multi_turn_miss_param_22`: candidate_success=`True`, regressed=`False`, activated=`True`, selected_tool=`cat`
- `multi_turn_miss_param_35`: candidate_success=`False`, regressed=`True`, activated=`False`, selected_tool=`None`
- `multi_turn_miss_param_39`: candidate_success=`False`, regressed=`True`, activated=`True`, selected_tool=`cat`

## New Regression Cases
- `multi_turn_miss_param_9`: activated=`False`, selected_tool=`None`, blocked_reason=`activation_predicates_unmet`

## Interpretation
M2.7z dev rerun compact feedback-effect diagnostic. Use stop_loss and formal M2.7f gate before considering any holdout request.
