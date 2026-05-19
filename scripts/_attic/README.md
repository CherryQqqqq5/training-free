# scripts/_attic/

Scripts archived during repo cleanup pre-P1.

Criteria for inclusion:
1. Zero outbound references found in scripts/, tests/, configs/, docs/,
   abhe_archive/, outputs/artifacts/stage1_bfcl_acceptance/.
2. Does NOT produce any tracked active artifact path.
3. Pre-deletion verification: all four ABHE checkers
   (no_leakage_boundary, review_bundle, approval_chain, planning_ready)
   remained green after the move.

Restore:
  git mv scripts/_attic/<name>.py scripts/<name>.py

Removal policy:
  Do NOT git rm these. Keep until BFCL +Xpp delivery is signed off; revisit then.
