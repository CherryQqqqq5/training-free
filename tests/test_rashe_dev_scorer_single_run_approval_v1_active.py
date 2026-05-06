from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_rashe_dev_scorer_single_run_approval_v1_active import (
    AUTHORIZED_TRUE_FIELDS,
    DEFAULT_ACTIVE,
    IMMUTABLE_EXPECTED,
    MUST_FALSE_FIELDS,
    PENDING_PACKET,
    REQUIRED_RECORDS,
    validate_active,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _active() -> dict:
    return json.loads((REPO_ROOT / DEFAULT_ACTIVE).read_text(encoding="utf-8"))


def _pending() -> dict:
    return json.loads((REPO_ROOT / PENDING_PACKET).read_text(encoding="utf-8"))


def test_active_approval_is_exactly_approved_not_started() -> None:
    active = _active()
    pending = _pending()
    assert validate_active(active, pending) == []
    assert active["artifact_kind"] == "rashe_dev_scorer_single_run_approval_v1_active"
    assert active["approval_status"] == "approved"
    assert active["authorized"] is True
    assert active["execution_started"] is False
    assert active["active_approval_state"] == "approved_not_started"
    assert active["one_attempt_only"] is True
    assert active["run_attempt_index"] == 1
    assert active["max_attempts"] == 1


def test_only_authorized_fields_are_true() -> None:
    active = _active()
    pending = _pending()
    for key in AUTHORIZED_TRUE_FIELDS:
        assert active[key] is True
        assert pending[key] is False
    for key in MUST_FALSE_FIELDS:
        assert active[key] is False


def test_immutable_scope_matches_pending() -> None:
    active = _active()
    for key, value in IMMUTABLE_EXPECTED.items():
        assert active[key] == value
    assert active["required_records"] == REQUIRED_RECORDS
    assert active["required_output_paths"] == _pending()["required_output_paths"]


def test_unapproved_extra_flip_is_rejected() -> None:
    active = _active()
    pending = _pending()
    mutated = copy.deepcopy(active)
    mutated["full_suite_authorized"] = True
    blockers = validate_active(mutated, pending, check_roots=False)
    assert any("full_suite_authorized" in blocker for blocker in blockers)

    mutated = copy.deepcopy(active)
    mutated["max_dev_cases"] = 30
    blockers = validate_active(mutated, pending, check_roots=False)
    assert any("max_dev_cases" in blocker for blocker in blockers)


def test_hash_links_are_enforced() -> None:
    active = _active()
    active["linked_pending_approval_packet_sha256"] = "0" * 64
    blockers = validate_active(active, _pending(), check_roots=False)
    assert any("linked_pending_approval_packet_sha256" in blocker for blocker in blockers)


def test_existing_output_or_temp_root_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    active = _active()
    pending = _pending()
    Path(active["allowed_output_root"]).mkdir(parents=True)
    blockers = validate_active(active, pending, check_roots=True, check_hashes=False)
    assert any("allowed_output_root_exists" in blocker for blocker in blockers)

    active = _active()
    active["temp_work_root"] = str(tmp_path / "tmp_root")
    Path(active["temp_work_root"]).mkdir(parents=True)
    blockers = validate_active(active, pending, check_roots=True, check_hashes=False)
    assert any("temp_work_root" in blocker for blocker in blockers)


def test_raw_or_claim_material_is_rejected() -> None:
    for key in ("prompt_text", "raw_trace", "provider_exchange", "case_id", "gold", "expected", "tool_args", "scorer_diff", "candidate_output"):
        active = _active()
        active[key] = "redacted"
        blockers = validate_active(active, _pending(), check_roots=False)
        assert any("forbidden_key" in blocker for blocker in blockers)

    active = _active()
    active["note"] = "expected " + "score gain " + "will " + "improve"
    blockers = validate_active(active, _pending(), check_roots=False)
    assert any("forbidden_value" in blocker for blocker in blockers)
