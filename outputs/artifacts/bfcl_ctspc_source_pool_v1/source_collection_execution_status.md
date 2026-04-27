# M2.8-pre-e Source Collection Execution Status

- head: `e40a9ca5`
- source_collection_execution_passed: `true`
- source_collection_only: `true`
- no_candidate_rules: `true`
- candidate_commands: `[]`
- provider_profile: `novacode`
- upstream_model: `gpt-5.4`
- does_not_authorize_scorer: `true`

## Completed Categories
- `memory_kv` on port `8071`
- `memory_rec_sum` on port `8072`
- `memory_vector` on port `8073`
- `multiple` on port `8078`
- `parallel` on port `8079`
- `parallel_multiple` on port `8080`
- `simple_java` on port `8081`
- `simple_javascript` on port `8082`
- `simple_python` on port `8083`

## Post-Rebuild Gate
- m27t_source_pool_ready: `True`
- explicit selected/generatable: `28` / `25`
- stratified selected/generatable: `30` / `27`
- explicit_holdout_ready: `False`
- stratified_holdout_ready: `False`
- scorer_authorization_ready: `False`
- m2_8pre_offline_passed: `False`
- blockers: `['explicit_total_below_40', 'explicit_candidate_generatable_below_35', 'explicit_holdout_below_20', 'stratified_holdout_below_20']`

## Warnings
- BFCL command completed with exit 0, but logs reported Hugging Face embedding dependency connection errors during some memory_vector cases.

This artifact is compact source-collection evidence only. It is not candidate evaluation, holdout evidence, or BFCL performance evidence.
