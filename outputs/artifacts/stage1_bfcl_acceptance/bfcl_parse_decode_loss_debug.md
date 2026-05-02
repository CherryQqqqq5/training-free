# BFCL Parse/Decode-Loss Debug

Status: no-provider synthetic fixture artifact only. No live telemetry, BFCL generate, smoke, evaluate, scorer, full baseline, candidate path, performance evidence, +3pp claim, SOTA claim, or Huawei claim was run or authorized.

handler_import_available: `True`
responses_handler_available: `True`
decode_execute_called: `True`
decode_execute_nonempty_for_valid_fixture: `True`
shape_mismatch_detected: `True`
suspected_parse_decode_failure_stage: `not_reproduced_offline_valid_function_call_decodes_nonempty`
next_recommended_patch_gate: `no_patch_live_decode_exception_shape_capture_gate`

Variant summary:
- `valid_json_string_arguments_completed_status`: stage=`accepted_by_bfcl_parse_decode`, missing_fields=`none`, parse_exception=`none`, decode_exception=`none`, decode_nonempty=`True`
- `valid_object_arguments_completed_status`: stage=`accepted_by_bfcl_parse_decode`, missing_fields=`none`, parse_exception=`none`, decode_exception=`none`, decode_nonempty=`True`
- `missing_call_id`: stage=`bfcl_parse_missing_call_id`, missing_fields=`call_id`, parse_exception=`AttributeError`, decode_exception=`none`, decode_nonempty=`False`
- `missing_status`: stage=`accepted_by_bfcl_parse_decode`, missing_fields=`none`, parse_exception=`none`, decode_exception=`none`, decode_nonempty=`True`
- `missing_name`: stage=`bfcl_parse_missing_name`, missing_fields=`name`, parse_exception=`AttributeError`, decode_exception=`none`, decode_nonempty=`False`
- `missing_arguments`: stage=`bfcl_parse_missing_arguments`, missing_fields=`arguments`, parse_exception=`AttributeError`, decode_exception=`none`, decode_nonempty=`False`
- `name_nested_under_function`: stage=`bfcl_parse_missing_name`, missing_fields=`name`, parse_exception=`AttributeError`, decode_exception=`none`, decode_nonempty=`False`
- `arguments_nested_under_function`: stage=`bfcl_parse_missing_arguments`, missing_fields=`arguments`, parse_exception=`AttributeError`, decode_exception=`none`, decode_nonempty=`False`
- `invalid_json_string_arguments`: stage=`bfcl_decode_arguments_json_string_invalid`, missing_fields=`none`, parse_exception=`none`, decode_exception=`JSONDecodeError`, decode_nonempty=`False`
- `status_in_progress`: stage=`accepted_by_bfcl_parse_decode`, missing_fields=`none`, parse_exception=`none`, decode_exception=`none`, decode_nonempty=`True`

The artifact stores only booleans, enum labels, counts, and shape labels. It intentionally omits raw prompts, BFCL case content, provider payloads, logs, traces, raw tool arguments, endpoint/key values, gold/reference/expected data, scorer diffs, and candidate output.
