# Provider Green Preflight

- Provider green preflight passed: `True`
- Required fields: `{'source_collection_rerun_ready': True, 'candidate_evaluation_ready': True, 'upstream_auth_passed': True, 'model_route_available': True, 'bfcl_compatible_response': True}`
- Required checks: `{'chat_tool_call': True, 'responses_tool_call': True, 'chat_text_response': True, 'trace_emission': True}`
- Expected API key env: `NOVACODE_API_KEY`
- Provider profile: `novacode`
- Provider route policy: `chuangzhi_novacode_only_openrouter_disabled`
- Upstream base URL: `https://apicz.boyuerichdata.com/v1`
- Upstream model: `gpt-5.2`
- Blockers: `[]`
- Next action: `provider_green_run_source_collection_when_scope_approved`

This checker is offline-only and does not run BFCL, a model, or a scorer.
