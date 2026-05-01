# Approved Source Metadata Compact Provenance

Status: approved sanitized metadata root prepared only. This provenance note is outside the metadata root and is not a nonce-to-raw-case mapping.

Generated root: outputs/artifacts/stage1_bfcl_acceptance/approved_source_metadata_compact/

Scope:
- Records are category/ordinal slots only for the signed 8 categories x 20 records.
- Each metadata record contains only category, ordinal, prompt_family, source_nonce, and source_family_id.
- source_nonce values were generated independently with Python secrets.token_urlsafe(24).
- source_nonce values were not derived from raw case ids, prompts, traces, BFCL contents, gold, expected, reference, provider payloads, scorer outputs, candidate outputs, repair outputs, or feedback.
- No nonce-to-raw-case mapping is committed.
- No raw case, prompt, gold, expected, reference, trace, provider, scorer, candidate, repair, feedback, holdout, or full-suite material was used or written.
- This artifact does not authorize provider transport, source execution, source diagnostics, BFCL execution, scorer execution, candidate generation, performance evidence, or Huawei readiness.

Current boundary: compact source-input manifests may be derived from this sanitized metadata root by scripts/build_rashe_source_inputs_compact.py and validated by scripts/check_rashe_source_inputs_compact.py. Provider transport remains separately unauthorized until reviewed.
