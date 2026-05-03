# BFCL Measurement Readiness Gate

Status: pending and fail-closed. This packet does not authorize provider calls, BFCL generate/evaluate, scorer, baseline, candidates, or performance claims.

## Frozen Target

- Frozen target commit: `1c52d67151c8cc917144c413cdfa1912db0ef67b`
- Route: `novacode/gpt-4.1`
- Fallback/OpenRouter: disabled
- `gpt-5.2`: historical/superseded only
- Candidates: inert, not activated

The packet includes an explicit justification allowing a later gate-artifact-only commit to follow this frozen target without changing behavior or authorizing execution.

## Protocol Snapshot

- Evaluator package: `bfcl-eval==2025.12.17`
- BFCL evaluator checkout: `f7cf735`
- BFCL version: `v4`
- BFCL data version: pinned by evaluator checkout
- BFCL model alias: `gpt-4o-mini-2024-07-18-FC`
- Config files: `configs/bfcl_eval_protocol.yaml`, `configs/runtime_bfcl_structured.yaml`, `configs/runtime.yaml`, `configs/bfcl_v4_phase1.env`

## Evidence Boundary

The exact 8-ID after-classifier generate-only smoke passed, but this is readiness evidence only. It is not BFCL measurement evidence and is not performance or +3pp evidence.

## Future Stop Gates

Future measurement execution must stop on route drift, missing manifest, raw/secret leak, candidate activation, scorer-feedback contamination, output boundary failure, fallback/OpenRouter activation, or active `gpt-5.2` route.

Only compact manifests and metrics may be committed. Raw prompts, BFCL cases, provider payloads, logs, traces, result trees, endpoint/key values, scorer diffs, and candidate outputs remain forbidden.
