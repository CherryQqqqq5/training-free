# BFCL Client/Proxy Conformance Debug Packet

Status: prepared and fail-closed. This packet does not authorize provider requests, BFCL smoke, BFCL scorer, full/default baseline, candidate activation, candidate JSONL/pool, scorer-feedback tuning, performance evidence, +3pp claim, or Huawei readiness.

- runtime_blocker_base_commit: `1006dc95120817bc8b49a7350c1f2f9ab3075433`
- current_head_observed: `97bd2c49bc31c6a15123c53ab99a54436ec92e87`
- route: `novacode/gpt-4.1`
- fallback_allowed: `false`
- endpoint/key: env-only, values forbidden in artifacts

Allowed work is limited to synthetic toy fixtures, a fake upstream, existing proxy conversion helpers/runtime engine, optional BFCL/OpenAI parser imports, and shape-level sanitized outputs.
