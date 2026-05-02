# RASHE Provider Payload Shape Diff

Status: sanitized shape-only protocol alignment artifact. No provider call, Phase B execution, diagnostics write, source input read, candidate, scorer, performance, +3pp, or Huawei path is authorized by this artifact.

- successful_synthetic_variant: `baseline_chat_tools_required`
- phase_b_payload_builder: `scripts.rashe_source_provider_client:build_source_diagnostic_chat_payload`
- alignment_passed: `true`
- blockers: `[]`

## High-Level Shape Conclusion

The Phase B planned provider payload now uses the same OpenAI-compatible chat tools envelope as the successful synthetic protocol variant: fixed `gpt-4.1`, one user message, one function tool, function-object `tool_choice`, `max_tokens`, and no raw persistence.

Only field-level structure is recorded. Raw prompt text, raw tool schema text, arguments, case IDs, gold/expected/reference, provider payloads, diagnostics, candidates, scorer data, and performance claims are forbidden.
