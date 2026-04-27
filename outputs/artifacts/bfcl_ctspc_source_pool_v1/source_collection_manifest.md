# M2.7t Source Pool Manifest

- Ready: `False`
- Source collection commands: `9`
- Cases per missing category: `30`
- Discovery source: `bfcl_runnable_categories_plus_raw_files`
- Candidate source categories: `14`

| Category | Available | Needs Collection | Selected Cases | ID Source | Run IDs File |
| --- | ---: | ---: | ---: | --- | --- |
| `irrelevance` | `True` | `False` | `0` | `None` | `None` |
| `memory_kv` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_kv/baseline/bfcl/test_case_ids_to_generate.json` |
| `memory_rec_sum` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_rec_sum/baseline/bfcl/test_case_ids_to_generate.json` |
| `memory_vector` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_vector/baseline/bfcl/test_case_ids_to_generate.json` |
| `multi_turn_base` | `True` | `False` | `0` | `None` | `None` |
| `multi_turn_long_context` | `True` | `False` | `0` | `None` | `None` |
| `multi_turn_miss_func` | `True` | `False` | `0` | `None` | `None` |
| `multi_turn_miss_param` | `True` | `False` | `0` | `None` | `None` |
| `multiple` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline/bfcl/test_case_ids_to_generate.json` |
| `parallel` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel/baseline/bfcl/test_case_ids_to_generate.json` |
| `parallel_multiple` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline/bfcl/test_case_ids_to_generate.json` |
| `simple_java` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_java/baseline/bfcl/test_case_ids_to_generate.json` |
| `simple_javascript` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_javascript/baseline/bfcl/test_case_ids_to_generate.json` |
| `simple_python` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_python/baseline/bfcl/test_case_ids_to_generate.json` |

## Planned Baseline-Only Commands
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_kv/baseline 8071 memory_kv /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_rec_sum/baseline 8072 memory_rec_sum /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_vector/baseline 8073 memory_vector /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline 8078 multiple /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel/baseline 8079 parallel /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline 8080 parallel_multiple /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_java/baseline 8081 simple_java /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_javascript/baseline 8082 simple_javascript /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```
```bash
bash /cephfs/qiuyn/training-free/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_python/baseline 8083 simple_python /cephfs/qiuyn/training-free/configs/runtime_bfcl_structured.yaml
```

No candidate commands are emitted. Source collection results are not performance evidence.
