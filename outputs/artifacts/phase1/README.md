# Phase-1 Artifact Shape

Expected generated files per run:

- `metrics.json`
- `repairs.jsonl`
- `failure_summary.json`

Expected generated files per candidate:

- `rule.yaml`
- `metrics.json`
- `repairs.jsonl`
- `failure_summary.json`
- `accept.json`

Expected archive layout after selection:

- `rules/accepted/<patch_id>/...` or `rules/rejected/<patch_id>/...`
- `rules/active/<patch_id>.yaml` for accepted runtime activation
