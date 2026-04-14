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

- Conda + OpenRouter setup: [docs/setup_conda_openrouter.md](docs/setup_conda_openrouter.md)
- Method: [docs/golden_rule_onepager.md](docs/golden_rule_onepager.md) (includes roadmap ↔ IR field map)
- Failure taxonomy: [docs/failure_taxonomy.md](docs/failure_taxonomy.md) (`error_type` / issue `kind` vocabulary)
- Protocol: [docs/experiment_protocol_bfcl_v4.md](docs/experiment_protocol_bfcl_v4.md)

## Quickstart

**Conda + OpenRouter only** (typical lab server): follow [docs/setup_conda_openrouter.md](docs/setup_conda_openrouter.md) in order—`conda activate tf`, `pip install -e .` + `bfcl-eval`, `bash scripts/init_bfcl_project_root.sh`, then `source configs/bfcl_v4_phase1.env` and `source configs/bfcl_v4_openrouter.env`, export `OPENROUTER_API_KEY` (and referer), run `run_phase1_smoke.sh` then baseline.

**venv workflow** (local machine):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
bash scripts/install_bfcl.sh
```

For conda, skip `install_bfcl.sh` (it creates a conflicting `.venv`) and use `init_bfcl_project_root.sh` after installing deps.

Default upstream profile is **OpenRouter** (`configs/runtime.yaml`, `configs/bfcl_v4_phase1.env`). For Novacode:

```bash
export GRC_UPSTREAM_PROFILE=novacode
export NOVACODE_BASE_URL="https://your-novacode-endpoint/v1"
export NOVACODE_API_KEY="..."
```

Run the Phase-1 baseline (model id must match your OpenRouter model when using OpenRouter):

```bash
source configs/bfcl_v4_phase1.env
source configs/bfcl_v4_openrouter.env
export OPENROUTER_API_KEY="..."
export OPENROUTER_HTTP_REFERER="https://your-lab.example"
bash scripts/run_bfcl_v4_baseline.sh "${GRC_UPSTREAM_MODEL}"
```

Pre-BFCL smoke (proxy + upstream + trace shape):

```bash
source configs/bfcl_v4_phase1.env
source configs/bfcl_v4_openrouter.env
export OPENROUTER_API_KEY="..."
export OPENROUTER_HTTP_REFERER="https://your-lab.example"
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
  "${GRC_UPSTREAM_MODEL}" \
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
- `GRC_UPSTREAM_PROFILE=openrouter|novacode` selects a relay preset; default is `openrouter` (`grok-3`); `novacode` defaults to `gpt-5.4`.
- The BFCL runner omits `--test-category` by default so the evaluator can run its default full-suite selection.
- `--run-ids` is now opt-in via `GRC_BFCL_USE_RUN_IDS=1`; default runs no longer implicitly depend on `test_case_ids_to_generate.json`.
- `scripts/aggregate_bfcl_metrics.py` uses heuristic BFCL metric discovery because evaluator output filenames can vary across installs.
