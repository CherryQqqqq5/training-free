# M2.7z Feedback Effect

- Ready: `True`
- Previous regression cases resolved: `0/4`
- Previous regression cases still regressed: `4`
- New regression cases: `0`
- Record-only feedback case activations: `2`
- Diagnostic-only feedback case activations: `5`
- Previous fixed cases preserved: `1/1`

## Previous Regression Cases
- `multi_turn_miss_param_27`: candidate_success=`False`, regressed=`True`, activated=`True`, selected_tool=`mv`
- `multi_turn_miss_param_35`: candidate_success=`False`, regressed=`True`, activated=`False`, selected_tool=`None`
- `multi_turn_miss_param_38`: candidate_success=`False`, regressed=`True`, activated=`False`, selected_tool=`None`
- `multi_turn_miss_param_39`: candidate_success=`False`, regressed=`True`, activated=`True`, selected_tool=`cat`

## New Regression Cases

## Interpretation
M2.7z dev rerun compact feedback-effect diagnostic. Use stop_loss and formal M2.7f gate before considering any holdout request.
