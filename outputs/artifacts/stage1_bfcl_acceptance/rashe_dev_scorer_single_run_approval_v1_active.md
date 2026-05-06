# RASHE Dev Scorer Single-Run Approval v1 Active

Status: approved active approval state, not started. This artifact records the project-owner approved exactly-one bounded dev scorer smoke boundary.

It links the pending review packet plus Stage 4 draft execution packet, command manifest, and dev manifest by path and sha256. The canonical draft packet is not mutated.

Current boundary: approval flip active after project-owner review; `execution_started=false`, one attempt only, max 12 dev cases, compact outputs only, fresh output paths required, and raw temporary cleanup required. Candidate JSONL/pool, holdout, full suite, final claim gates, and external acceptance flags remain false.

This file does not run the smoke and does not add an execution runner.

Owner-approved flip fields are recorded in `owner_approved_flip_fields`; active-state false fields are limited to `must_remain_false_fields`.
