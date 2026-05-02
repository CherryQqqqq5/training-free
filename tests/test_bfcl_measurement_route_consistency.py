import json
import shutil
from pathlib import Path

import yaml

from scripts.check_bfcl_measurement_route_consistency import check

CONFIGS = [
    Path("configs/runtime.yaml"),
    Path("configs/runtime_bfcl_structured.yaml"),
    Path("configs/bfcl_eval_protocol.yaml"),
    Path("configs/bfcl_v4_phase1.env"),
]
ARTIFACTS = [
    Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_route_consistency.json"),
    Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_route_update_approval_packet.json"),
]


def copy_min_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for rel in CONFIGS + ARTIFACTS:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(rel, dest)
    return root


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def blockers(root: Path) -> list[str]:
    return check(root)["blockers"]


def test_route_consistency_passes_active_gpt_4_1_route():
    summary = check(Path("."))
    assert summary["bfcl_measurement_route_consistency_passed"] is True
    assert summary["route_model"] == "gpt-4.1"
    assert summary["fallback_allowed"] is False
    assert summary["gpt_4o_fallback_allowed"] is False


def test_rejects_active_gpt_5_2_in_runtime_yaml(tmp_path):
    root = copy_min_repo(tmp_path)
    path = root / "configs/runtime.yaml"
    data = load_yaml(path)
    data["upstream"]["model"] = "gpt-5.2"
    write_yaml(path, data)

    joined = "\n".join(blockers(root))
    assert "runtime_yaml_upstream_model_invalid:'gpt-5.2'" in joined
    assert "runtime_yaml_active_gpt_5_2:upstream.model" in joined


def test_rejects_active_gpt_5_2_in_runtime_bfcl_structured_yaml(tmp_path):
    root = copy_min_repo(tmp_path)
    path = root / "configs/runtime_bfcl_structured.yaml"
    data = load_yaml(path)
    data["upstream"]["profiles"]["novacode"]["model"] = "gpt-5.2"
    write_yaml(path, data)

    joined = "\n".join(blockers(root))
    assert "runtime_bfcl_structured_yaml_novacode_model_invalid:'gpt-5.2'" in joined
    assert "runtime_bfcl_structured_yaml_active_gpt_5_2:upstream.profiles.novacode.model" in joined


def test_rejects_active_gpt_5_2_in_bfcl_eval_protocol(tmp_path):
    root = copy_min_repo(tmp_path)
    path = root / "configs/bfcl_eval_protocol.yaml"
    data = load_yaml(path)
    data["model"]["upstream_model_route"] = "gpt-5.2"
    write_yaml(path, data)

    joined = "\n".join(blockers(root))
    assert "bfcl_eval_protocol_upstream_model_route_invalid:'gpt-5.2'" in joined
    assert "bfcl_eval_protocol_active_gpt_5_2:model.upstream_model_route" in joined


def test_rejects_active_gpt_5_2_in_bfcl_v4_phase1_env(tmp_path):
    root = copy_min_repo(tmp_path)
    path = root / "configs/bfcl_v4_phase1.env"
    text = path.read_text().replace('export GRC_UPSTREAM_MODEL="gpt-4.1"', 'export GRC_UPSTREAM_MODEL="gpt-5.2"')
    path.write_text(text)

    joined = "\n".join(blockers(root))
    assert "bfcl_v4_phase1_env_default_model_not_gpt_4_1:'gpt-5.2'" in joined
    assert "bfcl_v4_phase1_env_active_gpt_5_2" in joined


def test_allows_old_signed_model_gpt_5_2_only_in_historical_route_update_fields(tmp_path):
    root = copy_min_repo(tmp_path)
    packet_path = root / "outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_route_update_approval_packet.json"
    packet = load_json(packet_path)
    assert packet["old_signed_model"] == "gpt-5.2"
    assert packet["old_signed_model_active"] is False
    assert check(root)["bfcl_measurement_route_consistency_passed"] is True

    metadata_path = root / "outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_route_consistency.json"
    metadata = load_json(metadata_path)
    metadata["active_route_note"] = "gpt-5.2"
    write_json(metadata_path, metadata)
    assert "route_metadata_active_gpt_5_2:active_route_note" in blockers(root)


def test_rejects_gpt_4o_fallback_allowed_true(tmp_path):
    root = copy_min_repo(tmp_path)
    path = root / "configs/bfcl_eval_protocol.yaml"
    data = load_yaml(path)
    data["model"]["gpt_4o_fallback_allowed"] = True
    data["model"]["fallback_model"] = "gpt-4o"
    write_yaml(path, data)

    joined = "\n".join(blockers(root))
    assert "bfcl_eval_protocol_gpt_4o_fallback_allowed_not_false:True" in joined
    assert "bfcl_eval_protocol_fallback_allowed_true:model.gpt_4o_fallback_allowed" in joined
    assert "bfcl_eval_protocol_gpt_4o_fallback_route:model.fallback_model" in joined


def test_rejects_endpoint_literal_in_runtime_yaml(tmp_path):
    root = copy_min_repo(tmp_path)
    path = root / "configs/runtime.yaml"
    data = load_yaml(path)
    data["upstream"]["base_url"] = "https" + "://example.invalid/v1"
    write_yaml(path, data)

    joined = "\n".join(blockers(root))
    assert "runtime_yaml_endpoint_literal_forbidden:upstream.base_url" in joined


def test_rejects_endpoint_literal_in_runtime_bfcl_structured_yaml(tmp_path):
    root = copy_min_repo(tmp_path)
    path = root / "configs/runtime_bfcl_structured.yaml"
    data = load_yaml(path)
    data["upstream"]["profiles"]["novacode"]["base_url"] = "https" + "://example.invalid/v1"
    write_yaml(path, data)

    joined = "\n".join(blockers(root))
    assert "runtime_bfcl_structured_yaml_endpoint_literal_forbidden:upstream.profiles.novacode.base_url" in joined


def test_rejects_key_like_literal_in_runtime_yaml(tmp_path):
    root = copy_min_repo(tmp_path)
    path = root / "configs/runtime.yaml"
    data = load_yaml(path)
    data["upstream"]["api_key"] = "sk-" + "A" * 24
    write_yaml(path, data)

    joined = "\n".join(blockers(root))
    assert "runtime_yaml_key_literal_forbidden:upstream.api_key" in joined


def test_accepts_env_only_endpoint_reference_and_disabled_feedback():
    runtime = load_yaml(Path("configs/runtime.yaml"))
    structured = load_yaml(Path("configs/runtime_bfcl_structured.yaml"))
    for data in [runtime, structured]:
        upstream = data["upstream"]
        assert upstream["base_url_env"] == "NOVACODE_BASE_URL"
        assert upstream["endpoint_env_only"] is True
        assert upstream["api_key_env_only"] is True
        assert upstream["endpoint_value_committed"] is False
        assert upstream["api_key_value_committed"] is False
        policy = data["runtime_policy"]
        assert policy["scorer_feedback_enabled"] is False
        assert policy["scorer_feedback_status"] == "disabled_inert_for_measurement_only"
        assert policy["scorer_feedback_path"] is None
    assert check(Path("."))["bfcl_measurement_route_consistency_passed"] is True


def test_rejects_active_scorer_feedback_path(tmp_path):
    root = copy_min_repo(tmp_path)
    path = root / "configs/runtime_bfcl_structured.yaml"
    data = load_yaml(path)
    data["runtime_policy"]["scorer_feedback_enabled"] = True
    data["runtime_policy"]["scorer_feedback_status"] = "enabled"
    data["runtime_policy"]["scorer_feedback_path"] = "outputs/artifacts/scorer_feedback.json"
    write_yaml(path, data)

    joined = "\n".join(blockers(root))
    assert "runtime_bfcl_structured_yaml_scorer_feedback_enabled_not_false:True" in joined
    assert "runtime_bfcl_structured_yaml_scorer_feedback_status_not_disabled_inert:'enabled'" in joined
    assert "runtime_bfcl_structured_yaml_scorer_feedback_path_active:'outputs/artifacts/scorer_feedback.json'" in joined


def test_rejects_missing_disabled_inert_scorer_feedback_status(tmp_path):
    root = copy_min_repo(tmp_path)
    path = root / "configs/runtime_bfcl_structured.yaml"
    data = load_yaml(path)
    data["runtime_policy"].pop("scorer_feedback_status")
    write_yaml(path, data)

    joined = "\n".join(blockers(root))
    assert "runtime_bfcl_structured_yaml_scorer_feedback_status_not_disabled_inert:None" in joined
