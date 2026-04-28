# Explicit Obligation Smoke Protocol

- Protocol ready for review: `True`
- Protocol lane: `memory_heavy_first_smoke`
- Memory-heavy imbalance: `True`
- Positive / control cases: `12` / `8`
- Future provider profile: `novacode`
- Separate approval required: `True`
- Approval status: `pending`
- Execution allowed: `False`
- Candidate set frozen/hash: `True` / `72aeb6ac7d57031c777037f208f3910f3214c255af2d3ec7ffdff8ed522caff8`
- Allowed provider profiles: `['novacode']`
- Candidate commands: `[]`
- Planned commands: `[]`
- Stop-loss gate: `{'control_activation_count': 0, 'exact_tool_choice_count': 0, 'argument_creation_count': 0, 'case_regressed_count_max': 0, 'net_case_gain_min': 1, 'candidate_accuracy_must_exceed_baseline': True}`
- Formal pass gate: `{'candidate_accuracy_delta_pp_min': 3.0, 'case_fixed_greater_than_regressed': True, 'case_regressed_count_max': 0, 'holdout_required_for_retain': True}`
- Blockers: `[]`
- Next action: `request_separate_memory_heavy_smoke_approval`

Offline protocol only. It does not authorize BFCL/model/scorer runs.
