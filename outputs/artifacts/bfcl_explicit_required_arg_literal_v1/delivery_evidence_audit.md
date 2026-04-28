# First-Stage Delivery Evidence Audit

- Claim status: `scaffold_and_diagnostic_package_only`
- SOTA +3pp claim ready: `False`
- Offline only: `True`
- P0 blockers: `['artifact_boundary_not_clean', 'm2_8pre_offline_not_passed', 'scorer_authorization_not_ready', 'policy_conversion_not_observed_in_existing_traces', 'runtime_dry_run_compiler_not_ready']`

## Gate Snapshot

- Artifact boundary passed: `False`
- Forbidden artifact count: `14992`
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
- Policy candidate count: `63`
- Recommended tools count: `67`
- Candidate capability distribution: `{'copy': 6, 'create_file': 18, 'directory_navigation': 18, 'move_or_rename': 4, 'read_content': 8, 'search_or_find': 4, 'write_content': 5}`
- Postcondition low-risk review eligible: `12`
- Postcondition already satisfied filtered: `82`
- Postcondition negative controls ready: `True`
- Postcondition negative-control activation count: `0`
- Runtime dry-run compiler ready: `False`
- Runtime dry-run compiler blocker: `low_risk_support_too_small_or_witness_precision_pending`

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

## Source/Layout Evidence

- Source result availability ready: `True`
- Alias family coverage zero: `True`
- Deterministic family coverage zero: `True`
- Source result root cause: `source_collection_subset_vs_full_dataset_audit_scope_mismatch`
- Source scope mismatch count: `2065`
- Audit missing source result count: `1690`
- Route recommendation: `align_audit_scope_with_source_collection_subset`

This audit is diagnostic. It does not authorize BFCL/model/scorer runs.
