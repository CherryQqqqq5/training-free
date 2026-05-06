# RASHE Dev Manifest v1

Status: pending fixed dev smoke manifest draft. It contains only aggregate category caps and skill labels; it contains no case identifiers or raw material.

- max_dev_cases: `12`
- category cap: `2` per allowed category
- allowed skills: `bfcl_multi_turn_state_tracking`, `bfcl_hallucination_abstain`
- disallowed skills: `bfcl_web_search_decomposition`, `bfcl_memory_retrieve_before_answer`, `bfcl_parser_feedback_retry`
- candidate activation mode: `in_memory_spec_only_no_jsonl_no_pool`

No holdout, full suite, candidate JSONL, candidate pool, persisted candidate outputs, or performance evidence is authorized.
