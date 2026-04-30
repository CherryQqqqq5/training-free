# Stage-1 BFCL Negative Evidence Report

This report summarizes why the current Stage-1 BFCL +3pp claim is not
supportable under the approved evidence gates. It is a negative-evidence and
delivery-risk artifact, not a performance claim.

## Readiness State

- Provider technical preflight: green for Chuangzhi/Novacode `novacode` /
  `gpt-5.2`. Provider green is not scorer authorization.
- Candidate pool ready: `false`.
- Scorer authorized: `false`.
- Performance evidence: `false`.
- SOTA/+3pp claim ready: `false`.
- Huawei acceptance ready: `false`.
- Current blocker: `deterministic_stage1_family_search_exhausted`.
- Next action: `negative_evidence_report_or_scope_change_review`.

## Family Evidence Table

| family / hypothesis | evidence source | key counters | stop gate | result |
| --- | --- | --- | --- | --- |
| `explicit_required_arg_literal_completion` | `outputs/artifacts/stage1_bfcl_acceptance/batch1_full50_extractor_yield_diagnostic.json`; `outputs/artifacts/stage1_bfcl_acceptance/batch2_source_collection_pilot_snapshot.json` | Batch1/Batch2 selected-call diagnostics show `selected_calls_with_missing_required=0`, `selected_calls_with_exactly_one_missing_required_arg=0`, `accepted_candidates=0` | no selected call with exactly one missing required arg | zero-yield; candidate pool not authorized |
| `wrong_arg_key_alias_repair` | `outputs/artifacts/stage1_bfcl_acceptance/wrong_arg_key_alias_repair_diagnostic.json` | `alias_repair_eligible_count=0` | no deterministic unique alias repair | zero-yield; candidate pool not authorized |
| `deterministic_schema_local_non_live_repair` | `outputs/artifacts/stage1_bfcl_acceptance/schema_local_non_live_repair_diagnostic.json` | `schema_local_repair_eligible_count=0` | no deterministic schema-local conversion | zero-yield; candidate pool not authorized |
| structural malformed/final-before-tool | `outputs/artifacts/stage1_bfcl_acceptance/selected_call_structural_failure_attribution_raw_pilot.json` | `parser_refined=true`, `raw_candidate_tool_call_count=25`, `raw_schema_matched_tool_call_count=14`, eligible structural count `0` | no strict malformed/final-before-tool eligibility | zero-yield; structural expansion unauthorized |
| raw tool-name/schema normalization | `outputs/artifacts/stage1_bfcl_acceptance/raw_payload_schema_not_matched_subtyping_audit.json` | bucket 10/10, `no_schema_name_candidate_count=10`, `deterministic_source_schema_only_possible_count=0` | no source-schema-only deterministic tool-name match | zero-yield; normalization family unauthorized |
| schema retrieval/rerank feasibility | `outputs/artifacts/stage1_bfcl_acceptance/schema_retrieval_rerank_feasibility_diagnostic.json` | `single_schema_high_margin_count=0`, `all_schema_scores_tied_or_low_margin_count=10`, `multiple_high_margin_schema_candidates_count=4` | high-margin schema retrieval stop gates fail | zero-yield; recommendation `stop_no_yield_research_review` |
| baseline-only scored failure taxonomy | `outputs/artifacts/stage1_bfcl_acceptance/baseline_only_scored_failure_taxonomy_audit.json` | `scored_case_count=30`, `baseline_failure_count=22`, taxonomy denominator `22` failure detail rows | audit-only; no candidate extraction or performance scoring | diagnostic taxonomy only; not +3pp evidence |

## No-Leakage Boundary

The zero-yield candidate diagnostics do not use scorer gold, expected answers,
references, candidate outputs, repair outputs, or per-case scorer diffs for
candidate generation. The baseline-only scored taxonomy was approved only for
aggregate failure taxonomy and compact hashes/counters; it does not authorize
case selection, candidate JSONL, dev/holdout manifests, prompt tuning, provider
tuning, or repair recommendations.

## Why +3pp Is Not Supportable Now

A +3pp claim requires a ready candidate pool, aligned baseline/candidate scorer
runs, paired comparison, regression accounting, and accepted cost/latency
limits. The current evidence has no authorized candidate pool and no candidate
scorer chain. Provider green and scored taxonomy artifacts are diagnostic
inputs, not performance evidence. Therefore SOTA/+3pp and Huawei acceptance
claims are forbidden.

## Overfitting Controls

The engineering stop condition is deliberate: no Batch3, no family hunting, no
source expansion, no scorer rerun, and no candidate-pool promotion under current
evidence. Continuing to search for a small positive slice after multiple
zero-yield deterministic diagnostics would weaken the claim boundary and raise
overfitting risk.

## Future Scope-Change Options

The following are not authorized and are not performance claims. They require a
separate scope-change decision before implementation or execution:

- schema/parser feedback retry
- prompt or context canonicalization
- verifier or test-time repair
- training/data route

Until such a scope change is approved, the active Stage-1 state is fail-closed:
`candidate_pool_ready=false`, `scorer_authorized=false`,
`performance_evidence=false`, `sota_3pp_claim_ready=false`, and
`huawei_acceptance_ready=false`.
