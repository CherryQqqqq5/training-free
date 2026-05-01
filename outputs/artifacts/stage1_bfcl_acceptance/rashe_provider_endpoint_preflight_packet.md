# RASHE Provider Endpoint/Model/Tool-Calling Preflight Packet

Status: approved for preflight mechanism preparation only. This packet does not authorize Phase B source diagnostics, provider requests, BFCL execution, candidate generation, scorer execution, performance evidence, +3pp claims, or Huawei acceptance.

## Scope

- Packet kind: `provider_endpoint_model_tool_calling_preflight`
- Preflight only: `true`
- Phase B execution authorized: `false`
- Provider request path authorized: `true`, synthetic toy preflight only
- The actual synthetic provider preflight request path is signed for review, but execution still requires separate reviewer authorization and was not run in this commit.

## Signed Environment Names

Endpoint env names may be checked for presence only: `CHUANGZHI_NOVACODE_ENDPOINT`, `NOVACODE_ENDPOINT`.

API key env names may be checked for presence only: `CHUANGZHI_API_KEY`, `NOVACODE_API_KEY`.

The endpoint value and key value must not be printed, logged, written to artifacts, written to git, or included in commands. Future provider preflight must require HTTPS endpoint policy without recording the endpoint value.


## Actual Preflight Request Path

The packet signs a future `--execute-preflight` path for a minimal synthetic endpoint/model/tool-calling check. That path may read only signed endpoint/key env values during execution and must not print or persist those values. It may issue only synthetic toy chat/tool-calling requests, never BFCL/source cases or compact diagnostic payloads. This commit implements the path for review but records `actual_preflight_executed_in_this_commit=false`.

## Model Route

The signed primary model remains `gpt-5.2`. A future capability preflight may observe `gpt-5.4` only as an optional capability observation. If only `gpt-5.4` is supported, the result must be `route_update_required`; the current `gpt-5.2` Phase B packet/runbook/checkers must be updated before any source diagnostic execution.

## Synthetic Tool-Calling Probe

Any future provider preflight must use a minimal synthetic toy request only. It may check standard chat completions, `tools`, `tool_choice`, and returned `tool_calls` shape. It must not include BFCL/source cases, raw prompts, raw tool data, traces, case IDs, gold/expected/reference, scorer diffs, candidate outputs, repair outputs, feedback, holdout/full-suite data, or compact source diagnostic payloads.

If the endpoint supports only standard chat completions, the next step is OpenAI-compatible chat adapter review. The compact source diagnostic payload must not be sent directly to Phase B.

## Output Boundary

Allowed compact result fields are `endpoint_present`, `key_present`, `https_valid`, `auth_ok`, `model_gpt_5_2_available`, `optional_model_gpt_5_4_observed`, `tool_calling_supported`, `tool_choice_supported`, `tool_calls_returned`, `raw_payload_persisted`, `raw_prompt_persisted`, `candidate_generation_authorized`, `scorer_authorized`, `performance_evidence`, and `blocker`.

In this commit, the runner supports dry-run/plan-only only and does not request the provider.
