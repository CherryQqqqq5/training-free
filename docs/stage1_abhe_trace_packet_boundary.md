# Stage 1 ABHE Trace Packet Boundary

ABHE trace extraction is a separate approval packet from bounded dev smoke. It is mechanism explanation only, not validation evidence.

The temporary trace extraction packet may request sanitized trace cards for `state_tracking_v0` and `hallucination_abstain_v0`. It remains draft or pending until separately approved. It does not authorize provider calls, BFCL generation, BFCL evaluation, scorer execution, candidate generation, candidate activation, or performance claims.

Allowed output is limited to sanitized trace cards with:

- `trace_card_id`
- `source_hash`
- `behavior_cluster`
- `observed_failure_pattern`
- `state_variable_lost`
- `turn_span_summary`
- `allowed_compact_evidence`
- `forbidden_fields_absent = true`

Forbidden material must not be included: raw prompt, raw trace, raw payload, raw case id, gold answer, expected answer, reference answer, scorer diff, candidate output text, provider exchange, endpoint value, or tool argument values.

Trace cards do not change archive state. They cannot move an entry to `dev_passed`, cannot serve as paired baseline/candidate evidence, and cannot support SOTA/+3pp or Huawei acceptance wording.
