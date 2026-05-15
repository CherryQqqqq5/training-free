# Stage 1 ABHE State Tracking Candidate Spec Draft

entry_id: `state_tracking_v0`

target_behavior_cluster: `multi_turn_state_lost`

activation_predicates:

- multi-turn only
- state carryover evidence required
- previous-turn entity, constraint, or selected option must be referenced by a later turn
- current compact diagnostic must indicate state loss

non_target_exclusion_predicates:

- single-turn excluded
- search/memory watch excluded
- no mutation
- answerability-only failures excluded
- ambiguous mixed-mechanism cases excluded

primary_metrics:

- `target_bucket_reduction`
- `fixed_count`
- `regressed_count`
- `net_fixed`

safety_metrics:

- `non_target_regression_count`
- `activation_precision`
- `activation_recall`
- `cost_delta_pct`
- `latency_delta_pct`
- `leakage_count`
- `boundary_violation_count`

telemetry_requirements:

- activation decision
- matched behavior cluster
- stop condition decision
- compact-only bucket result

stop_loss:

- `fixed_count <= regressed_count`
- `target_bucket_reduction <= 0`
- high non-target regression
- leakage or boundary violation
- cost or latency cap exceeded

rollback:

- demote to `demoted_regression_not_controlled` when regressions dominate
- request narrower router when non-target regression is high
- split when mixed strata obscure the mechanism

not_authorized_surfaces:

- provider calls
- BFCL generation or evaluation
- scorer execution
- executable rule materialization
- holdout or full suite
- performance, SOTA, +3pp, or Huawei acceptance claims
