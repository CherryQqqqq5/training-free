# RASHE Opportunity Table

Selection mode: behavior-first, BFCL-stratified. BFCL categories are sampling, reporting, and validation slices only; they do not define the candidate names.

Current boundary: `performance_evidence=false`, `scorer_authorized=false`, `candidate_pool_ready=false`.

| Behavior cluster | Evidence count | Category coverage | Proposed evolution subject | Status | Recommended action |
| --- | ---: | ---: | --- | --- | --- |
| `multi_turn_state_lost` | 80 | 4 | `skill_metadata`, `router_policy`, `verifier_stop_condition` | `active_seed` | `dev_smoke_candidate` |
| `unsupported_or_irrelevant_answer` | 40 | 2 | `skill_metadata`, `router_policy`, `verifier_stop_condition` | `active_seed` | `dev_smoke_candidate` |
| `memory_retrieve_update_confusion` | 20 | 1 | `router_policy`, `verifier_stop_condition`, `proposal_policy` | `watch` | `watch_until_cross_category_evidence_or_reviewer_exception` |
| `search_query_or_fetch_failure` | 18 | 1 | `router_policy`, `workflow_patch`, `verifier_stop_condition` | `watch` | `watch_until_cross_category_evidence_or_reviewer_exception` |

## Notes

- `multi_turn_state_lost` and `unsupported_or_irrelevant_answer` are active seed candidates because they have multi-stratum evidence and existing spec-only proposal artifacts.
- `memory_retrieve_update_confusion` and `search_query_or_fetch_failure` are watchlist clusters because the current evidence is strong but single-stratum. They should not become active candidates until a behavior discovery scan or reviewer exception supplies broader support.
- The current web-search compact diagnostic has `search_query_too_broad=11`, `fetch_missing_after_search=6`, and `wrong_first_tool=1`; `answered_without_tool=2` is tracked separately to avoid overstating the query/fetch mechanism.
