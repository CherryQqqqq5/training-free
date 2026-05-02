from __future__ import annotations

import copy
import json
import unittest

from scripts.build_bfcl_parse_decode_loss_debug import VARIANT_ORDER, build_report
from scripts.check_bfcl_parse_decode_loss_debug import validate_artifact, validate_packet


class BFCLParseDecodeLossDebugTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_report()

    def _record(self, variant: str) -> dict:
        return next(record for record in self.report["records"] if record["variant"] == variant)

    def test_valid_proxy_responses_function_call_decodes_or_records_precise_fields(self) -> None:
        record = self._record("valid_json_string_arguments_completed_status")
        self.assertTrue(record["proxy_responses_function_call_has_name"])
        self.assertTrue(record["proxy_responses_function_call_has_arguments"])
        self.assertTrue(record["proxy_responses_function_call_has_call_id"])
        self.assertEqual(record["missing_required_decode_fields"], [])
        if self.report["handler_import_available"]:
            self.assertTrue(record["decode_execute_called"])
            if not record["decode_execute_nonempty"]:
                self.assertNotEqual(record["suspected_parse_decode_failure_stage"], "")

    def test_missing_call_id_status_name_arguments_variants_are_classified(self) -> None:
        self.assertIn("call_id", self._record("missing_call_id")["missing_required_decode_fields"])
        self.assertFalse(self._record("missing_status")["proxy_responses_function_call_has_status"])
        self.assertIn("name", self._record("missing_name")["missing_required_decode_fields"])
        self.assertIn("arguments", self._record("missing_arguments")["missing_required_decode_fields"])
        for variant in ("missing_call_id", "missing_status", "missing_name", "missing_arguments"):
            self.assertTrue(self._record(variant)["suspected_parse_decode_failure_stage"])

    def test_arguments_string_and_object_variants_are_handled_or_classified(self) -> None:
        string_record = self._record("valid_json_string_arguments_completed_status")
        object_record = self._record("valid_object_arguments_completed_status")
        self.assertEqual(string_record["arguments_shape_label"], "json_string")
        self.assertEqual(object_record["arguments_shape_label"], "object")
        if self.report["handler_import_available"]:
            self.assertTrue(string_record["decode_execute_called"])
            self.assertTrue(object_record["decode_execute_called"])

    def test_name_field_placement_variants_are_classified(self) -> None:
        nested = self._record("name_nested_under_function")
        self.assertEqual(nested["name_field_placement_label"], "nested_function_object")
        self.assertIn("name", nested["missing_required_decode_fields"])

    def test_invalid_json_arguments_variant_is_decode_exception_or_classified(self) -> None:
        record = self._record("invalid_json_string_arguments")
        self.assertEqual(record["arguments_shape_label"], "json_string")
        if self.report["handler_import_available"]:
            self.assertTrue(record["decode_execute_called"])
            self.assertFalse(record["decode_execute_nonempty"])
            self.assertTrue(record["decode_exception_class"] != "none" or record["suspected_parse_decode_failure_stage"])

    def test_checker_accepts_clean_report_and_packet_shape(self) -> None:
        packet = {
            "artifact_kind": "bfcl_parse_decode_loss_debug_packet",
            "approval_status": "prepared",
            "route_profile": "novacode",
            "route_model": "gpt-4.1",
            "no_provider_required": True,
            "synthetic_fixtures_only": True,
            "authorized": False,
            "provider_request_authorized": False,
            "live_telemetry_authorized": False,
            "bfcl_generate_authorized": False,
            "bfcl_smoke_authorized": False,
            "bfcl_evaluate_authorized": False,
            "scorer_authorized": False,
            "full_baseline_authorized": False,
            "candidate_runtime_activation_authorized": False,
            "candidate_jsonl_authorized": False,
            "candidate_pool_ready": False,
            "performance_evidence": False,
            "sota_3pp_claim_ready": False,
            "huawei_acceptance_ready": False,
            "fallback_allowed": False,
            "gpt_4o_fallback_allowed": False,
            "gpt_5_2_active": False,
            "openrouter_allowed": False,
        }
        self.assertEqual(validate_packet(packet), [])
        self.assertEqual(validate_artifact(self.report), [])

    def test_checker_rejects_raw_material_secrets_and_execution_flags(self) -> None:
        dirty = copy.deepcopy(self.report)
        dirty["provider_request_executed"] = True
        self.assertTrue(any("provider_request_executed" in blocker for blocker in validate_artifact(dirty)))
        dirty = copy.deepcopy(self.report)
        dirty["raw_prompt_text"] = "redacted"
        self.assertTrue(any("forbidden_key" in blocker for blocker in validate_artifact(dirty)))
        dirty = copy.deepcopy(self.report)
        dirty["notes"] = "api key value"
        self.assertTrue(any("forbidden_value" in blocker for blocker in validate_artifact(dirty)))

    def test_no_provider_no_bfcl_generate_no_scorer_flags_remain_false(self) -> None:
        for key in (
            "provider_request_executed",
            "live_telemetry_executed",
            "bfcl_generate_executed",
            "bfcl_smoke_executed",
            "bfcl_evaluate_executed",
            "scorer_executed",
            "full_baseline_executed",
            "candidate_runtime_activation_authorized",
            "candidate_jsonl_authorized",
            "candidate_pool_ready",
            "performance_evidence",
            "sota_3pp_claim_ready",
            "huawei_acceptance_ready",
        ):
            self.assertFalse(self.report[key])
        self.assertTrue(self.report["no_provider"])
        self.assertTrue(self.report["synthetic_fixtures_only"])

    def test_variant_matrix_complete_and_raw_free(self) -> None:
        self.assertEqual(self.report["variant_order"], list(VARIANT_ORDER))
        self.assertEqual(len(self.report["records"]), len(VARIANT_ORDER))
        text = json.dumps(self.report, sort_keys=True).lower()
        for forbidden in ("provider payload", "raw prompt", "scorer diff", "gold/reference/expected", "candidate output"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
