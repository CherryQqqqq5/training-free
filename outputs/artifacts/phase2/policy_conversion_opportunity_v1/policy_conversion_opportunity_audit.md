# Policy Conversion Opportunity Audit

- Ready: `True`
- Trace count: `9254`
- Rule-hit traces: `697`
- No-tool policy failure traces: `1069`
- Policy candidate count: `54`
- Recommended tools count: `56`
- Candidate capability distribution: `{'copy': 6, 'create_file': 18, 'directory_navigation': 18, 'move_or_rename': 4, 'read_content': 1, 'search_or_find': 2, 'write_content': 5}`
- Recommended tool distribution: `{'cat': 1, 'cd': 18, 'cp': 6, 'echo': 5, 'find': 2, 'grep': 2, 'mv': 4, 'touch': 18}`
- Rejection reason counts: `{'candidate_ready': 54, 'no_rule_hit': 372, 'no_schema_local_recommended_tool': 552, 'not_no_tool_policy_failure': 8185, 'postcondition_already_satisfied': 91}`

Offline audit only. This artifact does not authorize BFCL/model/scorer runs.
