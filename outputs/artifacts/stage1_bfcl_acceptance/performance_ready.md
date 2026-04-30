# Stage-1 BFCL Performance Ready

- Formal BFCL performance acceptance ready: `False`
- Provider green preflight passed: `True`
- Paired BFCL score chain ready: `False`
- Required 3pp target passed: `False`
- Performance claim allowed: `False`
- Artifact boundary passed: `True`
- M2.8-pre offline passed: `False`
- Blockers: `['paired_bfcl_score_chain_not_ready', 'baseline_candidate_manifest_alignment_not_passed', 'required_3pp_target_not_passed', 'performance_claim_not_allowed', 'm2_8pre_offline_not_passed', 'scorer_authorization_not_ready', 'paired_comparison_missing', 'acceptance_decision_missing', 'regression_report_missing', 'cost_latency_report_missing', 'baseline_run_artifact_schema_not_passed', 'candidate_run_artifact_schema_not_passed', 'baseline_run_kind_invalid', 'candidate_run_kind_invalid', 'absolute_delta_missing', 'paired_accuracy_missing', 'acceptance_decision_3pp_not_passed', 'cost_latency_not_within_bounds', 'combined_theory_prior_holdout_not_ready', 'wrong_arg_key_alias_family_coverage_zero', 'deterministic_schema_local_family_coverage_zero', 'combined_demote_candidate_below_35', 'explicit_literal_candidate_pool_gate_not_passed', 'explicit_total_below_40', 'explicit_demote_candidate_below_35', 'wrong_arg_key_alias_demote_below_20', 'deterministic_schema_local_demote_below_20', 'explicit_ambiguous_literal_present', 'explicit_holdout_below_20', 'combined_theory_prior_holdout_below_20', 'stratified_without_complete_theory_priors_not_authorized']`
- Next action: `run_provider_green_source_collection_then_rebuild_candidate_pool_and_generate_paired_scores`

This checker is offline-only. It verifies performance evidence artifacts but does not run BFCL, a model, or a scorer.
