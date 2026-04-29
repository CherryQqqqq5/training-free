# Stage-1 BFCL Performance Ready

- Formal BFCL performance acceptance ready: `False`
- Provider green preflight passed: `False`
- Paired BFCL score chain ready: `False`
- Required 3pp target passed: `False`
- Performance claim allowed: `False`
- Artifact boundary passed: `True`
- M2.8-pre offline passed: `False`
- Blockers: `['provider_green_preflight_not_passed', 'paired_bfcl_score_chain_not_ready', 'baseline_candidate_manifest_alignment_not_passed', 'required_3pp_target_not_passed', 'performance_claim_not_allowed', 'm2_8pre_offline_not_passed', 'scorer_authorization_not_ready', 'provider_auth_401', 'provider_required_fields_not_green', 'paired_comparison_missing', 'acceptance_decision_missing', 'regression_report_missing', 'cost_latency_report_missing', 'baseline_run_artifact_schema_not_passed', 'candidate_run_artifact_schema_not_passed', 'baseline_run_kind_invalid', 'candidate_run_kind_invalid', 'absolute_delta_missing', 'paired_accuracy_missing', 'acceptance_decision_3pp_not_passed', 'cost_latency_not_within_bounds', 'combined_theory_prior_holdout_not_ready', 'wrong_arg_key_alias_family_coverage_zero', 'deterministic_schema_local_family_coverage_zero', 'combined_demote_candidate_below_35', 'explicit_literal_candidate_pool_gate_not_passed', 'explicit_total_below_40', 'explicit_demote_candidate_below_35', 'wrong_arg_key_alias_demote_below_20', 'deterministic_schema_local_demote_below_20', 'explicit_ambiguous_literal_present', 'explicit_holdout_below_20', 'combined_theory_prior_holdout_below_20', 'stratified_without_complete_theory_priors_not_authorized']`
- Next action: `fix_provider_then_generate_same_protocol_baseline_candidate_bfcl_scores`

## Formal Stage-1 Blockers After R3

| Blocker | Current status | Required to clear |
| --- | --- | --- |
| `provider_green` | `blocked` | `provider_green_preflight_passed=true` with approved credential, frozen provider/model route, BFCL alias, runtime config, and clean artifact boundary |
| `source_manifests` | `blocked_until_provider_green` | Provider-green source collection manifests signed for the frozen provider/model/protocol and compact artifact boundary |
| `35_plus_explicit_literal_pool` | `blocked` | `explicit_literal_candidate_pool_passed=true` with at least 35 eligible explicit literal candidates |
| `dev_holdout_split` | `blocked` | Dev20 and holdout20 manifests ready, disjoint, integrity-checked, and not sourced from scorer/gold leakage |
| `scorer_authorization` | `blocked` | Provider green, source manifests, no-leakage, dev/holdout split, SOTA/baseline freeze, and explicit literal pool gate all signed |
| `paired_bfcl_scorer` | `missing` | Same-protocol baseline and candidate BFCL scorer artifacts, run schemas, manifest alignment, regression report, cost/latency report, and paired comparison |
| `sota_3pp_claim` | `not_ready` | Frozen comparator and `absolute_delta_pp >= 3.0` with `required_3pp_target_passed=true` and `performance_claim_allowed=true` |

Offline pool audit may proceed without acceptance risk only as scaffold and
diagnostic evidence. It must not call provider, BFCL, a model, or a scorer; it
must not be counted as source collection evidence, scorer authorization, paired
BFCL evidence, or SOTA/+3pp readiness. Accepted offline extractor candidates
cannot clear acceptance until provider green, signed source manifests, and
pool/split gates pass.

This checker is offline-only. It verifies performance evidence artifacts but does not run BFCL, a model, or a scorer.
