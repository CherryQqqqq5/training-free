# Stage 1 ABHE Hallucination Abstain Candidate Spec Draft

entry_id: `hallucination_abstain_v0`

target_behavior_cluster: `unsupported_or_irrelevant_answer`

activation_predicates:

- answerability failure only
- compact diagnostic indicates unsupported, hallucinated, or irrelevant response behavior
- evidence boundary is unclear or insufficient under the target bucket

non_target_exclusion_predicates:

- valid actionable tool-use case excluded
- do not suppress valid tool calls
- state-tracking-only failures excluded
- search/memory watch excluded
- answerable cases excluded

primary_metrics:

- `target_bucket_reduction`
- `fixed_count`
- `regressed_count`
- `net_fixed`

safety_metrics:

- false abstain tracked
- `non_target_regression_count`
- `activation_precision`
- `activation_recall`
- `cost_delta_pct`
- `latency_delta_pct`
- `leakage_count`
- `boundary_violation_count`

telemetry_requirements:

- activation decision
- answerability failure kind
- abstain boundary decision
- compact-only bucket result

stop_loss:

- false abstain on valid actionable cases
- `target_bucket_reduction <= 0`
- `fixed_count <= regressed_count`
- leakage or boundary violation
- cost or latency cap exceeded

rollback:

- demote when there is no mechanism signal
- request narrower router when false abstain or non-target regression is high
- split when answerability buckets are mixed

not_authorized_surfaces:

- provider calls
- BFCL generation or evaluation
- scorer execution
- executable rule materialization
- holdout or full suite
- performance, SOTA, +3pp, or Huawei acceptance claims
