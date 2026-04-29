# Explicit Obligation Smoke Ready

- Ready: `False`
- Execution allowed: `False`
- Gates: `{'bfcl_executable_manifest_ready': True, 'smoke_selection_ready_after_baseline_dry_audit': False, 'selection_gate_passed': False, 'artifact_boundary_passed': False, 'scorer_authorization_ready': False, 'candidate_commands_empty': True, 'planned_commands_empty': True}`
- Source-pool negative-control activations: `0`
- Materialized protocol negative-control activations: `14`
- Selected smoke baseline control activations: `0`
- Candidate commands: `[]`
- Planned commands: `[]`
- Blockers: `['smoke_selection_not_ready_after_baseline_dry_audit', 'selection_gate_not_passed', 'artifact_boundary_not_passed', 'scorer_authorization_not_ready', 'blocked_insufficient_true_controls', 'primary_positive_capability_miss_below_6', 'baseline_ceiling_positive_count_above_2', 'control_memory_activation_present']`
- Next action: `rebuild_candidate_pool_or_upgrade_theory_prior_before_smoke`
- Next required actions: `['rebuild_candidate_pool_or_upgrade_theory_prior_before_smoke', 'clean_or_move_forbidden_artifacts_before_smoke', 'repair_m2_8pre_scorer_authorization_before_smoke']`

This checker is offline-only. It does not authorize BFCL/model/scorer execution.
