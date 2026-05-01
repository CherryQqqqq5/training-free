# RASHE source real-trace approval packet

- report_scope: `rashe_source_real_trace_approval_packet`
- approval_status: `approved`
- authorized: `true`
- source_collection_authorized: `true`
- provider_calls_authorized: `true`
- provider_profile: `Chuangzhi/Novacode`
- provider_model: `gpt-5.2`
- raw_trace_capture_authorized: `false`
- raw_payload_capture_authorized: `false`
- candidate_generation_authorized: `false`
- candidate_pool_ready: `false`
- scorer_authorized: `false`
- performance_evidence: `false`
- sota_3pp_claim_ready: `false`
- huawei_acceptance_ready: `false`

This approval is limited to bounded source evidence collection. Execution still requires passing `scripts/check_rashe_source_real_trace_approved.py --compact --strict` and following `docs/stage1_rashe_source_collection_runbook.md`. This commit does not execute collection.

## Approved Categories
- `agentic_web_search`
- `agentic_memory`
- `multi_turn_base`
- `multi_turn_long_context`
- `multi_turn_miss_param`
- `multi_turn_miss_func`
- `hallucination`
- `irrelevance`

Case count: 20-50 per category, total 100-200 max.

## Allowed Outputs
Only compact sanitized counters, hashes, category labels, and no-leakage audit booleans may be published under `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/`.

## Still Forbidden
- raw trace capture
- raw payload capture or tracked raw payloads
- raw provider payload tracked or committed
- raw case ID, gold, expected, reference, scorer diff, candidate output, repair output, feedback, holdout feedback, or full-suite feedback
- candidate generation or candidate JSONL
- BFCL scorer execution
- dev/holdout/full manifests
- performance evidence, BFCL +3pp, SOTA, or Huawei acceptance claims

## Hard Stop Gates
- raw trace tracked or raw payload tracked/committed
- raw provider payload tracked/committed
- forbidden field or path denylist hit
- candidate JSONL created
- scorer executed
- artifact boundary failure
- candidate_call_count nonzero
- scorer_call_count nonzero
- raw_payload_tracked_count nonzero
- forbidden_field_violation_count nonzero

## Compact Diagnostic Schema
Schema path: `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json`.

Required fields: `category`, `case_count`, `provider_call_count`, `raw_payload_tracked_count`, `forbidden_field_violation_count`, `failure_bucket_counts`, `candidate_generation_authorized`, `scorer_authorized`, `performance_evidence`.
