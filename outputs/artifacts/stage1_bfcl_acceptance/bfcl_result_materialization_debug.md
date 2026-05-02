# BFCL Result Materialization Debug

No provider, BFCL generate, evaluate, scorer, full baseline, candidate, performance, +3pp, or Huawei path is executed.

Signed IDs: `web_search_base_0`, `multi_turn_base_0`. Route labels: `novacode` / `gpt-4.1`.

Synthetic variants distinguish provider/proxy empty output, nonempty tool-call or text output materialized as empty, result-classifier misses, and CLI exception-to-empty handling.

Suspected next isolation target: `bfcl_result_materialization_or_handler_decode_path`.
