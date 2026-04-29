# Provider Green Preflight

- Provider green preflight passed: `False`
- Required fields: `{'source_collection_rerun_ready': False, 'candidate_evaluation_ready': False, 'upstream_auth_passed': False, 'model_route_available': False, 'bfcl_compatible_response': False}`
- Required checks: `{'chat_tool_call': False, 'responses_tool_call': False, 'chat_text_response': False, 'trace_emission': False}`
- Expected API key env: `None`
- Blockers: `['provider_auth_401', 'provider_required_fields_not_green']`
- Next action: `configure_valid_approved_provider_credentials_then_run_planned_baseline_source_collection_commands`

This checker is offline-only and does not run BFCL, a model, or a scorer.
