# BFCL Proxy Runtime Adapter Envelope Shape Diff

Status: sanitized shape-only preparation artifact. No provider call, BFCL smoke retry, scorer, candidate activation, performance, +3pp, or Huawei path is authorized.

- route: `novacode/gpt-4.1`
- stopped_smoke: `repeated_empty_model_response`, progress `6/8`, committed artifacts `false`
- shape_fields_only: `true`
- conclusion: `synthetic_provider_contract_passed_but_bfcl_proxy_runtime_adapter_envelope_requires_review_before_retry`
- adapter_risk_labels: `['tool_choice_form_differs_function_object_vs_required_string', 'proxy_adapter_additional_properties_flag_unknown_or_not_enforced', 'proxy_adapter_token_field_unknown_until_capture']`

The successful synthetic provider contract proves the env-only novacode gpt-4.1 tool-call path can return an OpenAI-compatible tool call. The stopped BFCL smoke used the reviewed eight run IDs but failed on repeated empty responses before any smoke artifact was committed. This artifact records only envelope and parser structure; it does not include raw prompts, provider payloads, response bodies, headers, logs, traces, case content, gold/reference/expected values, scorer diffs, endpoint/key values, source nonce mappings, or candidate output.
