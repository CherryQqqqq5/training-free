# Stage-1 ABHE Archive Policy

Status: policy and checker contract. This document does not authorize provider calls, BFCL scorer execution, candidate generation, or performance claims.

## Required Archive Entry Fields

Each ABHE archive entry must include:

- `entry_id`
- `target_behavior_cluster`
- `source_evidence_count`
- `coverage_strata`
- `status`
- `mechanism_hypothesis`
- `risk_flags`
- `recommended_action`
- `dev_feedback_history`
- `state_transition_history`

ABHE entries are behavior-level entries, not BFCL category-bound candidates.

## Current Entries

`state_tracking_v0`

- source evidence: 80
- coverage strata: `multi_turn_base`, `multi_turn_long_context`, `multi_turn_miss_func`, `multi_turn_miss_param`
- status: `proposal_ready`
- next action: request bounded dev smoke

`hallucination_abstain_v0`

- source evidence: 40
- coverage strata: `hallucination`, `irrelevance`
- status: `proposal_ready`
- next action: request bounded dev smoke

`unresolved_search_memory_watch_v0`

- source evidence: 40
- coverage strata: `agentic_web_search`, `agentic_memory`
- status: `watch`
- next action: split or collect more compact diagnostics

## Allowed Statuses

Pre-dev:

- `observed_cluster`
- `seed_archive_entry`
- `proposal_ready`
- `dev_smoke_requested`
- `watch`

Post-dev:

- `dev_smoke_authorized`
- `dev_smoke_executed`
- `dev_passed`
- `narrow_router_requested`
- `split_requested`
- `demoted`
- `rejected`
- `rejected_boundary_failure`
- `demoted_no_mechanism_signal`
- `demoted_regression_not_controlled`
- `holdout_requested`
- `holdout_authorized`
- `holdout_passed`

## Planner Contract

`scripts/plan_abhe_next_evolution.py` reads:

- `abhe_archive/archive_index.json`
- `abhe_archive/opportunity_table.json`
- optional `abhe_archive/dev_feedback/*.json`

It writes:

- `outputs/artifacts/stage1_bfcl_acceptance/abhe_next_evolution_plan.json`

The planner must keep these fields true:

- `does_not_call_provider=true`
- `does_not_call_bfcl_or_model=true`
- `does_not_authorize_scorer=true`
- `does_not_generate_candidate=true`
- `does_not_claim_performance=true`

The planner output is a request plan, not an execution packet and not validation evidence.

## No-Leakage Boundary

ABHE artifacts must not contain:

- forbidden raw prompt
- forbidden raw trace
- forbidden raw payload
- forbidden provider exchange
- forbidden raw case ID
- forbidden gold answer
- forbidden expected/reference answer
- forbidden tool argument values
- forbidden scorer diff
- forbidden candidate output
- forbidden API key, bearer token, endpoint value, or secret

Allowed references are compact hashes, aggregate counts, category strata names, behavior cluster names, and paths to approved compact artifacts.

## Dev Smoke Packet Boundary

`scripts/check_abhe_dev_smoke_packet.py` is a fail-closed checker for future packet drafts. It should accept only a pending request packet unless an explicit active approval artifact is separately created and reviewed.

A pending ABHE dev smoke packet must include:

- baseline command template
- candidate command template
- case list hash
- fresh dev slice source
- provider, model, and protocol
- runtime config path
- candidate rule path
- artifact boundary
- cost and latency cap
- regression cap
- stop-loss criteria

It must keep authorization and execution false:

- `authorized=false`
- `execution_started=false`
- `provider_calls_authorized=false`
- `bfcl_generate_authorized=false`
- `bfcl_evaluate_authorized=false`
- `scorer_authorized=false`
- `candidate_generation_authorized=false`
- `candidate_jsonl_authorized=false`
- `candidate_pool_ready=false`
- `performance_evidence=false`
