import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_source_metadata_approval_packet import check

SCRIPT = Path("scripts/check_rashe_source_metadata_approval_packet.py")
PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_metadata_approval_packet.json")
SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_metadata_compact.schema.json")


def copy_inputs(tmp_path: Path) -> tuple[Path, Path]:
    packet = tmp_path / "packet.json"
    schema = tmp_path / "schema.json"
    shutil.copy(PACKET, packet)
    shutil.copy(SCHEMA, schema)
    return packet, schema


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_metadata_approval_checker_compact_passes_current_packet():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_source_metadata_approval_packet_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["authorized"] is True
    assert summary["approved_metadata_root_path"] == "outputs/artifacts/stage1_bfcl_acceptance/approved_source_metadata_compact/"
    assert summary["downstream_output_manifest_root"] == "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/"
    assert summary["records_per_category"] == 20
    assert summary["total_record_count"] == 160
    assert summary["metadata_root_prepared"] is False
    assert summary["metadata_generated"] is False
    assert summary["source_input_manifests_generated"] is False
    assert summary["provider_transport_authorized"] is False
    assert summary["source_diagnostic_execution_authorized"] is False
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False


def test_fails_if_signed_paths_drift_outside_artifact_dir(tmp_path):
    packet_path, schema_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["approved_metadata_root_path"] = "/tmp/raw_trace/source_metadata/"
    packet["downstream_output_manifest_root"] = "outputs/bfcl_runs/raw_payload/"
    write_json(packet_path, packet)

    summary = check(packet_path, schema_path)

    assert summary["rashe_source_metadata_approval_packet_passed"] is False
    blockers = summary["blockers"]
    assert "packet_approved_metadata_root_path_invalid:'/tmp/raw_trace/source_metadata/'" in blockers
    assert "packet_approved_metadata_root_path_outside_signed_artifact_dir:'/tmp/raw_trace/source_metadata/'" in blockers
    assert "packet_downstream_output_manifest_root_invalid:'outputs/bfcl_runs/raw_payload/'" in blockers
    assert "packet_downstream_output_manifest_root_outside_signed_artifact_dir:'outputs/bfcl_runs/raw_payload/'" in blockers
    assert any(blocker.startswith("packet_approved_metadata_root_path_raw_path_indicator") for blocker in blockers)
    assert any(blocker.startswith("packet_downstream_output_manifest_root_raw_path_indicator") for blocker in blockers)


def test_fails_if_allowed_or_output_fields_include_forbidden_raw_fields(tmp_path):
    packet_path, schema_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["allowed_metadata_fields"].append("case_id")
    packet["output_manifest_fields"].append("raw_prompt")
    write_json(packet_path, packet)

    summary = check(packet_path, schema_path)

    blockers = summary["blockers"]
    assert "packet_allowed_metadata_fields_invalid" in blockers
    assert "packet_output_manifest_fields_invalid" in blockers
    assert "packet_allowed_metadata_field_forbidden:case_id" in blockers
    assert "packet_output_manifest_field_forbidden:raw_prompt" in blockers


def test_fails_if_category_count_ordinal_or_taxonomy_policy_drifts(tmp_path):
    packet_path, schema_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["approved_categories"] = ["agentic_web_search"]
    packet["records_per_category"] = 25
    packet["total_record_count"] = 200
    packet["ordinal_policy"]["base"] = 1
    packet["ordinal_policy"]["max"] = 20
    packet["prompt_family_taxonomy"].append("raw prompt summary")
    packet["category_prompt_family"]["agentic_web_search"] = "raw prompt summary"
    packet["prompt_family_policy"]["raw_prompt_summary_allowed"] = True
    write_json(packet_path, packet)

    summary = check(packet_path, schema_path)

    blockers = summary["blockers"]
    assert "packet_approved_categories_invalid" in blockers
    assert "packet_records_per_category_invalid:25" in blockers
    assert "packet_total_record_count_invalid:200" in blockers
    assert "packet_ordinal_policy_invalid:base:1" in blockers
    assert "packet_ordinal_policy_invalid:max:20" in blockers
    assert "packet_prompt_family_taxonomy_invalid" in blockers
    assert "packet_category_prompt_family_invalid" in blockers
    assert "packet_prompt_family_policy_not_false:raw_prompt_summary_allowed" in blockers


def test_fails_if_nonce_or_source_family_policy_weakens(tmp_path):
    packet_path, schema_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    nonce = packet["source_nonce_policy"]
    nonce["min_length"] = 8
    nonce["high_entropy_random_required"] = False
    nonce["case_id_derivation_allowed"] = True
    nonce["prompt_derivation_allowed"] = True
    nonce["gold_expected_reference_derivation_allowed"] = True
    nonce["trace_path_derivation_allowed"] = True
    nonce["provider_payload_derivation_allowed"] = True
    nonce["nonce_to_raw_case_mapping_committed"] = True
    packet["source_family_id_policy"]["allowed_in_output_manifest"] = True
    packet["source_family_id_policy"]["case_specific_information_allowed"] = True
    packet["source_family_id_policy"]["controlled_taxonomy_only"] = False
    packet["source_family_id_policy"]["taxonomy_values"] = ["case_specific_family"]
    packet["source_family_id_policy"]["category_mapping_required"] = False
    packet["source_family_id_taxonomy"] = ["case_specific_family"]
    packet["category_source_family_id"]["agentic_web_search"] = "case_specific_family"
    write_json(packet_path, packet)

    summary = check(packet_path, schema_path)

    blockers = summary["blockers"]
    assert "packet_source_nonce_min_length_too_small" in blockers
    assert "packet_source_nonce_entropy_not_required" in blockers
    for key in [
        "case_id_derivation_allowed",
        "prompt_derivation_allowed",
        "gold_expected_reference_derivation_allowed",
        "trace_path_derivation_allowed",
        "provider_payload_derivation_allowed",
        "nonce_to_raw_case_mapping_committed",
    ]:
        assert f"packet_source_nonce_policy_not_false:{key}" in blockers
    assert "packet_source_family_id_policy_not_false:allowed_in_output_manifest" in blockers
    assert "packet_source_family_id_policy_not_false:case_specific_information_allowed" in blockers
    assert "packet_source_family_id_taxonomy_not_required" in blockers
    assert "packet_source_family_id_policy_taxonomy_values_invalid" in blockers
    assert "packet_source_family_id_category_mapping_not_required" in blockers
    assert "packet_source_family_id_taxonomy_invalid" in blockers
    assert "packet_category_source_family_id_invalid" in blockers


def test_fails_if_downstream_execution_or_counts_are_enabled(tmp_path):
    packet_path, schema_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    for key in [
        "metadata_root_prepared",
        "metadata_generated",
        "source_input_manifests_generated",
        "provider_transport_authorized",
        "source_diagnostic_execution_authorized",
        "candidate_generation_authorized",
        "candidate_pool_ready",
        "scorer_authorized",
        "performance_evidence",
        "huawei_acceptance_ready",
    ]:
        packet[key] = True
    for key in [
        "candidate_call_count",
        "scorer_call_count",
        "provider_transport_call_count",
        "source_diagnostic_run_count",
        "raw_payload_tracked_count",
        "forbidden_field_violation_count",
    ]:
        packet[key] = 1
    packet["no_leakage_required"]["raw_case_id_used"] = True
    packet["no_leakage_required"]["nonce_to_raw_mapping_committed"] = True
    write_json(packet_path, packet)

    summary = check(packet_path, schema_path)

    blockers = summary["blockers"]
    assert "packet_provider_transport_authorized_not_false:True" in blockers
    assert "packet_source_diagnostic_execution_authorized_not_false:True" in blockers
    assert "packet_candidate_generation_authorized_not_false:True" in blockers
    assert "packet_scorer_authorized_not_false:True" in blockers
    assert "packet_performance_evidence_not_false:True" in blockers
    assert "packet_huawei_acceptance_ready_not_false:True" in blockers
    assert "packet_provider_transport_call_count_not_zero:1" in blockers
    assert "packet_source_diagnostic_run_count_not_zero:1" in blockers
    assert "packet_no_leakage_field_not_false:raw_case_id_used" in blockers
    assert "packet_no_leakage_field_not_false:nonce_to_raw_mapping_committed" in blockers


def test_fails_if_schema_allows_extra_fields_or_weak_nonce(tmp_path):
    packet_path, schema_path = copy_inputs(tmp_path)
    schema = load_json(schema_path)
    schema["additionalProperties"] = True
    schema["properties"]["case_id"] = {"type": "string"}
    schema["required"].append("case_id")
    schema["properties"]["source_nonce"]["minLength"] = 8
    schema["properties"]["source_family_id"].pop("enum", None)
    schema["properties"]["ordinal"]["minimum"] = 1
    schema["properties"]["ordinal"]["maximum"] = 20
    write_json(schema_path, schema)

    summary = check(packet_path, schema_path)

    blockers = summary["blockers"]
    assert "schema_additional_properties_not_false" in blockers
    assert "schema_required_fields_invalid" in blockers
    assert "schema_property_not_allowed:case_id" in blockers
    assert "schema_property_forbidden:case_id" in blockers
    assert "schema_source_nonce_min_length_too_small" in blockers
    assert "schema_source_family_id_enum_invalid" in blockers
    assert "schema_ordinal_bounds_invalid" in blockers
