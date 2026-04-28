# Memory Operation Dev Smoke Protocol

- Ready for review: `True`
- Provider required: `novacode`
- Target case count: `6`
- Generation case count: `26`
- Prereq case count: `20`
- Selected category counts: `{'memory_kv': 3, 'memory_rec_sum': 3}`
- Generation category counts: `{'memory_kv': 13, 'memory_rec_sum': 13}`
- Snapshot dependency closure ready: `True`
- Case list hash: `bd9d6a8e02254ec8597ee986c0502bc0e301adcdb5dfea2ee9ecb00fa62ec626`
- Generation list hash: `7201aeefcd775db5a0a97f3ad048160214215e90e807710c3bfbb8ecc6e3db3c`
- Runtime rule hash: `5b7f722a104f1d32b7be2993877bbaa622ae84d93062e6be3d5074b956ba4d1a`
- Candidate commands: `[]`
- Planned commands: `[]`
- Does not authorize scorer: `True`
- Next action: `request_explicit_memory_only_dev_smoke_execution_approval`

This protocol freezes the small memory-only dev smoke design. It does not execute BFCL/model/scorer.
Memory target cases require BFCL prerequisite entries to initialize snapshots before the target turns run.
