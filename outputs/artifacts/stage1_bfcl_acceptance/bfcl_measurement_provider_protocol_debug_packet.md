# BFCL Measurement Provider Protocol Debug Packet

Status: `approved` for exactly one synthetic, pre-BFCL provider protocol debug request path. This does not authorize BFCL smoke, BFCL full/default evaluation, scorer execution, candidate activation, performance evidence, +3pp claims, SOTA claims, or Huawei readiness.

## Signed Route

- provider_profile: `Chuangzhi/Novacode`
- active_profile: `novacode`
- route_model: `gpt-4.1`
- fallback_allowed: `false`
- gpt-4o fallback: `false`
- OpenRouter: `false`
- endpoint/key policy: env-only, value not committed

## Failed Stage 1 Attempt Status

- failure_class: `empty_model_response_before_measurement_completion`
- completed_cases_before_stop: `4`
- observed_progress: `4/5217`
- metrics_produced: `false`
- manifest_produced: `false`
- performance_evidence: `false`
- +3pp/Huawei claim: `false`

This failed attempt is protocol/runtime readiness evidence only. It is not measurement evidence.

## Authorization Boundary

- protocol_debug_preparation_authorized: `true`
- protocol_debug_execution_authorized: `true`
- provider_request_authorized: `true`
- provider_request_scope: `exactly_one_synthetic_pre_bfcl_protocol_debug_path`
- provider_request_count: `1`
- bfcl_smoke_authorized: `false`
- bfcl_full_eval_authorized: `false`
- scorer_authorized: `false`
- candidate_specs_inert: `true`
- candidate_runtime_activation_authorized: `false`
- candidate_jsonl_authorized: `false`
- candidate_pool_ready: `false`
- performance_evidence: `false`
- sota_3pp_claim_ready: `false`
- huawei_acceptance_ready: `false`

## Synthetic Debug Scope

The approved execution path may use only one synthetic, pre-BFCL protocol probe against the signed `novacode` / `gpt-4.1` route. The probe checks empty-response detection, required tool-call detection, and OpenAI-compatible response shape detection. It must not use BFCL cases, source inputs, prompts, gold/reference material, scorer feedback, candidate specs, candidate output, or Phase B diagnostics.

Raw logs, raw traces, provider payloads, prompts, headers, request bodies, response bodies, endpoint values, and key values are not approved for persistence or commit. The runner may emit only compact sanitized booleans/status fields.
