# BFCL Performance Proof Roadmap

## Summary

The next phase is a BFCL performance proof, not another smoke-test loop. The main claim is same-base-model improvement: with the same evaluator alias, upstream route, runtime config, and budget constraints, CTSPC must show at least `+3pp` absolute improvement over a clean baseline before any full-suite or SOTA claim.

Current Phase-2 evidence shows the system can diagnose and activate next-action policy, but BFCL scorer-level gain is not proven. M2.7d found `34` `multi_turn_miss_param` cases with file/path tools, but overlap with the current wrong-stop target families is `0`; near-term experiments must therefore be framed as schema-local CTSPC performance subsets, not failure-family repair claims.

## Stage Gates

- Stage 0 freezes the protocol: BFCL evaluator/version, data/version anchor, base model alias, upstream route, runtime config, categories, target metric, and `+3pp` same-base-model objective.
- Stage 1 freezes a clean BFCL baseline with no CTSPC candidate rules; every run must emit `metrics.json`, `run_manifest.json`, score/result sources, traces, cost, and latency.
- Stage 2 runs an opportunity scan across BFCL categories to find baseline-wrong, schema-local, candidate-generatable cases; do not run BFCL in this stage.
- Stage 3 runs a paired 30-case subset only after Stage 2 finds at least `30` selected cases and at least `20` candidate-generatable cases.
- Stage 4 expands only after Stage 3 has positive net case gain; target is a 100-case subset with `>= +3pp`, positive net gain, no holdout regression over `0.5pp`, and cost/latency within `+10%`.
- Stage 5 validates full categories, then Stage 6 runs official full BFCL and compares against the Stage 0 frozen SOTA/baseline snapshot.

## Required Stage-3 Evidence

The first scorer-level proof is a paired 30-case subset. It must use the same model, route, runtime config, selected IDs, and BFCL scorer for baseline and candidate. It passes only if:

- `case_fixed_count > case_regressed_count`
- `net_case_gain >= 2`
- candidate accuracy is greater than baseline accuracy
- `policy_plan_activated_count > 0`
- recommended-tool match and raw-normalized arg match rates among activated cases are each `>= 0.6`
- `stop_allowed_false_positive_count = 0`

If Stage 3 fails, diagnose by layer: no action candidate means fix mining/tool-state/action-candidates; non-activation means fix predicates/rulescope; wrong tool means fix actuation; wrong args means fix binding; arg match without scorer gain means fix trajectory continuation or final-answer handling.

## Artifacts

Compact artifacts may be committed under `outputs/artifacts/`. Raw traces, BFCL result trees, logs, and repair-record JSONL remain server-only.

Required compact artifacts by milestone:

- `bfcl_baseline_freeze/metrics.json`, `category_scores.md`, `run_manifest.json`
- `bfcl_opportunity_scan_v1/scan_summary.json`, `category_opportunity_table.md`
- `bfcl_ctspc_subset30_v1/subset_manifest.json`, `subset_case_report.jsonl`, `subset_summary.json`, `subset_summary.md`

## Non-Goals

- Do not enter M2.8 or full BFCL validation before a positive paired subset.
- Do not add non-file/path domain tools to the CTSPC v0 file/path allowlist.
- Do not use archived `fresh_02` as CTSPC performance evidence.
- Do not claim leaderboard SOTA before an official full BFCL run and frozen SOTA comparison.
