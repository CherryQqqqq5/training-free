# BFCL Proxy Runtime Adapter Envelope Shape Diff

Status: sanitized shape-only preparation artifact. No provider call, BFCL smoke retry, scorer, candidate activation, performance, +3pp, or Huawei path is authorized.

- route: `novacode/gpt-4.1`
- stopped_smoke: `repeated_empty_model_response`, progress `6/8`, committed artifacts `false`
- shape_fields_only: `true`
- conclusion: `bfcl_proxy_runtime_adapter_envelope_aligned_to_synthetic_contract_shape_without_execution`
- adapter_risk_labels: `[]`

The successful synthetic provider contract proves the env-only novacode gpt-4.1 tool-call path can return an OpenAI-compatible tool call. The BFCL proxy/runtime adapter policy is now aligned at the envelope level: function-object tool choice for single-tool requests, required tool choice for multi-tool requests, schema-local additionalProperties=false, path-specific token fields with chat-completions using max_tokens and Responses using max_output_tokens, explicit temperature/stream/timeout fields, and compact empty-response stop-gate labels. The stopped BFCL smoke used the reviewed eight run IDs but failed on repeated empty responses before any smoke artifact was committed. This artifact records only envelope and parser structure; it does not include raw prompts, provider payloads, response bodies, headers, logs, traces, case content, gold/reference/expected values, scorer diffs, endpoint/key values, source nonce mappings, or candidate output.
