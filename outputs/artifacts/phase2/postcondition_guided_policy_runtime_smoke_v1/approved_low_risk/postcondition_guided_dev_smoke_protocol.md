# Postcondition-Guided Dev Smoke Protocol

- Ready for review: `False`
- Provider required: `novacode`
- Selected case count: `3`
- Capability distribution: `{'search_or_find': 2, 'read_content': 1}`
- Selected case list hash: `ecf93f7a1568a20fe242615d015f5b985413386f581a3e1997c4125a0d57bd73`
- Runtime rule hash: `849c82f79806518caaa8a4d9ce69641517ef808228aed66aaf01bf19d698c475`
- Candidate commands: `[]`
- Planned commands: `[]`
- Does not authorize scorer: `True`
- Positive lane case count: `1`
- Diagnostic inactive case count: `2`
- Control lane: `{'synthetic_final_answer_negative_control_activated': False, 'synthetic_no_prior_tool_output_negative_control_activated': False, 'synthetic_missing_capability_negative_control_activated': False, 'required_control_activation_count': 0}`
- Hard pins: `['provider_required', 'selected_case_list_hash', 'runtime_rule_sha256']`
- First failure: `{'check': 'selected_low_risk_case_count', 'actual': 3, 'expected': 9}`
- Next action: `fix_postcondition_guided_smoke_protocol_inputs`

This protocol freezes a tiny postcondition-guided paired smoke design. It does not run BFCL/model/scorer.
The smoke is limited to low-risk read/search capability guidance and cannot support retain, holdout, 100-case, or SOTA claims.
