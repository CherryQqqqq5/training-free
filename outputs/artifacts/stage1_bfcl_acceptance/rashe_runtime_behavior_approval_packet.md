# RASHE runtime behavior approval packet

- report_scope: `rashe_runtime_behavior_approval_packet`
- approval_status: `pending`
- authorized: `false`
- performance_evidence: `false`
- scorer_authorized: `false`
- candidate_generation_authorized: `false`
- huawei_acceptance_ready: `false`

This is a fail-closed approval skeleton. It does not authorize execution, provider calls, source collection, candidate generation, scorer use, paired comparison, performance evidence, SOTA/+3pp claims, or Huawei acceptance readiness.

## Purpose
Future approval boundary for default-disabled RASHE runtime behavior.

## Prerequisites
- rashe_offline_scaffold_ready=true
- runtime skeleton remains default disabled
- rollback plan reviewed
- cost latency regression gates defined
- no provider/scorer side effect proof reviewed

## Allowed If Approved
- default-disabled runtime behavior wiring
- bounded skill router invocation in reviewed path
- compact verifier counters
- rollbackable config toggle

## Forbidden Until Approved
- prompt injection
- retry
- tool path mutation
- RuleEngine/proxy active path import
- provider side effects
- scorer side effects
- source collection
- candidate generation
- dev/holdout/full BFCL

## Rollback / Stop Gates
- default_enabled must remain false until separate enable approval
- any provider/scorer/source side effect stops execution
- cost/latency/regression gate failure stops execution
- ambiguous router decision fail-closed

## No-Leakage Defaults
- candidate_output_used: `false`
- case_id_specific_rules_allowed: `false`
- expected_used: `false`
- full_suite_feedback_used: `false`
- gold_used: `false`
- holdout_feedback_used: `false`
- raw_trace_committed: `false`
- scorer_diff_used: `false`
