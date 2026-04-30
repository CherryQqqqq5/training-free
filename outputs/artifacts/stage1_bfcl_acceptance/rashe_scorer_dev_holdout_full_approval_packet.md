# RASHE scorer dev/holdout/full approval packet

- report_scope: `rashe_scorer_dev_holdout_full_approval_packet`
- approval_status: `pending`
- authorized: `false`
- performance_evidence: `false`
- scorer_authorized: `false`
- candidate_generation_authorized: `false`
- huawei_acceptance_ready: `false`

This is a fail-closed approval skeleton. It does not authorize execution, provider calls, source collection, candidate generation, scorer use, paired comparison, performance evidence, SOTA/+3pp claims, or Huawei acceptance readiness.

## Purpose
Future approval boundary for scorer use after candidate pool and split gates pass.

## Prerequisites
- same provider/model/protocol comparator frozen
- candidate pool ready and no-leakage clean
- dev/holdout disjoint manifests signed
- baseline and candidate commands reviewed
- paired comparison checker reviewed

## Allowed If Approved
- baseline dev scorer command
- candidate dev scorer command
- holdout scorer command after dev pass
- paired baseline/candidate comparison artifacts
- compact run schema artifacts

## Forbidden Until Approved
- BFCL scorer
- candidate run
- paired comparison
- dev/holdout/full-suite scoring
- provider/model/protocol drift
- gold leakage into candidate path
- performance claim before paired gate

## Rollback / Stop Gates
- same provider/model/protocol mismatch stops scoring
- dev/holdout overlap stops scoring
- paired comparison regression stops claim
- run schema checker failure stops claim

## No-Leakage Defaults
- candidate_output_used: `false`
- case_id_specific_rules_allowed: `false`
- expected_used: `false`
- full_suite_feedback_used: `false`
- gold_used: `false`
- holdout_feedback_used: `false`
- raw_trace_committed: `false`
- scorer_diff_used: `false`
