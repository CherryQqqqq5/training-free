# BFCL Exact 2-ID Generate-Only Smoke Rerun Gate

Status: pending and fail-closed.

This packet requests future approval for one exact 2-ID BFCL generate-only smoke rerun after the materialization preservation patch. It does not authorize execution in its committed state.

## Requested Scope

- Signed IDs only: `web_search_base_0`, `multi_turn_base_0`
- Route: `novacode/gpt-4.1`
- Candidate specs inert
- Generate-only smoke rerun sufficient to check both IDs for nonempty/non-protocol results
- Compact artifact only at `outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_generate_smoke_rerun_compact.json`

## Still Not Authorized

- Provider request
- BFCL generate or smoke execution
- BFCL evaluate or scorer
- Full/default baseline
- Candidate activation, JSONL, or pool generation
- Performance, +3pp, SOTA, or Huawei claim

## Future Stop Gates

Future execution must stop and fail closed on any empty model response, protocol error, missing result, route drift, raw or secret material, extra ID, second run, or candidate activation.

Only compact flags, enums, counts, and path-class labels are allowed. Unsanitized prompt or case material, provider bodies, headers, logs, traces, model text, tool arguments, reference materials, scoring diffs, endpoint/key values, and candidate data remain forbidden.
