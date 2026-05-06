# Implementation Plans

## Stage 1 RASHE Archive-Based Evolution

Status: in progress.

Objective: reinterpret Stage 3 RASHE seed skills as archive entries for behavior-level self-evolution, not as a BFCL-category-to-skill checklist.

Plan:

1. Add the RASHE evolution protocol with allowed evolution subjects, feedback sources, lifecycle gates, and reviewer responsibilities.
2. Add a seeded evolution archive under `outputs/artifacts/stage1_bfcl_acceptance/rashe_evolution_archive/`.
3. Add a behavior-first opportunity table that ranks stable failure clusters instead of BFCL category names.
4. Add a fail-closed archive checker and focused tests.
5. Update the pending dev scorer request and dev smoke packet to point at the archive and opportunity table while keeping all execution and scorer authorization flags false.

Validation target: JSON parse checks, `scripts/check_rashe_evolution_archive.py --compact --strict`, focused pytest, and existing Stage 4 packet checkers. No provider calls, BFCL generate/evaluate, scorer execution, candidate JSONL, candidate pool, holdout, full suite, or performance claim are part of this plan.
