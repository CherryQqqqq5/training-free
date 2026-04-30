# RASHE StepTraceBuffer Design

This document specifies the RASHE v0.2 StepTraceBuffer research contract for Step G. It is an offline design artifact only. It does not authorize runtime behavior, provider calls, source collection, candidate generation, scorer execution, paired comparison, SOTA/+3pp, BFCL performance evidence, or Huawei acceptance claims.

## Scope

StepTraceBuffer is a sanitized offline buffer for step-level agent state summaries. It exists to support training-free skill-harness research after deterministic Stage-1 repair families reached zero-yield. It must not become a repository for raw BFCL traces or scorer-derived repair labels.

Allowed record sources:

- synthetic fixtures committed for tests
- approved compact records with raw payloads removed
- local parser/status summaries produced under an explicit offline approval
- schema hashes, prompt hashes, and case hashes when they cannot identify raw case content

Forbidden record sources:

- raw `case_id`
- raw trace text or raw provider payload
- raw model response body
- BFCL gold, expected answer, reference answer, possible answer, oracle/checker output
- scorer diff, scorer feedback text, or per-case pass/fail repair recommendation
- candidate output or repair output
- holdout/full-suite feedback used to generate, select, tune, or threshold skills

`case_hash` is allowed. Raw `case_id` is forbidden. A buffer implementation must reject raw case identifiers recursively, including inside metadata fields. The allowed `source_scope` values at Step G are `synthetic`, `approved_compact`, and `dev_only_future`; real traces and source-derived records require a separate source/real-trace approval before they can be written.

## Record Schema

A v0.2 StepTraceBuffer record should use these fields:

| field | required | meaning | constraints |
| --- | --- | --- | --- |
| `trace_hash` | yes | stable hash for the sanitized step record | hash only; no raw trace content |
| `category` | yes | coarse BFCL or synthetic category | no split claim or performance claim |
| `step_index` | yes | zero-based step number within the sanitized trace | integer; no raw turn text |
| `state_signature` | yes | compact local state summary | hash or enum-like summary only |
| `action_shape` | yes | local action form such as `no_tool`, `tool_call`, `malformed_tool_call`, `schema_mismatch` | local/parser-derived only |
| `outcome_local` | yes | local offline outcome class | cannot contain scorer/gold labels |
| `skill_tags` | yes | candidate skill tags suggested by offline signals | tags only, not active routing authorization |
| `source_scope` | yes | `synthetic`, `approved_compact`, or `dev_only_future` | never `holdout`, `full_suite`, or raw source |
| `case_hash` | optional | anonymized case hash | allowed only as hash |
| `schema_hash` | optional | visible schema hash | allowed only as hash |
| `prompt_hash` | optional | prompt/current-turn hash | allowed only as hash |

`outcome_local` is limited to local/offline classes such as:

- `parser_ok`
- `parser_reject`
- `schema_present`
- `schema_missing`
- `ambiguous_router_reject`
- `no_match_reject`
- `forbidden_field_reject`
- `path_indicator_reject`

A future `dev_only_future` source scope may be used only after separate approval. It may record aggregate dev diagnostics for research triage, but it must not generate skills from holdout/full-suite feedback and must not use scorer diff, expected values, or pass/fail labels as skill content.

## Buffer Behavior

The buffer must be inert by default. It is a sanitized record store and local validator, not a runtime policy engine and not a repair candidate source.

- no provider calls
- no scorer calls
- no source collection calls
- no BFCL runtime import
- no prompt injection
- no retry behavior
- no candidate JSONL, dev manifest, holdout manifest, or BFCL run artifact creation

The buffer may perform only local validation, hashing, deduplication by `trace_hash`, and compact counter aggregation.

Required counters:

- `record_count`
- `synthetic_record_count`
- `approved_compact_record_count`
- `dev_only_future_record_count`
- `forbidden_field_violation_count`
- `raw_case_id_rejected_count`
- `case_hash_allowed_count`
- `raw_trace_rejected_count`
- `raw_provider_payload_rejected_count`
- `gold_or_expected_rejected_count`
- `scorer_diff_rejected_count`
- `holdout_or_full_feedback_rejected_count`
- `provider_call_count=0`
- `scorer_call_count=0`
- `source_collection_call_count=0`
- `candidate_generation_authorized=false`
- `runtime_behavior_authorized=false`

## No-Leakage Proof Obligations

A checker for this design must prove:

1. Recursive forbidden-key scans reject raw `case_id`, gold, expected, reference, possible answer, score, scorer diff, candidate output, repair output, raw trace, and raw provider response fields.
2. `case_hash` is accepted only as a hash-like identifier and never interpreted as a target label.
3. `outcome_local` values are local/parser/status classes only.
4. `source_scope=dev_only_future` cannot be used until separately approved and cannot write or select skills from holdout/full-suite feedback.
5. All provider/scorer/source/candidate/runtime authorization flags remain false.

## Future Gates

These approvals must stay separate:

- source or real-trace approval for any non-synthetic compact records
- runtime behavior approval before connecting any buffer output to prompt injection or runtime hooks
- candidate generation approval before emitting candidate rules or manifests
- scorer approval before any baseline/candidate BFCL scoring
- Huawei/performance approval before any +3pp or SOTA claim

Passing StepTraceBuffer checks is not BFCL performance evidence, does not make Stage-1 +3pp ready, and does not authorize runtime execution.
