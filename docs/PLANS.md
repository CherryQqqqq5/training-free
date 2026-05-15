# Implementation Plans

## Stage 1 ABHE Archive-Based Evolution

Status: in progress.

Current next patch: align active evidence wording and prepare ABHE approval packet drafts.

Objective: migrate the active Stage-1 narrative from RASHE-as-method to ABHE as the behavior-level archive planning method, while retaining RASHE artifacts as discovery scaffold evidence.

Plan:

1. Add ABHE method, transition, and archive policy docs.
2. Add `abhe_archive/` with behavior-level entries, opportunity table, policy config, empty dev feedback slot, and state transition log.
3. Add a fail-closed planner that outputs only request decisions for proposal-ready entries.
4. Add static checkers for archive policy, leakage boundary, and future dev-smoke packet drafts.
5. Update the active evidence index so ABHE is the main planning route and RASHE is marked as discovery predecessor.

Validation target: JSON parse checks, `scripts/check_abhe_archive_policy.py --compact --strict`, `scripts/plan_abhe_next_evolution.py --write --compact --strict`, `scripts/check_abhe_no_leakage_boundary.py --compact --strict`, focused pytest, and existing RASHE archive checker for predecessor continuity.

Explicitly out of scope: provider calls, BFCL generate/evaluate, scorer execution, candidate JSONL, candidate pool, source collection, trace extraction, holdout, full suite, performance claim, +3pp claim, or Huawei acceptance claim.

## Stage 1 RASHE Predecessor Retention

Status: retained / superseded in main narrative.

RASHE artifacts remain in place for traceability. They are discovery scaffold evidence for compact diagnostic, behavior clustering, and archive seeding. They are not the current complete method, not a direct scorer route, and not performance evidence.

Retained predecessor artifacts include:

- `docs/stage1_rashe_*.md`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/*`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_evolution_archive/*`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_stage3_evidence_index.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_opportunity_table.json`
