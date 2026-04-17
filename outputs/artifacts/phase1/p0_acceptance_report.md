# P0 Acceptance Report

Date: 2026-04-16

## Scope

This report checks whether Phase-1 P0 is actually closed in the current repository checkout.

The acceptance question is split into two separate claims:

- `P0 implementation`: the mining/runtime taxonomy cleanup is present in code and covered by tests.
- `P0 evidence closure`: the repository still contains enough run artifacts to re-verify the documented P0 conclusions.

## Verification Steps

The following checks were run in the current workspace:

- inspected the tracked Phase-1 status claims in [README.md](/Users/cherry/Documents/trainingfree/README.md:21)
- inspected the canonical taxonomy in [docs/failure_taxonomy.md](/Users/cherry/Documents/trainingfree/docs/failure_taxonomy.md:1)
- inspected runtime classification in [src/grc/runtime/engine.py](/Users/cherry/Documents/trainingfree/src/grc/runtime/engine.py:28)
- inspected mined-failure logic in [src/grc/compiler/mine.py](/Users/cherry/Documents/trainingfree/src/grc/compiler/mine.py:113)
- inspected patch compilation behavior in [src/grc/compiler/trace_to_patch.py](/Users/cherry/Documents/trainingfree/src/grc/compiler/trace_to_patch.py:206)
- ran `PYTHONPATH=src:. pytest -q tests/test_runtime_engine.py tests/test_mine_failures.py tests/test_selector_pareto.py tests/test_aggregate_bfcl_metrics.py`

Result:

- `27 passed in 0.10s`

## Findings

### 1. P0 classification logic is implemented

The current runtime no-tool path classifies:

- `clarification_request`
- `unsupported_request`
- `hallucinated_completion`
- `malformed_output`
- `natural_language_termination`
- residual `empty_tool_call`

Evidence:

- runtime record-only policy for these classes is present in [src/grc/runtime/engine.py](/Users/cherry/Documents/trainingfree/src/grc/runtime/engine.py:32)
- no-tool classification is applied in [src/grc/runtime/engine.py](/Users/cherry/Documents/trainingfree/src/grc/runtime/engine.py:218)
- miner deduplicates stale validation echo and keeps refined no-tool kinds in [src/grc/compiler/mine.py](/Users/cherry/Documents/trainingfree/src/grc/compiler/mine.py:149) and [src/grc/compiler/mine.py](/Users/cherry/Documents/trainingfree/src/grc/compiler/mine.py:258)
- runtime tests cover `unsupported_request`, `malformed_output`, `hallucinated_completion`, `clarification_request`, and true `empty_tool_call` in [tests/test_runtime_engine.py](/Users/cherry/Documents/trainingfree/tests/test_runtime_engine.py:23)

Verdict:

- `P0 implementation` is present.

### 2. The repository does not contain the raw artifacts needed to re-verify the documented P0 snapshot

README states that the key P0 snapshot comes from `outputs/bfcl_v4/baseline/multi_turn_miss_param/traces` and lists 4 residual failures there, see [README.md](/Users/cherry/Documents/trainingfree/README.md:43).

In the current checkout:

- `outputs/bfcl_v4/baseline/multi_turn_miss_param/` contains only `artifacts/`
- `outputs/bfcl_v4/baseline/multi_turn_miss_param/traces/` does not exist
- baseline roots for `simple_python`, `multiple`, and `parallel_multiple` do not exist under `outputs/bfcl_v4/baseline/`

Additional mismatch:

- [outputs/bfcl_v4/baseline/multi_turn_miss_param/artifacts/metrics.json](/Users/cherry/Documents/trainingfree/outputs/bfcl_v4/baseline/multi_turn_miss_param/artifacts/metrics.json:25) references 8 `metric_sources`
- all 8 referenced paths are absent in the current checkout
- [outputs/bfcl_v4/baseline/multi_turn_miss_param/artifacts/metrics.json](/Users/cherry/Documents/trainingfree/outputs/bfcl_v4/baseline/multi_turn_miss_param/artifacts/metrics.json:36) also points to a non-existent `trace_dir`

Verdict:

- the documented P0 snapshot is not reproducible from the current repository contents alone.

### 3. Existing patch artifacts are metadata-only and not backed by trace files

For all three current patch subsets:

- `outputs/bfcl_v4/patch/simple_python/traces/`
- `outputs/bfcl_v4/patch/multiple/traces/`
- `outputs/bfcl_v4/patch/parallel_multiple/traces/`

the directories exist but contain `0` trace files.

At the same time, the tracked `failure_summary.json` files claim non-zero `trace_count`:

- [outputs/bfcl_v4/patch/simple_python/artifacts/failure_summary.json](/Users/cherry/Documents/trainingfree/outputs/bfcl_v4/patch/simple_python/artifacts/failure_summary.json:2) says `400`
- [outputs/bfcl_v4/patch/multiple/artifacts/failure_summary.json](/Users/cherry/Documents/trainingfree/outputs/bfcl_v4/patch/multiple/artifacts/failure_summary.json:2) says `200`
- [outputs/bfcl_v4/patch/parallel_multiple/artifacts/failure_summary.json](/Users/cherry/Documents/trainingfree/outputs/bfcl_v4/patch/parallel_multiple/artifacts/failure_summary.json:2) says `200`

This means the current repo preserves summary metadata without the underlying trace evidence.

Verdict:

- current tracked run artifacts are insufficient for P0 auditability.

### 4. Candidate patches are empty, and selector output already marks them invalid

Each current candidate rule file is empty:

- [rules/candidates/patch_simple_python_001/rule.yaml](/Users/cherry/Documents/trainingfree/rules/candidates/patch_simple_python_001/rule.yaml:1)
- [rules/candidates/patch_multiple_001/rule.yaml](/Users/cherry/Documents/trainingfree/rules/candidates/patch_multiple_001/rule.yaml:1)
- [rules/candidates/patch_parallel_multiple_001/rule.yaml](/Users/cherry/Documents/trainingfree/rules/candidates/patch_parallel_multiple_001/rule.yaml:1)

They all contain:

- `rules: []`
- `failure_ir: []`
- `source_failure_count: 0`

Selector output explicitly blocks them as invalid. Example:

- [rules/candidates/patch_simple_python_001/accept.json](/Users/cherry/Documents/trainingfree/rules/candidates/patch_simple_python_001/accept.json:61) lists `source_failure_count <= 0` and `rules empty`

This matches current compiler behavior:

- `compile_patch` will happily emit an empty `PatchBundle` when the mined failure file is empty, see [src/grc/compiler/trace_to_patch.py](/Users/cherry/Documents/trainingfree/src/grc/compiler/trace_to_patch.py:212)

Verdict:

- Phase-1 has no accepted evidence yet that P0 mining is producing non-empty candidate patches in the tracked artifacts.

### 5. There is a tooling gap that can mask missing evidence as "zero failures"

`mine_failures()` iterates over `Path(trace_dir).glob("*.json")` without validating that `trace_dir` exists, see [src/grc/compiler/mine.py](/Users/cherry/Documents/trainingfree/src/grc/compiler/mine.py:113).

Operational consequence:

- a missing trace directory produces an empty iterator
- the CLI still writes a valid-looking `0`-line failure JSONL
- that empty failure file can then compile into an empty patch bundle

This does not invalidate the taxonomy implementation, but it does invalidate naive acceptance based only on "mine completed successfully".

Verdict:

- missing raw evidence can currently be mistaken for a clean run.

## Acceptance Decision

Current decision for this checkout:

- `P0 implementation`: yes
- `P0 evidence closure`: no
- `P0 formally accepted`: no
- `P1 implementation may start`: yes, but only with the evidence gap called out explicitly

## Required Closure Items

P0 should be considered fully accepted only after these are done:

- restore or rerun `outputs/bfcl_v4/baseline/multi_turn_miss_param/traces/`
- rerun mining on that baseline and confirm the residual no-tool taxonomy directly from raw traces
- restore or rerun baseline artifacts for `simple_python`, `multiple`, and `parallel_multiple`
- rerun the same taxonomy pass on those three subsets
- reject silent success on missing `trace_dir` in the mining path so future "0 failures" results are trustworthy

## Practical Recommendation

The repository is ready to move into P1 implementation work, but not ready to claim that P0 is fully closed.

The safe project statement is:

- P0 taxonomy cleanup is implemented and test-covered
- P0 artifact-based acceptance is still incomplete in the current checkout
- P1 should proceed together with a small evidence-restoration task or a stricter mining preflight check
