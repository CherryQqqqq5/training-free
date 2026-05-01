# RASHE source real-trace approval packet

- report_scope: `rashe_source_real_trace_approval_packet`
- approval_status: `pending`
- authorized: `false`
- source_collection_authorized: `false`
- provider_calls_authorized: `false`
- raw_trace_capture_authorized: `false`
- raw_payload_capture_authorized: `false`
- candidate_generation_authorized: `false`
- scorer_authorized: `false`
- performance_evidence: `false`
- huawei_acceptance_ready: `false`

This packet is preparation only. It does not authorize source collection, raw trace capture, provider calls, candidate generation, candidate JSONL, scorer use, paired comparison, performance evidence, SOTA/+3pp claims, or Huawei acceptance readiness.

## Purpose
Future approval boundary for real trace/source collection inputs to RASHE. The current lane remains pending/fail-closed.

## Required Future Conditions
- bounded source scope signed by reviewer
- separately signed raw root before any raw capture
- raw payload handling plan approved
- sanitization policy approved
- artifact boundary and path denylist gates passing

## Raw Payload Handling Rules
- No source collection or raw payload capture is authorized while approval_status is `pending`.
- Any future raw payload capture requires a separately signed raw root outside tracked artifacts.
- No raw payload, raw trace, raw case ID, provider payload, or scorer output may be committed to tracked artifacts.

## Sanitization And Publication Rules
- Publish only sanitized compact artifacts after separate approval.
- Allowed publication shape is hashes, aggregate counters, source scope labels, and no-leakage audit booleans only.
- Forbidden fields and path indicators must be rejected before artifact publication.
- Candidate JSONL and dev/holdout/full manifests remain unauthorized.

## Forbidden Fields
- raw_case_id
- raw_trace
- raw_provider_payload
- gold
- expected
- reference
- scorer_diff
- candidate_output
- repair_output
- feedback
- holdout_feedback
- full_suite_feedback

## Path Denylist
- `provider://`
- `scorer://`
- `source_collection://`
- `/provider/`
- `/scorer/`
- `/source_collection/`
- `outputs/bfcl_runs`
- `raw_trace`
- `raw_response_capture`

## Zero Counters
- provider_call_count: `0`
- source_collection_call_count: `0`
- scorer_call_count: `0`
- candidate_call_count: `0`
- raw_trace_count: `0`
- raw_payload_capture_count: `0`
- tracked_raw_payload_count: `0`
- raw_path_leak_count: `0`
- path_denylist_violation_count: `0`
- forbidden_field_violation_count: `0`
- artifact_boundary_failure_count: `0`

## Rollback / Stop Gates
- source/provider/scorer/candidate count nonzero
- forbidden field violation
- path denylist or raw path leak
- artifact boundary failure
- tracked raw payload artifact detected
