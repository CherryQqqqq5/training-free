# Explicit Literal Candidate Expansion Spec

This specification turns the first-stage explicit-literal runbook into an
implementation contract for extractor and checker work. It is offline-only. It
does not authorize BFCL scorer execution and does not claim that the current
repository already has a 35+ candidate pool.

Current known state: the explicit literal family is still below the required
35+ demote-candidate threshold. Engineering must rebuild source collection and
rerun offline audits before scorer authorization can be requested.

## Scope

The only in-scope performance family for this spec is:

```text
explicit_required_arg_literal_completion
```

Out of scope for this expansion pass:

- memory-operation policies
- postcondition-guided policies
- CTSPC-v0 trajectory/action policies
- wrong-key alias repair, unless a later combined-family route explicitly
  selects it
- deterministic schema-local repair, unless a later combined-family route
  explicitly selects it
- structured retry or output-contract preservation

## Extractor Inputs

The extractor may read only baseline-side, model-visible evidence:

- BFCL dataset record:
  - `id`
  - `question` or equivalent prompt/messages field
  - `function`
  - `function[].name`
  - `function[].parameters.properties`
  - `function[].parameters.required`
- baseline result record:
  - `id`
  - emitted tool calls under the result payload
- baseline trace records:
  - request messages
  - request tools
  - raw upstream response
  - parsed tool calls
  - validation issues
  - prior tool observations visible before the repaired tool call
- run metadata:
  - `source_run_root`
  - category
  - run manifest fields needed for reproducibility

The extractor must not read scorer gold, expected calls, candidate outputs, or
holdout feedback.

## Candidate Extraction Algorithm

For each source category and case:

1. Build a schema map from the BFCL dataset:
   `normalized_tool_name -> function schema`.
2. Parse baseline emitted tool calls from baseline result and trace.
3. Accept a tool call for candidate extraction only when:
   - tool name maps to exactly one dataset function;
   - arguments are a JSON object;
   - the call can be uniquely identified when multiple calls are present.
4. Compute missing required args:
   `missing_required_args = required_args - emitted_arg_keys`.
5. Continue only when `len(missing_required_args) == 1`.
6. Build observable text sources:
   - `current_request`: current user/system/request text;
   - `current_observation`: prior tool observation text visible in baseline trace.
7. Extract typed literal candidates for the missing arg:
   - string: quoted strings, file-like literals, directory/name cue literals;
   - integer/number: numeric literals;
   - boolean: explicit `true/false/yes/no`;
   - enum: exact or case-insensitive enum surface;
   - array/object: reject unless a single JSON literal is explicitly present and
     schema-compatible.
8. Select a candidate only when exactly one literal is schema-compatible and
   grounded in `current_request` or `current_observation`.
9. Emit an accepted candidate or a rejected diagnostic record with a stable
   reject reason.

## Output JSONL Schema

Accepted and rejected records should use the machine-readable schema draft at:

```text
outputs/artifacts/bfcl_explicit_required_arg_literal_v1/explicit_literal_candidate_schema.json
```

Required accepted-candidate fields:

- `case_id`
- `category`
- `source_run_root`
- `candidate_rules_type`
- `rule_type`
- `candidate_origin`
- `tool`
- `emitted_tool_name`
- `required_arg`
- `schema_arg_name`
- `required_args`
- `missing_required_args`
- `emitted_tool_args`
- `schema_type`
- `literal_value`
- `selected_literal`
- `unique_literal_value`
- `literal_candidates`
- `literal_candidate_count`
- `literal_source`
- `literal_source_span`
- `literal_source_text_hash`
- `literal_source_observed_as`
- `literal_source_rank`
- `disambiguation_cue`
- `schema_type_match`
- `literal_uniqueness`
- `no_next_tool_intervention`
- `exact_tool_choice`
- `trajectory_mutation`
- `tool_choice_mutation`
- `gold_value_mutation`
- `used_gold_fields`
- `used_score_fields`
- `used_candidate_output`
- `candidate_generatable`
- `rejection_reason`
- `retention_prior`

Required accepted-candidate values:

- `candidate_rules_type = explicit_required_arg_literal_completion`
- `rule_type = explicit_required_arg_literal_completion`
- `candidate_generatable = true`
- `rejection_reason = null`
- `literal_source in {current_request, current_observation}`
- `schema_type_match = true`
- `literal_uniqueness = true`
- `no_next_tool_intervention = true`
- `exact_tool_choice = false`
- `trajectory_mutation = false`
- `tool_choice_mutation = false`
- `gold_value_mutation = false`
- `used_gold_fields = false`
- `used_score_fields = false`
- `used_candidate_output = false`
- `retention_prior.rule_family = explicit_required_arg_literal_completion`
- `retention_prior.retain_eligibility = demote_candidate`
- `retention_prior.intervention_scope = argument_only`

## Reject Reasons

Reject records must preserve case/category/source/tool context where available
and set `candidate_generatable=false`.

Stable reject reasons:

- `missing_source_result`
- `missing_emitted_tool_call`
- `no_matching_emitted_tool`
- `parallel_call_mapping_not_unique`
- `missing_schema_properties`
- `required_args_already_present`
- `multiple_missing_required_args`
- `no_observable_literal`
- `ambiguous_observable_literal`
- `schema_type_mismatch`
- `source_result_only`
- `literal_span_missing`
- `literal_source_denylisted`
- `memory_or_hidden_state_category_excluded`
- `gold_or_scorer_dependency_detected`
- `candidate_output_dependency_detected`
- `trajectory_or_tool_choice_mutation_required`

Rejected records may remain in audit artifacts. They must not be emitted into
runtime candidate rules and must not count toward the 35+ pool.

## No Leakage Checks

The extractor and checker must fail closed if a candidate literal depends on any
gold, scorer, candidate-output, or holdout-feedback source.

Denied field names and provenance tokens:

- `gold`
- `answer`
- `expected`
- `ground_truth`
- `oracle`
- `checker`
- `reference`
- `possible_answer`
- `score`
- `valid`
- `scorer`
- `candidate_output`
- `patched_output`
- `holdout_feedback`

Allowed literal sources:

- `current_request`
- `current_observation`

Required no-leakage evidence:

- `literal_source_span` is non-empty.
- `literal_source_text_hash` is non-empty.
- `literal_value` or its normalized form can be reproduced from the span.
- `literal_source` is not `source_result_tool_args` or `source_result_only`.
- `grounding_rejection_reason` is not `source_result_only`.
- `used_gold_fields=false`.
- `used_score_fields=false`.
- `used_candidate_output=false`.

Any record that fails one check is diagnostic-only and cannot enter dev or
holdout manifests.

## 35+ Pool Selection

Build the scorer-eligible pool from accepted explicit-literal candidates only.

Eligibility filter:

- keep only unique case candidates with `retain_eligibility=demote_candidate`;
- require all no-leakage checks to pass;
- require no trajectory or tool-choice mutation;
- exclude memory categories from explicit-literal performance authorization;
- exclude source-result-only diagnostic records.

Sort deterministically by:

1. category priority:
   - `multi_turn_miss_func`
   - `multi_turn_long_context`
   - `multi_turn_base`
   - `parallel_multiple`
   - `multiple`
2. `literal_source`: `current_request` before `current_observation`;
3. `confidence` descending;
4. `literal_source_rank` ascending, missing rank last;
5. `trajectory_sensitive_tool=false` before `true`;
6. read/search tools before mutating tools:
   - preferred: `cat`, `grep`, `find`, `sort`, `diff`;
   - later: `touch`, `mkdir`, `cp`, `mv`, `cd`;
7. `case_id`;
8. `tool`;
9. `schema_arg_name`.

Deduplicate by `case_id` after sorting. Keep the highest-ranked record and move
other same-case candidates to diagnostic rejection with a duplicate-case reason.

The pool is scorer-ready only when it has at least 35 deduplicated,
leakage-clean, demote-eligible explicit-literal candidates. This is not
currently established by the checked-in artifacts.

## Dev20 and Holdout20 Split

Split only after the 35+ pool filter succeeds.

Dev20:

- select 20 unique case ids;
- round-robin by category priority;
- cap any single category at 12 cases when possible;
- cap any single tool at 5 cases when possible;
- cap trajectory-sensitive or mutating tools at 6 cases when possible;
- prefer at least 12 `current_request` grounded cases.

Holdout20:

- select from remaining candidates only;
- require zero case-id overlap with dev20;
- round-robin by category priority;
- approximate dev category/tool/literal-source distribution;
- mark same-source-root risk if source roots cannot be separated;
- never use dev scorer feedback to reorder holdout.

If fewer than 40 candidates exist, dev20 may be prepared only as a diagnostic
scorer request with explicit acceptance-owner approval. It does not authorize
holdout or performance claims. Formal holdout planning requires a complete,
disjoint holdout20.

Manifest requirements:

- `selected_case_ids`
- `selected_case_count`
- `unique_selected_case_count`
- `duplicate_selected_case_ids`
- `dev_holdout_overlap_case_ids`
- `category_distribution`
- `tool_distribution`
- `literal_source_distribution`
- `source_run_root_distribution`
- `same_source_root_risk`
- `candidate_rules_type`
- `authorized_theory_prior_families`
- `no_next_tool_intervention`
- `exact_tool_choice`
- `leakage_audit_passed`
- `planned_commands=[]`
- `candidate_commands=[]`

## Dev Fail and Pass Branch

Dev fail branch:

- provider preflight red: stop, do not run holdout;
- baseline/candidate schema incomplete: invalidate run;
- manifest mismatch on protocol, provider, route, category, selected ids, runtime
  config, or tool schema: invalidate run;
- no candidate activation: fix runtime hook or rule scope offline;
- filled-arg match rate below threshold: fix extractor or binding offline;
- candidate accuracy not greater than baseline: reject current scorer config;
- fixed cases not greater than regressed cases: inspect regression family and
  remove risky tool slices offline;
- unacceptable cost/latency regression: reject current scorer config;
- leakage detected: invalidate pool and rebuild from source;
- any fail branch: do not run holdout, do not update retained rules, and do not
  claim performance.

Dev pass branch:

- freeze the candidate rule bundle and candidate manifest;
- preserve compact baseline/candidate artifacts;
- produce paired comparison, regression, and cost/latency reports;
- rerun artifact-boundary and paired-comparison gates;
- request holdout execution without reordering holdout by dev feedback;
- state that dev pass authorizes only the holdout step, not +3pp/full-suite/SOTA
  claims.

Holdout pass is required before any expansion to 100-case or full-suite
performance validation. Full first-stage performance acceptance still requires
the Huawei-approved +3pp comparison under the frozen protocol.

