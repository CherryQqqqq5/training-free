# RASHE performance +3pp Huawei acceptance approval packet

- report_scope: `rashe_performance_3pp_huawei_acceptance_approval_packet`
- approval_status: `pending`
- authorized: `false`
- performance_evidence: `false`
- scorer_authorized: `false`
- candidate_generation_authorized: `false`
- huawei_acceptance_ready: `false`

This is a fail-closed approval skeleton. It does not authorize execution, provider calls, source collection, candidate generation, scorer use, paired comparison, performance evidence, SOTA/+3pp claims, or Huawei acceptance readiness.

## Purpose
Future approval boundary for BFCL +3pp/SOTA/Huawei readiness claims after paired evidence exists.

## Prerequisites
- paired BFCL baseline/candidate comparison passed
- +3pp delta evidence present
- no regression gate passed
- cost/latency gates passed
- artifact boundary and run schema gates passed
- Huawei acceptance owner signoff requested

## Allowed If Approved
- formal performance evidence publication after paired gate
- SOTA/+3pp claim after signed acceptance review
- Huawei readiness artifact after owner approval

## Forbidden Until Approved
- performance evidence
- SOTA/+3pp claim
- Huawei acceptance readiness claim
- claim from unpaired or partial score
- claim from provider/model drift
- claim before no-leakage and regression gates

## Rollback / Stop Gates
- +3pp threshold miss stops claim
- any paired regression stops claim
- cost/latency bound failure stops claim
- artifact boundary failure stops claim
- Huawei owner rejection stops claim

## No-Leakage Defaults
- candidate_output_used: `false`
- case_id_specific_rules_allowed: `false`
- expected_used: `false`
- full_suite_feedback_used: `false`
- gold_used: `false`
- holdout_feedback_used: `false`
- raw_trace_committed: `false`
- scorer_diff_used: `false`
