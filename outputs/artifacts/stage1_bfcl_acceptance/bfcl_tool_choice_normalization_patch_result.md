# BFCL Tool Choice Normalization Patch Result

Status: completed for offline behavior patch only.

## Patch

- Name: `bfcl_measurement_responses_to_chat_tool_choice_normalization`
- Kind: `proxy_normalization`
- Target scope: `bfcl_measurement_generate_path_only`
- Condition: `tools_present_and_tool_choice_missing_or_none`
- Normalized value: `required`
- Code paths touched: `src/grc/runtime/proxy.py`, `configs/runtime_bfcl_structured.yaml`

## Boundary

This result does not authorize provider requests, live telemetry, BFCL generate/smoke/evaluate, scorer, full baseline, candidate activation, candidate JSONL/pool, performance evidence, +3pp, SOTA, or Huawei claims.
