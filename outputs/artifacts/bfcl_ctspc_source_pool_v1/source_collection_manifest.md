# M2.7t Source Pool Manifest

- Ready: `False`
- Source collection commands: `7`
- Cases per missing category: `30`
- Discovery source: `installed_bfcl_data`
- Candidate source categories: `12`

| Category | Available | Needs Collection | Selected Cases | Run IDs File |
| --- | ---: | ---: | ---: | --- |
| `irrelevance` | `True` | `False` | `0` | `None` |
| `memory` | `False` | `True` | `30` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/memory/baseline/bfcl/test_case_ids_to_generate.json` |
| `multi_turn_base` | `True` | `False` | `0` | `None` |
| `multi_turn_long_context` | `True` | `False` | `0` | `None` |
| `multi_turn_miss_func` | `True` | `False` | `0` | `None` |
| `multi_turn_miss_param` | `True` | `False` | `0` | `None` |
| `multiple` | `False` | `True` | `30` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline/bfcl/test_case_ids_to_generate.json` |
| `parallel` | `False` | `True` | `30` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel/baseline/bfcl/test_case_ids_to_generate.json` |
| `parallel_multiple` | `False` | `True` | `30` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline/bfcl/test_case_ids_to_generate.json` |
| `simple_java` | `False` | `True` | `30` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_java/baseline/bfcl/test_case_ids_to_generate.json` |
| `simple_javascript` | `False` | `True` | `30` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_javascript/baseline/bfcl/test_case_ids_to_generate.json` |
| `simple_python` | `False` | `True` | `30` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_python/baseline/bfcl/test_case_ids_to_generate.json` |

## Planned Baseline-Only Commands
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/memory/baseline 8071 memory /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline 8076 multiple /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel/baseline 8077 parallel /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline 8078 parallel_multiple /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_java/baseline 8079 simple_java /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_javascript/baseline 8080 simple_javascript /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_python/baseline 8081 simple_python /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```

No candidate commands are emitted. Source collection results are not performance evidence.
