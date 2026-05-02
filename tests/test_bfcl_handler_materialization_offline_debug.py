from __future__ import annotations

import copy
import json
import unittest

from scripts.build_bfcl_handler_materialization_offline_debug import VARIANTS, build_report
from scripts.check_bfcl_handler_materialization_offline_debug import validate


class BFCLHandlerMaterializationOfflineDebugTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_report()

    def _records(self, variant: str) -> list[dict]:
        return [record for record in self.report["records"] if record["variant"] == variant]

    def test_synthetic_responses_function_call_decodes_nonempty_when_handler_available(self) -> None:
        if self.report["handler_import_available"]:
            self.assertTrue(self.report["responses_decode_execute_exercised"])
            self.assertTrue(self.report["responses_function_call_decodes_nonempty"])

    def test_synthetic_chat_tool_call_decodes_nonempty_when_handler_available(self) -> None:
        if self.report["handler_import_available"]:
            self.assertTrue(self.report["chat_decode_execute_exercised"])
            self.assertTrue(self.report["chat_tool_call_decodes_nonempty"])

    def test_nonempty_responses_tool_call_materializes_nonempty_result_shape(self) -> None:
        for record in self._records("responses_function_call"):
            self.assertTrue(record["classifier_detected_tool_call"])
            self.assertFalse(record["classifier_empty_model_response"])

    def test_nonempty_text_materializes_as_text_failure_not_empty(self) -> None:
        for record in self._records("text_only"):
            self.assertTrue(record["classifier_detected_no_tool_text"])
            self.assertFalse(record["classifier_empty_model_response"])

    def test_true_empty_materializes_as_empty_model_response(self) -> None:
        for record in self._records("true_empty"):
            self.assertTrue(record["classifier_empty_model_response"])

    def test_result_classifier_detects_nonempty_tool_call_shape(self) -> None:
        for variant in ("responses_function_call", "chat_tool_call"):
            for record in self._records(variant):
                self.assertTrue(record["classifier_detected_tool_call"])

    def test_result_classifier_does_not_false_empty_nonempty_shape(self) -> None:
        self.assertFalse(self.report["result_classifier_false_empty_for_nonempty"])

    def test_exception_path_not_silently_classified_as_empty(self) -> None:
        self.assertFalse(self.report["exception_path_swallowed_as_empty"])
        for record in self._records("handler_exception"):
            self.assertTrue(record["exception_preserved_as_protocol_debug"])

    def test_no_provider_no_bfcl_generate_no_scorer_flags(self) -> None:
        for key in ("provider_request_executed", "bfcl_generate_executed", "bfcl_smoke_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed", "performance_evidence"):
            self.assertFalse(self.report[key])
        self.assertTrue(self.report["no_provider"])
        self.assertTrue(self.report["synthetic_fake_upstream_only"])

    def test_artifact_contains_no_raw_secret_case_material(self) -> None:
        text = json.dumps(self.report, sort_keys=True)
        for forbidden in ("sk-", "provider payload", "raw prompt", "scorer diff", "gold/reference/expected"):
            self.assertNotIn(forbidden, text.lower())
        self.assertEqual(validate(self.report), [])

    def test_checker_rejects_raw_or_execution_drift(self) -> None:
        dirty = copy.deepcopy(self.report)
        dirty["provider_request_executed"] = True
        self.assertTrue(any("provider_request_executed" in blocker for blocker in validate(dirty)))
        dirty = copy.deepcopy(self.report)
        dirty["records"][0]["endpoint_value"] = "secret"
        self.assertTrue(any("forbidden_key" in blocker for blocker in validate(dirty)))
        dirty = copy.deepcopy(self.report)
        dirty["suspected_failure_stage"] = ""
        self.assertIn("suspected_failure_stage_missing", validate(dirty))

    def test_variant_matrix_is_complete(self) -> None:
        self.assertEqual(self.report["variants"], list(VARIANTS))
        self.assertEqual(len(self.report["records"]), 12)


if __name__ == "__main__":
    unittest.main()
