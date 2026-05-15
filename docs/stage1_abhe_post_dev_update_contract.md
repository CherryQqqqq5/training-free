# Stage 1 ABHE Post-Dev Update Contract

ABHE post-dev update is not enabled yet. The current planner must stay fail-closed when dev feedback is present until the post-dev transition code is implemented and reviewed.

Dev feedback records must match `abhe_archive/dev_feedback.schema.json`. Required fields:

- `entry_id`
- `dev_run_id_hash`
- `fresh_dev_slice_hash`
- `target_bucket_reduction`
- `fixed_count`
- `regressed_count`
- `net_fixed`
- `non_target_regression_count`
- `activation_precision`
- `activation_recall`
- `cost_delta_pct`
- `latency_delta_pct`
- `leakage_count`
- `boundary_violation_count`
- `provider_model_protocol_match`
- `raw_material_absent`
- `candidate_pool_created`
- `holdout_touched`
- `full_suite_touched`

Boundary values:

- `provider_model_protocol_match` must be true.
- `raw_material_absent` must be true.
- `candidate_pool_created` must be false.
- `holdout_touched` must be false.
- `full_suite_touched` must be false.
- Raw prompt, raw trace, raw payload, raw case id, gold answer, expected answer, reference answer, scorer diff, candidate output text, provider exchange, endpoint value, and tool argument values must not be persisted.

Future transition rules remain documented but not active:

- `leakage_count > 0` -> `rejected_boundary_failure`
- `target_bucket_reduction <= 0` -> `demoted_no_mechanism_signal`
- `fixed_count <= regressed_count` -> `demoted_regression_not_controlled`
- high non-target regression -> `narrow_router_requested`
- mixed strata result -> `split_requested`
- target bucket down plus fixed greater than regressed plus cost ok -> `dev_passed`

Until those transitions are implemented, `plan_abhe_next_evolution.py` must report `dev_feedback_present_post_dev_planner_not_implemented` and set `next_required_action` to `run_check_abhe_dev_feedback_and_enable_post_dev_planner`.
