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

Checker-required accepted-candidate fields. These must match
`scripts/check_explicit_literal_candidate_pool.py::REQUIRED_CANDIDATE_FIELDS`:

- `case_id`
- `category`
- `candidate_generatable`
- `candidate_origin`
- `candidate_rules_type`
- `rule_type`
- `source_run_root`
- `tool`
- `schema_arg_name`
- `selected_literal`
- `literal_source`
- `literal_source_span`
- `literal_source_text_hash`
- `used_gold_fields`
- `used_score_fields`
- `used_candidate_output`
- `retention_prior`

Extractor-recommended audit fields. These are not required by the current
checker, but should be emitted when available because they make candidate
review, source expansion, and scorer authorization auditable:

- `emitted_tool_name`
- `required_arg`
- `required_args`
- `missing_required_args`
- `emitted_tool_args`
- `schema_type`
- `literal_value`
- `unique_literal_value`
- `literal_candidates`
- `literal_candidate_count`
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
- `rejection_reason`

The current checker specifically consumes the following no-leakage / grounding
fields and fails closed when they are missing or invalid:

- `literal_source_span`
- `literal_source_text_hash`
- `used_gold_fields`
- `used_score_fields`
- `used_candidate_output`

Accepted-candidate identity fields:

- `candidate_rules_type`
- `rule_type`
- `schema_arg_name`
- `selected_literal`
- `literal_source`
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

## Extractor Implementation Checklist

Engineering should implement the provider-green extractor as an offline script
with explicit function boundaries. Recommended entrypoint:

```text
scripts/build_explicit_literal_candidate_pool.py
```

The script must not call BFCL, a provider, a model, or a scorer. It reads
already-collected source artifacts and writes candidate JSONL, audit JSON, and
dev/holdout manifest drafts only.

### CLI Boundary

Required CLI flags:

- `--source-root`: source collection root containing BFCL result/trace artifacts.
- `--categories`: comma-separated BFCL categories to scan.
- `--output-root`: default
  `outputs/artifacts/bfcl_explicit_required_arg_literal_v1`.
- `--candidate-jsonl`: default `output-root/candidate_rules.jsonl`.
- `--audit-json`: default `output-root/explicit_literal_extractor_audit.json`.
- `--dev-manifest`: default
  `output-root/explicit_required_arg_literal_dev20_manifest.json`.
- `--holdout-manifest`: default
  `output-root/explicit_required_arg_literal_holdout20_manifest.json`.
- `--min-pool-size`: default `35`.
- `--dev-count`: default `20`.
- `--holdout-count`: default `20`.
- `--dry-run`: compute records and audit counts without writing manifests.
- `--strict`: return non-zero when the offline pool/split gate fails.

The CLI must write `planned_commands=[]` and `candidate_commands=[]` in every
artifact it owns. Any artifact containing scorer/provider commands is invalid
for this stage.

### Function Boundaries

Use small pure functions where possible so tests can cover edge cases without
large BFCL fixtures.

Input loading:

- `load_dataset_records(category: str) -> dict[str, dict]`
  - wraps `bfcl_eval.utils.load_dataset_entry(category, include_prereq=False)`;
  - returns records keyed by `id`;
  - reads only dataset prompt/function schema fields.
- `find_result_file(source_root: Path, category: str) -> Path | None`
  - finds `BFCL_v4_{category}_result.json` under `bfcl/result`;
  - returns `None` instead of raising when missing.
- `load_result_records(source_root: Path, category: str) -> tuple[dict[str, dict], dict]`
  - parses JSONL result rows keyed by `id` or `case_id`;
  - returns stats: raw lines, parsed lines, parse errors, missing ids.
- `load_trace_records(source_root: Path, category: str) -> dict[str, dict]`
  - reads trace/request artifacts when present;
  - must tolerate absent traces and mark `trace_missing_count`;
  - must not read scorer, gold, expected, reference, or candidate-output paths.

Schema helpers:

- `normalize_tool_name(name: Any) -> str`
  - normalize dots/spaces consistently with existing M2.8-pre builder.
- `function_map(dataset_record: dict) -> dict[str, dict]`
  - maps normalized function name to BFCL function schema;
  - rejects duplicate normalized names for the case.
- `required_args(function_schema: dict) -> list[str]`
  - returns only string required args.
- `arg_schema(function_schema: dict, arg: str) -> dict`
  - returns `parameters.properties[arg]` or `{}`.

Tool-call parser:

- `parse_tool_calls(result_record: dict, trace_record: dict | None) -> list[ToolCall]`
  - accepts the known BFCL layouts: list of `{tool_name: json_args}` mappings,
    OpenAI-style `tool_calls[].function.{name,arguments}`, and trace-side
    parsed tool-call lists;
  - parses JSON string arguments into dicts;
  - rejects non-object args for explicit literal completion;
  - preserves call index and raw source path for audit.
- `match_single_schema_tool_call(calls: list[ToolCall], schema_map: dict) -> ToolCall | Reject`
  - requires exactly one call to map to exactly one schema function;
  - when parallel calls are present, accepts only if call-to-schema mapping is
    unique and the candidate case id remains unique;
  - otherwise rejects with `parallel_call_mapping_not_unique`,
    `missing_emitted_tool_call`, or `no_matching_emitted_tool`.
- `compute_missing_required_args(call_args: dict, required: list[str]) -> list[str]`
  - returns missing required schema args only;
  - rejects if zero or more than one missing arg.

Observable-source builder:

- `extract_current_request_text(dataset_record: dict, trace_record: dict | None) -> str`
  - concatenates model-visible system/user request text for the repaired turn;
  - must not use gold/reference fields.
- `extract_current_observation_text(trace_record: dict | None, call_index: int) -> str`
  - concatenates only tool observations visible before the selected tool call;
  - rejects observations after the selected call.
- `observable_sources(...) -> list[ObservableSource]`
  - returns ordered sources: `current_request` first, then
    `current_observation`;
  - each source carries source name, text, and stable source path/turn metadata.

Literal grounder:

- `ground_literals(source: ObservableSource, schema: dict, arg_name: str, emitted_args: dict) -> list[GroundedLiteral]`
  - extracts schema-compatible literal candidates with start/end offsets;
  - string: quoted literals, filename/path-like tokens, enum surfaces, and
    argument-name cue spans;
  - number/integer: numeric spans with type-safe normalization;
  - boolean: explicit true/false/yes/no spans;
  - enum: exact or case-insensitive enum surface, normalized to schema value;
  - array/object: accept only a single explicit JSON literal span that parses
    and matches schema shape, otherwise reject.
- `select_unique_literal(candidates: list[GroundedLiteral]) -> GroundedLiteral | Reject`
  - removes literals already present in emitted args;
  - requires exactly one schema-compatible candidate across allowed sources;
  - rejects with `no_observable_literal`, `ambiguous_observable_literal`, or
    `schema_type_mismatch`.
- `literal_source_text_hash(source_text: str, span: tuple[int, int]) -> str`
  - hashes the exact text slice used for grounding;
  - the slice must reproduce `selected_literal` or its typed normalized value.

Leakage auditor:

- `audit_record_no_leakage(record: dict, source_metadata: dict) -> tuple[bool, list[str]]`
  - requires `literal_source in {"current_request", "current_observation"}`;
  - requires non-empty `literal_source_span`;
  - requires non-empty `literal_source_text_hash`;
  - requires `used_gold_fields is False`;
  - requires `used_score_fields is False`;
  - requires `used_candidate_output is False`;
  - rejects `source_result_only` and `source_result_tool_args` as pool sources;
  - scans field names, source path fragments, and string values for the
    checker-forbidden tokens: `gold`, `answer`, `expected`, `ground_truth`,
    `oracle`, `checker`, `reference`, `possible_answer`;
  - additionally audits algorithm-denied provenance tokens:
    `score`, `valid`, `scorer`, `candidate_output`, `patched_output`,
    `holdout_feedback`.

Candidate emitter:

- `build_candidate_record(...) -> dict`
  - fills every checker-required field in the schema JSON;
  - sets `candidate_generatable=true`;
  - sets both `candidate_rules_type` and `rule_type` to
    `explicit_required_arg_literal_completion`;
  - sets `retention_prior.retain_eligibility=demote_candidate`;
  - sets `retention_prior.intervention_scope=argument_only`;
  - sets `used_gold_fields=false`, `used_score_fields=false`, and
    `used_candidate_output=false`.
- `build_reject_record(...) -> dict`
  - preserves case/category/tool/source context;
  - sets `candidate_generatable=false`;
  - sets one stable `rejection_reason`;
  - never writes rejected records into runtime candidate rules unless the
    destination is explicitly named as a diagnostic audit file.

Pool selection and manifest splitter:

- `filter_pool_eligible(records: list[dict]) -> list[dict]`
  - keeps only leakage-clean, demote-candidate, argument-only explicit literal
    records;
  - excludes memory categories, source-result-only records, trajectory
    mutation, and tool-choice mutation;
  - deduplicates by `case_id` after deterministic sorting.
- `sort_pool(records: list[dict]) -> list[dict]`
  - uses the category/source/confidence/tool/case ordering defined in
    `35+ Pool Selection`.
- `split_dev_holdout(pool: list[dict], dev_count: int = 20, holdout_count: int = 20) -> tuple[dict, dict]`
  - runs only after the 35+ filter passes;
  - selects dev by category round-robin with category/tool/mutating-tool caps;
  - selects holdout from remaining cases only;
  - writes zero dev/holdout overlap;
  - marks `same_source_root_risk` when roots cannot be separated;
  - never reads or uses scorer feedback.
- `write_manifest(path: Path, selected: list[dict], pool: list[dict], split_name: str) -> None`
  - writes all manifest fields listed above;
  - writes `planned_commands=[]` and `candidate_commands=[]`.

### Implementation Acceptance Checklist

Before requesting scorer authorization, engineering must be able to check every
box below from local artifacts:

- candidate JSONL exists at
  `outputs/artifacts/bfcl_explicit_required_arg_literal_v1/candidate_rules.jsonl`;
- every accepted record has the 17 checker-required fields;
- every accepted record has non-empty `literal_source_span` and
  `literal_source_text_hash`;
- every accepted record has `used_gold_fields=false`,
  `used_score_fields=false`, and `used_candidate_output=false`;
- no accepted record contains checker-forbidden provenance tokens outside the
  allowed provenance flag keys;
- no accepted record uses `source_result_only` or `source_result_tool_args` as
  `literal_source`;
- accepted records are unique by `case_id`;
- pool has at least 35 deduplicated leakage-clean demote candidates;
- dev manifest has exactly 20 unique ids;
- holdout manifest has exactly 20 unique ids or is explicitly absent because
  formal holdout is not yet authorized;
- dev and holdout have zero overlap when both exist;
- manifests contain no scorer/provider commands;
- `scripts/check_explicit_literal_candidate_pool.py --strict` fails closed until
  all pool/split conditions are met and passes only after they are met.

### Test Fixture Design

Add focused unit tests under `tests/test_build_explicit_literal_candidate_pool.py`.
Use `tmp_path` and monkeypatch loaders instead of depending on live BFCL
installation or provider output.

Extractor fixture matrix:

| Fixture | Dataset prompt/schema | Baseline result/trace | Expected extractor output | Expected checker/split behavior |
| --- | --- | --- | --- | --- |
| `happy_path_current_request` | One BFCL record in `multi_turn_miss_func`; prompt contains exactly one visible literal, for example `"report.csv"`; function schema has required args `["query", "file_name"]`; schema type for `file_name` is string. | Result emits the same tool with `{"query": "error"}` and omits `file_name`; trace is absent or contains no extra observations. | One accepted record with `candidate_generatable=true`, `schema_arg_name="file_name"`, `selected_literal="report.csv"`, `literal_source="current_request"`, non-empty `literal_source_span`, non-empty `literal_source_text_hash`, and all three leakage flags false. | Candidate is eligible; no reject reason; contributes one unique case to the 35+ pool. |
| `missing_source_result` | Valid BFCL dataset record and function schema. | No result file, no matching result row, or unparsable result row for the case. | One diagnostic reject with `candidate_generatable=false`, `rejection_reason="missing_source_result"`, and case/category context preserved. | Does not enter candidate JSONL pool or dev/holdout manifests; audit count increments missing-source bucket. |
| `parallel_ambiguity` | Prompt contains one valid literal; schema contains one missing required arg. | Result has multiple tool calls where more than one maps to the same schema function, or call index cannot be uniquely tied to the candidate case. | Diagnostic reject with `rejection_reason="parallel_call_mapping_not_unique"`; no accepted candidate. | Does not count toward 35+; verifies parser refuses non-unique parallel layouts rather than guessing. |
| `gold_leakage` | Dataset prompt/schema would otherwise support an accepted candidate. | Source metadata, path, field name, or string payload contains denied provenance such as `gold`, `expected`, `reference`, `oracle`, or `possible_answer`; or extraction would require a gold/scorer field. | Reject with `rejection_reason="gold_or_scorer_dependency_detected"` or leakage audit failure; `used_gold_fields`, `used_score_fields`, and `used_candidate_output` must not be true in any accepted record. | `scripts.check_explicit_literal_candidate_pool.evaluate` reports `candidate_gold_leakage_detected` if such a record reaches candidate JSONL; fixture should normally keep it diagnostic-only. |
| `source_result_only` | Prompt does not contain the missing literal and prior visible observation is empty. | Result/emitted args or source result contains the missing value. | Reject with `rejection_reason="source_result_only"` or `literal_source="source_result_only"` only in diagnostic audit output. | Never eligible; checker must block if `source_result_only` appears in runtime candidate JSONL. |
| `ambiguous_literal` | Prompt contains two schema-compatible literals for the same missing arg, for example `"a.csv"` and `"b.csv"` for `file_name`, or numbers `5` and `6` for integer arg. | Result emits matching tool with exactly one required arg missing. | Reject with `rejection_reason="ambiguous_observable_literal"`; include `literal_candidate_count=2` and candidate list in audit fields when available. | Does not count toward pool; validates no heuristic tie-breaker silently selects one literal. |
| `schema_mismatch` | Prompt contains a visible literal whose surface is incompatible with the missing arg schema, for example `"five"` when schema type is integer or a string outside enum. | Result emits matching tool with that required arg missing. | Reject with `rejection_reason="schema_type_mismatch"`; no accepted record. | Does not count toward pool; validates type normalization is fail-closed. |
| `dev_holdout_split_40_cases` | Forty accepted synthetic records spanning the priority categories and at least several tools; each record has unique `case_id`, allowed literal source, span/hash, and demote retention prior. | Result/trace fixtures are already converted into accepted candidate records or generated through the extractor path. | `candidate_rules.jsonl` has at least 40 accepted records; dev manifest has 20 unique ids; holdout manifest has 20 unique ids; both include distributions, no commands, and zero overlap. | `scripts.check_explicit_literal_candidate_pool.evaluate` passes; then perturb duplicates/overlap/missing hash to confirm fail-closed blockers. |

### R1 Rejection Taxonomy Increment

After the current-request happy path, the next real extractor increment is a
single rejection-taxonomy pass. It must not add scorer execution, observation
grounding, holdout selection changes, or non-explicit repair families. Its goal
is to make failure accounting stable before broad source expansion.

R1 scope:

- keep accepted-candidate behavior unchanged for `happy_path_current_request`;
- emit rejected records into `explicit_literal_extractor_audit.json.rejections`;
- keep `candidate_rules.jsonl` accepted-only;
- report canonical counts in
  `explicit_literal_extractor_audit.json.reject_reason_counts` and
  `explicit_literal_candidate_pool_build_summary.json.reject_reason_counts`;
- use canonical `rejection_reason` on every rejected record. A temporary
  backward-compatible `reason` alias is allowed during migration, but
  `rejection_reason` is the field downstream code must consume.

Canonical R1 reject reasons:

- `missing_source_result`
- `parallel_call_mapping_not_unique`
- `ambiguous_observable_literal`
- `schema_type_mismatch`

R1 must retire provisional reason names from build outputs:

- `result_jsonl_missing_or_empty` -> `missing_source_result`
- `current_request_literal_not_unique` -> `ambiguous_observable_literal`
- `no_single_missing_required_arg` remains diagnostic-only outside R1 unless
  engineering narrows it to one of the canonical reasons with evidence.

Rejected audit records must preserve enough context for source expansion
debugging while remaining leakage-safe. Required rejected-record fields:

- `case_id`: string, or `null` only when no result row exists for a category;
- `category`: BFCL category;
- `source_run_root`: source artifact root, when known;
- `candidate_generatable`: `false`;
- `candidate_rules_type`: `explicit_required_arg_literal_completion`;
- `rule_type`: `explicit_required_arg_literal_completion`;
- `rejection_reason`: one canonical R1 reason;
- `tool`: emitted tool name when known, otherwise `null`;
- `schema_arg_name`: missing required arg when known, otherwise `null`;
- `literal_source`: `current_request` when rejection is about prompt grounding,
  otherwise `null`;
- `used_gold_fields`: `false`;
- `used_score_fields`: `false`;
- `used_candidate_output`: `false`.

Optional rejected-record audit fields:

- `source_result_path`
- `result_row_count`
- `tool_call_count`
- `matched_tool_call_count`
- `missing_required_args`
- `literal_candidates`
- `literal_candidate_count`
- `schema_type`
- `literal_source_span`
- `literal_source_text_hash`

Precise R1 fixture expectations:

```json
{
  "fixture": "missing_source_result",
  "candidate_rules_jsonl_rows": [],
  "summary_patch": {
    "accepted_record_count": 0,
    "rejected_record_count": 1,
    "reject_reason_counts": {"missing_source_result": 1}
  },
  "audit_rejection": {
    "case_id": null,
    "category": "multi_turn_miss_func",
    "source_run_root": "/tmp/source/multi_turn_miss_func/baseline",
    "candidate_generatable": false,
    "candidate_rules_type": "explicit_required_arg_literal_completion",
    "rule_type": "explicit_required_arg_literal_completion",
    "rejection_reason": "missing_source_result",
    "tool": null,
    "schema_arg_name": null,
    "literal_source": null,
    "used_gold_fields": false,
    "used_score_fields": false,
    "used_candidate_output": false,
    "source_result_path": null,
    "result_row_count": 0
  }
}
```

```json
{
  "fixture": "parallel_call_mapping_not_unique",
  "candidate_rules_jsonl_rows": [],
  "summary_patch": {
    "accepted_record_count": 0,
    "rejected_record_count": 1,
    "reject_reason_counts": {"parallel_call_mapping_not_unique": 1}
  },
  "audit_rejection": {
    "case_id": "case_parallel_1",
    "category": "parallel_multiple",
    "source_run_root": "/tmp/source/parallel_multiple/baseline",
    "candidate_generatable": false,
    "candidate_rules_type": "explicit_required_arg_literal_completion",
    "rule_type": "explicit_required_arg_literal_completion",
    "rejection_reason": "parallel_call_mapping_not_unique",
    "tool": "grep",
    "schema_arg_name": "file_name",
    "literal_source": null,
    "used_gold_fields": false,
    "used_score_fields": false,
    "used_candidate_output": false,
    "tool_call_count": 2,
    "matched_tool_call_count": 2,
    "missing_required_args": ["file_name"]
  }
}
```

```json
{
  "fixture": "ambiguous_observable_literal",
  "candidate_rules_jsonl_rows": [],
  "summary_patch": {
    "accepted_record_count": 0,
    "rejected_record_count": 1,
    "reject_reason_counts": {"ambiguous_observable_literal": 1}
  },
  "audit_rejection": {
    "case_id": "case_ambiguous_1",
    "category": "multi_turn_miss_func",
    "source_run_root": "/tmp/source/multi_turn_miss_func/baseline",
    "candidate_generatable": false,
    "candidate_rules_type": "explicit_required_arg_literal_completion",
    "rule_type": "explicit_required_arg_literal_completion",
    "rejection_reason": "ambiguous_observable_literal",
    "tool": "grep",
    "schema_arg_name": "file_name",
    "literal_source": "current_request",
    "used_gold_fields": false,
    "used_score_fields": false,
    "used_candidate_output": false,
    "literal_candidates": ["a.txt", "b.txt"],
    "literal_candidate_count": 2,
    "schema_type": "string"
  }
}
```

```json
{
  "fixture": "schema_type_mismatch",
  "candidate_rules_jsonl_rows": [],
  "summary_patch": {
    "accepted_record_count": 0,
    "rejected_record_count": 1,
    "reject_reason_counts": {"schema_type_mismatch": 1}
  },
  "audit_rejection": {
    "case_id": "case_schema_mismatch_1",
    "category": "multi_turn_miss_func",
    "source_run_root": "/tmp/source/multi_turn_miss_func/baseline",
    "candidate_generatable": false,
    "candidate_rules_type": "explicit_required_arg_literal_completion",
    "rule_type": "explicit_required_arg_literal_completion",
    "rejection_reason": "schema_type_mismatch",
    "tool": "calculate_area",
    "schema_arg_name": "height",
    "literal_source": "current_request",
    "used_gold_fields": false,
    "used_score_fields": false,
    "used_candidate_output": false,
    "literal_candidates": ["five"],
    "literal_candidate_count": 1,
    "schema_type": "integer"
  }
}
```

R1 fixture acceptance criteria:

- each fixture writes zero accepted rows to `candidate_rules.jsonl`;
- each fixture writes exactly one audit rejection unless the test intentionally
  includes multiple cases;
- `reject_reason_counts` contains only canonical R1 reason keys for these
  cases;
- no rejected record sets any leakage flag to true;
- rejected records do not count toward `eligible_count`, dev manifests, or
  holdout manifests;
- no fixture introduces scorer/provider commands.

### R2 Current-Observation Happy Path

R2 should add exactly one accepted-candidate path beyond
`happy_path_current_request`: a missing required argument whose unique literal
is visible in a prior tool observation before the repaired tool call. Parallel
rejection remains out of scope for this R2 slice.

Fixture: `happy_path_current_observation`

Dataset prompt/schema:

- category: `multi_turn_long_context` or `multi_turn_miss_func`;
- one BFCL record with tool `grep`;
- function schema has required args `["pattern", "file_name"]`;
- schema type for `file_name` is `string`;
- current request asks to search the file from the previous result, but does
  not itself contain the literal filename.

Baseline result/trace:

- prior visible tool observation before the selected tool call contains exactly
  one schema-compatible literal, for example `The file is "archive.log".`;
- baseline result emits `grep` with `{"pattern": "ERROR"}` and omits
  `file_name`;
- the observation must occur before the selected emitted tool call index;
- no later observation or scorer/gold/candidate-output field may be used.

Expected accepted candidate record:

```json
{
  "case_id": "case_observation_1",
  "category": "multi_turn_long_context",
  "candidate_generatable": true,
  "candidate_origin": "current_observation_explicit_literal_extractor",
  "candidate_rules_type": "explicit_required_arg_literal_completion",
  "rule_type": "explicit_required_arg_literal_completion",
  "source_run_root": "/tmp/source/multi_turn_long_context/baseline",
  "tool": "grep",
  "schema_arg_name": "file_name",
  "selected_literal": "archive.log",
  "literal_source": "current_observation",
  "literal_source_span": {
    "source": "current_observation",
    "turn_index": 0,
    "start": 13,
    "end": 24,
    "text": "archive.log"
  },
  "literal_source_text_hash": "<sha256-of-exact-span-text>",
  "used_gold_fields": false,
  "used_score_fields": false,
  "used_candidate_output": false,
  "retention_prior": {
    "rule_family": "explicit_required_arg_literal_completion",
    "theory_class": "schema_constraint_completion",
    "retain_eligibility": "demote_candidate",
    "literal_source": "current_observation",
    "precondition_observable": true,
    "postcondition_local": true,
    "intervention_scope": "argument_only",
    "tool_choice_mutation": false,
    "trajectory_mutation": false,
    "exact_tool_choice": false
  }
}
```

Expected summary/audit fields:

- `accepted_record_count=1`;
- `rejected_record_count=0`;
- `reject_reason_counts={}`;
- `candidate_record_count=1`;
- `eligible_count=1` when `min_pool_size` or `min_eligible` is set to `1` in
  the fixture;
- `planned_commands=[]`;
- `candidate_commands=[]`.

Checker expectations:

- `scripts.check_explicit_literal_candidate_pool.evaluate` treats
  `literal_source="current_observation"` as an allowed pool source;
- the candidate fails closed if `literal_source_span` or
  `literal_source_text_hash` is missing;
- the candidate fails closed if any of `used_gold_fields`, `used_score_fields`,
  or `used_candidate_output` is not exactly `false`;
- the candidate must not enter dev/holdout unless it is unique by `case_id` and
  the normal pool/split thresholds are satisfied.

### R3 Parallel Rejection and Source Priority

R3 is a bounded quality increment. It should not add provider/scorer execution,
new repair families, memory/postcondition behavior, or broad parser support. It
adds one fail-closed parallel rejection and one deterministic source-priority
rule so later source expansion does not admit unstable candidates.

R3 scope:

- reject ambiguous parallel tool-call mappings with
  `parallel_call_mapping_not_unique`;
- apply deterministic source priority when both request and prior observation
  contain literals;
- keep `candidate_rules.jsonl` accepted-only;
- write rejected records only under
  `explicit_literal_extractor_audit.json.rejections`;
- preserve the checker-required accepted fields unchanged.

#### Parallel Mapping Rejection

Rejection reason:

```text
parallel_call_mapping_not_unique
```

Use this rejection when a result row has multiple emitted tool calls and the
extractor cannot prove a single selected call maps to exactly one dataset
function and exactly one missing required argument. Do not guess by call order
when two calls have the same normalized tool name, when two schema functions
normalize to the same emitted name, or when two candidate calls would generate
different missing-arg repairs for the same case.

Fixture: `r3_parallel_call_mapping_not_unique`

Dataset prompt/schema:

- category: `parallel_multiple`;
- one case with request text containing exactly one visible literal, for
  example `"audit.log"`;
- function schema has tool `grep` with required args
  `["pattern", "file_name"]`.

Baseline result/trace:

- result row contains two emitted `grep` calls for the same case;
- each call maps to the same schema function;
- each call omits `file_name`;
- both calls are plausible repair targets and no trace metadata identifies one
  as the selected repaired call.

Expected rejected audit record:

```json
{
  "case_id": "case_parallel_r3",
  "category": "parallel_multiple",
  "source_run_root": "/tmp/source/parallel_multiple/baseline",
  "candidate_generatable": false,
  "candidate_rules_type": "explicit_required_arg_literal_completion",
  "rule_type": "explicit_required_arg_literal_completion",
  "rejection_reason": "parallel_call_mapping_not_unique",
  "tool": "grep",
  "schema_arg_name": "file_name",
  "literal_source": null,
  "used_gold_fields": false,
  "used_score_fields": false,
  "used_candidate_output": false,
  "tool_call_count": 2,
  "matched_tool_call_count": 2,
  "missing_required_args": ["file_name"]
}
```

Expected summary/audit fields:

- `accepted_record_count=0`;
- `rejected_record_count=1`;
- `reject_reason_counts={"parallel_call_mapping_not_unique": 1}`;
- `candidate_record_count=0`;
- `eligible_count=0`;
- `planned_commands=[]`;
- `candidate_commands=[]`.

No-leakage constraints:

- the rejection must be derivable from dataset schema plus baseline result/trace
  structure only;
- the extractor must not inspect scorer/gold/expected/reference/candidate-output
  fields to choose between parallel calls;
- all rejected records must keep `used_gold_fields=false`,
  `used_score_fields=false`, and `used_candidate_output=false`;
- rejected parallel records must never be written to runtime candidate JSONL.

BFCL validity protection:

- prevents a rule from filling an argument on the wrong tool call in BFCL
  parallel categories;
- prevents inflated candidate counts from duplicated same-case calls;
- preserves exact tool-choice and argument-only intervention assumptions for
  accepted explicit-literal candidates.

#### Request/Observation Priority Rules

When both `current_request` and prior `current_observation` are available, R3
must choose candidates by deterministic priority rather than merging all
literals into one ambiguous bag.

Implementation-safe decision order:

1. Build schema-compatible literal sets separately for `current_request` and
   prior `current_observation`; do not merge them before counting.
2. Reject with `ambiguous_observable_literal` when either source has more than
   one compatible literal for the missing arg.
3. When both sources have one compatible literal:
   - if their normalized typed values are equal, accept the request literal and
     set `literal_source="current_request"`;
   - if their normalized typed values differ, reject with
     `ambiguous_observable_literal`.
4. When only `current_request` has one compatible literal, accept it and set
   `literal_source="current_request"`.
5. When only prior `current_observation` has one compatible literal, accept it
   and set `literal_source="current_observation"`.
6. Ignore observations after the selected emitted tool call; using them is a
   leakage failure, not a candidate.

This order is intentionally request-preferred only for the same-literal case.
It does not allow a request literal to silently override a different prior
observation literal.

Fixture: `r3_request_preferred_over_observation_same_literal`

Dataset prompt/schema:

- category: `multi_turn_long_context`;
- tool `grep`, missing required arg `file_name`;
- request contains exactly one literal: `"archive.log"`;
- prior observation before the call also contains `"archive.log"`.

Expected accepted candidate differences from R2:

```json
{
  "case_id": "case_priority_same_literal",
  "category": "multi_turn_long_context",
  "candidate_generatable": true,
  "candidate_origin": "current_request_explicit_literal_extractor",
  "candidate_rules_type": "explicit_required_arg_literal_completion",
  "rule_type": "explicit_required_arg_literal_completion",
  "tool": "grep",
  "schema_arg_name": "file_name",
  "selected_literal": "archive.log",
  "literal_source": "current_request",
  "literal_source_span": {
    "source": "current_request",
    "text": "archive.log"
  },
  "literal_source_text_hash": "<sha256-of-request-span-text>",
  "used_gold_fields": false,
  "used_score_fields": false,
  "used_candidate_output": false,
  "retention_prior": {
    "retain_eligibility": "demote_candidate",
    "literal_source": "current_request",
    "intervention_scope": "argument_only",
    "tool_choice_mutation": false,
    "trajectory_mutation": false,
    "exact_tool_choice": false
  }
}
```

Fixture: `r3_request_observation_conflict_rejected`

Dataset prompt/schema:

- category: `multi_turn_long_context`;
- tool `grep`, missing required arg `file_name`;
- request contains exactly one compatible literal: `"request.log"`;
- prior observation before the call contains a different compatible literal:
  `"observed.log"`.

Expected rejected audit record:

```json
{
  "case_id": "case_priority_conflict",
  "category": "multi_turn_long_context",
  "source_run_root": "/tmp/source/multi_turn_long_context/baseline",
  "candidate_generatable": false,
  "candidate_rules_type": "explicit_required_arg_literal_completion",
  "rule_type": "explicit_required_arg_literal_completion",
  "rejection_reason": "ambiguous_observable_literal",
  "tool": "grep",
  "schema_arg_name": "file_name",
  "literal_source": null,
  "literal_sources": ["current_request", "current_observation"],
  "used_gold_fields": false,
  "used_score_fields": false,
  "used_candidate_output": false,
  "literal_candidates": ["request.log", "observed.log"],
  "literal_candidate_count": 2,
  "schema_type": "string"
}
```

Checker expectations:

- accepted request-priority records pass the existing checker because
  `literal_source="current_request"` is allowed and all 17 required fields are
  present;
- accepted observation records from R2 remain checker-eligible because
  `literal_source="current_observation"` is allowed;
- rejected priority-conflict and parallel records do not enter
  `candidate_rules.jsonl`, so they cannot count toward 35+ or dev/holdout;
- if a rejected record is accidentally written to candidate JSONL, it must fail
  checker eligibility because `candidate_generatable=false`, required accepted
  fields may be null, and/or `literal_source` is not one allowed accepted source.

### R4 Offline Candidate-Pool Expansion

R4 is the first source-expansion increment after R2/R3. It uses only existing
offline BFCL dataset, baseline result, and baseline trace/source artifacts. It
must not call a provider, run BFCL, invoke a scorer, read gold/reference fields,
or lower the retention prior. The only accepted repair family remains
`explicit_required_arg_literal_completion`.

#### Source Search Plan

The extractor should discover inputs in this order:

1. Read the source collection manifest:
   `outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_manifest.json`.
2. For each `category_status[]` entry, collect `existing_source_roots[]` when
   present. If `existing_source_roots[]` is absent but
   `source_artifacts_available=true`, probe the category source root under the
   manifest root as a fallback.
3. Within each source root, search for baseline result JSONL files:
   - `bfcl/result/**/BFCL_v4_{category}_result.json`
   - `**/BFCL_v4_{category}_result.json`
4. Within the same source root, search for trace/request artifacts only when
   they are baseline-side artifacts. Trace files may provide request messages,
   parsed tool calls, validation issues, and prior observations before the
   selected call. They must not provide scorer output or gold/reference calls.
5. Load BFCL dataset records for the same category from the local BFCL dataset
   loader or an explicit `--dataset-json` fixture. Use only `id`, prompt/messages,
   function name, function parameter properties, and required args.

R4 category expansion order:

1. `multi_turn_miss_func`
2. `multi_turn_long_context`
3. `multi_turn_base`
4. `parallel_multiple`
5. `multiple`

Do not include memory categories in the 35+ pool. Memory-heavy records may be
reported in audit counts only.

#### Accepted Candidate Taxonomy

R4 may accept only these explicit-literal candidate source types:

- `current_request_unique_required_literal`
  - one emitted tool call maps uniquely to one schema function;
  - exactly one required arg is missing;
  - `current_request` contains exactly one schema-compatible literal for that
    arg;
  - no conflicting compatible literal exists in prior observations.
- `current_observation_unique_required_literal`
  - one emitted tool call maps uniquely to one schema function;
  - exactly one required arg is missing;
  - `current_request` contains zero compatible literals;
  - prior observations before the selected call contain exactly one compatible
    literal;
  - no later observation is used.
- `current_request_preferred_same_literal`
  - `current_request` and prior observation each contain exactly one compatible
    literal;
  - their normalized typed values are equal;
  - accepted record uses `literal_source="current_request"` and the request
    span/hash.

All accepted R4 records must keep:

- `candidate_rules_type="explicit_required_arg_literal_completion"`;
- `rule_type="explicit_required_arg_literal_completion"`;
- `candidate_generatable=true`;
- `retention_prior.retain_eligibility="demote_candidate"`;
- `retention_prior.intervention_scope="argument_only"`;
- `retention_prior.tool_choice_mutation=false`;
- `retention_prior.trajectory_mutation=false`;
- `retention_prior.exact_tool_choice=false`;
- `used_gold_fields=false`;
- `used_score_fields=false`;
- `used_candidate_output=false`;
- non-empty `literal_source_span`;
- non-empty `literal_source_text_hash`.

No accepted R4 record may depend on `source_result_only`,
`source_result_tool_args`, scorer output, candidate output, hidden state, or a
postcondition.

#### Rejected Candidate Taxonomy

R4 should emit rejected diagnostics for source-expansion accounting, but rejected
records must not enter `candidate_rules.jsonl` or count toward 35+.

Canonical R4 rejection reasons:

- `missing_source_result`
  - no result file, empty result file, no matching result row, or invalid result
    layout for a source root/category.
- `missing_dataset_record`
  - result row has a case id that cannot be found in the local BFCL dataset
    record source.
- `missing_emitted_tool_call`
  - result row exists but no emitted tool call can be parsed.
- `no_matching_emitted_tool`
  - emitted tool names do not map to the dataset function schema.
- `parallel_call_mapping_not_unique`
  - R3 parallel ambiguity: more than one plausible selected call/schema mapping.
- `missing_schema_properties`
  - function schema lacks usable `parameters.properties` or `required`.
- `required_args_already_present`
  - emitted args already contain all required args.
- `multiple_missing_required_args`
  - more than one required arg is absent.
- `no_observable_literal`
  - neither current request nor prior observation contains a compatible literal.
- `ambiguous_observable_literal`
  - any allowed source has multiple compatible literals, or request and
    observation contain different compatible literals for the same missing arg.
- `schema_type_mismatch`
  - a visible literal is present but cannot normalize to the missing arg schema.
- `source_result_only`
  - the literal is only recoverable from emitted result/tool args or non-visible
    source-result fields.
- `gold_or_scorer_dependency_detected`
  - extraction would require denied gold/scorer/reference/provenance fields.
- `candidate_output_dependency_detected`
  - extraction would require candidate/patched output.

Rejected records must include `rejection_reason`, category, case id when known,
source root when known, leakage flags set to false unless the reason itself is a
detected dependency, and optional diagnostic fields such as `tool_call_count`,
`matched_tool_call_count`, `missing_required_args`, `literal_candidates`, and
`literal_candidate_count`.

#### Leakage Guard

R4 must prove each accepted literal is model-visible before the repaired call:

- `literal_source` must be exactly `current_request` or `current_observation`;
- `literal_source_span.text` must be a slice from the selected source;
- `literal_source_text_hash` must be computed from the exact span text;
- observation spans must have turn/call metadata proving they precede the
  selected emitted call;
- field names, path fragments, and string payloads used for accepted candidates
  must not contain denied provenance tokens:
  `gold`, `answer`, `expected`, `ground_truth`, `oracle`, `checker`,
  `reference`, `possible_answer`, `score`, `valid`, `scorer`,
  `candidate_output`, `patched_output`, `holdout_feedback`;
- dev/holdout scorer feedback must not be read or used for ordering.

If a literal cannot be reproduced from a prompt/observation span, reject it. Do
not fill from emitted tool args, source result args, scorer labels, or expected
calls.

#### Target Metrics

R4 target is candidate-pool expansion without lowering the theory prior:

- at least 35 deduplicated, leakage-clean, demote-eligible accepted records;
- target 40+ accepted records before formal dev/holdout split so dev20 and
  holdout20 can be disjoint;
- at least 20 accepted records from `current_request` when available, with
  observation candidates used only after request-unique cases are exhausted;
- zero accepted records from memory categories;
- zero accepted records with `source_result_only` or denied provenance;
- zero duplicate accepted `case_id`s after deterministic sorting;
- `reject_reason_counts` reported for every scanned category/source root;
- no scorer/provider commands in build summary, audit, dev manifest, or holdout
  manifest.

The pool is still not a performance claim. It only authorizes the offline
candidate-pool gate and a later acceptance-owner scorer authorization request
when the existing checker passes.

### R5 Provider-Green Source Collection Priority

R5 handles the case where the offline existing source pool has zero usable BFCL
result files. It defines the smallest source-collection sequence to create
inputs for `explicit_required_arg_literal_completion` after provider preflight
is green. R5 is source collection only: it must not run candidate scoring,
holdout, full-suite scoring, memory policies, postcondition policies, or CTSPC
trajectory/action policies.

#### Minimal Category Order

Collect categories in batches. After each batch, rebuild the explicit-literal
candidate pool and run the offline candidate-pool gate. Stop as soon as the
pool reaches the target metrics below.

Batch 1:

1. `multi_turn_miss_func`

Rationale: this is the highest-yield category for missing required argument
repairs because the failure mode is directly aligned with a tool/function miss
or omitted schema argument. It should produce the densest `current_request` and
prior-observation literal candidates per source-collection run.

Batch 2:

2. `multi_turn_long_context`
3. `multi_turn_base`

Rationale: both preserve multi-turn observable context, so they are the next
best source for R2/R3 `current_observation` and same-literal
request/observation priority candidates. They are still argument-only and do not
require postcondition or trajectory repair.

Batch 3:

4. `multiple`

Rationale: single-turn or simpler multi-function records may still contain
prompt-visible missing required literals. They are less targeted than miss-func
and multi-turn context categories but safer than parallel categories because
tool-call mapping ambiguity is lower.

Batch 4:

5. `parallel_multiple`

Rationale: this can add candidates, but only when R3 parallel mapping proves a
unique selected call/schema mapping. Ambiguous rows must reject with
`parallel_call_mapping_not_unique`, so expected accepted yield is lower and
rejection accounting is more important.

Do not collect memory categories for the mainline pool. `memory_kv`,
`memory_rec_sum`, and `memory_vector` may remain diagnostic-only source lanes,
but they do not count toward 35+ because their improvement mechanism depends on
memory state rather than deterministic argument literal completion.

#### Stop Criteria

After each batch, run the extractor/checker offline. Stop source collection when
all of the following are true:

- at least 35 deduplicated accepted candidates;
- target 40+ accepted candidates if a disjoint dev20/holdout20 split is being
  prepared;
- every accepted candidate has
  `retention_prior.retain_eligibility="demote_candidate"`;
- every accepted candidate has `literal_source` in
  `{current_request, current_observation}`;
- every accepted candidate has non-empty `literal_source_span` and
  `literal_source_text_hash`;
- zero accepted candidates from memory categories;
- zero accepted candidates with `source_result_only`, scorer/gold/reference, or
  candidate-output provenance;
- zero duplicate accepted `case_id`s after deterministic sorting;
- build summary, audit, dev manifest, and holdout manifest contain
  `planned_commands=[]` and `candidate_commands=[]`;
- `scripts/check_explicit_literal_candidate_pool.py --strict` passes.

If Batch 4 completes and the pool is still below 35, do not lower the retention
prior and do not add memory/postcondition/CTSPC. Instead report the category
yield table, rejection taxonomy counts, and remaining blocker as
`eligible_explicit_literal_candidates_below_35`.

#### Yield Accounting

Every batch must report:

- scanned category;
- source root;
- result file path and parsed row count;
- trace file availability count;
- accepted count by source type:
  `current_request_unique_required_literal`,
  `current_observation_unique_required_literal`,
  `current_request_preferred_same_literal`;
- rejected count by canonical R4 reason;
- deduplicated accepted count after sorting;
- cumulative accepted count toward 35 and 40;
- memory/postcondition/CTSPC accepted count, which must remain zero.

#### Artifact Boundary

R5 source collection must preserve a clean deliverable artifact boundary.
Deliverable paths under `outputs/artifacts/` may contain only compact manifests,
metrics, summaries, candidate JSONL, and audit summaries needed by the offline
gate. They must not contain raw BFCL result trees, traces, logs, provider
payloads, `.env` material, or repair records such as `repairs.jsonl`.

Raw source diagnostics may be produced only under the explicit source-collection
run root outside the deliverable summary files, or under another non-deliverable
diagnostic path that is excluded by `scripts/check_artifact_boundary.py`. The
source collection manifest may reference those raw paths, but checked-in
deliverable artifacts must keep only compact counts, hashes, paths, and
category/source-root status.

After every source-collection batch, run the artifact-boundary gate before using
the batch for explicit-literal candidate expansion. If raw diagnostics or repair
records are found under deliverable artifacts, stop and move or exclude them
before rebuilding the candidate pool.

#### Scope Boundary

Memory, postcondition, and CTSPC remain out of scope for R5 because they change
the intervention type:

- memory requires hidden or persistent state and cannot prove the literal came
  from the current prompt/observation span;
- postcondition-guided repair depends on outcome validation after a tool action,
  not a deterministic missing-argument precondition;
- CTSPC repairs trajectory/action choice and can change tool sequence, while
  the explicit-literal pool must preserve exact tool choice and mutate only a
  missing argument.

Keeping these out of R5 protects the first-stage claim boundary: the pool tests
deterministic argument/tool-use repair only, and any later performance result
can be attributed to `explicit_required_arg_literal_completion` rather than a
mixed repair stack.

Minimum fixtures:

- `dataset_record_one_missing_arg`
  - prompt contains one quoted filename or numeric literal;
  - function schema has two required args;
  - emitted tool args include one required arg and miss the grounded arg.
- `result_record_simple_mapping`
  - BFCL result layout as `{"result": [{"tool": "{\"arg\": \"x\"}"}]}`.
- `result_record_openai_tool_call`
  - OpenAI-style `tool_calls[].function.name/arguments` layout.
- `trace_record_prior_observation`
  - contains a prior tool observation with the literal and verifies the
    selected source is `current_observation`.
- `parallel_result_ambiguous`
  - two matching calls or non-unique call/schema mapping; expects
    `parallel_call_mapping_not_unique`.
- `source_result_only_literal`
  - literal appears only in emitted tool args/result, not request/observation;
    expects reject and no pool eligibility.
- `gold_leakage_path_or_field`
  - source metadata includes `gold`, `expected`, or `reference`; expects
    leakage rejection.
- `ambiguous_prompt_literals`
  - two schema-compatible literals in visible context; expects
    `ambiguous_observable_literal`.
- `schema_type_mismatch`
  - prompt literal is visible but cannot normalize to required schema type;
    expects `schema_type_mismatch`.
- `dev_holdout_split_40_cases`
  - 40 accepted records across categories/tools; expects dev20/holdout20,
    zero overlap, no duplicate ids, and no commands.

Required unit-test assertions:

- accepted record contains the exact 17 checker-required fields;
- `literal_source_span` is the exact visible text slice;
- `literal_source_text_hash` changes when the source slice changes;
- no test fixture reads scorer/gold/candidate-output fields to build a
  candidate;
- the candidate JSONL produced from 40 clean fixtures passes
  `scripts.check_explicit_literal_candidate_pool.evaluate`;
- fixtures with leakage, source-result-only grounding, missing span/hash,
  duplicate case ids, or dev/holdout overlap fail closed.

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
