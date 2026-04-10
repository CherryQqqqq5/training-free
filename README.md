# Golden Rule Compiler

BFCL-first Golden Rule Compiler Phase-1 scaffold.

This repository keeps the BFCL evaluator external, runs an OpenAI-compatible harness proxy, and compiles trace evidence into deterministic multi-site harness patches.

## Phase-1 Scope

Phase-1 now includes:

1. BFCL-first baseline and candidate runners with a pinned evaluator protocol.
2. Explicit compiler IR: `FailureTrace -> FailureIR -> RuleIR -> PatchBundle -> ValidationRecord`.
3. Deterministic multi-site runtime hooks across request-side prompt injection and response-side tool guard, argument sanitizer, verification hook, and fallback metadata.
4. Filesystem-backed candidate lifecycle under `rules/candidates/`, `rules/accepted/`, and `rules/rejected/`.
5. Standardized artifact outputs: `metrics.json`, `repairs.jsonl`, `failure_summary.json`, `accept.json`.

Phase-1 still does not:

1. Modify BFCL evaluator internals.
2. Search code-space harness candidates.
3. Use a learned proposer or selector.
4. Implement full Meta-Harness search over historical candidates.

## Docs

- Method: [docs/golden_rule_onepager.md](/Users/cherry/Documents/trainingfree/docs/golden_rule_onepager.md)
- Protocol: [docs/experiment_protocol_bfcl_v4.md](/Users/cherry/Documents/trainingfree/docs/experiment_protocol_bfcl_v4.md)

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Install BFCL and copy the pinned protocol env:

```bash
bash scripts/install_bfcl.sh
```

Set your upstream endpoint in `configs/runtime.yaml`, then run the Phase-1 baseline:

```bash
bash scripts/run_bfcl_v4_baseline.sh
```

Run the pre-BFCL smoke first if you want to verify proxy, upstream connectivity, trace shape, and aggregator discovery without launching a full benchmark:

```bash
export GRC_UPSTREAM_BASE_URL="https://your-endpoint.example/v1"
bash scripts/run_phase1_smoke.sh
```

Compile a candidate from the baseline traces:

```bash
grc mine \
  --trace-dir outputs/bfcl_v4/baseline/traces \
  --out outputs/reports/failures.jsonl

grc compile \
  --failures outputs/reports/failures.jsonl \
  --out rules/candidates/patch_auto_001/rule.yaml \
  --patch-id patch_auto_001 \
  --candidate-dir rules/candidates/patch_auto_001
```

Run the candidate and aggregate its artifacts into the candidate directory:

```bash
bash scripts/run_bfcl_v4_patch.sh \
  gpt-4o-2024-11-20-FC \
  outputs/bfcl_v4/patch \
  8012 \
  "" \
  configs/runtime.yaml \
  rules/candidates/patch_auto_001 \
  outputs/bfcl_v4/patch/traces \
  rules/candidates/patch_auto_001 \
  outputs/bfcl_v4/baseline/artifacts/metrics.json
```

Or run the full Phase-1 ablation loop:

```bash
bash scripts/run_phase1_ablation.sh
```

## Layout

- `configs/bfcl_v4_phase1.env`: pinned evaluator/model protocol
- `rules/baseline_empty/`: enforced empty rule set for clean baseline runs
- `rules/seeds/`: tracked seed rules
- `rules/candidates/`: per-candidate evidence directories
- `rules/accepted/`: selector-approved rules
- `rules/rejected/`: selector-rejected rules
- `outputs/artifacts/phase1/`: tracked artifact templates

## Notes

- `configs/runtime.yaml` still requires a real upstream endpoint and API key env var.
- `GRC_UPSTREAM_BASE_URL` can override `configs/runtime.yaml`, so the repo no longer requires editing tracked config just to point at an endpoint.
- The BFCL runner omits `--test-category` by default so the evaluator can run its default full-suite selection.
- `scripts/aggregate_bfcl_metrics.py` uses heuristic BFCL metric discovery because evaluator output filenames can vary across installs.
