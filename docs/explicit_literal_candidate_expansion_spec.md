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
