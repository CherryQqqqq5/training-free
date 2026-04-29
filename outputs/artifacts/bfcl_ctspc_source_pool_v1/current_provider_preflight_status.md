# Current Provider Preflight Status

- Source collection rerun ready: `false`
- Candidate evaluation ready: `false`
- Attempted category: `multi_turn_long_context`
- Attempted scope: `baseline_source_collection_preflight_only`
- BFCL/model run completed: `false`
- Raw trace/score/result artifacts committed: `false`
- Blocking condition: `valid_provider_credential_required_before_source_collection_or_scorer`

## Attempted Provider Profiles

| Provider profile | Expected env | Result | HTTP status | Failure class |
| --- | --- | --- | ---: | --- |
| `openrouter` | `OPENROUTER_API_KEY` | `blocked` | `401` | `missing_authentication_header` |
| `novacode` | `NOVACODE_API_KEY` | `blocked` | `401` | `invalid_api_key` |

Next required action: configure valid approved provider credentials, then run the planned baseline-only source collection commands from `source_collection_manifest.md`.

This artifact is compact preflight evidence only. It is not BFCL source collection evidence, candidate evaluation, holdout evidence, or performance evidence.
