# BFCL Proxy Preflight Failure Telemetry Gate Packet

Pending fail-closed gate. No provider request, live preflight, BFCL generate/evaluate, scorer, full baseline, candidate activation, candidate JSONL/pool, or performance claim is authorized.

Future scope is exactly one sanitized local proxy/preflight telemetry attempt that writes compact labels only and stops before BFCL generate. If provider-call evidence appears, the future attempt must stop/fail. Raw prompts, cases, provider payloads, response headers, logs, traces, model output, tool args, result trees, scorer diffs, endpoint values, and key values are forbidden.
