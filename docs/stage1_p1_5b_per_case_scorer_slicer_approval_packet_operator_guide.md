# Stage1 ABHE-v0 P1.5b — per-case scorer slicer approval packet operator guide

Status: `formal-json-packet-shipped-draft-pending-signature` on feature
branch `feat/p1-5b-approval-packet-structure`. Companion to the
original draft (which remains untouched).

## Files

- **Draft specification** (review-only, never edited after initial commit):
  `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_p1_5b_per_case_scorer_slicer_approval_packet_draft.md`
- **Formal JSON packet** (this artifact is the consumable):
  `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_approval_packet.json`
- **Checker**:
  `scripts/check_abhe_v0_per_case_scorer_slicer_approval_packet.py`
- **Tests** (17 boundary tests):
  `tests/test_abhe_v0_per_case_scorer_slicer_approval_packet.py`

## Current state (verifiable by command)

```bash
# Default mode: structural well-formed check — exit 0
python scripts/check_abhe_v0_per_case_scorer_slicer_approval_packet.py --compact

# Strict mode: authorization check — exit 1 (correctly fail-closed, unsigned)
python scripts/check_abhe_v0_per_case_scorer_slicer_approval_packet.py --strict
```

The packet ships with:
- `approval_status = "draft_pending_signature"`
- All 6 authorization fields false
- All 14 forced-false boundary fields false
- All 11 required stop-loss triggers present
- All 8 signature fields present but unfilled (`"<unsigned>"` or `null`)

## To sign (operator workflow)

1. Open `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_approval_packet.json`.
2. Set `approval_status` to `"approved"`.
3. Set all 6 authorization fields to `true`:
   - `authorized`
   - `provider_calls_authorized`
   - `bfcl_generate_authorized`
   - `bfcl_evaluate_authorized`
   - `scorer_authorized`
   - `per_case_scorer_invocation_authorized`
4. Fill `signature_block`:
   - `signed_by`: your identity (non-empty string)
   - `signed_at_iso8601_utc`: ISO-8601 UTC timestamp string
   - `signed_at_commit_sha`: the repo commit SHA at signing time
   - `cost_latency_cap_token_budget`: positive int (suggested `1000000`)
   - `cost_latency_cap_wall_clock_s`: positive int (suggested `1800`)
   - `regression_cap_error_class_delta_max_cases`: positive int (suggested `2`)
   - `cost_amplification_cap_factor`: positive float (suggested `5.0`)
   - `provider_504_rate_cap_pct`: positive float (suggested `5.0`)
5. Run `python scripts/check_abhe_v0_per_case_scorer_slicer_approval_packet.py --strict`.
   Exit 0 confirms the packet is signed and consumable.

## Defense in depth — the checker also rejects

- `authorized=True` while `approval_status="draft_pending_signature"`
  (privilege escalation attempt)
- `holdout_authorized=True` even when signed (boundary always-false)
- Missing or corrupted stop-loss triggers
- Schema/version mismatch
- Missing runtime config file on disk
- `approval_scope` not matching the expected literal
- Provider/profile/model/route/protocol mismatches with literals
- `approved_arms` not matching `["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]`
- Pre-rerun dependencies inconsistent (e.g., `p3_backoff_policy_wired_into_proxy=true`)

These rejections are all tested in
`tests/test_abhe_v0_per_case_scorer_slicer_approval_packet.py`.

## What signing does NOT authorize

Even after signing, the packet remains bounded:

- `holdout_authorized = false`
- `full_suite_authorized = false`
- `archive_update_authorized = false`
- `performance_claim_authorized = false`
- `performance_evidence = false`
- `sota_3pp_claim_ready = false`
- `huawei_acceptance_ready = false`
- All raw-material-committed booleans false
- Only the 24-case `multi_turn_miss_param` slice in the bounded dev
  smoke is authorized for per-case scorer invocation.

## What signing DOES authorize (precisely)

- `provider_calls_authorized = true`
- `bfcl_generate_authorized = true`
- `bfcl_evaluate_authorized = true`
- `scorer_authorized = true`
- `per_case_scorer_invocation_authorized = true`

...on the literal:
- `approved_provider = "ToolCallingFunction/OpenAICompatible"`
- `approved_profile = "toolcallingfunction"`
- `approved_model = "gpt-4.1"`
- `approved_route_policy = "toolcallingfunction_openai_compatible_only_openrouter_disabled"`
- `approved_protocol = "bfcl_v4_abhe_v0_per_case_scorer_slicer_bounded_residual_dev_smoke_toolcallingfunction"`
- `approved_arms = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]`
- `approved_selected_case_ids_hash = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"`
- `approved_selected_case_count = 48`
- `approved_target_category = "multi_turn_miss_param"`
- `approved_target_selected_compact_case_count = 24`
- `approved_target_unique_scorer_unit_count_post_slicing = 24`

## Honest pre-rerun expectation

Even when the slicer works and rerun completes successfully, the only
guaranteed outcome is that **the score-output contract probe becomes
satisfiable** for the target category. This does **not** mean any arm
beats baseline. Reporting arm-level outcomes still requires the
P1.5a-style aggregate matrix to be regenerated against the new sliced
artifacts. Per-case signal does not by itself imply +3pp or any claim.
