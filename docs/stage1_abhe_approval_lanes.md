# Stage 1 ABHE Approval Lanes

ABHE separates planning readiness from execution authorization. Passing a planning checker does not authorize provider calls, BFCL generation, BFCL evaluation, scorer execution, candidate generation, holdout, full suite, or performance claims.

State machine:

```text
planning_ready
-> trace_extraction_review_requested
-> trace_extraction_approved
-> trace_cards_generated
-> trace_cards_checked
-> fresh_dev_slice_requested
-> fresh_dev_slice_approved
-> dry_run_runner_materialized
-> execution_readiness_review
-> bounded_dev_smoke_authorized
-> bounded_dev_smoke_executed
-> dev_feedback_checked
-> post_dev_transition_planned
```

Current state:

- `planning_ready`
- `trace_extraction_packet_pending`
- `dev_smoke_packet_pending`
- `trace_card_contract_ready`
- `fresh_dev_slice_request_pending`
- `dry_run_runner_materialized`
- `execution_readiness_review`

Not reached:

- trace extraction approval
- trace cards generated
- fresh dev slice approval
- fresh dev slice materialized
- execution authorization
- bounded dev smoke execution
- dev feedback checked
- post-dev transition planned

Current ABHE remains fail-closed. `abhe_planning_ready=true` means the review package is coherent. `abhe_execution_ready=false` means the execution chain still lacks approved fresh slice materialization, execution approval, candidate spec approval, runtime config selection, and scorer authorization.
