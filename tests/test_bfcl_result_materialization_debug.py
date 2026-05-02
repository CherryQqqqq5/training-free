from __future__ import annotations

import copy
import json
import unittest

from scripts.build_bfcl_result_materialization_debug import SIGNED_IDS, VARIANTS, build_report
from scripts.check_bfcl_result_materialization_debug import validate_artifact, validate_packet


class BFCLResultMaterializationDebugTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_report()

    def test_no_provider_generate_scorer_flags(self) -> None:
        for key in ("provider_request_executed", "bfcl_generate_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed", "performance_evidence"):
            self.assertFalse(self.report[key])
        for record in self.report["records"]:
            self.assertFalse(record["provider_request_executed"])
            self.assertFalse(record["bfcl_generate_executed"])
            self.assertFalse(record["scorer_executed"])

    def test_variant_matrix_complete(self) -> None:
        self.assertEqual(self.report["signed_run_ids"], list(SIGNED_IDS))
        self.assertEqual(self.report["debug_variants"], list(VARIANTS))
        self.assertEqual(len(self.report["records"]), len(SIGNED_IDS) * len(VARIANTS))
        self.assertEqual(validate_artifact(self.report), [])

    def test_provider_or_proxy_empty_variant(self) -> None:
        records = [r for r in self.report["records"] if r["fake_upstream_variant"] == "provider_or_proxy_empty"]
        for record in records:
            self.assertTrue(record["provider_or_proxy_returned_empty"])
            self.assertEqual(record["suspected_materialization_stage"], "provider_or_proxy_returned_empty")

    def test_nonempty_proxy_outputs_materialized_as_empty_variants(self) -> None:
        tool_records = [r for r in self.report["records"] if r["fake_upstream_variant"] == "proxy_tool_call_materialized_empty"]
        text_records = [r for r in self.report["records"] if r["fake_upstream_variant"] == "proxy_text_materialized_empty"]
        for record in tool_records:
            self.assertTrue(record["proxy_returned_nonempty_tool_call"])
            self.assertTrue(record["bfcl_handler_stored_empty"])
        for record in text_records:
            self.assertTrue(record["proxy_returned_nonempty_text"])
            self.assertTrue(record["bfcl_handler_stored_empty"])

    def test_result_parser_and_cli_exception_variants(self) -> None:
        parser_records = [r for r in self.report["records"] if r["fake_upstream_variant"] == "result_parser_missed_nonempty"]
        exception_records = [r for r in self.report["records"] if r["fake_upstream_variant"] == "cli_exception_swallowed_as_empty"]
        for record in parser_records:
            self.assertTrue(record["bfcl_result_file_contains_nonempty_shape"])
            self.assertFalse(record["classifier_detected_nonempty_output"])
        for record in exception_records:
            self.assertTrue(record["cli_exception_observed"])
            self.assertEqual(record["cli_exception_classification"], "synthetic_exception_to_empty")

    def test_rejects_raw_or_secret_material(self) -> None:
        dirty = copy.deepcopy(self.report)
        dirty["records"][0]["suspected_materialization_stage"] = "raw prompt leaked"
        self.assertTrue(any("forbidden_value" in blocker for blocker in validate_artifact(dirty)))
        dirty = copy.deepcopy(self.report)
        dirty["records"][0]["endpoint_value"] = "secret"
        self.assertTrue(any("forbidden_key" in blocker for blocker in validate_artifact(dirty)))

    def test_rejects_execution_or_authorization_drift(self) -> None:
        dirty = copy.deepcopy(self.report)
        dirty["provider_request_executed"] = True
        self.assertTrue(any("provider_request_executed" in blocker for blocker in validate_artifact(dirty)))
        dirty = copy.deepcopy(self.report)
        dirty["route_model"] = "gpt-5.2"
        self.assertIn("artifact_route_drift", validate_artifact(dirty))

    def test_packet_fail_closed(self) -> None:
        packet = {
            "artifact_kind": "bfcl_result_materialization_debug_packet",
            "approval_status": "prepared",
            "route_profile": "novacode",
            "route_model": "gpt-4.1",
            "signed_run_ids": list(SIGNED_IDS),
            "debug_variants": list(VARIANTS),
            "compact_shape_only": True,
            "synthetic_fake_upstream_only": True,
            "endpoint_env_only": True,
            "api_key_env_only": True,
        }
        for key in ("authorized", "provider_request_authorized", "bfcl_generate_authorized", "bfcl_smoke_authorized", "bfcl_evaluate_authorized", "scorer_authorized", "full_baseline_authorized", "candidate_runtime_activation_authorized", "candidate_generation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "provider_request_executed", "bfcl_generate_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed", "endpoint_value_committed", "api_key_value_committed", "raw_material_persisted"):
            packet[key] = False
        self.assertEqual(validate_packet(packet), [])
        packet["provider_request_authorized"] = True
        self.assertTrue(any("provider_request_authorized" in blocker for blocker in validate_packet(packet)))

    def test_summary_contains_no_raw_values(self) -> None:
        text = json.dumps(self.report, sort_keys=True)
        self.assertNotIn("sk-", text)
        self.assertNotIn("provider payload", text.lower())


if __name__ == "__main__":
    unittest.main()
