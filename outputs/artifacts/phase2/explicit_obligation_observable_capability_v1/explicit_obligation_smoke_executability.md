# Explicit Obligation Smoke Executability

- BFCL executable manifest ready: `False`
- Protocol ready for review: `True`
- Positive / control records: `12` / `8`
- Executable case ids: `0` / `20`
- Dependency closure ready: `False`
- Missing BFCL case ids: `20`
- Protocol ids that are not BFCL ids: `20`
- Candidate commands: `[]`
- Planned commands: `[]`
- Blockers: `['explicit_protocol_not_bfcl_executable', 'protocol_case_ids_include_audit_ids']`
- Next action: `materialize_explicit_obligation_candidates_to_bfcl_case_ids_before_smoke`

This check is offline only and never authorizes BFCL/model/scorer execution.
