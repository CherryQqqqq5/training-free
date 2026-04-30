# Stage-1 RASHE v0 Offline Skeleton Spec

RASHE v0 is an offline skeleton only. It is disabled by default and does not hook into RuleEngine, proxy runtime, BFCL, provider calls, scorer calls, source collection, candidate generation, dev/holdout manifests, or performance claims.

## Scope

The skeleton defines compact schemas, seed skill declarations, and an offline checker:

- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/skill.schema.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/step_trace.schema.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/router_decision.schema.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/verifier_report.schema.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/seed_skills/*.json`
- `scripts/check_rashe_v0_offline.py`

## Seed Skills

The v0 seed SkillBank contains four static declarative skills:

| skill_id | purpose |
| --- | --- |
| `bfcl_current_turn_focus` | keep multi-turn reasoning anchored to the current user turn |
| `bfcl_schema_reading` | preserve visible schema names and required properties |
| `bfcl_tool_call_format_guard` | guard tool-call serialization and reject ambiguous payloads |
| `bfcl_memory_web_search_discipline` | avoid unnecessary memory or web-search calls when not required |

Each seed skill is disabled, offline-only, and runtime-unauthorized. Each includes allowed triggers, forbidden triggers, no-leakage policy, and rollback policy. No seed skill may include gold, expected, scorer, candidate, repair, holdout, case-id-specific, or raw trace content.

## Offline Router Semantics

The v0 checker includes a deterministic fixture router for tests only:

- multi-turn/current-turn signals select `bfcl_current_turn_focus`
- malformed/no-tool/tool-like payload signals select `bfcl_tool_call_format_guard`
- schema/required-property signals select `bfcl_schema_reading`
- memory/web-search discipline signals select `bfcl_memory_web_search_discipline`
- ambiguous multi-skill signals fail closed

This router is not connected to runtime behavior.

## Fail-Closed Invariants

- `offline_only=true`
- `enabled=false`
- `runtime_authorized=false`
- `provider_call_count=0`
- `scorer_call_count=0`
- `source_collection_call_count=0`
- `candidate_generation_authorized=false`
- `forbidden_field_violation_count=0`

## Verification

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_rashe_v0_offline.py --compact --strict
PYTHONPATH=.:src .venv/bin/python -m pytest -q tests/test_rashe_v0_offline.py
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
git diff --check
```

Passing the offline checker does not authorize runtime implementation, provider calls, source collection, candidate generation, scorer execution, paired comparison, SOTA/+3pp, or Huawei acceptance claims.
