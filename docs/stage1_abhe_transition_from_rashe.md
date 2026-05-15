# Stage-1 ABHE Transition From RASHE

Status: transition note only. This document changes the main narrative and planning boundary. It does not move historical artifacts, authorize execution, or create performance evidence.

## Transition Summary

RASHE is the discovery scaffold and predecessor.

ABHE is the current main planning method: Archive-Based Behavior Harness Evolution.

RASHE completed the compact diagnostic to behavior cluster to archive seed phase. ABHE starts from that archive and decides which behavior-level entries are worth requesting for fresh bounded dev smoke.

## What Is Superseded

The following RASHE statements are superseded in the main narrative:

- RASHE is the current complete method.
- RASHE should directly enter dev smoke.
- RASHE route is ready to enter scorer.
- RASHE scaffold proves the self-evolution loop is complete.

Correct wording:

RASHE is ABHE's discovery and scaffold predecessor. It completed compact diagnostic, behavior clustering, and archive seeding. The next-stage main method is ABHE. Current evidence supports planning and approval packet preparation only.

## Retained RASHE Artifacts

Do not bulk-rename or move existing RASHE artifacts. Keep them for traceability:

- `docs/stage1_rashe_*.md`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/*`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_evolution_archive/*`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_stage3_evidence_index.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_opportunity_table.json`

These are retained as scaffold evidence and discovery predecessor artifacts. They are no longer the active method narrative.

## New ABHE Artifacts

The ABHE mainline uses:

- `docs/stage1_abhe_method_overview.md`
- `docs/stage1_abhe_transition_from_rashe.md`
- `docs/stage1_abhe_archive_policy.md`
- `abhe_archive/archive_index.json`
- `abhe_archive/opportunity_table.json`
- `abhe_archive/policy_config.yaml`
- `scripts/plan_abhe_next_evolution.py`
- `scripts/check_abhe_archive_policy.py`
- `scripts/check_abhe_no_leakage_boundary.py`
- `scripts/check_abhe_dev_smoke_packet.py`

The first planner output is:

- `outputs/artifacts/stage1_bfcl_acceptance/abhe_next_evolution_plan.json`

## Boundary Carry-Forward

The fail-closed boundary carries forward unchanged:

- `source_collection_authorized=false`
- `candidate_generation_authorized=false`
- `candidate_pool_ready=false`
- `candidate_jsonl_authorized=false`
- `scorer_authorized=false`
- `performance_evidence=false`
- `sota_3pp_claim_ready=false`
- `huawei_acceptance_ready=false`

The active route can be named ABHE only as a planning route. It remains non-performance evidence.

## Deterministic Route Downgrade

The deterministic argument/tool-name/schema families remain retained as negative evidence:

- `explicit_required_arg_literal_completion`
- `wrong_arg_key_alias_repair`
- `deterministic_schema_local_non_live_repair`
- raw tool-name/schema normalization
- schema retrieval/rerank feasibility

They should not appear as active next-step planning. Their role is to explain why Stage 1 pivoted to archive-based behavior evolution.

## Search And Memory Downgrade

The search/memory archive item is a mixed watch entry. It is diagnostics-only until split and supported:

- `search_query_or_fetch_failure`
- `memory_retrieve_update_confusion`

It must not be proposed as a third dev smoke as a single mixed entry.

