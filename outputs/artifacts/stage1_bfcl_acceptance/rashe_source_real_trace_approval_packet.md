# RASHE source real-trace approval packet

- report_scope: `rashe_source_real_trace_approval_packet`
- approval_status: `pending`
- authorized: `false`
- performance_evidence: `false`
- scorer_authorized: `false`
- candidate_generation_authorized: `false`
- huawei_acceptance_ready: `false`

This is a fail-closed approval skeleton. It does not authorize execution, provider calls, source collection, candidate generation, scorer use, paired comparison, performance evidence, SOTA/+3pp claims, or Huawei acceptance readiness.

## Purpose
Future approval boundary for real trace/source collection inputs to RASHE.

## Prerequisites
- runtime/source approval signed separately
- raw payload handling plan reviewed
- sanitization policy reviewed
- forbidden field denylist enforced
- artifact boundary pass required

## Allowed If Approved
- bounded source collection for approved categories only
- raw payload capture under approved raw root only
- compact sanitized counters and hashes
- artifact-boundary-checked manifests

## Forbidden Until Approved
- raw trace collection
- source collection
- raw payload committed to tracked artifacts
- gold/expected/scorer/candidate fields
- candidate generation
- scorer execution
- performance claim

## Rollback / Stop Gates
- forbidden field violation stops collection
- artifact boundary failure stops publication
- raw path leak stops promotion
- provider/model drift stops run

## No-Leakage Defaults
- candidate_output_used: `false`
- case_id_specific_rules_allowed: `false`
- expected_used: `false`
- full_suite_feedback_used: `false`
- gold_used: `false`
- holdout_feedback_used: `false`
- raw_trace_committed: `false`
- scorer_diff_used: `false`
