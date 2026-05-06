# RASHE Dev Scorer Execution Packet v1

Status: pending execution packet draft only. `approval_status=pending`, `authorized=false`, and `execution_started=false`. This draft does not authorize a smoke run.

Boundary: one future dev smoke attempt only after separate reviewer approval. Holdout, full suite, full baseline, candidate JSONL, candidate pool, persisted candidate outputs, final claim gates, and external acceptance flags remain false.

The dev cap is `max_dev_cases=12`, selected as a conservative draft cap for reviewer confirmation. Allowed categories are limited to the two approved proposal families: multi-turn state tracking and hallucination/abstain.

Candidate activation mode is `in_memory_spec_only_no_jsonl_no_pool`. Raw prompt, trace, payload, provider exchange, case identifiers, gold/expected answers, tool argument values, scorer deltas, and candidate output text must not be persisted.

Required future records are fixed/regressed/unchanged counts, candidate-only and baseline-only failure counts, plus cost and latency buckets. These are measurement-design fields for a dev smoke, not performance evidence.
