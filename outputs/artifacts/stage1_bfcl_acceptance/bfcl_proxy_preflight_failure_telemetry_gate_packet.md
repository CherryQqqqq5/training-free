# BFCL Proxy Preflight Failure Telemetry Gate Packet

Pending fail-closed gate. No provider request, upstream-backed preflight, BFCL generate/evaluate, scorer, full baseline, candidate activation, candidate JSONL/pool, or performance claim is authorized.

Future scope is exactly one sanitized local-stub proxy/preflight telemetry attempt. The preflight upstream mode is `local_stub_no_provider`; upstream provider transport must be blocked and instrumented as blocked. If provider-call or upstream-transport evidence appears, the future attempt must stop/fail. Raw prompts, cases, provider payloads, response headers, logs, traces, model output, tool args, result trees, scorer diffs, endpoint values, and key values are forbidden.
