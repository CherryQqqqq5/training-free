# Stage 1 ABHE Trace Card Contract

Trace cards are sanitized mechanism explanations. They are not performance evidence, not paired baseline/candidate evidence, and not permission to run BFCL or scorer.

Allowed trace card fields:

- `trace_card_id`
- `source_hash`
- `entry_id`
- `behavior_cluster`
- `observed_failure_pattern`
- `state_variable_lost`
- `answerability_failure_kind`
- `turn_span_summary`
- `allowed_compact_evidence`
- `forbidden_fields_absent = true`

`state_variable_lost` is required for `state_tracking_v0`. `answerability_failure_kind` is required for `hallucination_abstain_v0`.

Forbidden material must not be included: raw prompt, raw trace, raw payload, raw case id, gold answer, expected answer, reference answer, scorer diff, candidate output text, tool argument values, provider exchange, endpoint value, API key, bearer token, or secret.

`scripts/check_abhe_trace_cards.py` validates the schema and any trace card file that exists. If no trace card file exists, the checker can still validate the output contract; `--require-cards` is reserved for a separately approved extraction step.

Trace cards cannot change archive status to `dev_passed`. They can only support reviewer understanding of mechanism hypotheses before a separate bounded dev smoke approval.
