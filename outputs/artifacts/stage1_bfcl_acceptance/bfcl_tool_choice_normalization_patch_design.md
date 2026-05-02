# BFCL Tool Choice Normalization Patch Design

This is a prep-only design for a future minimal offline patch. It does not modify proxy/runtime behavior.

## Proposed Patch

- Name: `bfcl_measurement_responses_to_chat_tool_choice_normalization`
- Kind: `proxy_normalization`
- Target scope: `bfcl_measurement_generate_path_only`
- Condition: `tools_present_and_tool_choice_missing_or_none`
- Normalized value: `required`

## Intended Boundary

The future patch should only affect the BFCL measurement/generate Responses-to-chat normalization path. It must not authorize or affect candidate activation, scorer, baseline, performance reporting, or general runtime behavior unless separately reviewed.

## Rollback

Revert the future behavior patch commit, rerun the no-provider request tool-choice debug checker, and rerun route plus artifact-boundary gates.

## Required Offline Tests

- Missing tool choice with tools normalizes to `required` in the BFCL measurement path.
- Explicit `none` tool choice with tools normalizes to `required` in the BFCL measurement path.
- Tools absent does not normalize.
- Existing explicit `required` or function-object choice is preserved.
- Non-BFCL measurement path is unchanged or fails closed.
- Route remains `novacode/gpt-4.1`.
- Candidate, scorer, baseline, and performance flags remain false.
