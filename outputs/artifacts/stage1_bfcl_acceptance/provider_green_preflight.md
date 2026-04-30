# Provider Green Preflight

- Provider green preflight passed: `False`
- Required fields: `{'source_collection_rerun_ready': False, 'candidate_evaluation_ready': False, 'upstream_auth_passed': False, 'model_route_available': False, 'bfcl_compatible_response': False}`
- Required checks: `{'chat_tool_call': False, 'responses_tool_call': False, 'chat_text_response': False, 'trace_emission': True}`
- Expected API key env: `OPENROUTER_API_KEY`
- Blockers: `['chat_text_response_preflight_failed', 'chat_tool_call_preflight_failed', 'provider_auth_401', 'provider_preflight_checks_not_green', 'responses_tool_call_preflight_failed']`
- Next action: `None`

This checker is offline-only and does not run BFCL, a model, or a scorer.
