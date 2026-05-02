# BFCL One-ID Live Shape Telemetry After Tool Choice Patch Packet

Status: pending and fail-closed. This prepares a future rerun only; it does not authorize execution.

## Scope

- Signed run ID: `web_search_base_0`
- Route: `novacode/gpt-4.1`
- Future output artifact: `outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_after_tool_choice_patch_compact.json`
- Previous artifact to preserve: `outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_compact.json`
- Patch state commit: `2d7d8059919f2eb019907eaeb8a2289223b26519`
- Post-patch request tool choice: `required_string`

## Non-Authorization

Provider request, live telemetry, BFCL generate, smoke, evaluate, scorer, full baseline, candidate paths, performance evidence, +3pp, SOTA, and Huawei claims remain unauthorized until a separate manager execution authorization flips the packet state or provides an explicit approved packet.

## Boundary

A future execution must use the after-patch output path and must fail closed if that output already exists unless a separately approved clean-output policy is provided. The previous telemetry artifact must remain valid and untouched.
