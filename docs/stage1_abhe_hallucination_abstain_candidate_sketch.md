# Stage 1 ABHE Hallucination Abstain Candidate Sketch

Entry: `hallucination_abstain_v0`

Target bucket: `unsupported_or_irrelevant_answer`

Hypothesis: an evidence-boundary verifier or abstain policy may reduce unsupported, hallucinated, or irrelevant answers when the fresh dev slice exposes answerability failures.

Activation boundary:

- The candidate applies only to the target answerability bucket.
- Fresh dev slice only.
- Paired baseline/candidate evaluation only after a separate bounded dev smoke approval.
- No watch entry, holdout, full suite, provider call, BFCL run, or scorer is authorized by this sketch.

Primary metrics:

- `target_bucket_reduction`
- `false_abstain_count`
- `fixed_count`
- `regressed_count`
- `non_target_regression_count`
- `cost_delta_pct`
- `latency_delta_pct`

Risks:

- Over-abstain on valid actionable cases.
- Suppressing valid tool calls.
- Evaluator mismatch between abstain behavior and target answerability.
- Non-target regression.

Stop-loss:

- False abstain appears on valid actionable cases.
- Target bucket does not decrease.
- Regression is high.
- Leakage or boundary violation is detected.

This sketch does not define a prompt patch, candidate YAML, dev case list, or raw example. It exists only to make the future execution packet reviewable.
