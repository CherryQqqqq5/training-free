# Stage 1 RASHE Evolution Protocol

## Purpose

RASHE self-evolution is archive-based behavior evolution. BFCL categories are used for sampling, reporting, and validation strata only. They are not the evolution subject and must not be mapped directly into a fixed list of benchmark-named skills.

The current Stage 3 artifacts are seed archive material: compact source diagnostics, spec-only proposal artifacts, and an offline router/proposer replay. They are not scorer evidence, not candidate activation, and not performance evidence.

## Evolution Subjects

Allowed RASHE evolution subjects are:

- `skill_metadata`
- `router_policy`
- `verifier_stop_condition`
- `workflow_patch`
- `proposal_policy`

A candidate may cover more than one subject, but the archive entry must name the primary subject and the allowed subobjects. Candidate names should describe a behavior cluster, not a BFCL subset.

## Feedback Sources

Allowed feedback sources for selecting the next evolution target are:

- compact source diagnostic aggregates
- dev paired feedback after a separately approved bounded dev smoke
- regression, cost, latency, and leakage reports
- holdout generalization after a separate holdout approval
- reviewer feedback from Hooke and Maxwell

Forbidden feedback sources before explicit authorization are raw traces, raw prompts, raw payloads, raw provider exchanges, raw case identifiers, gold answers, expected answers, reference answers, scorer diffs, candidate outputs, holdout materials, full-suite materials, and credential-bearing material.

## Lifecycle

```text
observed_cluster
  -> seed_archive_entry
  -> proposal_ready
  -> dev_smoke_requested
  -> dev_smoke_authorized
  -> dev_smoke_executed
  -> dev_passed | demoted | rejected
  -> holdout_requested
  -> holdout_authorized
  -> holdout_passed | rejected
```

Rejected and demoted entries remain in the archive. Archive history is part of the search record and must not be deleted to make the current candidate set look cleaner.

## State Gates

| State | Allowed | Forbidden |
| --- | --- | --- |
| `observed_cluster` | Record compact aggregate evidence | Create candidate JSONL, activate candidates, or run scorer |
| `seed_archive_entry` | Store source evidence and constraints | Claim performance or use dev/holdout material |
| `proposal_ready` | Write spec-only proposals and review packets | Run BFCL scorer or create a candidate pool |
| `dev_smoke_requested` | Freeze commands, split policy, stop-loss, and compact outputs | Execute commands |
| `dev_smoke_authorized` | Run exactly the approved bounded dev smoke once | Full BFCL, holdout, broader provider changes, or repeated retries |
| `dev_smoke_executed` | Emit paired compact reports | Claim Huawei readiness, +3pp, or final performance |
| `dev_passed` | Request holdout review | Promote directly to full suite |
| `demoted` | Keep entry for history and regression context | Delete the failed search branch |
| `rejected` | Keep rejection reason and leakage/regression notes | Resubmit unchanged as active |
| `holdout_requested` | Freeze holdout scope and stop-loss | Touch holdout data before approval |
| `holdout_authorized` | Execute only the approved holdout | Full-suite or acceptance claims |
| `holdout_passed` | Request broader measurement | State external acceptance without separate gate |

No transition may jump from source diagnostic evidence directly to performance claim.

## Opportunity Selection

The next evolution target is chosen behavior-first and BFCL-stratified:

```text
opportunity_score =
  failure_mass
  x category_coverage_factor
  x fixability_prior
  x low_leakage_risk
  x low_regression_risk
```

Active candidates should normally have evidence across multiple BFCL strata. A single-stratum signal goes to the watchlist unless reviewers approve a bounded exception.

## Seed Candidate Interpretation

`bfcl_multi_turn_state_tracking` is a seed behavior candidate for `multi_turn_state_lost`. It may evolve through skill metadata, router trigger, verifier, or stop condition changes. It is not a final complete skill.

`bfcl_hallucination_abstain` is a seed safety candidate for unsupported or irrelevant answers. It may later split into narrower candidates such as no-evidence rejection, irrelevant-tool rejection, or unsupported-request boundaries, but only after dev feedback supports the split.

Both seed candidates must carry `not_bfcl_category_bound=true`. Their trigger basis is behavior cluster evidence; BFCL subsets only provide coverage and reporting slices.

## Stage 4 Dev Smoke Purpose

The next dev scorer packet, if approved later, should validate whether archive entries with `status=proposal_ready` produce a positive dev signal on target behavior clusters. It must not be framed as validating BFCL category skills.

Required future metrics are:

- `dev_accuracy_delta_pp`
- `fixed_count`
- `regressed_count`
- `target_bucket_reduction`
- `cost_delta_pct`
- `latency_delta_pct`
- `leakage_count`

Success levels:

- L0: run complete and artifacts clean
- L1: candidate activated only on target behavior clusters
- L2: target bucket count reduced
- L3: `fixed_count > regressed_count`
- L4: `dev_accuracy_delta_pp > 0` and cost/latency within bound

Only L3/L4 may justify a holdout request.

## Governance Roles

Hooke owns safety, anti-overfit, leakage, holdout contamination, category-binding checks, and stop-loss review. Hooke reports `overfit_risk_class`, `leakage_risk_class`, `category_binding_detected`, and `holdout_contamination_detected`.

Maxwell owns measurement validity and causal attribution. Maxwell reports `measurement_validity`, `paired_comparison_ready`, `target_mechanism_evidence`, and `regression_surface`.

Pascal owns implementation and artifact validation after Hooke and Maxwell boundaries are explicit. Pascal must not flip pending approval artifacts to approved.
