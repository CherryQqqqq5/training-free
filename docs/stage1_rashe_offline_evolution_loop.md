# RASHE Offline Evolution Loop Design

This document defines the Stage-1 RASHE offline evolution loop after the Step N proposal draft schema. It is a research design document only. It does not authorize runtime behavior, source collection, proposer execution against real traces, candidate generation, scorer execution, BFCL performance evidence, +3pp claims, SOTA claims, or Huawei acceptance claims.

## Purpose

RASHE treats seed skills, sanitized StepTrace summaries, router decisions, and proposal drafts as a training-free outer-loop research surface. The goal of the offline loop is to organize evidence for future skill package refinement while preserving fail-closed leakage controls.

The loop is intentionally narrower than a runtime agent loop. It can draft documentation or metadata patch plans for human review. It cannot mutate prompts, retry tool calls, emit BFCL candidates, or score BFCL performance.

## State Machine

The allowed offline state machine is:

```text
trace_buffer_summary
  -> router_decision_summary
  -> proposal_draft
  -> human/research review
  -> skill_metadata_patch_plan
```

### `trace_buffer_summary`

Input is a sanitized aggregate over StepTrace v0.2 records. It may contain only compact counts, hashes, local parser/verifier outcomes, action shapes, skill tags, and allowed source scopes.

It must not contain raw `case_id`, raw trace text, raw provider payload, gold, expected answer, scorer diff, candidate output, repair output, holdout feedback, or full-suite feedback.

### `router_decision_summary`

Input is an aggregate over compact router decisions. It may contain selected skill counts, reject counts, source scope counts, call-count reject fields, and decision statuses.

It is not a runtime action log. It must not contain prompt injection text, retry decisions, provider calls, scorer calls, source collection calls, candidate manifests, or BFCL run artifacts.

### `proposal_draft`

A proposal draft is inert metadata only. It may propose one of the currently allowed draft kinds:

- `skill_metadata_refinement_draft`
- `progressive_disclosure_policy_draft`
- `router_policy_refinement_draft`

A proposal draft may cite sanitized `source_trace_hashes`, `source_scope`, `selected_skill_id`, `router_decision_status`, `rationale_tags`, and `blocked_reason`. It must keep all authorization flags false and all provider/scorer/source call counts zero.

### `human/research review`

Human/research review is the first point where a proposal can be interpreted. Review may accept, reject, or request a narrower patch plan. Review must not use hidden gold, expected answers, scorer diffs, holdout/full-suite feedback, raw traces, or raw provider payloads to improve skill content.

### `skill_metadata_patch_plan`

A skill metadata patch plan is a reviewed plan to edit docs or static seed skill metadata only. It may identify fields such as `scope`, `trigger_priority`, `conflicts_with`, `requires_schema`, `requires_current_turn`, `forbidden_sources`, or `evaluation_status`.

It must not include candidate JSONL, prompt text, retry policy, BFCL dev/holdout manifests, scorer commands, runtime hook changes, provider route changes, or evaluator changes.

## Proposal Output Boundary

A proposal may produce only:

- documentation patch plans
- static seed skill metadata patch plans
- router policy metadata patch plans
- review notes and local counters

A proposal must not produce:

- BFCL candidate JSONL
- repair rules
- prompt injection text
- retry policy
- dev or holdout manifests
- provider calls
- scorer calls
- source collection calls
- runtime hook changes
- performance claims

If a proposed change would require runtime behavior, source or real-trace access, candidate generation, or scorer comparison, the loop must stop and request a separate approval gate.

## Stop Conditions

The loop must stop immediately if any of these conditions are observed:

- forbidden evidence hit
- raw case identifier, raw trace text, or raw provider payload hit
- nonzero provider/scorer/source call count
- unapproved `source_scope`
- `proposal_kind` outside the allowed draft enum
- any authorization flag set to true
- candidate, repair, dev manifest, holdout manifest, prompt injection, retry, provider, scorer, or source collection surface appears
- any use of holdout or full-suite feedback to generate, select, tune, or threshold skills

Stop means no proposal acceptance and no metadata patch plan. The output should be a reject summary with local counters and blocked reasons only.

## Required Counters

An offline evolution summary should report these counters:

- `trace_buffer_summary_count`
- `router_decision_summary_count`
- `proposal_draft_count`
- `accepted_proposal_draft_count`
- `rejected_proposal_draft_count`
- `accepted_proposal_draft_count_by_kind`
- `rejected_proposal_draft_count_by_kind`
- `blocked_reason_counts`
- `source_scope_counts`
- `selected_skill_id_counts`
- `router_decision_status_counts`
- `forbidden_evidence_reject_count`
- `raw_case_identifier_reject_count`
- `raw_trace_or_provider_payload_reject_count`
- `call_count_nonzero_reject_count`
- `source_scope_reject_count`
- `proposal_kind_reject_count`
- `auth_flag_true_reject_count`
- `candidate_or_runtime_surface_reject_count`

These counters are evidence hygiene counters, not BFCL performance metrics.

The summary must also keep these gate fields false or zero:

- `provider_call_count=0`
- `scorer_call_count=0`
- `source_collection_call_count=0`
- `runtime_behavior_authorized=false`
- `prompt_injection_authorized=false`
- `retry_authorized=false`
- `candidate_generation_authorized=false`
- `scorer_authorized=false`
- `performance_evidence=false`

## Future Approval Gates

The following gates remain separate and are not granted by this document:

1. source or real-trace approval before using any real trace or non-synthetic compact record beyond already approved compact artifacts
2. runtime behavior approval before any router decision, skill, or proposal can affect prompts, retries, tools, or execution paths
3. proposer/candidate approval before any candidate JSONL, repair rule, dev manifest, holdout manifest, or BFCL candidate artifact is emitted
4. scorer approval before any BFCL baseline/candidate scoring or paired comparison
5. performance/Huawei approval before any +3pp, SOTA, or acceptance claim

## Non-Performance Boundary

Passing the offline evolution loop, proposal draft checker, router checker, StepTraceBuffer checker, or seed skill metadata checker is not BFCL performance evidence. It does not make Stage-1 +3pp ready. It is only a fail-closed research scaffold for deciding whether a future, separately approved RASHE experiment is justified.
