# Postcondition-Guided Dev Smoke Protocol

- Ready for review: `True`
- Provider required: `novacode`
- Selected case count: `9`
- Capability distribution: `{'search_or_find': 3, 'read_content': 6}`
- Selected case list hash: `a90b91e5c9adab03d03b841861d768ab0e9be8c1557f74a4a7e6421ed86a3860`
- Runtime rule hash: `849c82f79806518caaa8a4d9ce69641517ef808228aed66aaf01bf19d698c475`
- Candidate commands: `[]`
- Planned commands: `[]`
- Does not authorize scorer: `True`
- Positive lane case count: `9`
- Control lane: `{'synthetic_final_answer_negative_control_activated': False, 'synthetic_no_prior_tool_output_negative_control_activated': False, 'synthetic_missing_capability_negative_control_activated': False, 'required_control_activation_count': 0}`
- Hard pins: `['provider_required', 'selected_case_list_hash', 'runtime_rule_sha256']`
- First failure: `None`
- Next action: `request_explicit_postcondition_guided_paired_smoke_execution_approval`

This protocol freezes a tiny postcondition-guided paired smoke design. It does not run BFCL/model/scorer.
The smoke is limited to low-risk read/search capability guidance and cannot support retain, holdout, 100-case, or SOTA claims.
