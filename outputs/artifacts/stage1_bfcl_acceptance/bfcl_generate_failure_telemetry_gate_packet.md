# BFCL Generate Failure Telemetry Gate Packet

- Approval status: `approved`
- Authorized: `true`
- Provider request authorized: `true`
- BFCL generate authorized: `true`
- Scope: exactly one sanitized generate-stage failure telemetry attempt only.
- Route: `novacode/gpt-4.1`
- Candidate specs: inert
- BFCL smoke/evaluate/scorer/full baseline/candidate/performance execution: `false`
- Output policy: compact telemetry fields only; raw logs, prompts, cases, provider payloads, result trees, scorer diffs, endpoint/key values, and candidate outputs are forbidden.
- Claim policy: diagnostic only; no BFCL measurement evidence and no +3pp/SOTA/Huawei claim.
