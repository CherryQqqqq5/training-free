# BFCL Proxy Runtime Adapter Debug Packet

Status: prepared only. This packet authorizes sanitized proxy/runtime adapter debug preparation and shape-diff construction only. It does not authorize a provider request, BFCL smoke retry, full/default BFCL run, scorer execution, candidate activation, candidate JSONL or pool generation, performance evidence, +3pp claim, SOTA claim, or Huawei readiness.

## Route

- active_profile: `novacode`
- route_model: `gpt-4.1`
- fallback_allowed: `false`
- gpt_4o_fallback_allowed: `false`
- OpenRouter allowed: `false`
- endpoint/key: env-only; values must never be printed, committed, or written to artifacts.

## Stopped Smoke Facts

- exact reviewed run IDs materialized: `true`
- run ID count: `8`
- stopped_on: `repeated_empty_model_response`
- progress_observed: `6/8`
- committed smoke artifacts/results: `false`
- performance claim: `false`

## Allowed Shape Diff

Only field-level structure may be written: route/model, request top-level keys, message count, role sequence, content length buckets, tools count, tool schema structural flags and hash, tool choice mode, token field presence, timeout/streaming flags, parser expected response keys, reviewed run-id references, and empty-response handling path labels. Raw prompts, provider payloads, response bodies, headers, logs, traces, case content, gold/reference/expected, scorer diffs, endpoint/key values, source nonce mappings, and candidate output are forbidden.
