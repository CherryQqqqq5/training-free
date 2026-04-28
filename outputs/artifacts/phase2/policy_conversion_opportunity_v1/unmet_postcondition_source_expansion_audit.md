# Unmet Postcondition Source Expansion Audit

- Ready: `True`
- Trace count: `9254`
- Typed satisfaction distribution: `{'ambiguous': 7413, 'satisfied_strong': 831, 'satisfied_weak': 644, 'unmet_strong': 366}`
- Capability distribution: `{'compare': 36, 'copy': 166, 'create_file': 359, 'directory_navigation': 428, 'move_or_rename': 115, 'read_content': 272, 'search_or_find': 418, 'unknown': 7321, 'write_content': 139}`
- Strong unmet candidate count: `18`
- Low-risk strong unmet candidate count: `1`
- High-risk strong unmet candidate count: `17`
- Strong unmet capability distribution: `{'copy': 1, 'create_file': 4, 'directory_navigation': 8, 'read_content': 1, 'write_content': 4}`
- Strong unmet risk lane distribution: `{'high_risk_mutation_or_trajectory': 17, 'low_risk_observation': 1}`
- Full records omitted for compact artifact: `True`
- Next required action: `expand_source_or_state_abstraction_before_smoke`

Offline diagnostic only. It does not authorize BFCL/model/scorer runs.
