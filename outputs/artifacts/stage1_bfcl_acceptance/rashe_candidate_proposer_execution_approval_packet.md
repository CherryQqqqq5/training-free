# RASHE candidate proposer execution approval packet

- report_scope: `rashe_candidate_proposer_execution_approval_packet`
- approval_status: `pending`
- authorized: `false`
- performance_evidence: `false`
- scorer_authorized: `false`
- candidate_generation_authorized: `false`
- huawei_acceptance_ready: `false`

This is a fail-closed approval skeleton. It does not authorize execution, provider calls, source collection, candidate generation, scorer use, paired comparison, performance evidence, SOTA/+3pp claims, or Huawei acceptance readiness.

## Purpose
Future approval boundary for candidate/proposer execution after separate no-leakage review.

## Prerequisites
- approved source scope exists
- no-leakage gate reviewed
- proposal schema gate passed
- candidate pool promotion criteria signed
- dev/holdout split policy reviewed before any scorer use

## Allowed If Approved
- bounded proposer execution over approved sanitized inputs
- candidate metadata draft generation after approval
- candidate pool checker execution
- compact no-leakage audit artifacts

## Forbidden Until Approved
- candidate/proposer execution
- candidate JSONL
- dev/holdout manifest creation
- gold/expected use
- scorer diff use
- holdout/full-suite feedback use
- performance evidence

## Rollback / Stop Gates
- any leakage counter nonzero stops candidate promotion
- candidate checker failure stops pool use
- holdout/full-suite feedback in candidate path stops execution
- ambiguous proposal source stops execution

## No-Leakage Defaults
- candidate_output_used: `false`
- case_id_specific_rules_allowed: `false`
- expected_used: `false`
- full_suite_feedback_used: `false`
- gold_used: `false`
- holdout_feedback_used: `false`
- raw_trace_committed: `false`
- scorer_diff_used: `false`
