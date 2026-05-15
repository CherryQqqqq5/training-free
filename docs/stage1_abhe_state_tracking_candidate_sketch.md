# Stage 1 ABHE State Tracking Candidate Sketch

Entry: `state_tracking_v0`

Target bucket: `multi_turn_state_lost`

Hypothesis: a state tracking, router, or stop condition harness patch may reduce multi-turn state loss when the fresh dev slice contains state carryover failures.

Activation boundary:

- Multi-turn only.
- Fresh dev slice only.
- Paired baseline/candidate evaluation only after a separate bounded dev smoke approval.
- No watch entry, holdout, full suite, provider call, BFCL run, or scorer is authorized by this sketch.

Primary metrics:

- `target_bucket_reduction`
- `fixed_count`
- `regressed_count`
- `non_target_regression_count`
- `cost_delta_pct`
- `latency_delta_pct`

Risks:

- Non-target regression.
- Over-routing state tracking to cases that do not need it.
- Stop condition drift.
- Latency or token increase.

Stop-loss:

- `fixed_count <= regressed_count`
- Non-target regression is high.
- Leakage or boundary violation is detected.
- Cost or latency exceeds the approved cap.

This sketch does not define a prompt patch, candidate YAML, dev case list, or raw example. It exists only to make the future execution packet reviewable.
