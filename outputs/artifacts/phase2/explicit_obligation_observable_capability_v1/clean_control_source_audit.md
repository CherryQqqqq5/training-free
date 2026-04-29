# Explicit Obligation Clean-Control Source Audit

- Artifact kind: `clean_control_insufficiency_audit`
- Diagnostic only: `True`
- Offline only: `True`
- Execution allowed: `False`
- Smoke ready: `False`
- Selection gate passed: `False`
- Scorer or model run: `False`
- Polluted controls counted as clean: `False`
- Clean-control source audit ready: `True`
- Materialized protocol controls / selected controls / true controls: `20` / `8` / `1`
- Clean selected controls: `0` / `8`
- Materialized protocol negative-control activations: `14`
- Source traces scanned: `154`
- Memory-capable no-activation traces: `72`
- Clean source control candidates: `17`
- Source trace counts by category: `{'memory': 3, 'memory_kv': 85, 'memory_rec_sum': 63, 'memory_vector': 3}`
- No-activation stage counts: `{'no_explicit_obligation': {'pass': 37, 'fail': 35, 'unknown': 0}, 'no_hidden_state_dependency': {'pass': 36, 'fail': 36, 'unknown': 0}, 'baseline_no_memory_activation': {'pass': 72, 'fail': 0, 'unknown': 0}, 'exact_bfcl_mapping': {'pass': 60, 'fail': 12, 'unknown': 0}, 'uniqueness': {'pass': 48, 'fail': 24, 'unknown': 0}}`
- Source/materialized/materialized-selected activation counts: `14` / `14` / `8`
- Duplicate BFCL/trace/audit counts: `0` / `0` / `0`
- Overlap / ambiguous / dependency-missing counts: `12` / `0` / `0`
- Candidate commands: `[]`
- Planned commands: `[]`
- Blockers: `['materialized_protocol_true_controls_below_target']`
- Next action: `materialize_clean_source_controls_to_bfcl_executable_protocol_before_smoke`

## Dominant No-Activation Rejection Reasons

- `clean_control_candidate`: `17`
- `exact_bfcl_mapping_fail`: `12`
- `no_explicit_obligation_fail`: `35`
- `no_hidden_state_dependency_fail`: `36`
- `overlaps_selected_positive_bfcl_case_id`: `12`
- `uniqueness_fail_bfcl_case_id`: `12`

## Recommended Clean-Control Candidates

- `memory_kv_13-customer-13` `memory_kv` `memory_kv/baseline/traces/67e7402c-3cba-4082-8d7c-c449db817668.json`
- `memory_kv_6-customer-6` `memory_kv` `memory_kv/baseline/traces/704f13b1-3300-4dff-9ad4-14b5da7f072b.json`
- `memory_kv_16-customer-16` `memory_kv` `memory_kv/baseline/traces/7216e11b-169e-4f2b-bd67-f26ff99a7ac0.json`
- `memory_kv_26-customer-26` `memory_kv` `memory_kv/baseline/traces/81ed0d6e-eaef-40e1-994f-3e420e5602a5.json`
- `memory_kv_10-customer-10` `memory_kv` `memory_kv/baseline/traces/8c746d1b-15b3-4b9d-a9ba-c07659fc136b.json`
- `memory_kv_20-customer-20` `memory_kv` `memory_kv/baseline/traces/bfd548df-e37b-4a4d-9328-e14ec861a698.json`
- `memory_kv_4-customer-4` `memory_kv` `memory_kv/baseline/traces/ccd00b4f-6710-4b60-a92d-8cf500086b23.json`
- `memory_kv_17-customer-17` `memory_kv` `memory_kv/baseline/traces/d27dcb0d-e1d9-4099-a981-157bd14e5759.json`
- `memory_kv_1-customer-1` `memory_kv` `memory_kv/baseline/traces/d3cb84ab-a7b6-435a-9554-330eeffb36d1.json`
- `memory_kv_5-customer-5` `memory_kv` `memory_kv/baseline/traces/f9f3ed8e-7da7-4609-9bf3-fb54e9ac1337.json`

This diagnostic reads existing artifacts only. It does not run BFCL, model inference, or scorer execution.
