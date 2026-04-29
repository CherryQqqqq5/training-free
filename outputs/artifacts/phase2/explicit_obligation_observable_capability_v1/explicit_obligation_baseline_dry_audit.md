# Explicit Obligation Baseline Dry Audit

- Baseline dry audit ready: `True`
- Smoke selection ready after dry audit: `False`
- Baseline ceiling risk: `True`
- Positive / control cases: `12` / `8`
- Primary positive capability-miss count: `0`
- Baseline already uses memory count: `12`
- Control memory activation count: `8`
- Unique BFCL case ids: `20` / `20`
- Unique trace paths: `20` / `20`
- Unique audit ids: `20` / `20`
- Positive buckets: `{'baseline_process_already_uses_memory': 12}`
- Control buckets: `{'control_memory_activation_present': 8}`
- Candidate commands: `[]`
- Planned commands: `[]`
- Blockers: `['primary_positive_capability_miss_below_6', 'baseline_ceiling_positive_count_above_2', 'control_memory_activation_present']`
- Next action: `replace_ceiling_or_false_positive_cases_before_smoke`

This audit is offline only and reads existing source traces. It does not authorize execution.
