from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.check_bfcl_exact_2id_smoke_approval_packet import validate_packet

PACKET_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_smoke_approval_packet.json")
REPLAY_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_request_replay.json")


class BFCLExact2IDSmokeApprovalPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = json.loads(PACKET_PATH.read_text(encoding="utf-8"))

    def test_approved_exact_generate_only_packet_passes(self) -> None:
        self.assertEqual(validate_packet(self.packet), [])
        self.assertEqual(self.packet["approval_status"], "approved")
        self.assertTrue(self.packet["authorized"])
        self.assertTrue(self.packet["provider_call_authorized"])
        self.assertTrue(self.packet["bfcl_smoke_authorized"])
        self.assertTrue(self.packet["bfcl_generate_authorized"])
        self.assertFalse(self.packet["bfcl_evaluate_authorized"])
        self.assertFalse(self.packet["scorer_authorized"])
        self.assertEqual(self.packet["bfcl_run_ids_manifest_mode"], "temporary_bfcl_package_path_with_backup_restore")
        self.assertEqual(self.packet["bfcl_run_ids_manifest_content"], "exact_signed_ids_only")
        self.assertTrue(self.packet["bfcl_run_ids_manifest_cleanup_required"])

    def test_rejects_pending_state_for_execution_packet(self) -> None:
        dirty = copy.deepcopy(self.packet)
        dirty["approval_status"] = "pending"
        dirty["authorized"] = False
        dirty["provider_call_authorized"] = False
        dirty["bfcl_smoke_authorized"] = False
        dirty["bfcl_generate_authorized"] = False
        blockers = validate_packet(dirty)
        self.assertTrue(any("approval_status_not_approved" in blocker for blocker in blockers))
        self.assertTrue(any("provider_call_authorized_not_true" in blocker for blocker in blockers))

    def test_rejects_extra_ids(self) -> None:
        dirty = copy.deepcopy(self.packet)
        dirty["signed_run_ids"] = ["web_search_base_0", "multi_turn_base_0", "irrelevance_0"]
        self.assertTrue(any("signed_run_ids_invalid" in blocker for blocker in validate_packet(dirty)))

    def test_rejects_full_default_or_8id_authorization(self) -> None:
        for key in ("full_baseline_authorized", "default_bfcl_authorized", "eight_id_smoke_authorized"):
            dirty = copy.deepcopy(self.packet)
            dirty[key] = True
            self.assertTrue(any(key in blocker for blocker in validate_packet(dirty)))

    def test_rejects_candidate_activation_jsonl_pool(self) -> None:
        for key in ("candidate_runtime_activation_authorized", "candidate_generation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready"):
            dirty = copy.deepcopy(self.packet)
            dirty[key] = True
            self.assertTrue(any(key in blocker for blocker in validate_packet(dirty)))

    def test_rejects_performance_3pp_huawei_claim(self) -> None:
        for key in ("performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready"):
            dirty = copy.deepcopy(self.packet)
            dirty[key] = True
            self.assertTrue(any(key in blocker for blocker in validate_packet(dirty)))

    def test_rejects_route_drift_fallback_openrouter(self) -> None:
        dirty = copy.deepcopy(self.packet)
        dirty["route_model"] = "gpt-4o"
        self.assertIn("route_drift", validate_packet(dirty))
        for key in ("fallback_allowed", "gpt_4o_fallback_allowed", "openrouter_allowed", "gpt_5_2_active"):
            dirty = copy.deepcopy(self.packet)
            dirty[key] = True
            self.assertTrue(any(key in blocker for blocker in validate_packet(dirty)))

    def test_rejects_raw_persistence_and_endpoint_key_literals(self) -> None:
        for key in ("raw_logs_committed", "raw_traces_committed", "raw_provider_payloads_committed", "raw_prompts_committed", "raw_gold_reference_scorer_diffs_committed"):
            dirty = copy.deepcopy(self.packet)
            dirty[key] = True
            self.assertTrue(any(key in blocker for blocker in validate_packet(dirty)))
        dirty = copy.deepcopy(self.packet)
        dirty["unexpected_endpoint"] = "https" + "://example.invalid/v1"
        self.assertTrue(any("forbidden_value" in blocker for blocker in validate_packet(dirty)))
        dirty = copy.deepcopy(self.packet)
        dirty["unexpected_key"] = "sk-" + "A" * 32
        self.assertTrue(any("forbidden_value" in blocker for blocker in validate_packet(dirty)))

    def test_replay_top_level_wording_is_cleaned(self) -> None:
        replay = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(replay["suspected_replay_failure_stage"], "not_reproduced_after_measurement_text_coercion_patch")
        text_records = [record for record in replay["records"] if record["fake_upstream_variant"] == "text_only"]
        self.assertTrue(text_records)
        for record in text_records:
            self.assertEqual(record["no_tool_text_classification"], "record_only_no_tool_text")
            self.assertFalse(record["engine_coerced_nonempty_text_to_empty"])
        empty_records = [record for record in replay["records"] if record["fake_upstream_variant"] == "true_empty"]
        self.assertTrue(empty_records)
        for record in empty_records:
            self.assertEqual(record["no_tool_text_classification"], "true_empty")
        tool_records = [record for record in replay["records"] if record["fake_upstream_variant"] == "tool_call"]
        self.assertTrue(tool_records)
        for record in tool_records:
            self.assertTrue(record["bfcl_decode_execute_nonempty"])


if __name__ == "__main__":
    unittest.main()
