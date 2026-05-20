# G5 — P1.5b approval packet signing record

## When
Signed at UTC `2026-05-20T02:39:45Z`.

## Pre-sign HEAD (`signed_at_commit_sha`)
`8519facd03b7cff6c72197bf3bee02b1741e202b`
(= `signed_at_commit_sha` field in `signature_block`)

## Who
`signed_by: cherry_via_claude_code`

Project owner `cherry` instructed Claude Code in session 2026-05-19 with
the explicit five-step plan (quoted below). Claude Code performed the
mechanical edit. The authority for the signing rests with the project
owner; the keystroke trail is via Claude Code for traceability.

## User instruction (verbatim, project owner, 2026-05-19)

> 第一，先不要跑 full BFCL。先完成 P1.5b approval packet 的签名和 caps：
> token budget、wall-clock cap、error-class regression cap、cost
> amplification cap、provider 504 rate cap。未签名前 strict mode
> fail-closed 是正确状态。

(Full five-step plan also covered: bounded slicer rerun → regenerate
P1/P1.5a artifacts → re-evaluate arms only after contract satisfied →
v3 wired bounded test (separate) → backoff policy in separate wire-step
PR with hard caps.)

## Cap values selected

Field | Value | Rationale
---|---|---
`cost_latency_cap_token_budget` | `2,000,000` | 72 case-arm runs in this smoke (24 cases × 3 arms). Multi-turn long-context cases can reach ~50k tokens; conservative ~30k average × 72 = 2.16M. 2M leaves buffer; bound enforces stop-loss.
`cost_latency_cap_wall_clock_s` | `3600` (60 min) | 72 runs × ~30s serial ≈ 36 min; with concurrency 4 ≈ 10 min. 60 min cap allows retry/slow paths without unbounded wall time.
`regression_cap_error_class_delta_max_cases` | `3` | Per-case scorer slicing should NOT change model behaviour (same prompts, same model, same temperature). Error class is expected to be identical per case. Allow ≤3-case drift to absorb temp=0 nondeterminism.
`cost_amplification_cap_factor` | `5.0` | "Beyond Max Tokens" (arxiv 2025) showed up to 658x amplification possible in multi-turn tool chains. 5x is a conservative defensive bound for a bounded smoke.
`provider_504_rate_cap_pct` | `10.0` | Backoff is NOT wired in this run (per user instruction; separate PR). C3 already showed 504 sensitivity. 10% (≤7 of 72) allows recovery; abort if exceeded.

`signed_by` = `cherry_via_claude_code` (honest delegation marker; allows
audit trail to reconstruct who instructed what).

## What signing authorizes (precisely)

Six AUTHORIZATION_FIELDS flipped to True:
- `authorized`
- `provider_calls_authorized`
- `bfcl_generate_authorized`
- `bfcl_evaluate_authorized`
- `scorer_authorized`
- `per_case_scorer_invocation_authorized`

Authorisation scope: `per_case_scorer_slicer_bounded_residual_dev_smoke_only`
- target_category = `multi_turn_miss_param`
- target_selected_compact_case_count = `24`
- target_unique_scorer_unit_count_post_slicing = `24`
- approved_arms = `[baseline, conditional_frozen_v2, runtime_slot_controller_v2]`
- approved_provider = `ToolCallingFunction/OpenAICompatible`
- approved_model = `gpt-4.1`

## What signing does NOT authorize

All 14 FORCED_FALSE booleans remain False:
- `holdout_authorized = false`
- `full_suite_authorized = false`
- `archive_update_authorized = false`
- `performance_claim_authorized = false`
- `performance_evidence = false`
- `sota_3pp_claim_ready = false`
- `huawei_acceptance_ready = false`
- `raw_outputs_committed = false`
- `raw_provider_payload_committed = false`
- `raw_bfcl_result_tree_committed = false`
- `gold_expected_committed = false`
- `scorer_diff_committed = false`
- `prompt_literal_committed = false`
- `argument_values_committed = false`

In particular, **provider transport backoff policy is NOT enabled** (per
user instruction 5: separate wire-step PR with hard caps). The rerun
will face raw provider 504 risk; the stop-loss mechanism handles
it via the 10% rate cap above.

## Verification (machine-checked)

```bash
$ source .venv/bin/activate && PYTHONPATH=. \
    python scripts/check_abhe_v0_per_case_scorer_slicer_approval_packet.py --strict
$ echo $?
0   # signed, all attestations consistent, all FORCED_FALSE hold
```

20 tests pass (boundary tests covering signed-state + synthetic-draft
regression + privilege-escalation rejection + FORCED_FALSE rejection +
stop-loss rejection).

## What this signing does NOT do

This signing alone does NOT execute the rerun. It only AUTHORIZES the
rerun. A separate runner (G6, next) must:
1. Read this packet via the strict checker (exit 0 required)
2. Build a per-case scorer slicer manifest
3. Execute with cap enforcement
4. Emit compact artifacts (no raw traces)
5. Regenerate P1 and P1.5a artifacts against the new sliced data

## Rollback plan

If the signed packet needs to be revoked:
1. Set `approval_status` back to `"rejected"` (or `"draft_pending_signature"`)
2. Flip all 6 AUTHORIZATION_FIELDS to False
3. Optionally reset signature_block to placeholders
4. `python scripts/check_abhe_v0_per_case_scorer_slicer_approval_packet.py --strict`
   will then exit 1, blocking future rerun attempts.
