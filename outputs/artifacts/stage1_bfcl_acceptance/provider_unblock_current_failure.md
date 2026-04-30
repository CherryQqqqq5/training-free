# Provider Unblock Current Failure

- Server: `10.220.5.159:/cephfs/qiuyn/training-free`
- Git head: `28b78b9e9504a4d0382538e65bc5227f804b1625`
- Provider green: `False`
- Secret values recorded: `False`

## Failed Checks
- `chat_tool_call`: passed=`False`, status=`401`, reason=`http 401: {'error': {'message': 'User not found.', 'code': 401}}`
- `responses_tool_call`: passed=`False`, status=`401`, reason=`http 401: {'error': {'message': 'User not found.', 'code': 401}}`
- `chat_text_response`: passed=`False`, status=`401`, reason=`http 401: {'error': {'message': 'User not found.', 'code': 401}}`
- `trace_emission`: passed=`True`, status=`None`, reason=`ok`

## Required Action
- `issue_valid_approved_provider_key`
- `confirm_account_exists_and_billing_or_project_access`
- `confirm_model_route_access`
- `confirm_chat_completions_and_tool_call_support`
- `rerun_provider_green_preflight_before_source_collection`

## Blocked Operations
- `provider_green`
- `source_collection`
- `candidate_pool_promotion`
- `dev_scorer`
- `holdout_scorer`
- `full_or_huawei_acceptance_scorer`
- `bfcl_3pp_claim`
