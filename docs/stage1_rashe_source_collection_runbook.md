# Stage 1 RASHE Source Collection Runbook

Status: approved-source execution-path preparation only. Execution requires passing `scripts/check_rashe_source_real_trace_approved.py --compact --strict` and `scripts/check_rashe_approval_packet_review_matrix_after_source_approval.py --compact --strict`; this commit implements the bounded execution adapter boundary but does not execute collection.

## Approved Packet

`outputs/artifacts/stage1_bfcl_acceptance/rashe_source_real_trace_approval_packet.json`

## Categories

- `agentic_web_search`
- `agentic_memory`
- `multi_turn_base`
- `multi_turn_long_context`
- `multi_turn_miss_param`
- `multi_turn_miss_func`
- `hallucination`
- `irrelevance`

First approved diagnostic round: exactly 20 cases per category across 8 categories, total 160 cases. The broader packet limit remains 20-50 per category and 100-200 total, but this runbook signs only the 8x20/160 command below.

## Provider Profile

Provider profile name only: Chuangzhi/Novacode `gpt-5.2`. Do not place API keys in commands, docs, artifacts, or tracked files.

## Output Root

`outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/`

Only compact sanitized counters, hashes, category labels, and no-leakage audit booleans are allowed under this root. The signed source-input root for future compact manifests is `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/`; source-input manifests must pass `scripts/check_rashe_source_inputs_compact.py --compact --strict` before provider transport is reviewed.

## Compact Source-Input Gate

Provider transport review is blocked until the metadata approval checker passes, approved sanitized metadata root is prepared, and compact source-input manifests exist and pass the checker. The builder accepts only approved sanitized source metadata and writes only `category`, `ordinal`, `prompt_family`, and `compact_source_hash`; it rejects raw case IDs, raw prompts, gold/expected/reference, traces, provider payloads, scorer diffs, candidate outputs, repair outputs, feedback, and performance material. This runbook signs the gate order; it does not run BFCL/provider/source diagnostics and does not create metadata or manifests from unavailable inputs.

```bash
.venv/bin/python scripts/check_rashe_source_metadata_approval_packet.py \
  --compact \
  --strict

.venv/bin/python scripts/build_rashe_source_inputs_compact.py \
  --source-root <approved-compact-source-metadata-root> \
  --output-root outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/ \
  --dry-run \
  --compact \
  --strict

.venv/bin/python scripts/check_rashe_source_inputs_compact.py \
  --root outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/ \
  --compact \
  --strict
```

The approved metadata root is `outputs/artifacts/stage1_bfcl_acceptance/approved_source_metadata_compact/`; the downstream manifest root is `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/`. Metadata records must use the signed coarse `source_family_id` taxonomy only: `agentic_web`, `agentic_memory`, `multi_turn_workflow`, or `abstention_safety`, with the fixed category mapping in the metadata approval packet. If the approved source metadata root is absent, the metadata checker and builder fail closed with `approved_bfcl_source_metadata_missing`. If the signed manifest root is absent, the checker fails closed with `approved_source_input_root_missing`. Do not use raw BFCL result roots, raw trace roots, or case-ID manifests as builder input. Source metadata preparation itself is a later step and must not commit nonce-to-raw-case mappings.


## Provider Endpoint Preflight Gate

Provider endpoint/model/tool-calling preflight is a Phase B prerequisite capability check, not Phase B execution. The packet is `outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_endpoint_preflight_packet.json`, and it is checked with:

```bash
.venv/bin/python scripts/check_rashe_provider_endpoint_preflight_packet.py --compact --strict
.venv/bin/python scripts/run_rashe_provider_endpoint_preflight.py --dry-run --compact --strict
```

This commit does not request the provider. The dry-run/plan-only runner may report whether signed endpoint/key env names are present, but it must not print or persist endpoint/key values. Any future synthetic provider preflight requires separate reviewer authorization and must use only a minimal toy chat/tool-calling request with no BFCL/source case, raw prompt, raw tool data, trace, gold/expected/reference, scorer diff, candidate output, feedback, or compact diagnostic payload. The signed primary model remains `gpt-5.2`; `gpt-5.4` may only be observed as optional capability. If only `gpt-5.4` is supported, the result is `route_update_required` and the signed model packet/checker/runbook/tests must be updated before source diagnostics may run. If the endpoint supports only standard chat completions, run an OpenAI-compatible chat adapter review before any Phase B execution.

## Signed Command Template

Do not run source collection in this commit. Before any future execution, run metadata/source gates and stop if any fails:

```bash
.venv/bin/python scripts/check_rashe_source_real_trace_approved.py --compact --strict
.venv/bin/python scripts/check_rashe_approval_packet_review_matrix_after_source_approval.py --compact --strict
.venv/bin/python scripts/check_rashe_source_metadata_approval_packet.py --compact --strict
.venv/bin/python scripts/check_rashe_source_inputs_compact.py --compact --strict
.venv/bin/python scripts/check_rashe_provider_transport_approved.py --compact --strict
```

This commit verifies the signed runner entrypoint in dry-run mode and implements the adapter-driven execution path for review. The signed adapter is `scripts.rashe_source_diagnostic_compact_adapter:run_compact_source_diagnostic`; the signed provider-client factory is `scripts.rashe_source_provider_client:build_chuangzhi_novacode_source_provider_client`; the signed source-case provider is `scripts.rashe_source_case_provider:build_signed_source_case_provider`. Do not remove `--dry-run` or use `--execute-approved-source` until a separate Phase B execution authorization confirms the command. The provider transport packet/checker must pass first; this commit still does not execute source diagnostics.

```bash
.venv/bin/python scripts/run_rashe_source_diagnostic_compact.py \
  --provider-profile "Chuangzhi/Novacode" \
  --model "gpt-5.2" \
  --categories agentic_web_search,agentic_memory,multi_turn_base,multi_turn_long_context,multi_turn_miss_param,multi_turn_miss_func,hallucination,irrelevance \
  --min-cases-per-category 20 \
  --max-cases-per-category 20 \
  --max-total-cases 160 \
  --output-root outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/ \
  --schema outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json \
  --source-input-root outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/ \
  --compact-sanitized-only \
  --publish-fields category,case_count,provider_call_count,raw_payload_tracked_count,forbidden_field_violation_count,failure_bucket_counts,candidate_generation_authorized,scorer_authorized,performance_evidence \
  --no-raw-trace \
  --no-raw-payload \
  --no-candidate-jsonl \
  --no-scorer \
  --execution-adapter scripts.rashe_source_diagnostic_compact_adapter:run_compact_source_diagnostic \
  --provider-client-factory scripts.rashe_source_provider_client:build_chuangzhi_novacode_source_provider_client \
  --source-case-provider scripts.rashe_source_case_provider:build_signed_source_case_provider \
  --dry-run \
  --compact \
  --strict
```

The template intentionally contains no API key. Real transport configuration must provide a signed HTTPS endpoint through environment only using `CHUANGZHI_NOVACODE_ENDPOINT` or `NOVACODE_ENDPOINT`; if no approved endpoint is present, execution fails closed as `provider_endpoint_missing`. If a key is read during a future approved execution, the runner reports `api_key_read=true` without recording the key value. In this commit it must not call a provider, write diagnostics, generate raw traces, raw provider payloads, candidate JSONL, scorer outputs, dev/holdout/full manifests, performance evidence, or Huawei readiness artifacts. A future execution command must replace only `--dry-run` with `--execute-approved-source` while keeping the signed adapter, signed provider-client factory, signed source-case provider, signed source-input root, provider profile, model, categories, counts, output root, and schema above unchanged; it must pass the same 8x20/160 signed bounds before it may write compact artifacts. The source-case provider boundary is signed and importable; it reads only compact source-input manifests and returns `category`, `ordinal`, `prompt_family`, and irreversible `compact_hash`. If the approved compact source inputs are absent when the source-case provider is actually called, it fails closed with `bfcl_source_inputs_missing`. With the source-case provider injected and no signed endpoint env configured, current execution fails closed with `provider_endpoint_missing`; the endpoint value itself must never be written into the command, logs, or artifacts. No real execution is authorized in this commit.

## Compact Artifact Schema

Schema path: `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json`.

Required fields:
- `category`
- `case_count`
- `provider_call_count`
- `raw_payload_tracked_count`
- `forbidden_field_violation_count`
- `failure_bucket_counts`
- `candidate_generation_authorized`
- `scorer_authorized`
- `performance_evidence`

Failure buckets:
- `answered_without_tool`
- `wrong_first_tool`
- `search_query_too_broad`
- `fetch_missing_after_search`
- `memory_not_retrieved`
- `memory_update_when_should_search`
- `multi_turn_state_lost`
- `invalid_tool_call_format`
- `parser_schema_failure`
- `final_answer_before_tool`
- `irrelevant_tool_call`
- `unsupported_hallucinated_answer`

## Forbidden Artifacts

- raw traces
- raw provider payloads
- raw case IDs
- gold, expected, reference, scorer diff, candidate output, repair output, feedback, holdout feedback, full-suite feedback
- candidate JSONL
- dev/holdout/full manifests
- scorer outputs
- performance or Huawei readiness artifacts

## Stop Gates

Stop immediately if any of the following occurs:
- approved-source checker fails
- artifact boundary checker fails
- raw trace or raw provider payload would be tracked or committed
- raw case ID or forbidden field appears in a compact artifact
- `raw_payload_tracked_count != 0`
- `forbidden_field_violation_count != 0`
- `candidate_generation_authorized != false`
- `scorer_authorized != false`
- `performance_evidence != false`
- candidate JSONL, scorer output, or dev/holdout/full manifest is produced

## Rollback Template

No rollback command should be run without explicit approval. If a future execution creates untracked source diagnostics that fail gates, remove only that future output root after review:

```bash
rm -rf outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/
```

Do not use `git reset --hard` or revert unrelated user/agent changes.
