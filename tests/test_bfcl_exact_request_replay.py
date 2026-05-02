from __future__ import annotations

import copy
import unittest

from scripts.build_bfcl_exact_request_replay import FAKE_VARIANTS, SIGNED_IDS, build_report
from scripts.check_bfcl_exact_request_replay import validate_artifact, validate_packet


class BFCLExactRequestReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_report()

    def test_replay_no_provider_no_smoke_no_scorer_flags(self) -> None:
        for key in (
            "provider_request_executed",
            "live_telemetry_executed",
            "bfcl_smoke_executed",
            "scorer_executed",
            "full_baseline_executed",
            "candidate_runtime_activation_authorized",
            "performance_evidence",
            "sota_3pp_claim_ready",
            "huawei_acceptance_ready",
        ):
            self.assertFalse(self.report[key])
        for record in self.report["records"]:
            self.assertFalse(record["provider_request_executed"])
            self.assertFalse(record["live_telemetry_executed"])
            self.assertFalse(record["bfcl_smoke_executed"])
            self.assertFalse(record["scorer_executed"])

    def test_replay_uses_required_string_tool_choice(self) -> None:
        self.assertEqual(self.report["signed_run_ids"], list(SIGNED_IDS))
        for record in self.report["records"]:
            self.assertEqual(record["exact_tool_choice_shape"], "required_string")
            self.assertEqual(record["forwarded_tool_choice_shape"], "required_string")
            self.assertTrue(record["multi_tool_schema_present"])

    def test_tool_call_variant_survives_or_reports_stage(self) -> None:
        tool_records = [record for record in self.report["records"] if record["fake_upstream_variant"] == "tool_call"]
        self.assertEqual(len(tool_records), len(SIGNED_IDS))
        for record in tool_records:
            self.assertTrue(record["responses_to_chat_conversion_exercised"])
            self.assertTrue(record["runtime_engine_exercised"])
            self.assertTrue(record["chat_to_responses_conversion_exercised"])
            self.assertTrue(record["engine_final_has_tool_calls"])
            self.assertTrue(record["responses_output_has_function_call"])
            self.assertTrue(record["bfcl_decode_execute_nonempty"])
            self.assertEqual(record["suspected_replay_failure_stage"], "required_string_multi_tool_survives_local_conversion_runtime_decode")

    def test_text_only_variant_detects_engine_coercion_vs_text(self) -> None:
        text_records = [record for record in self.report["records"] if record["fake_upstream_variant"] == "text_only"]
        self.assertEqual(len(text_records), len(SIGNED_IDS))
        for record in text_records:
            self.assertTrue(record["upstream_returned_nonempty_text"])
            self.assertFalse(record["engine_final_content_empty"])
            self.assertFalse(record["engine_coerced_nonempty_text_to_empty"])
            self.assertFalse(record["engine_final_has_tool_calls"])
            self.assertEqual(record["responses_output_has_message_text"], True)
            self.assertEqual(record["no_tool_text_classification"], "record_only_no_tool_text")
            self.assertEqual(record["suspected_replay_failure_stage"], "non_tool_text_preserved_as_message_text")

    def test_true_empty_variant_distinguished(self) -> None:
        empty_records = [record for record in self.report["records"] if record["fake_upstream_variant"] == "true_empty"]
        self.assertEqual(len(empty_records), len(SIGNED_IDS))
        for record in empty_records:
            self.assertTrue(record["upstream_returned_true_empty"])
            self.assertTrue(record["engine_final_content_empty"])
            self.assertEqual(record["no_tool_text_classification"], "true_empty")
            self.assertEqual(record["suspected_replay_failure_stage"], "true_empty_distinguished")

    def test_malformed_nonempty_variant_distinguished(self) -> None:
        malformed_records = [record for record in self.report["records"] if record["fake_upstream_variant"] == "malformed_nonempty"]
        self.assertEqual(len(malformed_records), len(SIGNED_IDS))
        for record in malformed_records:
            self.assertTrue(record["upstream_returned_nonempty_text"])
            self.assertEqual(record["suspected_replay_failure_stage"], "malformed_nonempty_response_shape_distinguished")

    def test_rejects_unsigned_ids(self) -> None:
        dirty = copy.deepcopy(self.report)
        dirty["records"][0]["run_id"] = "unsigned_case_0"
        self.assertTrue(any("unsigned_run_id" in blocker for blocker in validate_artifact(dirty)))

    def test_rejects_raw_prompt_or_secret_material(self) -> None:
        dirty = copy.deepcopy(self.report)
        dirty["records"][0]["suspected_replay_failure_stage"] = "raw prompt leaked"
        blockers = validate_artifact(dirty)
        self.assertTrue(any("forbidden_value" in blocker for blocker in blockers))

    def test_suspected_replay_failure_stage_required(self) -> None:
        dirty = copy.deepcopy(self.report)
        dirty["suspected_replay_failure_stage"] = ""
        self.assertIn("artifact_suspected_replay_failure_stage_missing", validate_artifact(dirty))
        dirty = copy.deepcopy(self.report)
        dirty["records"][0]["suspected_replay_failure_stage"] = ""
        self.assertIn("artifact_record_0_suspected_stage_missing", validate_artifact(dirty))

    def test_packet_fail_closed(self) -> None:
        packet = {
            "artifact_kind": "bfcl_exact_request_replay_packet",
            "approval_status": "prepared",
            "route_model": "gpt-4.1",
            "active_profile": "novacode",
            "signed_run_ids": list(SIGNED_IDS),
            "fake_upstream_variants": list(FAKE_VARIANTS),
            "candidate_specs_inert": True,
            "endpoint_env_only": True,
            "api_key_env_only": True,
            "compact_shape_only": True,
        }
        for key in (
            "authorized",
            "provider_request_authorized",
            "live_telemetry_authorized",
            "bfcl_smoke_authorized",
            "bfcl_scorer_authorized",
            "full_baseline_authorized",
            "candidate_runtime_activation_authorized",
            "performance_evidence",
            "sota_3pp_claim_ready",
            "huawei_acceptance_ready",
            "provider_request_executed",
            "live_telemetry_executed",
            "bfcl_smoke_executed",
            "scorer_executed",
            "full_baseline_executed",
            "endpoint_value_committed",
            "api_key_value_committed",
            "raw_material_persisted",
        ):
            packet[key] = False
        self.assertEqual(validate_packet(packet), [])
        packet["provider_request_authorized"] = True
        self.assertTrue(any("provider_request_authorized" in blocker for blocker in validate_packet(packet)))


if __name__ == "__main__":
    unittest.main()
