# Stage-1 BFCL Scope-Change Decision Memo

This memo is a decision packet for project lead and Huawei acceptance-owner review. It is not a performance claim, not scorer authorization, and not candidate-pool authorization.

## Current State

The deterministic Stage-1 BFCL family search is exhausted under the approved gates. The diagnostic and negative-evidence handoff is acceptable, but Huawei BFCL +3pp readiness is not achieved.

Fail-closed state:

- `candidate_pool_ready=false`
- `scorer_authorized=false`
- `performance_evidence=false`
- `sota_3pp_claim_ready=false`
- `huawei_acceptance_ready=false`

## Negative Evidence Summary

| family | evidence source | stop gate | result |
| --- | --- | --- | --- |
| explicit required-arg literal | Batch1/Batch2 selected-call diagnostics and negative evidence report | no selected call with exactly one missing required arg; accepted candidates remain 0 | zero-yield; candidate pool not authorized |
| wrong-key alias | `wrong_arg_key_alias_repair_diagnostic` | no deterministic unique alias repair; `alias_repair_eligible_count=0` | zero-yield; candidate pool not authorized |
| schema-local non-live | `schema_local_non_live_repair_diagnostic` | no deterministic schema-local conversion; `schema_local_repair_eligible_count=0` | zero-yield; candidate pool not authorized |
| structural malformed/final-before-tool | refined raw-response structural attribution | no strict malformed serialization or final-before-tool eligible path | zero-yield; structural expansion not authorized |
| emitted tool-name/schema normalization | raw payload schema-not-matched subtyping audit | raw schema-not-matched bucket has no deterministic source-schema-only tool-name candidate; `deterministic_source_schema_only_possible_count=0` | zero-yield; normalization family not authorized |
| schema retrieval/rerank feasibility | schema retrieval/rerank feasibility diagnostic | `single_schema_high_margin_count=0`; low-margin/ambiguous stop gates triggered | zero-yield; recommendation is stop/no-yield research review |

## Overfitting Controls

- No Batch3 under the current evidence.
- No same-pilot family hunting or repeated slicing to search for a positive subset.
- No scorer/gold-derived candidate generation.
- No source expansion, candidate-pool promotion, scorer run, paired comparison, SOTA claim, or Huawei acceptance claim without new explicit approval.
- Raw evidence remains untracked; tracked artifacts must stay compact and sanitized.

## Scope-Change Options

All options below are not yet authorized. Each requires a separate approval packet before implementation, source collection, candidate generation, or scoring.


Raman recommendation: if leadership insists on continuing Stage-1 BFCL work,
Option A `schema/parser feedback retry` is the preferred first scope-change
path. Option C `verifier/test-time repair` is secondary. All options remain not
yet authorized until project lead and Huawei acceptance owner choose and sign one
bounded approval packet.


### Option A: Schema / Parser Feedback Retry

Allowed evidence:

- Existing compact diagnostics and raw-response pilot metadata.
- Dataset/tool schema fields and parser error classes.
- Sanitized hashes/counters for parse failures and schema-match failures.

Forbidden leakage:

- Gold, expected answers, reference values, scorer diffs, candidate outputs, or repair outputs as value/tool/argument sources.
- Per-case repair recommendations derived from scorer gold.

Expected BFCL bucket:

- Raw payload schema-not-matched and selected schema-not-matched failures where adapter/parser attribution is plausible.

Cost/scorer implications:

- Likely requires adapter/parser changes and a new baseline/candidate comparison only after offline evidence shows a candidate family.
- No performance scorer until candidate pool and paired-comparison authorization are granted.

Stop gate:

- Stop if deterministic parser/schema attribution cannot identify at least a review-approved candidate family without scorer/gold leakage.
- Stop if candidate pool remains below threshold or cannot be split into clean dev/holdout manifests.


Option A approval-packet details required before implementation:

Allowed trigger classes:

- deterministic parser failure class with raw response present and sanitized
  parser status recorded
- schema-name attribution failure with dataset/tool schema available
- adapter serialization mismatch where no tool/function/argument/value is
  invented
- current-turn/schema mismatch class supported by compact hashes/counters, not
  gold labels

Forbidden triggers:

- scorer gold, expected values, references, possible answers, or per-case scorer
  diffs
- candidate output, repair output, hidden labels, or post-hoc pass/fail as a
  trigger source
- semantic/fuzzy tool selection, prompt tuning, model/provider tuning, or hidden
  LLM reranking
- same-pilot family hunting after a stop gate fails

Allowed feedback wording:

- parser/schema status such as `malformed_tool_call_json`,
  `schema_name_not_matched`, `arguments_unparseable`, or
  `selected_call_missing_after_adapter`
- schema-local normalization labels that do not expose gold tool identity or
  expected argument values
- aggregate bucket and hash references only

Required counters:

- audited_case_count
- raw_response_present_count
- dataset_schema_present_count
- parser_failure_class_counts
- schema_match_status_counts
- deterministic_retry_candidate_count
- leakage_counter_gold_or_expected
- scorer_diff_used_count
- ambiguous_retry_reject_count
- candidate_pool_authorized
- scorer_authorized
- cost_latency_risk_class
- regression_risk_class

Stop gates:

- stop on any nonzero gold/expected/scorer-diff leakage counter
- stop if deterministic retry candidates are fewer than the approved threshold
  for a clean dev/holdout split
- stop if ambiguous retry rejects dominate the reviewed bucket
- stop if cost/latency risk cannot be bounded before scorer authorization
- stop if the route requires changing provider/model/evaluator or BFCL tool
  schema

Cost/latency/regression requirements:

- approval packet must state whether the retry is local-only or introduces an
  additional model call
- candidate scorer authorization, if later requested, must include cost and
  latency bounds and a regression report
- no full-suite, SOTA/+3pp, or Huawei acceptance claim is allowed until paired
  baseline/candidate artifacts prove the required gain without unacceptable
  regression

### Option B: Prompt / Current-Turn Context Canonicalization

Allowed evidence:

- Current-turn prompt text, dataset schema text, tool descriptions, and compact source metadata.
- Aggregate prompt/schema retrieval diagnostics that do not use gold targets.

Forbidden leakage:

- Gold tool identity, expected argument values, scorer diff text, or outcome-selected case mining for candidate construction.
- Prompt tuning against the same pilot until a separate anti-overfitting protocol is approved.

Expected BFCL bucket:

- Tool selection or schema retrieval failures where prompt/schema signal is present but not robustly selected.

Cost/scorer implications:

- May change prompt/context construction and could affect token cost and latency.
- Requires strict baseline/candidate protocol alignment and cost/latency reporting if later authorized for performance scoring.

Stop gate:

- Stop if deterministic lexical/schema signal remains low-margin or ambiguous.
- Stop if the method requires semantic/fuzzy reranking, hidden model calls, or case-specific prompt tuning.

### Option C: Verifier / Test-Time Repair

Allowed evidence:

- Tool schema, emitted tool calls, parser status, and local schema validation results.
- Offline verifier acceptance/rejection counters.

Forbidden leakage:

- Execution feedback, postcondition gold, scorer expected values, reference answers, or any per-case scorer diff as a repair source.
- Tool-choice mutation or trajectory mutation unless separately approved as the explicit research target.

Expected BFCL bucket:

- Schema-valid selected-call failures, argument mismatch failures, and serialization/adapter failures that can be checked locally without gold.

Cost/scorer implications:

- May add local verifier compute and latency.
- Requires cost/latency bounds and regression checks before any performance claim.

Stop gate:

- Stop if verifier decisions are not deterministic, not schema-local, or cannot be audited without scorer/gold leakage.
- Stop if local repairs create ambiguous alternatives or overwrite existing canonical arguments.

### Option D: Training / Data Route

Allowed evidence:

- Aggregate failure taxonomy, dataset distribution summaries, and sanitized schema/prompt statistics.
- Separate train/dev/holdout data governance if the route is approved.

Forbidden leakage:

- Using evaluation gold, expected answers, or scorer diffs as training labels for the same acceptance split.
- Folding raw pilot cases into training or candidate selection without a new data split and leakage review.

Expected BFCL bucket:

- Broad tool-selection, argument-value, state/execution, and schema-retrieval failures that deterministic local repair cannot address.

Cost/scorer implications:

- Higher engineering and compute cost; likely changes the project from training-free deterministic repair to a data/training workflow.
- Requires a new acceptance protocol, data provenance review, and separate scorer authorization.

Stop gate:

- Stop if data governance, split integrity, or no-leakage guarantees cannot be established.
- Stop if the route conflicts with the project requirement for training-free Stage-1 delivery.


### Option E: Retrieval-Augmented Skill Harness Evolution (RASHE)

Status: proposed only, not authorized. See
`docs/stage1_rashe_scope_change_approval.md` and
`outputs/artifacts/stage1_bfcl_acceptance/scope_change_approval_rashe.json`.

Allowed evidence:

- sanitized step traces and compact parser/schema diagnostics
- SkillBank package metadata and deterministic router decisions
- local parser adapter, bounded retry, and verification-hook counters

Forbidden leakage:

- gold, expected, reference, possible-answer, scorer diff, candidate output, or
  repair output used for skill generation
- holdout/full-suite feedback used for skill generation or thresholds
- case-id-specific rules or answer memorization

Expected BFCL bucket:

- structural, parser/schema, and tool-use failures where a training-free harness
  or skill-routing change can be tested under the same provider/model/evaluator

Cost/scorer implications:

- may affect prompt/context length, local retry cost, verifier latency, and
  regression risk
- requires explicit cost, latency, regression, candidate-pool, and paired
  comparison gates before any scorer/performance claim

Stop gate:

- stop on any leakage counter nonzero
- stop if provider/model/evaluator drift is required
- stop if the route cannot produce a clean candidate pool and dev/holdout split
- stop if cost/latency/regression gates are undefined

## Decision Requested

Project lead and Huawei acceptance owner must choose one of the following before engineering proceeds:

1. Approve exactly one scope-change path above with a bounded approval packet.
2. Request a revised scope-change option with explicit evidence, leakage, cost, scorer, and stop-gate rules.
3. Stop the Stage-1 BFCL performance sprint and preserve the current diagnostic/negative-evidence handoff as final Stage-1 evidence.

Until that decision is made, the repo remains fail-closed: `candidate_pool_ready=false`, `scorer_authorized=false`, `performance_evidence=false`, `sota_3pp_claim_ready=false`, and `huawei_acceptance_ready=false`.
