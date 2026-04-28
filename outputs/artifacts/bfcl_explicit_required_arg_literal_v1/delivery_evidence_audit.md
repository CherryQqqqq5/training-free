# First-Stage Delivery Evidence Audit

- Claim status: `scaffold_and_diagnostic_package_only`
- SOTA +3pp claim ready: `False`
- Offline only: `True`
- P0 blockers: `['artifact_boundary_not_clean', 'm2_8pre_offline_not_passed', 'scorer_authorization_not_ready', 'policy_conversion_not_observed_in_existing_traces', 'runtime_dry_run_compiler_not_ready', 'postcondition_dev_smoke_stop_loss_failed', 'postcondition_candidate_mining_gap_filter_not_passed', 'postcondition_smoke_protocol_not_ready', 'low_risk_unmet_postcondition_pool_too_small']`

## Gate Snapshot

- Artifact boundary passed: `False`
- Forbidden artifact count: `16903`
- M2.8-pre passed: `False`
- Scorer authorization ready: `False`
- Remaining gap to 35 demote candidates: `18`

## Policy Conversion Evidence

- Trace files scanned: `5000`
- Rule hits: `388`
- Policy hits: `0`
- Recommended tools: `0`
- Selected next tool: `0`
- Next tool emitted: `0`
- Policy conversion observed: `False`
- Rule hits without policy hits: `388`
- Policy conversion absent reason: `policy_artifact_or_runtime_candidate_missing`

## Policy Opportunity Evidence

- Opportunity audit ready: `True`
- Policy candidate count: `54`
- Recommended tools count: `56`
- Candidate capability distribution: `{'copy': 6, 'create_file': 18, 'directory_navigation': 18, 'move_or_rename': 4, 'read_content': 1, 'search_or_find': 2, 'write_content': 5}`
- Postcondition low-risk review eligible: `3`
- Postcondition already satisfied filtered: `91`
- Postcondition negative controls ready: `True`
- Postcondition negative-control activation count: `0`
- Runtime dry-run compiler ready: `False`
- Runtime dry-run compiler blocker: `low_risk_support_too_small_or_witness_precision_pending`

## Postcondition Dev Smoke Evidence

- Smoke result ready: `True`
- Smoke stop-loss passed: `False`
- Smoke cases / activated / diagnostic inactive: `9` / `6` / `3`
- Fixed / regressed / net gain: `0` / `0` / `0`
- Candidate recommended-tool matches: `0`
- Primary failure source: `model_ignored_soft_guidance_or_postcondition_gap_overestimated`
- Activated candidate no-tool count: `6`
- Satisfaction audit ready: `True`
- Candidate mining gap filter passed: `False`
- Already satisfied in smoke: `9`
- Strong unmet in smoke: `0`
- Current smoke protocol ready: `False`
- Current selected cases / runtime replay activation: `3` / `1`
- Current protocol first failure: `{'actual': 3, 'check': 'selected_low_risk_case_count', 'expected': 9}`
- Protocol gating state: `fail_closed`
- Evidence classification: `negative_evidence_blocked_claim`

## Unmet Postcondition Source Expansion

- Audit ready: `True`
- Typed satisfaction distribution: `{'ambiguous': 7413, 'satisfied_strong': 831, 'satisfied_weak': 644, 'unmet_strong': 366}`
- Strong unmet candidates: `18`
- Low-risk strong unmet candidates: `1`
- High-risk strong unmet candidates: `17`
- Strong unmet capability distribution: `{'copy': 1, 'create_file': 4, 'directory_navigation': 8, 'read_content': 1, 'write_content': 4}`
- Strong unmet risk lane distribution: `{'high_risk_mutation_or_trajectory': 17, 'low_risk_observation': 1}`
- Next action: `expand_source_or_state_abstraction_before_smoke`

## Memory Operation Obligation Evidence

- Memory audit ready: `True`
- Memory operation candidates: `78`
- Memory candidate operations: `{'retrieve': 78}`
- Memory candidate categories: `{'memory_kv': 30, 'memory_rec_sum': 48}`
- Memory runtime enabled: `False`
- Memory negative controls passed: `True`
- Memory approval manifest ready: `True`
- Memory approval manifest sanitized: `True`
- Memory review manifest compiler input eligible count: `0`
- Memory compiler allowlist ready: `True`
- Memory compiler allowlist input count: `48`
- Memory first-pass review candidates: `48`
- Memory second-pass review candidates: `30`
- Memory dry-run policy ready: `True`
- Memory dry-run policy units: `1`
- Memory dry-run first-pass support: `48`
- Memory dry-run argument creation count: `0`
- Memory resolver audit passed: `True`
- Memory resolver resolved schemas: `48`
- Memory resolver blocked destructive tools: `288`
- Memory resolver forbidden mutation resolved count: `0`
- Memory activation simulation passed: `True`
- Memory activation count: `48`
- Memory activation negative-control count: `0`
- Memory activation argument creation count: `0`
- Memory runtime adapter ready: `True`
- Memory dev smoke ready: `True`
- Memory runtime loaded memory rules: `1`
- Memory runtime smoke next action: `request_separate_memory_only_dev_smoke_approval`

## Source/Layout Evidence

- Source result availability ready: `True`
- Alias family coverage zero: `True`
- Deterministic family coverage zero: `True`
- Source result root cause: `source_collection_subset_vs_full_dataset_audit_scope_mismatch`
- Source scope mismatch count: `2065`
- Audit missing source result count: `1690`
- Route recommendation: `align_audit_scope_with_source_collection_subset`

This audit is diagnostic. It does not authorize BFCL/model/scorer runs.
