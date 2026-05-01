# RASHE Provider Transport Approval Packet

Status: approved for bounded provider transport/source diagnostic execution path only; no execution is performed in this commit.

Approved scope:
- Provider profile: Chuangzhi/Novacode `gpt-5.2`
- Categories: signed 8 categories
- Case count: 20 per category, 160 total
- Source input root: `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/`
- Diagnostic output root: `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/`
- Schema: `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json`
- Adapter: `scripts.rashe_source_diagnostic_compact_adapter:run_compact_source_diagnostic`
- Provider-client factory: `scripts.rashe_source_provider_client:build_chuangzhi_novacode_source_provider_client`
- Source-case provider: `scripts.rashe_source_case_provider:build_signed_source_case_provider`

Credential and endpoint boundary:
- API keys are env-only and execution-time-only.
- Endpoint values are env-only and execution-time-only via signed env var names `CHUANGZHI_NOVACODE_ENDPOINT` or `NOVACODE_ENDPOINT`.
- Endpoint values must be HTTPS and must not contain raw/path indicators.
- This packet does not authorize reading profile files, hardcoded default endpoints, logging endpoint/key values, or writing endpoint/key values into artifacts.
- Missing endpoint must fail closed as `provider_endpoint_missing`; missing key must fail closed as `provider_key_missing`.

Output boundary:
- Raw request, raw response, raw trace, provider payload, case IDs, prompts, gold, expected, reference, scorer diff, candidate output, repair output, and feedback are forbidden.
- Only compact sanitized failure-bucket counters may be returned by transport.
- Candidate, scorer, performance, +3pp, and Huawei lanes remain unauthorized.

Execution boundary:
- A future execution must pass the provider transport approved checker and all upstream source gates.
- This commit does not run `--execute-approved-source` and does not generate diagnostics.
