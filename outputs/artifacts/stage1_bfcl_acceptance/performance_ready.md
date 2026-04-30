# Stage-1 BFCL Performance Ready

- Formal BFCL performance acceptance ready: `False`
- Active evidence index: `outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json`
- Active provider/profile/model: `Chuangzhi/Novacode` / `novacode` / `gpt-5.2`
- OpenRouter active evidence: `False`
- Performance evidence: `False`
- Scorer authorization: `False`
- Candidate pool ready: `False`
- SOTA +3pp claim ready: `False`
- Huawei acceptance ready: `False`
- Current blocker: `deterministic_argument_structural_and_tool_name_paths_zero_yield`
- Next action: `negative_evidence_report_or_scope_change_review`

This checker remains fail-closed. The active evidence index supersedes historical 401/OpenRouter/gpt-5.4/dev20/candidate artifacts for current Stage-1 claim scope.

This checker is offline-only. It verifies performance evidence artifacts but does not run BFCL, a model, or a scorer.

Fail-closed frontier: candidate_pool_ready=false; scorer_authorized=false; performance_evidence=false; sota_3pp_claim_ready=false; huawei_acceptance_ready=false.

Schema retrieval/rerank feasibility diagnostic: zero-yield; `single_schema_high_margin_count=0`; recommendation `stop_no_yield_research_review`. Readiness remains fail-closed.
