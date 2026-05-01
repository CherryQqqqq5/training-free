# RASHE source metadata approval packet

- report_scope: `rashe_source_metadata_approval_packet`
- approval_status: `approved`
- authorized: `true`
- approved metadata root: `outputs/artifacts/stage1_bfcl_acceptance/approved_source_metadata_compact/`
- downstream source-input root: `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/`
- metadata generated: `false`
- source-input manifests generated: `false`
- provider transport authorized: `false`
- diagnostic execution authorized: `false`
- candidate/scorer/performance/Huawei: `false`

This approval signs only the sanitized compact metadata contract needed before `rashe_source_inputs_compact/` can be built. It does not generate metadata, does not generate manifests, and does not authorize provider transport or execution.

## Required Scope

- 8 categories x exactly 20 metadata records per category.
- Ordinals are zero-based and continuous: `0..19`.
- Metadata fields only: `category`, `ordinal`, `prompt_family`, `source_nonce`, `source_family_id`.
- Output manifest fields only: `category`, `ordinal`, `prompt_family`, `compact_source_hash`.
- `source_family_id` may be read by the builder but must not be emitted to source-input manifests.

## Prompt Family Taxonomy

- `agentic_web_search` -> `web_search_required`
- `agentic_memory` -> `memory_retrieval_required`
- `multi_turn_base` -> `multi_turn_state_tracking`
- `multi_turn_long_context` -> `long_context_state_tracking`
- `multi_turn_miss_param` -> `multi_turn_missing_parameter`
- `multi_turn_miss_func` -> `multi_turn_missing_function`
- `hallucination` -> `hallucination_abstention`
- `irrelevance` -> `irrelevance_abstention`

## Source Nonce Policy

`source_nonce` must be a high-entropy random nonce, minimum length 32, suitable for deriving an irreversible `compact_source_hash`. It must not be derived from raw case IDs, prompts, gold/expected/reference, trace paths, provider payloads, or scorer/candidate material. No nonce-to-raw-case mapping may be committed to the repo or artifacts.

## Forbidden

Raw case IDs, raw prompts/text, tool traces, provider payloads, gold, expected, reference, scorer diff, candidate output, repair output, feedback, holdout/full feedback, candidate JSONL/pool, scorer outputs, performance evidence, and Huawei readiness claims remain forbidden.

## Required Gate Order

1. `scripts/check_rashe_source_metadata_approval_packet.py --compact --strict`
2. Prepare approved sanitized metadata root in a later authorized step.
3. `scripts/build_rashe_source_inputs_compact.py` and `scripts/check_rashe_source_inputs_compact.py`
4. Provider transport review only after source-input manifest checker passes.
