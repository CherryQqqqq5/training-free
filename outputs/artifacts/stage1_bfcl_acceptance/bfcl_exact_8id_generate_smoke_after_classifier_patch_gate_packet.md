# BFCL Exact 8-ID Generate-Only Smoke After Classifier Patch Gate

Status: approved for one exact 8-ID generate-only smoke after classifier patch.

## Signed ID Source

The eight labels come from `outputs/artifacts/stage1_bfcl_acceptance/bfcl_stage1_smoke_run_id_manifest.json`. No BFCL case content is included.

## Requested Future Scope

- Signed IDs only: `web_search_base_0`, `memory_kv_0-customer-0`, `multi_turn_base_0`, `multi_turn_long_context_0`, `multi_turn_miss_param_0`, `multi_turn_miss_func_0`, `irrelevance_0`, `live_irrelevance_0-0-0`
- Route: `novacode/gpt-4.1`
- Candidate specs inert
- Generate-only compact smoke after the classifier materialized-marker patch
- Future compact artifact path: `outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_8id_generate_smoke_after_classifier_patch_compact.json`

## Authorized For This Scope

- One provider request path only as required by the exact 8-ID generate-only smoke
- BFCL generate-only smoke for the eight signed IDs only

## Still Not Authorized

- BFCL evaluate or scorer
- Full/default baseline
- Candidate activation, JSONL, or pool generation
- Performance, +3pp, SOTA, or Huawei claim

## Future Stop Gates

Future execution must stop and fail closed on empty model response, protocol error, unknown compact status, missing result, route drift, unsanitized material, extra or missing ID, second run, or candidate activation.

Only compact flags, enums, counts, and path-class labels are allowed. Unsanitized prompts, cases, provider bodies, headers, logs, traces, model text, tool arguments, reference material, scoring diffs, endpoint/key values, and candidate data remain forbidden.
