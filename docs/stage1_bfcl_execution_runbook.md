# Provider-Green BFCL Execution Runbook

This runbook defines the engineering path after an approved provider route is
green. It does not change the Huawei acceptance requirements and it is not a
performance claim. Do not run source collection, BFCL scoring, candidate scoring,
holdout, or full-suite commands while provider preflight is red.

## 0. Preconditions

Run from the repository root:

```bash
cd /cephfs/qiuyn/training-free
export PYTHONPATH=.:src
export PATH="$PWD/.venv/bin:$PATH"
```

Required before execution:

- approved provider profile and model route frozen by the acceptance owner
- valid provider credential exported for that profile
- `configs/runtime_bfcl_structured.yaml` points at the frozen provider route
- no raw BFCL result/score trees, traces, logs, `.env`, or repair records in the
  committed delivery outputs

Fail-closed gate:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
```

Stop if this fails.

## 1. Provider Green Preflight

Run the local proxy preflight first. This is the only step allowed before source
collection or scorer execution.

Template:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/run_bfcl_preflight.py \
  --base-url http://127.0.0.1:${PORT} \
  --trace-dir outputs/artifacts/stage1_bfcl_acceptance/provider_preflight_traces \
  --config-path configs/runtime_bfcl_structured.yaml \
  --out outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json
```

Then run the hard gate:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_provider_green_preflight.py \
  --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json \
  --compact --strict
```

Fail-closed conditions include env missing, HTTP 401, HTTP 403, HTTP 429, model
unavailable, missing tool-call checks, failed chat tool-call preflight, failed
Responses tool-call preflight, failed text PONG preflight, and missing trace
emission. If the provider credential is unavailable, leave the gate red and
configure valid approved credentials before continuing.

## 2. Source Collection

Source collection is baseline-only and is not performance evidence. Use the
planned commands from:

```text
outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_manifest.json
outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_manifest.md
```

Mainline source collection priority after provider green:

1. `multi_turn_miss_func`
2. `multi_turn_long_context`
3. `multi_turn_base`
4. `parallel_multiple`
5. `multiple`

Dataset gates for this priority list are incremental and fail-closed. After
Batch 1, require dataset/schema coverage only for `multi_turn_miss_func`; after
Batch 2, require coverage for `multi_turn_miss_func`,
`multi_turn_long_context`, and `multi_turn_base`; after Batch 3, add
`multiple`; after Batch 4, add `parallel_multiple`. Candidate build may use only
categories that have both collected source artifacts and passed dataset/schema
coverage. Do not require all five categories upfront unless the collection has
reached Batch 4 without hitting the 35+ explicit-literal pool target.

Memory categories are not part of the first-stage deterministic
explicit-literal mainline. `memory_kv`, `memory_rec_sum`, and `memory_vector`
may remain diagnostic source-collection lanes, but they do not authorize the
mainline scorer route and must not be counted toward explicit-literal-only
performance authorization.

Run the mainline source collection first:

```bash
bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_func/baseline 8076 multi_turn_miss_func configs/runtime_bfcl_structured.yaml
bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_long_context/baseline 8075 multi_turn_long_context configs/runtime_bfcl_structured.yaml
bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_base/baseline 8074 multi_turn_base configs/runtime_bfcl_structured.yaml
bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline 8080 parallel_multiple configs/runtime_bfcl_structured.yaml
bash scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline 8078 multiple configs/runtime_bfcl_structured.yaml
```

Only after the mainline priority categories are collected should optional
diagnostic categories from the manifest be run. Optional diagnostic commands
must stay labeled as source collection and must not be used as scorer evidence.

Fail-closed gates after source collection:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
PYTHONPATH=.:src .venv/bin/python scripts/check_m28pre_offline.py --compact --strict
```

Stop if artifact boundary fails or if M2.8-pre remains below scorer
authorization thresholds.

## 3. Rebuild Candidate Pool and Offline Gate

Rebuild the deterministic argument/tool-use repair pool after source collection
has refreshed the raw source availability.

The explicit-literal extractor/checker contract is specified in
`docs/explicit_literal_candidate_expansion_spec.md`. The machine-readable schema
draft is
`outputs/artifacts/bfcl_explicit_required_arg_literal_v1/explicit_literal_candidate_schema.json`.
Those files are normative for candidate fields, no-leakage checks, 35+ pool
selection, and dev20/holdout20 split behavior.

```bash
PYTHONPATH=.:src .venv/bin/python scripts/build_m27t_source_pool_manifest.py
PYTHONPATH=.:src .venv/bin/python scripts/build_m28pre_explicit_required_arg_literal.py
PYTHONPATH=.:src .venv/bin/python scripts/check_m28pre_offline.py --compact --strict
```

Fail-closed requirements:

- explicit required-argument literal pool reaches at least 35 usable demote
  candidates by itself for the explicit-literal-only route
- explicit-literal dev20 and holdout20 manifests are non-overlapping and each
  meets its registered size
- combined deterministic repair pool reaches at least 35 demote candidates only
  when the combined-family route is selected
- wrong-key alias and deterministic schema-local zero coverage does not block
  explicit-literal-only scorer authorization when explicit literal itself has
  35+ usable demote candidates and valid dev/holdout split conditions
- dev and holdout manifests are disjoint
- duplicate case-id gates pass
- source-scope audit passes
- no candidate or scorer commands are emitted before authorization

Stop if `check_m28pre_offline.py --strict` fails.

### Explicit Literal Candidate I/O Schema

Each explicit required-argument literal candidate record must preserve these
input/provenance fields:

- `case_id`
- `category`
- `source_run_root`
- `tool`
- `required_arg`
- `schema_arg_name`
- `literal_candidates`
- `literal_candidate_count`
- `literal_source`
- `literal_source_anchor`
- `literal_source_observed_as`
- `literal_source_rank`
- `literal_type_match`
- `disambiguation_cue`
- `trajectory_sensitive_tool`
- `exact_tool_choice`
- `no_next_tool_intervention`

Each candidate record must preserve these output/selection fields:

- `candidate_generatable`
- `candidate_origin`
- `candidate_rules_type`
- `rule_type`
- `slice_name`
- `selected_literal`
- `unique_literal_value`
- `confidence`
- `grounding_rejection_reason`
- `rejection_reason`
- `retention_prior`

The `retention_prior` object must include:

- `rule_family`
- `theory_class`
- `retain_eligibility`
- `literal_source`
- `literal_source_observed_as`
- `literal_uniqueness`
- `schema_type_match`
- `precondition_observable`
- `postcondition_local`
- `intervention_scope`
- `tool_choice_mutation`
- `trajectory_mutation`
- `exact_tool_choice`

Required scorer-eligible values for explicit-literal-only dev/holdout:

- `candidate_generatable=true`
- `candidate_rules_type=explicit_required_arg_literal_completion`
- `rule_type=explicit_required_arg_literal_completion`
- `retention_prior.retain_eligibility=demote_candidate`
- `retention_prior.intervention_scope=argument_only`
- `retention_prior.tool_choice_mutation=false`
- `retention_prior.trajectory_mutation=false`
- `no_next_tool_intervention=true`

### No Leakage Audit

Before a candidate enters the 35+ pool, its selected literal must be supported by
a literal span proof from the current request or current observation. The proof
must identify the source field, span text, and normalization used to produce
`selected_literal`.

Denylist for candidate literal sourcing:

- `gold`
- `answer`
- `expected`
- `ground_truth`
- `oracle`
- `checker`
- `reference`
- `possible_answer`

Any record whose literal source path, metadata key, or provenance label contains
one of the denylist tokens is leakage-tainted and cannot enter dev, holdout, or
scorer artifacts. `source_result_only` candidates are diagnostic only. They may
remain in audit artifacts, but they do not count toward the 35+ scorer pool and
must not be emitted into candidate rules.

Fail-closed no-leakage checks:

- reject candidate if selected literal has no literal span proof
- reject candidate if span proof comes from denylisted gold/reference material
- reject candidate if `literal_source=source_result_only`
- reject candidate if `grounding_rejection_reason=source_result_only`
- reject candidate if multiple candidate literals remain and uniqueness is not
  proven

### 35+ Pool Ordering and Dev/Holdout Split

Build the explicit-literal scorer pool from leakage-clean demote candidates
only. Sort the pool deterministically by:

1. `category` according to source collection priority:
   `multi_turn_miss_func`, `multi_turn_long_context`, `multi_turn_base`,
   `parallel_multiple`, `multiple`
2. `confidence` descending
3. `literal_source_rank` ascending, with missing rank last
4. `trajectory_sensitive_tool=false` before `true`
5. `case_id` lexicographically
6. `tool`
7. `schema_arg_name`

Deduplicate by `case_id` before splitting. If multiple candidates share a
`case_id`, keep the highest-ranked candidate and send the rest to diagnostic
rejections.

Split algorithm:

1. Require at least 35 deduplicated, leakage-clean explicit literal demote
   candidates.
2. Select `dev20` by round-robin over categories in priority order from the
   sorted pool.
3. Select `holdout20` from the remaining pool using the same round-robin rule.
4. Verify `dev20` and `holdout20` are disjoint by `case_id`.
5. Verify both manifests have no duplicate selected case ids.
6. Verify both manifests have no planned scorer commands before authorization.

If fewer than 40 candidates exist, the split may still authorize a dev scorer
only when dev20 is complete and a separate acceptance owner decision explicitly
allows dev-only diagnostic scoring. It does not authorize holdout or performance
claims. Formal holdout planning requires a complete disjoint holdout20.

## 4. Dev Baseline and Candidate Scorer Templates

Only run these after provider green and M2.8-pre scorer authorization are both
green. Use the same `protocol_id`, BFCL model alias, provider profile, upstream
model route, runtime config, test category, selected case ids, and tool schema
for baseline and candidate.

Dev baseline template:

```bash
bash scripts/run_bfcl_v4_baseline.sh \
  gpt-4o-mini-2024-07-18-FC \
  outputs/bfcl_runs/dev20/baseline/<run_id> \
  8090 \
  <test_category> \
  configs/runtime_bfcl_structured.yaml
```

Dev candidate template:

```bash
bash scripts/run_bfcl_v4_patch.sh \
  gpt-4o-mini-2024-07-18-FC \
  outputs/bfcl_runs/dev20/candidate/<run_id> \
  8091 \
  <test_category> \
  configs/runtime_bfcl_structured.yaml \
  <candidate_rules_dir> \
  outputs/bfcl_runs/dev20/candidate/<run_id>/traces \
  outputs/bfcl_runs/dev20/candidate/<run_id>/artifacts \
  outputs/bfcl_runs/dev20/baseline/<run_id>/artifacts/metrics.json
```

Fail-closed gates:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_run_artifact_schema.py outputs/bfcl_runs/dev20/baseline/<run_id> --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_run_artifact_schema.py outputs/bfcl_runs/dev20/candidate/<run_id> --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
```

Stop if either run schema is incomplete, if metrics are not complete, if
score/result source summaries are missing, if sanitized trace summaries are
missing, or if candidate rule snapshot/hash and candidate record manifest are
missing.

### Dev Fail/Pass Branch

Dev fail branch:

- Stop immediately if provider green preflight is no longer green.
- Stop if baseline or candidate run schema fails.
- Stop if manifests drift on protocol, provider, model route, test category,
  selected case hash, runtime config, or tool schema.
- Stop if candidate accuracy is not greater than baseline accuracy.
- Stop if `absolute_delta_pp < 3.0` for the registered dev threshold.
- Stop if any unacceptable regression is present.
- Stop if cost or latency exceeds the registered bound.
- Do not run holdout, do not update retained rules, and do not claim
  performance. Produce diagnostics only.

Dev pass branch:

- Preserve compact baseline and candidate artifacts.
- Generate `paired_comparison.json`, `regression_report.json`,
  `cost_latency_report.json`, and `acceptance_decision.json` under the dev
  acceptance scope.
- Re-run artifact boundary and paired comparison gates.
- Only then request holdout execution. Dev pass is not a full-suite or SOTA
  claim; it only authorizes the next holdout step.

## 5. Holdout and Full-Suite Templates

Holdout is allowed only after the dev paired comparison is positive and no
regression blocker is present.

Holdout baseline:

```bash
bash scripts/run_bfcl_v4_baseline.sh \
  gpt-4o-mini-2024-07-18-FC \
  outputs/bfcl_runs/holdout20/baseline/<run_id> \
  8100 \
  <test_category> \
  configs/runtime_bfcl_structured.yaml
```

Holdout candidate:

```bash
bash scripts/run_bfcl_v4_patch.sh \
  gpt-4o-mini-2024-07-18-FC \
  outputs/bfcl_runs/holdout20/candidate/<run_id> \
  8101 \
  <test_category> \
  configs/runtime_bfcl_structured.yaml \
  <candidate_rules_dir> \
  outputs/bfcl_runs/holdout20/candidate/<run_id>/traces \
  outputs/bfcl_runs/holdout20/candidate/<run_id>/artifacts \
  outputs/bfcl_runs/holdout20/baseline/<run_id>/artifacts/metrics.json
```

Full-suite baseline and candidate use the same templates with:

```text
outputs/bfcl_runs/full_suite/baseline/<run_id>
outputs/bfcl_runs/full_suite/candidate/<run_id>
```

and the Huawei-approved full-suite category/scope. Do not claim SOTA or +3pp
from dev-only evidence. If Huawei requires full-suite evidence, holdout evidence
can only propose the candidate for full-suite execution.

Fail-closed gates are the same as dev, plus the paired comparison gate below.

## 6. Paired Comparison Artifact Paths

Write the formal acceptance artifacts under:

```text
outputs/artifacts/stage1_bfcl_acceptance/
  paired_comparison.json
  acceptance_decision.json
  regression_report.json
  cost_latency_report.json
  performance_ready.json
  performance_ready.md
```

`paired_comparison.json` must point at the compact run roots:

```json
{
  "baseline_run_root": "outputs/bfcl_runs/<scope>/baseline/<run_id>",
  "candidate_run_root": "outputs/bfcl_runs/<scope>/candidate/<run_id>",
  "baseline_run_manifest_path": "outputs/bfcl_runs/<scope>/baseline/<run_id>/run_manifest.json",
  "candidate_run_manifest_path": "outputs/bfcl_runs/<scope>/candidate/<run_id>/run_manifest.json",
  "absolute_delta_pp": 3.0,
  "target_absolute_delta_pp": 3.0
}
```

Fail-closed paired comparison gate:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_paired_comparison.py \
  --acceptance-root outputs/artifacts/stage1_bfcl_acceptance \
  --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json \
  --compact --strict
```

This fails unless baseline and candidate manifests align, both compact run
schemas pass, provider green still passes, candidate accuracy is greater than
baseline, `absolute_delta_pp >= 3.0`, no regression blocker is present, and
cost/latency bounds pass.

## 7. Final Gates

Run these before any handoff:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_provider_green_preflight.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_m28pre_offline.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_paired_comparison.py --acceptance-root outputs/artifacts/stage1_bfcl_acceptance --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_stage1_bfcl_performance_ready.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_first_stage_bfcl_ready.py --compact --strict
```

Expected current behavior is fail-closed until provider credentials are valid,
M2.8-pre scorer authorization passes, paired baseline/candidate scorer artifacts
exist, and the formal +3pp/no-regression comparison is complete.
