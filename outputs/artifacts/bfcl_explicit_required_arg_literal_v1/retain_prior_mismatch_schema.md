# Retain Prior Mismatch Schema

Offline schema only. BFCL failures diagnose prior mismatch; they do not create retain rules.

## Failure Reasons
- `literal_not_emitted`
- `model_ignored_guidance`
- `rule_not_applicable`
- `scorer_trajectory_mismatch`
- `wrong_arg_key`
- `wrong_arg_value`

## Required Join Keys
- `case_id`
- `rule_id`
- `candidate_id`
- `retention_prior.rule_family`
- `selected_tool`
- `required_arg`
