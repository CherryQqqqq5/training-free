# BFCL One-ID Live Shape Telemetry After Tool Choice Patch Packet

Status: approved for exactly one after-patch one-ID live-shape telemetry execution. This does not authorize smoke, evaluate, scorer, full baseline, candidate, or performance paths.

## Scope

- Signed run ID: `web_search_base_0`
- Route: `novacode/gpt-4.1`
- Future output artifact: `outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_after_tool_choice_patch_compact.json`
- Previous artifact to preserve: `outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_compact.json`
- Patch state commit: `2d7d8059919f2eb019907eaeb8a2289223b26519`
- Post-patch request tool choice: `required_string`

## Non-Authorization

Only the scoped provider request, BFCL generate needed for live-shape telemetry, and live-shape telemetry are authorized. Smoke, evaluate, scorer, full baseline, candidate paths, performance evidence, +3pp, SOTA, and Huawei claims remain unauthorized.

## Boundary

A future execution must use the after-patch output path and must fail closed if that output already exists unless a separately approved clean-output policy is provided. The previous telemetry artifact must remain valid and untouched.
