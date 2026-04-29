# M2.7t Source Pool Manifest

- Ready: `False`
- Source collection commands: `14`
- Cases per missing category: `30`
- Discovery source: `bfcl_runnable_categories_plus_raw_files`
- Candidate source categories: `14`

| Category | Available | Needs Collection | Selected Cases | ID Source | Run IDs File |
| --- | ---: | ---: | ---: | --- | --- |
| `irrelevance` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/irrelevance/baseline/bfcl/test_case_ids_to_generate.json` |
| `memory_kv` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_kv/baseline/bfcl/test_case_ids_to_generate.json` |
| `memory_rec_sum` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_rec_sum/baseline/bfcl/test_case_ids_to_generate.json` |
| `memory_vector` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_vector/baseline/bfcl/test_case_ids_to_generate.json` |
| `multi_turn_base` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_base/baseline/bfcl/test_case_ids_to_generate.json` |
| `multi_turn_long_context` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_long_context/baseline/bfcl/test_case_ids_to_generate.json` |
| `multi_turn_miss_func` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_func/baseline/bfcl/test_case_ids_to_generate.json` |
| `multi_turn_miss_param` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_param/baseline/bfcl/test_case_ids_to_generate.json` |
| `multiple` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline/bfcl/test_case_ids_to_generate.json` |
| `parallel` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel/baseline/bfcl/test_case_ids_to_generate.json` |
| `parallel_multiple` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline/bfcl/test_case_ids_to_generate.json` |
| `simple_java` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_java/baseline/bfcl/test_case_ids_to_generate.json` |
| `simple_javascript` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_javascript/baseline/bfcl/test_case_ids_to_generate.json` |
| `simple_python` | `False` | `True` | `30` | `bfcl_dataset_api` | `outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_python/baseline/bfcl/test_case_ids_to_generate.json` |

## Planned Baseline-Only Commands
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/irrelevance/baseline 8070 irrelevance /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_kv/baseline 8071 memory_kv /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_rec_sum/baseline 8072 memory_rec_sum /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/memory_vector/baseline 8073 memory_vector /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_base/baseline 8074 multi_turn_base /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_long_context/baseline 8075 multi_turn_long_context /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_func/baseline 8076 multi_turn_miss_func /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_param/baseline 8077 multi_turn_miss_param /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/multiple/baseline 8078 multiple /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel/baseline 8079 parallel /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/parallel_multiple/baseline 8080 parallel_multiple /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_java/baseline 8081 simple_java /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_javascript/baseline 8082 simple_javascript /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```
```bash
bash /Users/cherry/mnt/training-free/main-worktree/scripts/run_bfcl_v4_baseline.sh gpt-4o-mini-2024-07-18-FC outputs/artifacts/bfcl_ctspc_source_pool_v1/simple_python/baseline 8083 simple_python /Users/cherry/mnt/training-free/main-worktree/configs/runtime_bfcl_structured.yaml
```

No candidate commands are emitted. Source collection results are not performance evidence.
