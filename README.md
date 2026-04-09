# Golden Rule Compiler

BFCL-first Golden Rule Compiler MVP.

This repository keeps the official BFCL evaluation flow intact and adds an external OpenAI-compatible harness proxy plus a minimal compiler / selector loop.

## Scope of v1

v1 only does the following:

1. Proxy BFCL `chat.completions` requests to an upstream OpenAI-compatible endpoint.
2. Repair `tool_calls[].function.arguments` with a constrained argument sanitizer.
3. Record traces, mine failures, compile a YAML patch, and run a simple selector.

v1 intentionally does not:

1. Modify BFCL evaluator internals.
2. Do prompt evolution.
3. Search over multi-site patches.
4. Use a learned selector.

## Layout

```text
golden-rule-compiler/
├── pyproject.toml
├── README.md
├── .env.example
├── configs/
├── rules/
├── scripts/
├── src/grc/
└── outputs/
```

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Install BFCL separately:

```bash
bash scripts/install_bfcl.sh
```

Start the proxy:

```bash
source .venv/bin/activate
grc serve \
  --config configs/runtime.yaml \
  --rules-dir rules/active \
  --trace-dir outputs/traces/baseline
```

Run BFCL baseline:

```bash
bash scripts/run_bfcl_baseline.sh
```

Mine failures and compile a patch:

```bash
grc mine \
  --trace-dir outputs/traces/baseline \
  --out outputs/reports/failures.jsonl

grc compile \
  --failures outputs/reports/failures.jsonl \
  --out rules/active/001_arg_repair.yaml
```

Run the patched loop:

```bash
grc serve \
  --config configs/runtime.yaml \
  --rules-dir rules/active \
  --trace-dir outputs/traces/patch

bash scripts/run_bfcl_patch.sh
```

## Notes

- `configs/runtime.yaml` must be updated with your upstream endpoint before use.
- `outputs/` is kept in the repo so the directory structure exists, but generated artifacts are ignored by git.
- The current selector is intentionally simple and expects reduced metrics JSON inputs.

