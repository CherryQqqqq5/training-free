# BFCL Pre-generate Substage Observability Patch Gate Packet

Prepared fail-closed gate only. No provider call, BFCL generate, smoke, evaluate, scorer, full baseline, candidate activation, candidate JSONL/pool, or performance claim is authorized.

Future scope is limited to sanitized compact substage labels between preflight/preamble and BFCL CLI generate entry for the baseline/generate telemetry path. Raw logs, traces, prompts, cases, provider payloads, result trees, scorer diffs, endpoint values, and key values remain forbidden.

Required future labels:

- config_source_exit_class
- env_default_expansion_class
- category_arg_assembly_shape
- category_arg_validation_result
- bfcl_cli_import_probe_class_without_generate
- bfcl_cli_argument_probe_class_without_generate
- pre_generate_marker_boundary_class
- last_started_stage
- last_completed_stage
- suspected_pregenerate_failure_substage

No-provider BFCL CLI import and argument probes are marked `not_run_by_design` for this gate because even import/help probing could have package side effects unless separately reviewed.
