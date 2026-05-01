# Stage 1 RASHE Source Collection Runbook

Status: approved-source preparation only. Execution requires passing `scripts/check_rashe_source_real_trace_approved.py --compact --strict`; this commit does not execute collection.

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

Case count: 20-50 per category, total 100-200 max.

## Provider Profile

Provider profile name only: Chuangzhi/Novacode `gpt-5.2`. Do not place API keys in commands, docs, artifacts, or tracked files.

## Output Root

`outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/`

Only compact sanitized counters, hashes, category labels, and no-leakage audit booleans are allowed under this root.

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
