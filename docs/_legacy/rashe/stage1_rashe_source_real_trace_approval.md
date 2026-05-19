# Stage 1 RASHE Source Real-Trace Approval Preparation

Status: `pending` / `authorized=false`. This document prepares the approval lane only. It does not authorize source collection, raw trace capture, provider calls, candidate generation, BFCL scorer execution, performance evidence, SOTA/+3pp claims, or Huawei acceptance readiness.

Current gate: `scripts/check_rashe_source_real_trace_approval_packet.py --compact --strict`. Passing this gate means the packet remains fail-closed; it is not execution approval.

## Required Pending Boundary

- `source_real_trace_approval_status=pending`
- `authorized=false`
- `source_collection_authorized=false`
- `provider_calls_authorized=false`
- `raw_trace_capture_authorized=false`
- `raw_payload_capture_authorized=false`
- `candidate_generation_authorized=false`
- `candidate_pool_ready=false`
- `scorer_authorized=false`
- `performance_evidence=false`
- `sota_3pp_claim_ready=false`
- `huawei_acceptance_ready=false`

## Future Approval Conditions Only

Before any future source collection can be considered, reviewers must sign a bounded source scope, a raw payload handling plan, a separately signed raw root outside tracked artifacts, sanitization rules, artifact boundary gates, forbidden field gates, and path denylist gates.

Publication, if separately approved later, must be hash/counter-only sanitized compact artifacts. Raw payloads, raw traces, raw case IDs, provider payloads, scorer outputs, candidate outputs, candidate JSONL, and dev/holdout/full manifests remain out of scope.

## Fail-Closed Stop Gates

Any nonzero source/provider/scorer/candidate count, raw path leak, forbidden field, tracked raw payload artifact, or artifact boundary failure blocks this lane.
