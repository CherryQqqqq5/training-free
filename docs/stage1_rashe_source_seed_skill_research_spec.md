# RASHE Source Evidence Seed Skill Research Spec

Status: research/spec only. This document does not authorize candidate generation, candidate JSONL, scorer execution, performance evidence, or Huawei acceptance readiness.

## Seed Skill Research Surfaces

For bounded source diagnostics, reviewers may inspect whether compact failure buckets suggest future seed-skill work in these areas:

- search-query discipline
- memory retrieval/update discipline
- multi-turn state carryover
- tool-call format and parser-schema guardrails
- hallucination/irrelevance rejection

Each proposed seed skill must have a trigger, policy, and verifier before any later candidate admission review. This phase records only compact evidence buckets; it does not generate or admit candidates.

## Candidate Admission Criteria For Later Approval Only

A future candidate lane would require separate approval and must show:

- source evidence from approved compact diagnostics only
- no raw trace, raw case ID, provider payload, gold, expected, scorer diff, candidate output, repair output, feedback, holdout feedback, or full-suite feedback
- deterministic trigger-policy-verifier description
- no scorer or performance feedback in proposal construction
- candidate generation authorization signed separately

Current status: candidate generation remains unauthorized.
