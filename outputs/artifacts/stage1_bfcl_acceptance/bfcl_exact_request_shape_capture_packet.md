# BFCL Exact Request Shape Capture Packet

Status: prepared / fail-closed. This packet authorizes only no-provider shape capture of the exact BFCL handler request envelope for the signed run IDs `web_search_base_0` and `multi_turn_base_0`.

It does not authorize provider requests, live telemetry reruns, BFCL smoke, BFCL scorer, full/default baseline, candidate activation, candidate JSONL/pool, scorer-feedback tuning, performance evidence, +3pp, SOTA, or Huawei readiness.

The capture gate may load BFCL entries in memory and intercept handler kwargs before network. It must write only compact buckets and labels: no raw prompts, raw case content, full tool schemas/names, gold/reference/expected material, scorer diffs, provider payloads, logs, traces, endpoint/key values, or candidate output.
