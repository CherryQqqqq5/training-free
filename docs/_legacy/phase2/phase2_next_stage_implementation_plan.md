# Phase-2 Next Stage Implementation Plan

## Goal

Implement the next formal Phase-2 target:

> On `multi_turn_miss_param`, turn the current effective patch line into a minimal runnable policy-evolution loop, and prove its safety boundary on `simple_python`.

This phase must stop being framed as "optimize BFCL score" and instead produce a reproducible loop:

```text
run -> trace -> classify by (stage,type) -> mine signatures -> retrieve history
-> generate fresh/reuse/specialize candidates -> evaluate target + holdout
-> select accepted/retained/rejected -> update history -> next iteration
```

## Current State

Implemented already:

- `src/grc/compiler/failure_taxonomy.py`
  - `FailureStage`: `PRE_TOOL`, `MID_TOOL`, `POST_TOOL`
  - `FailureType`: `EMPTY_TOOL_CALL`, `ACTIONABLE_NO_TOOL_DECISION`, `POST_TOOL_PROSE_SUMMARY`, `TERMINATION_INADMISSIBLE`, `MALFORMED_CALL`, `ARG_UNDERSPECIFIED`, `CLARIFICATION_REQUEST`, `UNSUPPORTED_REQUEST`
  - predicates: `has_sufficient_literals`, `tool_output_sufficient`, `is_clarification`
- `src/grc/compiler/mine.py`
  - emits legacy `error_type` plus taxonomy fields on `FailureCase`
- `scripts/summarize_failure_taxonomy.py`
  - emits Table A style `(stage,type)` distribution and Top-3 families for one or more trace dirs
- `scripts/analyze_repair_contribution.py`
  - emits repair records and coverage/success/ablation-gain summaries
- `src/grc/compiler/trace_to_patch.py`
  - emits `policy_unit.yaml` for decision-layer policy rules
- `src/grc/selector/history.py`
  - supports history append/load/query/retrieve
- `src/grc/selector/pareto.py`
  - writes `history.jsonl` next to candidate output and uses `selection_score`
- Existing orchestration references:
  - `scripts/run_phase1_ablation.sh` already shows the baseline -> patch -> paired rerun -> assess -> select pattern.
  - `scripts/run_phase1_four_subset_e2e.sh` already shows the multi-slice loop including `simple_python`.
  - `scripts/assess_paired_rerun.py` already implements paired-rerun consistency and should be reused.

Server artifact reality from read-only inspection:

- Present:
  - `/cephfs/qiuyn/training-free/outputs/phase1_checks/multi_turn_miss_param`
  - `/cephfs/qiuyn/training-free/outputs/phase1_checks/simple_python`
  - `/cephfs/qiuyn/training-free/outputs/phase2_runs/multi_turn_miss_param_primary_v4`
- Not found at the expected path during inspection:
  - `/cephfs/qiuyn/training-free/outputs/phase2_runs/multi_turn_miss_param_rerun_v4`

Do not hard-code `rerun_v4` as present. Add path discovery and fail clearly if an expected run root is missing.

Checked-in local `outputs/` fixtures are not authoritative for Phase-2 verification because they may be stale and missing `run_manifest.json`. Use server artifacts or explicit run roots.

## Execution Status Update (2026-04-23)

Current server run: `/cephfs/qiuyn/training-free/outputs/phase2_evolution/iter_004_execute`.

- Minimal execute mode is no longer only a dry-run path for the current-server experiment: it selected executable proposal `fresh_02` and completed both target and holdout BFCL commands.
- Target `multi_turn_miss_param`: `42.0%` (`84 / 200`), `+5.5 pp` over baseline and `+2.0 pp` over `primary_v4`.
- Holdout `simple_python`: `95.0%` (`380 / 400`), matching baseline and showing no measured holdout regression in this run.
- Paired rerun is still active, so selector acceptance, history update, and `evolution_iteration_summary.json` remain pending.
- The current run should be treated as evidence that the execute path can run target + holdout, not yet as a completed evolution-loop claim.

## Implementation Changes

### 1. Make Taxonomy The First Analysis Axis

Add a reporting script:

- New file: `scripts/build_phase2_taxonomy_report.py`

Inputs:

- `--run LABEL=TRACE_DIR` repeated
- `--metrics LABEL=METRICS_JSON` repeated, optional
- `--out-json PATH`
- `--out-md PATH`
- `--require-runs baseline,primary_v4` defaulting to these two initially
- `--optional-run rerun_v4=TRACE_DIR` for run roots that may not exist yet

Behavior:

- Use `mine_failures(trace_dir)` and `failure.failure_label` as the primary key.
- Emit:
  - Table A: rows `run`, `accuracy`, `correct_count`, `failure_label`, `count`, `share`
  - Top-3 failure families per run
  - delta table versus baseline for every shared `failure_label`
  - merged comparison table keyed by `failure_label`, with count/share columns side-by-side per run
  - largest decreases and largest increases versus baseline
- Group every `failure_label` into:
  - `decision_layer_target`: any type in `ACTIONABLE_NO_TOOL_DECISION`, `POST_TOOL_PROSE_SUMMARY`, `TERMINATION_INADMISSIBLE`
  - `compatibility_heavy`: any type in `MALFORMED_CALL`, `ARG_UNDERSPECIFIED`, `EMPTY_TOOL_CALL`
  - `allowed_boundary`: any type in `CLARIFICATION_REQUEST`, `UNSUPPORTED_REQUEST`

Important boundary rule:

- If a clarification-like failure has `prior_explicit_literals_present=true`, classify/report it as boundary misuse and route it into decision-layer analysis rather than treating it as "allowed".

Implementation details:

- Do not remove `scripts/summarize_failure_taxonomy.py`; `build_phase2_taxonomy_report.py` should reuse its logic or call `mine_failures` directly.
- Add helper functions in a small module if needed:
  - `src/grc/compiler/failure_groups.py`
  - `group_failure_label(label, predicate_evidence=None) -> str`

Tests:

- Add `tests/test_phase2_taxonomy_report.py`.
- Fixture should include three synthetic runs and verify:
  - Table A uses `failure_label`, not raw `error_type`
  - Top-3 families are stable
  - clarification with explicit literal evidence is reported as boundary misuse
  - missing optional `rerun_v4` is reported as skipped rather than silently assumed

### 2. Add Failure Signature Mining

Add a dedicated signature layer:

- New file: `src/grc/compiler/failure_signature.py`

Define:

```python
class FailureSignature(BaseModel):
    stage: str
    type: str
    tool_schema_hash: str
    literals_pattern: str
```

Also define:

```python
class SignatureSummary(BaseModel):
    signature: FailureSignature
    count: int
    share: float
    failure_labels: list[str]
```

Functions:

- `tool_schema_hash(tool_schema_snapshot) -> str`
  - stable SHA256 prefix over sorted JSON
  - use `"*"` when no schema is available
- `literals_pattern(failure_case) -> str`
  - `explicit_context_literals` when `request_literals` exists
  - `prior_tool_outputs` when `prior_tool_outputs_present`
  - `no_explicit_literals` otherwise
- `signature_from_failure(failure_case, trace_payload=None) -> FailureSignature`
- `top_k_signatures(failures, k=5) -> list[SignatureSummary]`

Wire this into:

- `src/grc/compiler/trace_to_patch.py`
  - replace placeholder `tool_schema_hash="*"` and ad hoc literals pattern where trace data is unavailable
  - keep safe fallback to `"*"` for existing JSONL-only compile path
- `scripts/build_phase2_taxonomy_report.py`
  - emit `top_failure_signatures`
- `src/grc/selector/history.py`
  - retrieval should score full signatures, not only exact `stage`/`type`

Tests:

- Add `tests/test_failure_signature.py`.
- Cover deterministic hash, literal patterns, and Top-k aggregation.

### 3. Repair Attribution By Failure Family

Improve `scripts/analyze_repair_contribution.py` into a family-first report.

New CLI options:

- `--score-json PATH`
  - optional BFCL score/result file used to build `case_id -> final_success`
- `--result-json PATH`
  - optional fallback source for case success
- `--out-md PATH`

Output additions:

- `repair_by_family` table:
  - `failure_label`
  - `repair`
  - `repair_class`: `compatibility`, `decision_adjacent`, or `unknown`
  - `coverage`
  - `success`
  - `attribution_gain`
- `family_summary`:
  - total failures by family
  - compatibility repair coverage
  - decision-adjacent repair coverage
  - unknown repair coverage
- Built-in repair classes:
  - compatibility: `resolve_contextual_string_arg`, `repair_json`, `coerce_types`, `drop_unknown_key`, `fill_default`, `arguments_changed`
  - decision_adjacent: `coerce_no_tool_text_to_empty`, termination/no-tool coercions

Important interpretation rule:

- The script should not claim repair as the final algorithm contribution.
- It should explicitly separate compatibility gains from decision-policy gains.

Tests:

- Extend `tests/test_repair_attribution.py`.
- Verify per-family coverage/success and repair class assignment.
- Add one case proving `coerce_no_tool_text_to_empty` is counted separately on `POST_TOOL_PROSE_SUMMARY` versus `ACTIONABLE_NO_TOOL_DECISION`.
- Add one case proving `resolve_contextual_string_arg` is compatibility-heavy, not decision-layer gain.

### 4. Policy Proposal Generator

Add the missing bridge from history to compile.

New file:

- `src/grc/compiler/policy_proposal.py`

Inputs:

- current failures or top signatures
- history path
- candidate output root
- optional run metadata:
  - `target_category`, default `multi_turn_miss_param`
  - `holdout_category`, default `simple_python`
  - `iteration_id`

Outputs:

- multiple proposal directories:
  - `fresh/`
  - `reuse_<fingerprint>/`
  - `specialize_<fingerprint>/`

Functions:

- `generate_fresh(failures) -> PolicyProposal`
  - current behavior: compile from failure evidence
- `generate_reuse(signature, history_records) -> PolicyProposal`
  - rehydrate compatible historical `policy_unit`
  - no benchmark IDs or trace IDs in generated policy
- `generate_specialize(signature, history_records, current_predicates) -> PolicyProposal`
  - if current predicates are stricter than historical predicates, add the narrower predicate set
  - preserve `continue_condition`, `stop_condition`, `forbidden_terminations`, `evidence_requirements`
- `proposal_metadata`
  - include `proposal_mode`: `fresh`, `reuse`, or `specialize`
  - include `source_history_fingerprint` for reuse/specialize
  - include `reuse_source_patch_id` when the source has a patch id
  - include `failure_signature`
  - include `target_category`
  - include `holdout_category`

Do not implement mutation search in this stage. Mutation remains future work.

History schema upgrades:

- `proposal_kind`: `fresh`, `reuse`, `specialize`, `mutate`
- `reuse_source_patch_id`
- `reuse_source_fingerprint`
- `subset_family`: target slice or holdout slice family
- `regression_profile`: holdout deltas and clean-slice status
- `compile_status`: `ok`, `compile_failed`, `incomplete`, `rejected_before_eval`
- `reusable_for_search`: false for compile-failed or incomplete proposals

Retrieval scoring:

- Require exact match on `stage` and `type`.
- Add positive weights for:
  - exact `tool_schema_hash`
  - compatible `literals_pattern`
  - request predicate overlap
  - policy fingerprint overlap
- Return:
  - `match_score`
  - `match_reasons`
  - `matched_fields`

Rejected, incomplete, and compile-failed candidates should still be recorded in history for auditability, but must not be reusable unless explicitly marked safe.

Wire this into a new CLI command:

- `grc propose`

Arguments:

- `--failures PATH`
- `--history PATH`
- `--out-dir PATH`
- `--top-k-signatures 3`
- `--target-category multi_turn_miss_param`
- `--holdout-category simple_python`

Behavior:

- Mine top signatures from failure JSONL.
- Query history for each signature.
- Always emit one fresh proposal.
- Emit reuse/specialize only for history records with `reusable_for_search=true`.

Tests:

- Add `tests/test_policy_proposal.py`.
- Verify:
  - fresh proposal is always generated
  - reuse proposal only appears when `reusable_for_search=true`
  - specialize narrows request predicates and does not add benchmark IDs
  - retrieval reports `match_score` and `match_reasons`
  - compile-failed history records are auditable but not reused
  - fresh candidate exists without history
  - retained history record creates reuse proposal
  - narrower predicates create specialize proposal
  - rejected/non-reusable history is ignored

### 5. Minimal Evolution Iteration Runner

Add an orchestration script, not a giant framework:

- New file: `scripts/run_phase2_evolution_iteration.py`

Inputs:

- `--repo-root`
- `--target-category multi_turn_miss_param`
- `--holdout-category simple_python`
- `--baseline-run-root`
- `--target-run-root`
- `--holdout-run-root`
- `--history PATH`
- `--out-root PATH`
- `--dry-run`

Responsibilities:

1. Verify required existing roots exist.
2. Run or reuse taxonomy report:
   - baseline
   - current target candidate
   - optional rerun if discovered
3. Run `grc mine` on target traces to produce failures JSONL.
4. Run `grc propose` to generate fresh/reuse/specialize candidate dirs.
5. Print exact BFCL commands for each candidate if `--dry-run`.
6. If not dry-run, execute:
   - target candidate run on `multi_turn_miss_param`
   - holdout run on `simple_python`
7. Run selector for each evaluated candidate.
8. Append history via existing selector output.
9. Emit `evolution_iteration_summary.json` and `.md`.

Reuse existing scripts rather than inventing a separate harness:

- `scripts/run_bfcl_v4_baseline.sh`
- `scripts/run_bfcl_v4_patch.sh`
- `scripts/assess_paired_rerun.py`
- `grc select`
- `scripts/write_run_manifest.py`

The runner should construct these commands and record them in the summary even in dry-run mode.

Optional run discovery:

- Add `--optional-rerun-root LABEL=PATH`.
- Add `--allow-missing-rerun`.
- If an optional rerun is missing and `--allow-missing-rerun` is set, report it as `skipped_missing` in the summary.
- If an optional rerun is marked required, fail before candidate generation.

Safety defaults:

- Default to `--dry-run`.
- Do not remove existing run roots.
- Require explicit `--execute` to run BFCL.
- Never run more than one target candidate by default; use `--max-candidates`.
- Executable mode must require a holdout run root and must include `simple_python` or another explicitly named clean holdout.
- Executable mode must refuse to run if the holdout command cannot be constructed.

Iteration summary fields:

- `failure_rate_by_label`
- `top_failure_signatures`
- `proposal_count_by_mode`
- `history_reuse_count`
- `new_policy_count`
- `accepted_count`
- `retained_count`
- `rejected_count`
- `target_delta`
- `holdout_delta`
- `clean_slice_regression`
- `planned_commands`

Tests:

- Add `tests/test_phase2_evolution_iteration.py`.
- Use fixture directories and `--dry-run`.
- Verify it refuses missing run roots and emits deterministic planned commands.
- Verify it refuses executable mode without a holdout root.
- Verify missing optional `rerun_v4` is reported as skipped when `--allow-missing-rerun` is set.
- Verify planned commands include `run_bfcl_v4_patch.sh`, `assess_paired_rerun.py`, and `grc select`.

### 6. Experiment Protocol For This Stage

Required first report:

```bash
PYTHONPATH=src python scripts/build_phase2_taxonomy_report.py \
  --run baseline=/cephfs/qiuyn/training-free/outputs/phase1_checks/multi_turn_miss_param/traces \
  --run primary_v4=/cephfs/qiuyn/training-free/outputs/phase2_runs/multi_turn_miss_param_primary_v4/traces \
  --metrics baseline=/cephfs/qiuyn/training-free/outputs/phase1_checks/multi_turn_miss_param/artifacts/metrics.json \
  --metrics primary_v4=/cephfs/qiuyn/training-free/outputs/phase2_runs/multi_turn_miss_param_primary_v4/artifacts/metrics.json \
  --out-json outputs/phase2_analysis/taxonomy_table_a.json \
  --out-md outputs/phase2_analysis/taxonomy_table_a.md
```

If `rerun_v4` is found later, add:

```bash
--run rerun_v4=<rerun_trace_dir> \
--metrics rerun_v4=<rerun_metrics_json>
```

Rerun path discovery should be explicit:

```bash
find /cephfs/qiuyn/training-free/outputs/phase2_runs \
  -maxdepth 2 -type f -path '*/artifacts/metrics.json' \
  | sort \
  | grep 'multi_turn_miss_param.*v4'
```

Required first dry-run loop:

```bash
PYTHONPATH=src python scripts/run_phase2_evolution_iteration.py \
  --repo-root /cephfs/qiuyn/training-free \
  --target-category multi_turn_miss_param \
  --holdout-category simple_python \
  --baseline-run-root /cephfs/qiuyn/training-free/outputs/phase1_checks/multi_turn_miss_param \
  --target-run-root /cephfs/qiuyn/training-free/outputs/phase2_runs/multi_turn_miss_param_primary_v4 \
  --holdout-run-root /cephfs/qiuyn/training-free/outputs/phase1_checks/simple_python \
  --history /cephfs/qiuyn/training-free/rules/candidates/history.jsonl \
  --out-root /cephfs/qiuyn/training-free/outputs/phase2_evolution/iter_001 \
  --dry-run
```

Only after dry-run output is reviewed should `--execute` be used.

## Verification

Local tests:

```bash
PYTHONPATH=src python -m pytest \
  tests/test_failure_taxonomy.py \
  tests/test_failure_signature.py \
  tests/test_phase2_taxonomy_report.py \
  tests/test_repair_attribution.py \
  tests/test_policy_proposal.py \
  tests/test_phase2_evolution_iteration.py \
  tests/test_trace_to_patch.py \
  tests/test_selector_pareto.py
```

Full tests:

```bash
PYTHONPATH=src python -m pytest
```

Targeted script tests:

```bash
PYTHONPATH=src python -m pytest \
  tests/test_write_run_manifest.py \
  tests/test_assess_paired_rerun.py
```

Server smoke:

```bash
cd /cephfs/qiuyn/training-free
source .venv/bin/activate
PYTHONPATH=src python scripts/build_phase2_taxonomy_report.py \
  --run baseline=outputs/phase1_checks/multi_turn_miss_param/traces \
  --run primary_v4=outputs/phase2_runs/multi_turn_miss_param_primary_v4/traces \
  --metrics baseline=outputs/phase1_checks/multi_turn_miss_param/artifacts/metrics.json \
  --metrics primary_v4=outputs/phase2_runs/multi_turn_miss_param_primary_v4/artifacts/metrics.json \
  --out-json outputs/phase2_analysis/taxonomy_table_a.json \
  --out-md outputs/phase2_analysis/taxonomy_table_a.md
```

Acceptance criteria:

- All reports use `failure_label=(stage,type)` as the primary key.
- Top-3 failure families are reported for baseline and primary candidate.
- Repair attribution is broken down by failure family and repair class.
- `grc propose` emits at least one fresh proposal and demonstrably uses retained/accepted history when present.
- History retrieval is on the candidate-generation path, not only in tests.
- Dry-run evolution iteration emits commands and refuses missing roots.
- Dry-run summary reports failure rate by `(stage,type)`, policy reuse count, new proposal count, retained count, and clean-slice regression fields.
- No BFCL case IDs, hard-coded filenames, or benchmark-specific sample names appear in generated policies.
- `simple_python` is always included as a safety holdout in executable loop mode.

## Out Of Scope For This Stage

- Mutation search.
- Embedding-based retrieval.
- Learned selector.
- Claiming final algorithmic gain from repairs alone.
- Running full BFCL automatically before taxonomy report and dry-run loop are reviewed.
