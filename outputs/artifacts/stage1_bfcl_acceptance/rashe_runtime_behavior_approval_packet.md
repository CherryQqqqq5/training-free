# RASHE runtime behavior approval packet

- report_scope: `rashe_runtime_behavior_approval_packet`
- approval_status: `approved`
- authorized: `true`
- runtime_behavior_authorized: `true`
- runtime_behavior_scope: `synthetic_default_disabled_only`
- default_enabled_required_if_approved: `false`
- provider_calls_authorized: `false`
- source_collection_authorized: `false`
- candidate_generation_authorized: `false`
- candidate_pool_ready: `false`
- scorer_authorized: `false`
- performance_evidence: `false`
- sota_3pp_claim_ready: `false`
- huawei_acceptance_ready: `false`
- prompt_injection_authorized: `false`
- retry_authorized: `false`
- tool_path_mutation_authorized: `false`

This packet approves only L1 synthetic/default-disabled runtime behavior wiring. It does not authorize real BFCL runtime execution, provider calls, source collection, candidate generation, scorer use, paired comparison, performance evidence, SOTA/+3pp claims, or Huawei acceptance readiness.

## Purpose
Approve config-gated synthetic behavior tests for RASHE SkillRouter/verifier wiring while keeping runtime defaults disabled and all downstream lanes pending.

## Allowed After This Approval
- config-gated skill router call in synthetic tests
- config-gated verifier counters in synthetic tests
- router decision emission without provider/source/scorer side effects
- rollbackable config toggle with `enabled=false` default

## Still Forbidden After Approval
- provider calls
- source collection
- BFCL scorer
- candidate JSONL
- dev/holdout/full BFCL
- prompt injection into real BFCL requests
- retry behavior on real BFCL responses
- tool path mutation
- performance or Huawei acceptance claims
- raw trace, raw case_id, gold, expected answer, or scorer diff use

## Required Stop Gates
- default config must remain `enabled=false`
- any provider/scorer/source side effect stops execution
- any candidate/dev/holdout/full artifact generation stops execution
- ambiguous router decision must fail closed

## No-Leakage Defaults
- candidate_output_used: `false`
- case_id_specific_rules_allowed: `false`
- expected_used: `false`
- full_suite_feedback_used: `false`
- gold_used: `false`
- holdout_feedback_used: `false`
- raw_trace_committed: `false`
- scorer_diff_used: `false`
