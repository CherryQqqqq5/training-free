# M2.7t Source Pool Manifest

- Ready: `False`
- Source collection commands: `3`

| Category | Available | Needs Collection |
| --- | ---: | ---: |
| `multi_turn_base` | `False` | `True` |
| `multi_turn_miss_func` | `False` | `True` |
| `multi_turn_long_context` | `False` | `True` |

## Planned Baseline-Only Commands
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_base/baseline 8070 multi_turn_base /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_func/baseline 8071 multi_turn_miss_func /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_long_context/baseline 8072 multi_turn_long_context /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
