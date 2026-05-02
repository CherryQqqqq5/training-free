# BFCL Measurement-Only Approval Packet

Status: `pending` / fail-closed. This packet prepares a future measurement-only BFCL authorization review; it does not authorize scorer execution, provider calls, Phase B reruns, candidate JSONL, candidate pools, runtime activation, performance evidence, +3pp claims, SOTA claims, or Huawei readiness.

## Signed Scope

- target_commit_for_measurement: `62e84abeb01aa5fbcdacebb27c27083c6c305a02`
- prior_route_cleanup_commit: `94f2546d52e0e2b06d8e24630f7714fc8bbe475c`
- reviewed_measurement_gate_head: `62e84abeb01aa5fbcdacebb27c27083c6c305a02`
- proposer_artifact_commit: `e73900fc7553735e5dbf5121fc46d3ead44c5077`
- source_diagnostics_commit: `cc21c96b70ab51c2bf586c0e79cdde3838dcb05d`
- route: `Chuangzhi/Novacode` / `novacode` / `gpt-4.1`
- fallback_allowed: `false`
- gpt-4o fallback: `false`
- old signed model `gpt-5.2`: historical, superseded, inactive only
- measurement_kind: `current_system_measurement_only`
- candidate_specs_inert: `true`
- candidate_specs_runtime_activated: `false`

## BFCL Protocol

- BFCL version: `v4`
- evaluator package: `bfcl-eval==2025.12.17`
- checkout: `f7cf735`
- BFCL evaluator model alias: `gpt-4o-mini-2024-07-18-FC` (runner alias only, not provider fallback)
- runtime config: `configs/runtime_bfcl_structured.yaml`
- split: `holdout_or_full_measurement_only_pending_authorization`

## Authorization Boundary

- authorized: `false`
- scorer_authorized: `false`
- provider_call_authorized: `false`
- candidate_generation_authorized: `false`
- candidate_jsonl_authorized: `false`
- candidate_pool_ready: `false`
- candidate_runtime_activation_authorized: `false`
- performance_evidence: `false`
- sota_3pp_claim_ready: `false`
- huawei_acceptance_ready: `false`

## Output And Claim Policy

Raw logs, raw traces, provider payloads, per-case scorer diffs, candidate outputs, and feedback are not approved for commit. Future measurement may publish compact metrics/artifacts only if separately approved. No +3pp claim is allowed without a separately approved baseline-vs-treatment comparison.
