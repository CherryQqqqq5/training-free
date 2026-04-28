# M2.8-pre Deterministic Schema-Local Coverage Audit

- Audit ready: `True`
- Demote candidates: `0`
- Coverage zero: `True`
- Route recommendation: `fix_parser_or_source_result_layout`
- Blockers: `['deterministic_schema_local_demote_below_20', 'deterministic_schema_local_family_coverage_zero']`

| Rejection reason | Count |
| --- | ---: |
| `memory_or_hidden_state_category_excluded` | `465` |
| `missing_schema_properties` | `178` |
| `missing_source_result` | `1690` |
| `no_deterministic_schema_local_repair_detected` | `1357` |
| `parallel_call_mapping_not_unique` | `494` |
