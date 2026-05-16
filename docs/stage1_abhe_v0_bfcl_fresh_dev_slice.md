# Stage 1 ABHE-v0 BFCL Fresh Dev Slice Plan

This document defines the fresh BFCL dev slice gate for the first ABHE-v0 bounded dev smoke.

Current status: plan only. The slice is not materialized, and the selected case list hash remains pending until a fresh dev slice approval packet exists and passes review.

The slice may only target `state_tracking_v0` and `hallucination_abstain_v0`. It must use BFCL dev cases that are not part of the 160 compact discovery/archive-seed evidence. The archive seed source is excluded from validation.

Boundary:
- The plan does not authorize provider calls.
- The plan does not authorize BFCL generate or evaluate.
- The plan does not authorize scorer execution.
- The plan does not persist raw BFCL material.
- The plan does not create performance evidence.

If the BFCL dataset path is not reviewed and provided, `scripts/build_abhe_v0_bfcl_fresh_dev_slice.py` reports `bfcl_dataset_path_missing` as an execution blocker. It must not guess a dataset path.
